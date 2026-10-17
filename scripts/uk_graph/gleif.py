"""Exact registry matching and resumable access to public GLEIF records."""

import gzip
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from zipfile import ZipFile

import httpx

AUTHORITIES = {"RA000585", "RA000586", "RA000587"}
PARENT_TYPES = {"IS_DIRECTLY_CONSOLIDATED_BY", "IS_ULTIMATELY_CONSOLIDATED_BY"}
API = "https://api.gleif.org/api/v1/lei-records"


def stable_id(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def company_number(value):
    value = value.strip().upper()
    if value.isdigit() and len(value) <= 8:
        return value.zfill(8)
    return value if re.fullmatch(r"[A-Z]{2}[0-9]{6}", value) else ""


def registered_company(record):
    entity = record["attributes"]["entity"]
    authority = (entity.get("registeredAt") or {}).get("id")
    if authority not in AUTHORITIES:
        return ""
    return company_number(entity.get("registeredAs") or "")


def query(params, cache):
    cache.mkdir(parents=True, exist_ok=True)
    key = stable_id(params)
    path = cache / f"{key}.json.gz"
    if path.exists():
        with gzip.open(path, "rt") as stream:
            result = json.load(stream)
        if result["params"] != params:
            raise ValueError("Wrong GLEIF query cache")
        return result
    pages = []
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        page, last = 1, 1
        while page <= last:
            arguments = {**params, "page[size]": 200, "page[number]": page}
            for attempt in range(6):
                try:
                    response = client.get(API, params=arguments)
                    if response.status_code == 429 or response.status_code >= 500:
                        time.sleep(
                            min(60, max(2**attempt, int(response.headers.get("retry-after", "0"))))
                        )
                        continue
                    response.raise_for_status()
                    break
                except httpx.TransportError:
                    if attempt == 5:
                        raise
                    time.sleep(min(30, 2**attempt))
            else:
                raise ValueError("GLEIF request retries exhausted")
            payload = response.json()
            if "data" not in payload or "meta" not in payload:
                raise ValueError("GLEIF response has no complete data/pagination")
            pagination = payload["meta"]["pagination"]
            if pagination["currentPage"] != page:
                raise ValueError("Unexpected GLEIF pagination")
            last = pagination["lastPage"]
            pages.append(
                {
                    "url": str(response.url),
                    "body": response.text,
                    "sha256": hashlib.sha256(response.content).hexdigest(),
                }
            )
            page += 1
    records = [record for page in pages for record in json.loads(page["body"])["data"]]
    expected = json.loads(pages[0]["body"])["meta"]["pagination"]["total"]
    if len(records) != expected or len({r["id"] for r in records}) != expected:
        raise ValueError("Incomplete or inconsistent GLEIF query result")
    result = {"params": params, "pages": pages}
    temporary = path.with_suffix(".tmp")
    with gzip.open(temporary, "wt") as stream:
        json.dump(result, stream)
    temporary.replace(path)
    return result


def records_from_query(result):
    for page in result["pages"]:
        raw = page["body"].encode()
        if hashlib.sha256(raw).hexdigest() != page["sha256"]:
            raise ValueError("GLEIF cached response checksum mismatch")
        payload = json.loads(raw)
        for number, record in enumerate(payload["data"]):
            yield {
                "record": record,
                "evidence": {
                    "url": page["url"],
                    "response_sha256": page["sha256"],
                    "record_index": number,
                    "publish_date": payload["meta"]["goldenCopy"]["publishDate"],
                },
            }


def fetch_companies(companies, cache, workers=6):
    ids = sorted(companies)
    batches = [ids[start : start + 500] for start in range(0, len(ids), 500)]
    aliases = sorted(
        {str(int(value)) for value in ids if value.isdigit() and value.startswith("0")}
    )
    batches.extend(aliases[start : start + 500] for start in range(0, len(aliases), 500))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(query, {"filter[entity.registeredAs]": ",".join(batch)}, cache)
            for batch in batches
        ]
        for number, future in enumerate(futures, 1):
            result = future.result()
            for item in records_from_query(result):
                company = registered_company(item["record"])
                if company in companies:
                    yield company, item
            if number % 10 == 0 or number == len(futures):
                print(json.dumps({"companyBatches": number, "total": len(futures)}), flush=True)


def fetch_leis(leis, cache, workers=6):
    ids = sorted(leis)
    batches = [ids[start : start + 100] for start in range(0, len(ids), 100)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = pool.map(lambda batch: query({"filter[lei]": ",".join(batch)}, cache), batches)
        for result in results:
            yield from records_from_query(result)


def download_relationships(source, workers=12):
    """Fixed-release byte ranges avoid restarting a large file on a broken connection."""
    publication = json.loads((source / "golden-copy-publish.json").read_text())["data"]
    file = publication["rr"]["full_file"]["csv"]
    size, url = file["size"], file["url"]
    destination = source / "golden-relationships.csv.zip"
    parts = source / ("rr-parts-" + stable_id(url)[:12])
    parts.mkdir(exist_ok=True)

    def part(start):
        end = min(size, start + 1024 * 1024) - 1
        path = parts / str(start)
        if path.exists() and path.stat().st_size == end - start + 1:
            return path
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            for attempt in range(6):
                try:
                    response = client.get(
                        url,
                        headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"},
                    )
                    response.raise_for_status()
                    if (
                        response.status_code != 206
                        or response.headers.get("content-range") != f"bytes {start}-{end}/{size}"
                    ):
                        raise ValueError("GLEIF source did not honor the fixed file range")
                    if len(response.content) != end - start + 1:
                        raise ValueError("Truncated GLEIF source range")
                    temporary = path.with_suffix(".tmp")
                    temporary.write_bytes(response.content)
                    temporary.replace(path)
                    return path
                except httpx.TransportError:
                    if attempt == 5:
                        raise
                    time.sleep(2**attempt)
        raise ValueError("GLEIF source range retries exhausted")

    if not destination.exists():
        with ThreadPoolExecutor(max_workers=workers) as pool:
            paths = list(pool.map(part, range(0, size, 1024 * 1024)))
        temporary = destination.with_suffix(".tmp")
        with temporary.open("wb") as stream:
            for path in paths:
                stream.write(path.read_bytes())
        if temporary.stat().st_size != size:
            raise ValueError("Wrong relationship ZIP size")
        with ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError("Corrupt relationship ZIP")
        temporary.replace(destination)
    return destination
