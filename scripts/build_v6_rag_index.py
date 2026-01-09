from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def utc_index_id() -> str:
    return datetime.now(timezone.utc).strftime("v6_%Y%m%dT%H%M%SZ")


def read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            records.append(json.loads(line))
    return records


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    reference_path = root / "normalized" / "v6" / "reference_symbols.jsonl"
    guide_path = root / "normalized" / "v6" / "guide_sections.jsonl"

    index_id = utc_index_id()
    index_root = root / "artifacts" / "rag_indexes" / "v6" / index_id
    chunks_path = index_root / "chunks.jsonl"
    meta_path = index_root / "index_meta.json"

    if index_root.exists():
        raise SystemExit(f"index_exists:{index_root}")

    reference_rows = read_jsonl(reference_path)
    guide_rows = read_jsonl(guide_path)

    index_root.mkdir(parents=True, exist_ok=False)

    chunk_ids: set[str] = set()
    sample_ids: list[str] = []
    total_chunks = 0
    reference_run_ids: set[str] = set()
    guide_run_ids: set[str] = set()

    with chunks_path.open("w", encoding="utf-8") as handle:
        for row in reference_rows:
            if row.get("pine_version") != "v6":
                raise ValueError(f"invalid_pine_version:{row.get('pine_version')}")
            chunk_id = f"reference:{row['reference_symbol_id']}"
            if chunk_id in chunk_ids:
                raise ValueError(f"duplicate_chunk_id:{chunk_id}")
            chunk_ids.add(chunk_id)

            record = {
                "chunk_id": chunk_id,
                "doc_type": "reference",
                "pine_version": "v6",
                "canonical_url": row.get("canonical_url"),
                "body": row.get("raw_html"),
                "run_id": row.get("run_id"),
                "source_artifact_id": row.get("source_artifact_id"),
                "reference_symbol_id": row.get("reference_symbol_id"),
                "anchor_id": row.get("anchor_id"),
                "symbol_type": row.get("symbol_type"),
                "symbol_name": row.get("symbol_name"),
            }

            required = [
                "chunk_id",
                "doc_type",
                "pine_version",
                "canonical_url",
                "body",
                "run_id",
                "source_artifact_id",
                "reference_symbol_id",
                "anchor_id",
                "symbol_type",
                "symbol_name",
            ]
            missing = [key for key in required if record.get(key) in (None, "")]
            if missing:
                raise ValueError(f"missing_required:{','.join(missing)}")

            if len(sample_ids) < 5:
                sample_ids.append(chunk_id)
            reference_run_ids.add(record["run_id"])
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")
            total_chunks += 1

        for row in guide_rows:
            if row.get("pine_version") != "v6":
                raise ValueError(f"invalid_pine_version:{row.get('pine_version')}")
            chunk_id = f"guide:{row['guide_section_id']}"
            if chunk_id in chunk_ids:
                raise ValueError(f"duplicate_chunk_id:{chunk_id}")
            chunk_ids.add(chunk_id)

            record = {
                "chunk_id": chunk_id,
                "doc_type": "guide",
                "pine_version": "v6",
                "canonical_url": row.get("canonical_url"),
                "body": row.get("raw_html"),
                "run_id": row.get("run_id"),
                "source_artifact_id": row.get("source_artifact_id"),
                "guide_section_id": row.get("guide_section_id"),
                "section_title": row.get("section_title"),
                "section_path": row.get("section_path"),
                "segment_order": row.get("segment_order"),
                "segment_id": row.get("segment_id"),
            }

            required = [
                "chunk_id",
                "doc_type",
                "pine_version",
                "canonical_url",
                "body",
                "run_id",
                "source_artifact_id",
                "guide_section_id",
                "section_title",
                "section_path",
                "segment_order",
                "segment_id",
            ]
            missing = [key for key in required if record.get(key) in (None, "")]
            if missing:
                raise ValueError(f"missing_required:{','.join(missing)}")

            if len(sample_ids) < 5:
                sample_ids.append(chunk_id)
            guide_run_ids.add(record["run_id"])
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")
            total_chunks += 1

    expected_total = len(reference_rows) + len(guide_rows)
    if total_chunks != expected_total:
        raise ValueError("chunk_count_mismatch")

    meta = {
        "index_id": index_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "pine_version": "v6",
        "input_files": [
            {"path": str(reference_path), "row_count": len(reference_rows)},
            {"path": str(guide_path), "row_count": len(guide_rows)},
        ],
        "total_chunks": total_chunks,
        "reference_run_ids": sorted(reference_run_ids),
        "guide_run_ids": sorted(guide_run_ids),
    }

    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(f"index_id={index_id}")
    print(f"chunks_path={chunks_path}")
    print(f"meta_path={meta_path}")
    print(f"reference_rows={len(reference_rows)}")
    print(f"guide_rows={len(guide_rows)}")
    print(f"total_chunks={total_chunks}")
    print(f"sample_chunk_ids={sample_ids}")


if __name__ == "__main__":
    main()
