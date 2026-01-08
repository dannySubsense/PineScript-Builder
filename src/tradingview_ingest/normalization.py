from __future__ import annotations

import gzip
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from glob import glob
from typing import Iterable

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class GuideSegment:
    source_artifact_id: str
    canonical_url: str
    doc_type: str
    pine_version: str
    segment_id: str
    segment_order: int
    raw_html: str


@dataclass(frozen=True)
class GuidePage:
    guide_page_id: str
    canonical_url: str
    pine_version: str
    source_artifact_id: str
    page_order: int


@dataclass(frozen=True)
class GuideSection:
    guide_section_id: str
    guide_page_id: str
    pine_version: str
    parent_section_id: str | None
    section_level: str
    section_order: int
    source_artifact_id: str
    segment_id: str
    segment_order: int
    raw_html: str


@dataclass(frozen=True)
class WarningRecord:
    canonical_url: str
    source_artifact_id: str
    reason: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_segments(path: str) -> list[GuideSegment]:
    segments: list[GuideSegment] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("doc_type") != "guide":
                continue
            if item.get("pine_version") != "v5":
                raise ValueError("non_v5_segment_detected")
            segments.append(
                GuideSegment(
                    source_artifact_id=item["source_artifact_id"],
                    canonical_url=item["canonical_url"],
                    doc_type=item["doc_type"],
                    pine_version=item["pine_version"],
                    segment_id=item["segment_id"],
                    segment_order=int(item["segment_order"]),
                    raw_html=item["raw_html"],
                )
            )
    return segments


def latest_segment_file(root: str) -> str:
    candidates = sorted(glob(os.path.join(root, "artifacts", "segments", "*.jsonl")))
    if not candidates:
        raise FileNotFoundError("segments_not_found")
    return candidates[-1]


def latest_segmentation_run(root: str) -> str | None:
    candidates = sorted(
        glob(os.path.join(root, "artifacts", "segmentation_runs", "*.jsonl"))
    )
    if not candidates:
        return None
    return candidates[-1]


def load_fallback_pages(root: str) -> list[tuple[str, str]]:
    run_path = latest_segmentation_run(root)
    if not run_path:
        return []
    fallback: list[tuple[str, str]] = []
    with open(run_path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("doc_type") != "guide":
                continue
            if item.get("pine_version") != "v5":
                continue
            if item.get("reason") != "guide_no_h2":
                continue
            fallback.append((item["canonical_url"], item["source_artifact_id"]))
    return fallback


def decode_raw_html(raw_path: str) -> str:
    raw = open(raw_path, "rb").read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def extract_main_html(full_html: str) -> str:
    soup = BeautifulSoup(full_html, "html.parser")
    container = soup.select_one("main.content") or soup.select_one("main.main-pane")
    if container is None:
        container = soup.body
    if container is None:
        return full_html
    return "".join(str(node) for node in container.contents).strip()


def infer_section_level(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag_name in ("h2", "h3", "h1"):
        heading = soup.find(tag_name)
        if heading:
            if tag_name == "h1":
                return "lead"
            return tag_name
    return "fallback"


def build_pages(segments: Iterable[GuideSegment]) -> list[GuidePage]:
    by_url: dict[str, GuideSegment] = {}
    for segment in segments:
        if segment.canonical_url not in by_url:
            by_url[segment.canonical_url] = segment
    pages: list[GuidePage] = []
    for canonical_url, segment in sorted(by_url.items()):
        pages.append(
            GuidePage(
                guide_page_id=sha256_hex(canonical_url),
                canonical_url=canonical_url,
                pine_version="v5",
                source_artifact_id=segment.source_artifact_id,
                page_order=1,
            )
        )
    return pages


def build_sections(
    segments: Iterable[GuideSegment], fallback_pages: list[tuple[str, str]], raw_root: str
) -> tuple[list[GuideSection], list[WarningRecord]]:
    warnings: list[WarningRecord] = []
    sections: list[GuideSection] = []

    segments_by_url: dict[str, list[GuideSegment]] = {}
    for segment in segments:
        segments_by_url.setdefault(segment.canonical_url, []).append(segment)

    for canonical_url, page_segments in segments_by_url.items():
        page_segments.sort(key=lambda item: item.segment_order)
        guide_page_id = sha256_hex(canonical_url)
        last_h2_id: str | None = None
        for segment in page_segments:
            if not segment.raw_html.strip():
                warnings.append(
                    WarningRecord(
                        canonical_url=canonical_url,
                        source_artifact_id=segment.source_artifact_id,
                        reason="empty_raw_html",
                    )
                )
            section_level = infer_section_level(segment.raw_html)
            parent_section_id = None
            if section_level == "h3":
                parent_section_id = last_h2_id
                if parent_section_id is None:
                    warnings.append(
                        WarningRecord(
                            canonical_url=canonical_url,
                            source_artifact_id=segment.source_artifact_id,
                            reason="orphan_h3",
                        )
                    )
            if section_level == "h2":
                last_h2_id = sha256_hex(segment.segment_id)

            sections.append(
                GuideSection(
                    guide_section_id=sha256_hex(segment.segment_id),
                    guide_page_id=guide_page_id,
                    pine_version="v5",
                    parent_section_id=parent_section_id,
                    section_level=section_level,
                    section_order=segment.segment_order,
                    source_artifact_id=segment.source_artifact_id,
                    segment_id=segment.segment_id,
                    segment_order=segment.segment_order,
                    raw_html=segment.raw_html,
                )
            )

    for canonical_url, source_artifact_id in fallback_pages:
        if canonical_url in segments_by_url:
            continue
        raw_path = os.path.join(raw_root, "guide", "v5", f"{source_artifact_id}.html")
        if not os.path.exists(raw_path):
            raise ValueError("fallback_raw_missing")
        full_html = decode_raw_html(raw_path)
        raw_html = extract_main_html(full_html)
        segment_id = f"{source_artifact_id}:fallback"
        guide_page_id = sha256_hex(canonical_url)
        warnings.append(
            WarningRecord(
                canonical_url=canonical_url,
                source_artifact_id=source_artifact_id,
                reason="fallback_section_created",
            )
        )
        sections.append(
            GuideSection(
                guide_section_id=sha256_hex(segment_id),
                guide_page_id=guide_page_id,
                pine_version="v5",
                parent_section_id=None,
                section_level="fallback",
                section_order=1,
                source_artifact_id=source_artifact_id,
                segment_id=segment_id,
                segment_order=1,
                raw_html=raw_html,
            )
        )

    return sections, warnings


def load_existing_ids(path: str, field: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    existing: set[str] = set()
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            value = item.get(field)
            if value:
                existing.add(value)
    return existing


def append_jsonl(path: str, records: Iterable[dict]) -> int:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    count = 0
    with open(path, "a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")
            count += 1
    return count


def normalize_guides(root: str) -> tuple[int, int, int, list[WarningRecord]]:
    segments_path = latest_segment_file(root)
    segments = load_segments(segments_path)
    fallback_pages = load_fallback_pages(root)

    pages = build_pages(segments)
    sections, warnings = build_sections(
        segments=segments, fallback_pages=fallback_pages, raw_root=os.path.join(root, "raw")
    )

    pages_out = os.path.join(root, "normalized", "v5", "guide_pages.jsonl")
    sections_out = os.path.join(root, "normalized", "v5", "guide_sections.jsonl")
    warnings_out = os.path.join(root, "artifacts", "normalization_runs", f"{utc_now_iso()}.jsonl")

    existing_pages = load_existing_ids(pages_out, "guide_page_id")
    existing_sections = load_existing_ids(sections_out, "guide_section_id")

    pages_written = append_jsonl(
        pages_out,
        [page.__dict__ for page in pages if page.guide_page_id not in existing_pages],
    )
    sections_written = append_jsonl(
        sections_out,
        [
            section.__dict__
            for section in sections
            if section.guide_section_id not in existing_sections
        ],
    )
    append_jsonl(warnings_out, [warning.__dict__ for warning in warnings])

    fallback_count = sum(
        1 for warning in warnings if warning.reason == "fallback_section_created"
    )

    return pages_written, sections_written, fallback_count, warnings
