from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


REFERENCE_URL = "https://www.tradingview.com/pine-script-reference/v6/"
ANCHOR_PREFIXES = [
    "var_",
    "fun_",
    "const_",
    "type_",
    "kw_",
    "op_",
    "an_",
]


@dataclass(frozen=True)
class RenderConfig:
    viewport: dict[str, int]
    locale: str
    timezone: str
    user_agent: str
    render_wait_strategy: str
    max_wait_seconds: int
    post_render_delay_ms: int
    anchor_min_threshold: int
    stabilize_checks: int
    stabilize_interval_seconds: float
    max_scrolls: int


@dataclass(frozen=True)
class RenderResult:
    html: str
    anchor_ids: list[str]
    anchor_counts_by_prefix: dict[str, int]
    browser_name: str
    browser_version: str
    status: str
    notes: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def ensure_directories(paths: Iterable[str]) -> None:
    for path in paths:
        os.makedirs(path, exist_ok=True)


def anchor_prefix_counts(anchor_ids: list[str]) -> dict[str, int]:
    counts = {prefix: 0 for prefix in ANCHOR_PREFIXES}
    for anchor_id in anchor_ids:
        for prefix in ANCHOR_PREFIXES:
            if anchor_id.startswith(prefix):
                counts[prefix] += 1
                break
    return counts


def render_reference(
    url: str, config: RenderConfig
) -> RenderResult:
    notes = ""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=config.viewport,
            locale=config.locale,
            timezone_id=config.timezone,
            user_agent=config.user_agent,
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=config.max_wait_seconds * 1000)

        anchor_ids = []
        stable_count = 0
        previous_count = -1
        scrolls = 0

        start_time = time.time()
        while True:
            anchor_ids = page.evaluate(
                """
                (prefixes) => {
                    const nodes = Array.from(document.querySelectorAll('[id]'));
                    const ids = [];
                    for (const node of nodes) {
                        const id = node.getAttribute('id');
                        if (!id) continue;
                        if (id === 'tv-content') continue;
                        for (const prefix of prefixes) {
                            if (id.startsWith(prefix)) {
                                ids.push(id);
                                break;
                            }
                        }
                    }
                    return ids;
                }
                """,
                ANCHOR_PREFIXES,
            )
            current_count = len(anchor_ids)
            if current_count == previous_count:
                stable_count += 1
            else:
                stable_count = 0
            previous_count = current_count

            if current_count >= config.anchor_min_threshold and stable_count >= config.stabilize_checks:
                break

            if scrolls < config.max_scrolls:
                page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                scrolls += 1

            time.sleep(config.stabilize_interval_seconds)
            if time.time() - start_time > config.max_wait_seconds:
                notes = "render_timeout"
                break

        time.sleep(config.post_render_delay_ms / 1000)
        html = page.content()
        browser_name = "chromium"
        browser_version = browser.version()
        context.close()
        browser.close()

    counts = anchor_prefix_counts(anchor_ids)
    if len(anchor_ids) >= config.anchor_min_threshold and stable_count >= config.stabilize_checks:
        status = "complete"
    else:
        status = "partial"
    if notes:
        status = "failed"
    return RenderResult(
        html=html,
        anchor_ids=anchor_ids,
        anchor_counts_by_prefix=counts,
        browser_name=browser_name,
        browser_version=browser_version,
        status=status,
        notes=notes or "",
    )


def write_manifest(path: str, record: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_jsonl(path: str, record: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True))
        handle.write("\n")


def find_anchor_elements(soup: BeautifulSoup) -> list[object]:
    anchors = []
    for tag in soup.find_all(attrs={"id": True}):
        anchor_id = tag.get("id")
        if anchor_id == "tv-content":
            continue
        for prefix in ANCHOR_PREFIXES:
            if anchor_id.startswith(prefix):
                anchors.append(tag)
                break
    return anchors


def serialize_nodes(nodes: Iterable[object]) -> str:
    return "".join(str(node) for node in nodes).strip()


def infer_symbol_name(anchor_tag) -> str:
    for heading in anchor_tag.find_all(["h1", "h2", "h3", "h4"]):
        text = heading.get_text(" ", strip=True)
        if text:
            return text
    return anchor_tag.get_text(" ", strip=True)


def infer_symbol_type(anchor_tag, anchor_id: str) -> str:
    for candidate in anchor_tag.find_all(
        lambda tag: tag.has_attr("class")
        and any(
            key in " ".join(tag["class"]).lower()
            for key in ("type", "kind", "category")
        )
    ):
        text = candidate.get_text(strip=True)
        if text:
            return text
    for prefix in ANCHOR_PREFIXES:
        if anchor_id.startswith(prefix):
            return prefix.rstrip("_")
    return "unknown"


def segment_reference_html(
    html: str,
    canonical_url: str,
    run_id: str,
    source_artifact_id: str,
) -> tuple[list[dict], dict]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("main#tv-content") or soup.select_one("main.tv-content")
    if container is None:
        raise ValueError("reference_container_missing")

    anchors = find_anchor_elements(container)
    if not anchors:
        raise ValueError("reference_no_anchors")

    segments = []
    seen = set()
    empty_symbol_names = 0
    empty_raw = 0
    for idx, anchor in enumerate(anchors, start=1):
        anchor_id = anchor.get("id")
        if anchor_id in seen:
            raise ValueError("duplicate_anchor_id")
        seen.add(anchor_id)

        nodes = [anchor]
        for sibling in list(anchor.next_siblings):
            sibling_id = getattr(sibling, "attrs", {}).get("id")
            if sibling_id and any(sibling_id.startswith(prefix) for prefix in ANCHOR_PREFIXES):
                break
            nodes.append(sibling)

        raw_html = serialize_nodes(nodes)
        if not raw_html:
            empty_raw += 1

        symbol_name = infer_symbol_name(anchor)
        if not symbol_name:
            empty_symbol_names += 1

        symbol_type = infer_symbol_type(anchor, anchor_id)
        segments.append(
            {
                "canonical_url": canonical_url,
                "doc_type": "reference",
                "pine_version": "v6",
                "run_id": run_id,
                "source_artifact_id": source_artifact_id,
                "anchor_id": anchor_id,
                "symbol_type": symbol_type,
                "symbol_name": symbol_name,
                "segment_order": idx,
                "raw_html": raw_html,
                "segment_id": f"{source_artifact_id}:{anchor_id}",
            }
        )

    qc = {
        "segment_count": len(segments),
        "empty_symbol_names": empty_symbol_names,
        "empty_raw_html": empty_raw,
    }
    return segments, qc


def read_manifest(path: str) -> dict:
    return json.loads(open(path, "r", encoding="utf-8").read())


def drift_severity(anchor_count_delta: int, env_delta: bool) -> str:
    if anchor_count_delta == 0 and not env_delta:
        return "none"
    if anchor_count_delta != 0:
        if abs(anchor_count_delta) >= 10:
            return "high"
        return "medium"
    return "low"


def drift_recommended_action(severity: str) -> str:
    if severity == "none":
        return "ignore"
    if severity == "low":
        return "manual_review"
    if severity == "medium":
        return "resegment"
    return "block_pipeline"
