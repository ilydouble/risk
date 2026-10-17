"""Cache only required postcodes from the public ONS August 2026 hosted table."""

import argparse
import gzip
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from extend_uk_hyperedges import raw_records
from prepare_uk_basic_information import read_csv
from prepare_uk_financials import sha, write_json
from prepare_uk_graph import ROOT
from uk_graph.geography import FIELDS, NAME_SERVICE, POSTCODE_SERVICE, VINTAGE, canonical_postcode
from uk_graph.gleif import stable_id

BASE = ROOT / "outputs/uk-research-graph-20261017-v3"
OUTPUT = ROOT / "datasets/sources/ons-geography-202608-20261017"


def request_json(url, params=None):
    encoded = urllib.parse.urlencode(params or {"f": "json"})
    target = url + "?" + encoded if len(encoded) < 1800 else url
    for attempt in range(5):
        try:
            request = urllib.request.Request(
                target,
                data=encoded.encode() if len(encoded) >= 1800 else None,
                headers={"User-Agent": "UK-research-geography/1.0"},
            )
            with urllib.request.urlopen(request, timeout=90) as response:
                result = json.load(response)
            if "error" in result:
                raise ValueError(result["error"])
            return result
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2**attempt)


def batch(postcodes, directory, epoch):
    key = stable_id([epoch, postcodes])
    path = directory / (key + ".json.gz")
    if path.exists():
        with gzip.open(path, "rt") as stream:
            cached = json.load(stream)
        if cached["requestedPostcodes"] != postcodes or cached["epoch"] != epoch:
            raise ValueError("Cache identity mismatch")
        return path, cached
    params = {
        "f": "json",
        "where": "pcds IN (" + ",".join("'" + x + "'" for x in postcodes) + ")",
        "outFields": FIELDS,
        "returnGeometry": "false",
        "orderByFields": "ObjectId",
        "resultRecordCount": 1000,
    }
    pages, offset = [], 0
    while True:
        params["resultOffset"] = offset
        page = request_json(POSTCODE_SERVICE + "/query", params)
        pages.append(page)
        if not page.get("exceededTransferLimit"):
            break
        if not page.get("features"):
            raise ValueError("Pagination did not advance")
        offset += len(page["features"])
    result = {"epoch": epoch, "requestedPostcodes": postcodes, "query": params, "pages": pages}
    temporary = path.with_suffix(".part")
    with gzip.open(temporary, "wt") as stream:
        json.dump(result, stream, ensure_ascii=False)
    temporary.replace(path)
    return path, result


def fetch(base, output):
    output.mkdir(parents=True, exist_ok=True)
    raw = output / "raw"
    raw.mkdir(exist_ok=True)
    postcodes = {
        canonical_postcode(r["row"].get("RegAddress.PostCode", ""))
        for _, r in raw_records(base / "snapshot-raw-records.jsonl.gz")
    }
    postcodes.update(
        canonical_postcode(r.get("historical_registered_office_postcode", ""))
        for r in read_csv(base / "features.csv")
    )
    postcodes.discard("")
    ordered = sorted(postcodes)
    metadata = request_json(POSTCODE_SERVICE)
    epoch = metadata["editingInfo"]
    name_metadata = request_json(NAME_SERVICE)
    names_response = request_json(
        NAME_SERVICE + "/query",
        {
            "f": "json",
            "where": "1=1",
            "outFields": "LAD26CD,LAD26NM,RGN26CD,RGN26NM,CTRY26CD,CTRY26NM",
            "returnDistinctValues": "true",
            "returnGeometry": "false",
            "resultRecordCount": 1000,
        },
    )
    if names_response.get("exceededTransferLimit"):
        raise ValueError("Name lookup truncated")
    names = {}
    for feature in names_response["features"]:
        a = feature["attributes"]
        for prefix in ("LAD", "RGN", "CTRY"):
            code, name = a.get(prefix + "26CD"), a.get(prefix + "26NM")
            if code and name and "999999" not in code:
                if code in names and names[code] != name:
                    raise ValueError("Conflicting official names")
                names[code] = name
    write_json(output / "postcode-service.json", metadata)
    write_json(output / "name-service.json", name_metadata)
    write_json(output / "name-response.json", names_response)
    write_json(output / "names.json", names)
    results = {}
    index = []
    batches = [ordered[i : i + 800] for i in range(0, len(ordered), 800)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(batch, codes, raw, epoch) for codes in batches]
        for number, future in enumerate(as_completed(futures), 1):
            path, response = future.result()
            candidates = {code: [] for code in response["requestedPostcodes"]}
            for page_no, page in enumerate(response["pages"]):
                for feature_no, feature in enumerate(page["features"]):
                    attrs = feature["attributes"]
                    code = canonical_postcode(attrs["pcds"])
                    if code not in candidates:
                        raise ValueError("Unexpected postcode returned")
                    candidates[code].append(
                        {
                            "attributes": attrs,
                            "sourceFile": "raw/" + path.name,
                            "page": page_no,
                            "feature": feature_no,
                            "attributesSha256": stable_id(attrs),
                        }
                    )
            for code, values in candidates.items():
                results[code] = {
                    "status": "matched"
                    if len(values) == 1
                    else "ambiguous"
                    if values
                    else "not_found",
                    "candidates": values,
                }
            index.append({"file": "raw/" + path.name, "sha256": sha(path)})
            if number % 20 == 0 or number == len(batches):
                print(f"Postcode batches {number}/{len(batches)}", flush=True)
    if request_json(POSTCODE_SERVICE)["editingInfo"] != epoch:
        raise ValueError("Source table changed during extraction")
    if request_json(NAME_SERVICE)["editingInfo"] != name_metadata["editingInfo"]:
        raise ValueError("Name table changed during extraction")
    write_json(output / "postcodes.json", dict(sorted(results.items())))
    write_json(
        output / "source.json",
        {
            "postcodeService": POSTCODE_SERVICE,
            "nameService": NAME_SERVICE,
            "vintage": VINTAGE,
            "retrievedDate": "2026-10-17",
            "postcodeEpoch": epoch,
            "requestedPostcodes": len(ordered),
            "rawFiles": sorted(index, key=lambda x: x["file"]),
            "statusCounts": {
                status: sum(r["status"] == status for r in results.values())
                for status in ("matched", "ambiguous", "not_found")
            },
            "files": {
                name: sha(output / name)
                for name in (
                    "postcode-service.json",
                    "name-service.json",
                    "name-response.json",
                    "names.json",
                    "postcodes.json",
                )
            },
            "license": "https://www.ons.gov.uk/methodology/geography/licences",
            "historicalAddressesVerified": False,
            "historicalBoundariesVerified": False,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    fetch(args.base, args.output)
