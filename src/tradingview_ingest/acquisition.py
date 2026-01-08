from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


USER_AGENT = "PineScript-Builder acquisition/0.1"
ACCEPT_ENCODING = "gzip"
DEFAULT_TIMEOUT = 20


@dataclass(frozen=True)
class InventoryItem:
    canonical_url: str
    doc_type: str
    pine_version: str
    source_entry_point: str
    discovered_at: str
    discovery_method: str
    segmentation_strategy: str | None = None


@dataclass(frozen=True)
class FetchResult:
    status: int
    content_type: str | None
    content_encoding: str | None
    raw_bytes: bytes
    decoded_length: int | None


@dataclass(frozen=True)
class FailureRecord:
    canonical_url: str
    doc_type: str
    pine_version: str
    reason: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def url_hash(url: str) -> str:
    return sha256_hex(url.encode("utf-8"))


def safe_makedirs(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def load_inventory(path: str) -> list[InventoryItem]:
    raw = json.loads(open(path, "r", encoding="utf-8").read())
    items: list[InventoryItem] = []
    for entry in raw:
        items.append(
            InventoryItem(
                canonical_url=entry["canonical_url"],
                doc_type=entry["doc_type"],
                pine_version=entry["pine_version"],
                source_entry_point=entry.get("source_entry_point", ""),
                discovered_at=entry.get("discovered_at", ""),
                discovery_method=entry.get("discovery_method", ""),
                segmentation_strategy=entry.get("segmentation_strategy"),
            )
        )
    return sorted(items, key=lambda item: item.canonical_url)


def fetch_bytes(url: str, timeout: int = DEFAULT_TIMEOUT) -> FetchResult:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Encoding": ACCEPT_ENCODING,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        status = int(getattr(response, "status", 0) or 0)
        content_type = response.headers.get("Content-Type")
        content_encoding = response.headers.get("Content-Encoding")
        payload = response.read()
    decoded_length = None
    if content_encoding and "gzip" in content_encoding.lower():
        try:
            import gzip

            decoded_length = len(gzip.decompress(payload))
        except Exception:
            decoded_length = None
    else:
        decoded_length = len(payload)
    return FetchResult(
        status=status,
        content_type=content_type,
        content_encoding=content_encoding,
        raw_bytes=payload,
        decoded_length=decoded_length,
    )


def fetch_with_retries(url: str, retries: int, backoff_seconds: float) -> FetchResult:
    attempt = 0
    while True:
        try:
            return fetch_bytes(url)
        except Exception:
            attempt += 1
            if attempt > retries:
                raise
            time.sleep(backoff_seconds * (2 ** (attempt - 1)))


def fetch_robots_txt(host: str) -> str:
    robots_url = f"{host}/robots.txt"
    result = fetch_bytes(robots_url)
    if result.status != 200:
        return ""
    return result.raw_bytes.decode("utf-8", errors="replace")


def parse_robots_disallow(robots_txt: str) -> list[str]:
    disallow: list[str] = []
    active = False
    for line in robots_txt.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lower = stripped.lower()
        if lower.startswith("user-agent:"):
            agent = stripped.split(":", 1)[1].strip()
            active = agent == "*"
            continue
        if active and lower.startswith("disallow:"):
            path = stripped.split(":", 1)[1].strip()
            if path:
                disallow.append(path)
    return disallow


def is_allowed_by_robots(url: str, disallow_paths: Iterable[str]) -> bool:
    path = urlparse(url).path or "/"
    for disallow in disallow_paths:
        if path.startswith(disallow):
            return False
    return True


def artifact_paths(
    output_root: str, item: InventoryItem, suffix: str | None = None
) -> tuple[str, str]:
    base_dir = os.path.join(output_root, item.doc_type, item.pine_version)
    safe_makedirs(base_dir)
    file_hash = url_hash(item.canonical_url)
    base_name = f"{file_hash}.html"
    if suffix:
        base_name = f"{file_hash}.{suffix}.html"
    raw_path = os.path.join(base_dir, base_name)
    meta_path = raw_path + ".meta.json"
    return raw_path, meta_path


def existing_checksum(meta_path: str, raw_path: str) -> str | None:
    if not os.path.exists(meta_path) or not os.path.exists(raw_path):
        return None
    try:
        meta = json.loads(open(meta_path, "r", encoding="utf-8").read())
    except Exception:
        return None
    expected = meta.get("checksum")
    if not expected:
        return None
    actual = sha256_hex(open(raw_path, "rb").read())
    if actual != expected:
        return None
    return expected


def write_raw_and_meta(
    raw_path: str, meta_path: str, item: InventoryItem, result: FetchResult, run_id: str
) -> None:
    with open(raw_path, "wb") as handle:
        handle.write(result.raw_bytes)
    checksum = sha256_hex(result.raw_bytes)
    meta = {
        "canonical_url": item.canonical_url,
        "doc_type": item.doc_type,
        "pine_version": item.pine_version,
        "source_entry_point": item.source_entry_point,
        "discovered_at": item.discovered_at,
        "discovery_method": item.discovery_method,
        "segmentation_strategy": item.segmentation_strategy,
        "fetched_at": utc_now_iso(),
        "http_status": result.status,
        "content_type": result.content_type,
        "content_length": result.decoded_length,
        "content_encoding": result.content_encoding,
        "checksum": checksum,
        "acquisition_run_id": run_id,
    }
    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2, sort_keys=True)
        handle.write("\n")


def acquire_inventory(
    inventory: list[InventoryItem],
    output_root: str,
    run_log_path: str,
    retries: int,
    backoff_seconds: float,
    sleep_seconds: float,
) -> dict[str, int]:
    host = "https://www.tradingview.com"
    robots_txt = fetch_robots_txt(host)
    disallow_paths = parse_robots_disallow(robots_txt)
    run_id = os.path.basename(run_log_path).split(".")[0]
    safe_makedirs(os.path.dirname(run_log_path))

    counts = {
        "attempted": 0,
        "written": 0,
        "skipped": 0,
        "failed_guide": 0,
        "failed_reference": 0,
    }

    with open(run_log_path, "w", encoding="utf-8") as log_handle:
        for item in inventory:
            counts["attempted"] += 1
            if not is_allowed_by_robots(item.canonical_url, disallow_paths):
                record = FailureRecord(
                    canonical_url=item.canonical_url,
                    doc_type=item.doc_type,
                    pine_version=item.pine_version,
                    reason="robots_disallow",
                )
                log_handle.write(json.dumps(record.__dict__) + "\n")
                if item.doc_type == "reference":
                    counts["failed_reference"] += 1
                    break
                counts["failed_guide"] += 1
                continue

            raw_path, meta_path = artifact_paths(output_root, item)
            existing = existing_checksum(meta_path, raw_path)
            if existing:
                counts["skipped"] += 1
                continue

            try:
                result = fetch_with_retries(item.canonical_url, retries, backoff_seconds)
            except Exception:
                record = FailureRecord(
                    canonical_url=item.canonical_url,
                    doc_type=item.doc_type,
                    pine_version=item.pine_version,
                    reason="fetch_error",
                )
                log_handle.write(json.dumps(record.__dict__) + "\n")
                if item.doc_type == "reference":
                    counts["failed_reference"] += 1
                    break
                counts["failed_guide"] += 1
                continue

            if result.status < 200 or result.status >= 300:
                record = FailureRecord(
                    canonical_url=item.canonical_url,
                    doc_type=item.doc_type,
                    pine_version=item.pine_version,
                    reason=f"http_{result.status}",
                )
                log_handle.write(json.dumps(record.__dict__) + "\n")
                if item.doc_type == "reference":
                    counts["failed_reference"] += 1
                    break
                counts["failed_guide"] += 1
                continue

            suffix = None
            if os.path.exists(raw_path) or os.path.exists(meta_path):
                suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                raw_path, meta_path = artifact_paths(output_root, item, suffix)

            write_raw_and_meta(raw_path, meta_path, item, result, run_id)
            counts["written"] += 1

            time.sleep(sleep_seconds)

    return counts
