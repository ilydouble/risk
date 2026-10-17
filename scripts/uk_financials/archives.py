"""Read public ZIP indexes and selected members with validated HTTP byte ranges."""

import gzip
import hashlib
import io
import json
import re
import struct
import threading
import time
import zlib
from zipfile import ZipFile

import httpx

MAX_DOCUMENT = 50 * 1024 * 1024
CLIENT = None
THREAD_CLIENT = threading.local()
COUNT_LOCK = threading.Lock()
TRANSFER = {"requests": 0, "bytes": 0}


def http_client():
    if CLIENT is not None:
        return CLIENT
    if not hasattr(THREAD_CLIENT, "client"):
        # Separate pools prevent one stalled pooled connection blocking every download worker.
        THREAD_CLIENT.client = httpx.Client(
            timeout=httpx.Timeout(60, connect=15),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            headers={"User-Agent": "RiskResearchFinancials/1.0 (+https://github.com/ilydouble/risk)"},
            follow_redirects=True,
        )
    return THREAD_CLIENT.client


def ranged(url, start, end, etag=None):
    headers = {"Range": f"bytes={start}-{end}" if start >= 0 else f"bytes={start}"}
    if etag:
        headers["If-Match"] = etag
    for attempt in range(4):
        try:
            with http_client().stream("GET", url, headers=headers) as response:
                if response.status_code in (429, 500, 502, 503, 504):
                    time.sleep(min(30, int(response.headers.get("Retry-After", 2**attempt))))
                    continue
                response.raise_for_status()
                if response.status_code != 206:
                    raise ValueError("Server ignored Range; refusing a full archive download")
                match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers["Content-Range"])
                if not match:
                    raise ValueError("Invalid Content-Range")
                lower, upper, total = map(int, match.groups())
                if start >= 0 and (lower != start or upper != min(end, total - 1)):
                    raise ValueError("Unexpected byte interval")
                if etag and response.headers.get("ETag") != etag:
                    raise ValueError("Official archive changed during retrieval")
                payload = response.read()
                if len(payload) != upper - lower + 1:
                    raise ValueError("Truncated byte interval")
                with COUNT_LOCK:
                    TRANSFER["requests"] += 1
                    TRANSFER["bytes"] += len(payload)
                return payload, lower, total, response.headers.get("ETag")
        except httpx.HTTPError:
            if attempt == 3:
                raise
            time.sleep(2**attempt)
    raise ValueError("Range retries exhausted")


class IndexedZip(io.RawIOBase):
    def __init__(self, size, pieces):
        self.size, self.pieces, self.position = size, pieces, 0

    def seek(self, offset, whence=0):
        self.position = offset + (self.position if whence == 1 else self.size if whence == 2 else 0)
        return self.position

    def tell(self):
        return self.position

    def read(self, count=-1):
        count = min(self.size - self.position, count if count >= 0 else self.size)
        for start, content in self.pieces:
            if start <= self.position and self.position + count <= start + len(content):
                value = content[self.position - start : self.position - start + count]
                self.position += count
                return value
        raise ValueError("ZIP attempted to read outside its cached index")


def index_archive(url, cache):
    manifest_path = cache / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["url"] != url:
            raise ValueError("Index cache URL mismatch")
        tail = (cache / "tail.bin").read_bytes()
        directory = gzip.decompress((cache / "directory.gz").read_bytes())
    else:
        tail, tail_start, size, etag = ranged(url, -131072, None)
        position = tail.rfind(b"PK\x05\x06")
        if position < 0:
            raise ValueError("ZIP end record not found")
        _, _, _, _, _, directory_size, directory_start, _ = struct.unpack_from(
            "<4s4H2LH", tail, position
        )
        if directory_start == 0xFFFFFFFF or directory_size == 0xFFFFFFFF:
            locator = tail.rfind(b"PK\x06\x07", 0, position)
            if locator < 0:
                raise ValueError("ZIP64 locator missing")
            zip64_start = struct.unpack_from("<4sLQL", tail, locator)[2]
            zip64, _, _, _ = ranged(url, zip64_start, zip64_start + 55, etag)
            directory_size, directory_start = struct.unpack_from("<QQ", zip64, 40)
        directory, _, _, _ = ranged(
            url, directory_start, directory_start + directory_size - 1, etag
        )
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "tail.bin").write_bytes(tail)
        (cache / "directory.gz").write_bytes(gzip.compress(directory))
        manifest = {
            "url": url,
            "etag": etag,
            "archiveSize": size,
            "tailStart": tail_start,
            "directoryStart": directory_start,
            "directorySize": directory_size,
            "directorySha256": hashlib.sha256(directory).hexdigest(),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2))
    if hashlib.sha256(directory).hexdigest() != manifest["directorySha256"]:
        raise ValueError("Cached central directory digest mismatch")
    pieces = [(manifest["tailStart"], tail), (manifest["directoryStart"], directory)]
    with ZipFile(IndexedZip(manifest["archiveSize"], pieces)) as zipped:
        entries = [
            {
                "member": item.filename,
                "offset": item.header_offset,
                "compressedSize": item.compress_size,
                "size": item.file_size,
                "crc32": item.CRC,
                "compression": item.compress_type,
            }
            for item in zipped.infolist()
            if not item.is_dir()
        ]
    return manifest, entries


def member_bytes(manifest, entry):
    if entry["size"] > MAX_DOCUMENT or entry["compressedSize"] > MAX_DOCUMENT:
        raise ValueError("Financial document exceeds the explicit 50 MiB parsing limit")
    start = entry["offset"]
    # A small over-read normally includes the entire local name and extra fields in one request.
    content, _, _, _ = ranged(
        manifest["url"],
        start,
        min(
            start + 30 + len(entry["member"].encode()) + 2048 + entry["compressedSize"],
            manifest["archiveSize"] - 1,
        ),
        manifest["etag"],
    )
    header = struct.unpack_from("<4s5H3L2H", content)
    if header[0] != b"PK\x03\x04" or header[2] & 1:
        raise ValueError("Invalid or encrypted ZIP local member")
    name_length, extra_length = header[-2:]
    data_start = 30 + name_length + extra_length
    data_end = data_start + entry["compressedSize"]
    if data_end > len(content):
        content, _, _, _ = ranged(manifest["url"], start, start + data_end - 1, manifest["etag"])
    payload = content[data_start:data_end]
    if entry["compression"] == 8:
        inflater = zlib.decompressobj(-15)
        raw = inflater.decompress(payload, MAX_DOCUMENT + 1)
        if len(raw) > MAX_DOCUMENT or inflater.unconsumed_tail or not inflater.eof:
            raise ValueError("Invalid or oversized deflated document")
    elif entry["compression"] == 0:
        raw = payload
    else:
        raise ValueError("Unsupported ZIP compression")
    if len(raw) != entry["size"] or zlib.crc32(raw) != entry["crc32"]:
        raise ValueError("Financial document failed ZIP size/CRC validation")
    return raw
