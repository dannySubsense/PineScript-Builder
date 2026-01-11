from __future__ import annotations

import json
from pathlib import Path
from typing import Any


RETRIEVAL_MODES = {"reference_only", "reference_plus_guides"}
PINE_VERSIONS = {"v5", "v6"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _latest_index_dir(base_dir: Path) -> Path:
    if not base_dir.exists():
        raise FileNotFoundError(str(base_dir))
    dirs = [path for path in base_dir.iterdir() if path.is_dir()]
    if not dirs:
        raise FileNotFoundError(str(base_dir))
    return sorted(dirs, key=lambda item: item.name)[-1]


def _load_index(index_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    chunks_path = index_dir / "chunks.jsonl"
    meta_path = index_dir / "index_meta.json"
    chunks = _load_jsonl(chunks_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return chunks, meta


def _load_enrichment(pine_version: str) -> dict[str, dict[str, Any]]:
    root = _repo_root()
    enrichment_path = root / "artifacts" / "enrichment" / pine_version / "reference_symbols_enrichment.jsonl"
    records = _load_jsonl(enrichment_path)
    return {rec["reference_symbol_id"]: rec for rec in records}


def _build_provenance(chunk: dict[str, Any]) -> dict[str, Any]:
    provenance = {
        "canonical_url": chunk.get("canonical_url"),
        "run_id": chunk.get("run_id"),
        "source_artifact_id": chunk.get("source_artifact_id"),
    }
    if "segment_id" in chunk:
        provenance["segment_id"] = chunk["segment_id"]
    if "anchor_id" in chunk:
        provenance["anchor_id"] = chunk["anchor_id"]
    return provenance


def pine_query(query: str, pine_version: str, mode: str) -> dict[str, Any]:
    if pine_version not in PINE_VERSIONS:
        raise ValueError("pine_version_invalid")
    if mode not in RETRIEVAL_MODES:
        raise ValueError("mode_invalid")

    root = _repo_root()
    index_base = root / "artifacts" / "rag_indexes" / pine_version
    index_dir = _latest_index_dir(index_base)
    chunks, meta = _load_index(index_dir)

    if mode == "reference_only":
        filtered = [chunk for chunk in chunks if chunk.get("doc_type") == "reference"]
    else:
        if pine_version == "v5":
            filtered = [chunk for chunk in chunks if chunk.get("doc_type") == "reference"]
        else:
            filtered = [chunk for chunk in chunks if chunk.get("doc_type") in {"reference", "guide"}]

    enrichment = _load_enrichment(pine_version)
    response_chunks = []
    for chunk in filtered:
        reference_symbol_id = chunk.get("reference_symbol_id")
        enrichment_record = None
        if reference_symbol_id:
            enrichment_record = enrichment.get(reference_symbol_id)
        response_chunks.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "content": chunk.get("body"),
                "source_type": chunk.get("doc_type"),
                "reference_symbol_id": reference_symbol_id,
                "enrichment": enrichment_record,
                "provenance": _build_provenance(chunk),
            }
        )

    warnings = []
    if pine_version == "v5" and mode == "reference_plus_guides":
        warnings.append("guides_unavailable_for_v5")

    response = {
        "query": query,
        "pine_version": pine_version,
        "mode": mode,
        "chunks": response_chunks,
        "warnings": warnings,
        "metadata": {
            "retrieval_version": meta.get("index_id", index_dir.name),
            "artifact_run_ids": {
                "reference_run_ids": meta.get("reference_run_ids", []),
                "guide_run_ids": meta.get("guide_run_ids", []),
            },
        },
    }
    return response


def _qc_checks() -> None:
    sample_query = "bar_index"
    response_a = pine_query(sample_query, "v5", "reference_only")
    response_b = pine_query(sample_query, "v5", "reference_only")
    if response_a != response_b:
        raise SystemExit("qc_fail_determinism")

    for chunk in response_a["chunks"]:
        if "/pine-script-reference/v6/" in (chunk["provenance"].get("canonical_url") or ""):
            raise SystemExit("qc_fail_version_isolation")

    response_v6_ref = pine_query(sample_query, "v6", "reference_only")
    for chunk in response_v6_ref["chunks"]:
        if chunk.get("source_type") == "guide":
            raise SystemExit("qc_fail_mode_gating_reference_only")

    response_v6_all = pine_query(sample_query, "v6", "reference_plus_guides")
    has_guide = any(chunk.get("source_type") == "guide" for chunk in response_v6_all["chunks"])
    if response_v6_all["chunks"] and not has_guide:
        raise SystemExit("qc_fail_mode_gating_reference_plus_guides")

    for chunk in response_v6_ref["chunks"]:
        if chunk.get("source_type") == "reference" and chunk.get("enrichment") is None:
            raise SystemExit("qc_fail_enrichment_attachment")


if __name__ == "__main__":
    _qc_checks()
