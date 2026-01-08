from __future__ import annotations

import gzip
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class Artifact:
    source_artifact_id: str
    raw_path: str
    canonical_url: str
    doc_type: str
    pine_version: str


@dataclass(frozen=True)
class Segment:
    source_artifact_id: str
    canonical_url: str
    doc_type: str
    pine_version: str
    segment_id: str
    segment_type: str
    segment_order: int
    raw_html: str
    anchor_id: str | None = None
    symbol_name: str | None = None
    symbol_type: str | None = None


@dataclass(frozen=True)
class Failure:
    source_artifact_id: str
    canonical_url: str
    doc_type: str
    pine_version: str
    reason: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def decode_html(raw_bytes: bytes, content_encoding: str | None) -> str:
    payload = raw_bytes
    if content_encoding and "gzip" in content_encoding.lower():
        payload = gzip.decompress(payload)
    elif payload[:2] == b"\x1f\x8b":
        payload = gzip.decompress(payload)
    return payload.decode("utf-8", errors="replace")


def load_artifacts(raw_root: str) -> list[Artifact]:
    artifacts: list[Artifact] = []
    for root, _, files in os.walk(raw_root):
        for filename in files:
            if not filename.endswith(".html.meta.json"):
                continue
            meta_path = os.path.join(root, filename)
            meta = json.loads(open(meta_path, "r", encoding="utf-8").read())
            raw_path = meta_path.replace(".meta.json", "")
            artifact_id = os.path.basename(raw_path).replace(".html", "")
            artifacts.append(
                Artifact(
                    source_artifact_id=artifact_id,
                    raw_path=raw_path,
                    canonical_url=meta["canonical_url"],
                    doc_type=meta["doc_type"],
                    pine_version=meta["pine_version"],
                )
            )
    return sorted(artifacts, key=lambda item: item.canonical_url)


def read_meta_content_encoding(raw_path: str) -> str | None:
    meta_path = raw_path + ".meta.json"
    if not os.path.exists(meta_path):
        return None
    meta = json.loads(open(meta_path, "r", encoding="utf-8").read())
    return meta.get("content_encoding")


def has_meaningful_text(nodes: Iterable[object]) -> bool:
    for node in nodes:
        if hasattr(node, "get_text"):
            if node.get_text(strip=True):
                return True
        else:
            text = str(node).strip()
            if text:
                return True
    return False


def serialize_nodes(nodes: Iterable[object]) -> str:
    return "".join(str(node) for node in nodes).strip()


def parse_guide_segments(artifact: Artifact) -> list[Segment]:
    raw_bytes = open(artifact.raw_path, "rb").read()
    content_encoding = read_meta_content_encoding(artifact.raw_path)
    html = decode_html(raw_bytes, content_encoding)
    soup = BeautifulSoup(html, "html.parser")

    container = soup.select_one("main.content")
    if container is None:
        container = soup.select_one("main.main-pane")
    if container is None:
        container = soup.body
    if container is None:
        raise ValueError("guide_container_missing")

    headings = container.find_all("h2")
    if not headings:
        raise ValueError("guide_no_h2")

    segments: list[Segment] = []
    segment_order = 1

    first_h2 = headings[0]
    parent = first_h2.parent
    pre_nodes = []
    for child in list(parent.children):
        if child == first_h2:
            break
        pre_nodes.append(child)
    if pre_nodes and has_meaningful_text(pre_nodes):
        raw_html = serialize_nodes(pre_nodes)
        segments.append(
            Segment(
                source_artifact_id=artifact.source_artifact_id,
                canonical_url=artifact.canonical_url,
                doc_type=artifact.doc_type,
                pine_version=artifact.pine_version,
                segment_id=f"{artifact.source_artifact_id}:{segment_order}",
                segment_type="guide_section",
                segment_order=segment_order,
                raw_html=raw_html,
            )
        )
        segment_order += 1

    for heading in headings:
        nodes = [heading]
        for sibling in list(heading.next_siblings):
            if getattr(sibling, "name", None) == "h2":
                break
            nodes.append(sibling)
        raw_html = serialize_nodes(nodes)
        segments.append(
            Segment(
                source_artifact_id=artifact.source_artifact_id,
                canonical_url=artifact.canonical_url,
                doc_type=artifact.doc_type,
                pine_version=artifact.pine_version,
                segment_id=f"{artifact.source_artifact_id}:{segment_order}",
                segment_type="guide_section",
                segment_order=segment_order,
                raw_html=raw_html,
            )
        )
        segment_order += 1

    return segments


def extract_symbol_type(anchor_tag) -> str | None:
    if anchor_tag is None:
        return None
    candidates = anchor_tag.find_all(
        lambda tag: tag.has_attr("class")
        and any(
            key in " ".join(tag["class"]).lower()
            for key in ("type", "kind", "category")
        )
    )
    for candidate in candidates:
        text = candidate.get_text(strip=True)
        if text:
            return text
    return None


def parse_reference_segments(artifact: Artifact) -> list[Segment]:
    raw_bytes = open(artifact.raw_path, "rb").read()
    content_encoding = read_meta_content_encoding(artifact.raw_path)
    html = decode_html(raw_bytes, content_encoding)
    soup = BeautifulSoup(html, "html.parser")

    container = soup.select_one("main#tv-content") or soup.select_one("main.tv-content")
    if container is None:
        raise ValueError("reference_container_missing")

    anchors = []
    for tag in container.find_all(attrs={"id": True}):
        anchor_id = tag.get("id")
        if anchor_id == "tv-content":
            continue
        anchors.append(tag)

    if not anchors:
        raise ValueError("reference_no_anchors")

    segments: list[Segment] = []
    segment_order = 1
    for anchor in anchors:
        anchor_id = anchor.get("id")
        nodes = [anchor]
        for sibling in list(anchor.next_siblings):
            if getattr(sibling, "attrs", {}).get("id"):
                break
            nodes.append(sibling)
        raw_html = serialize_nodes(nodes)
        symbol_name = anchor.get_text(" ", strip=True) or None
        symbol_type = extract_symbol_type(anchor)
        segments.append(
            Segment(
                source_artifact_id=artifact.source_artifact_id,
                canonical_url=artifact.canonical_url,
                doc_type=artifact.doc_type,
                pine_version=artifact.pine_version,
                segment_id=f"{artifact.source_artifact_id}:{anchor_id}",
                segment_type="reference_entry",
                segment_order=segment_order,
                raw_html=raw_html,
                anchor_id=anchor_id,
                symbol_name=symbol_name,
                symbol_type=symbol_type,
            )
        )
        segment_order += 1

    return segments


def segment_artifacts(raw_root: str) -> tuple[list[Segment], list[Failure]]:
    artifacts = load_artifacts(raw_root)
    segments: list[Segment] = []
    failures: list[Failure] = []

    for artifact in artifacts:
        try:
            if artifact.doc_type == "guide":
                segments.extend(parse_guide_segments(artifact))
            elif artifact.doc_type == "reference":
                segments.extend(parse_reference_segments(artifact))
            else:
                failures.append(
                    Failure(
                        source_artifact_id=artifact.source_artifact_id,
                        canonical_url=artifact.canonical_url,
                        doc_type=artifact.doc_type,
                        pine_version=artifact.pine_version,
                        reason="unknown_doc_type",
                    )
                )
        except ValueError as exc:
            failures.append(
                Failure(
                    source_artifact_id=artifact.source_artifact_id,
                    canonical_url=artifact.canonical_url,
                    doc_type=artifact.doc_type,
                    pine_version=artifact.pine_version,
                    reason=str(exc),
                )
            )
            if artifact.doc_type == "reference":
                break
    return segments, failures


def write_segments(path: str, segments: list[Segment]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for segment in segments:
            handle.write(json.dumps(segment.__dict__, sort_keys=True))
            handle.write("\n")


def write_failures(path: str, failures: list[Failure]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for failure in failures:
            handle.write(json.dumps(failure.__dict__, sort_keys=True))
            handle.write("\n")
