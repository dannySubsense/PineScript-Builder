from __future__ import annotations

import json
import os


ANCHOR_PREFIXES = [
    "var_",
    "fun_",
    "const_",
    "type_",
    "kw_",
    "op_",
    "an_",
]
SYMBOL_TYPES = {prefix.rstrip("_") for prefix in ANCHOR_PREFIXES}


def derive_symbol_type(anchor_id: str) -> str:
    for prefix in ANCHOR_PREFIXES:
        if anchor_id.startswith(prefix):
            return prefix.rstrip("_")
    raise ValueError(f"unknown_anchor_prefix:{anchor_id}")


def normalize_reference_symbols(
    segments_path: str, output_path: str
) -> tuple[int, list[str]]:
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        raise FileExistsError(f"output_exists:{output_path}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    seen_ids: set[str] = set()
    sample_ids: list[str] = []
    written = 0

    with open(segments_path, "r", encoding="utf-8") as source, open(
        output_path, "a", encoding="utf-8"
    ) as target:
        for line in source:
            if not line.strip():
                continue
            segment = json.loads(line)

            anchor_id = segment.get("anchor_id")
            source_artifact_id = segment.get("source_artifact_id")
            reference_symbol_id = f"{source_artifact_id}:{anchor_id}"
            symbol_type = derive_symbol_type(anchor_id)

            record = {
                "reference_symbol_id": reference_symbol_id,
                "anchor_id": anchor_id,
                "symbol_name": segment.get("symbol_name", ""),
                "symbol_type": symbol_type,
                "canonical_url": segment.get("canonical_url"),
                "pine_version": "v6",
                "segment_order": segment.get("segment_order"),
                "raw_html": segment.get("raw_html"),
                "run_id": segment.get("run_id"),
                "source_artifact_id": source_artifact_id,
                "segment_id": segment.get("segment_id"),
                "symbol_name_normalized": "",
                "symbol_signature": "",
                "symbol_category": "",
                "notes": "",
            }

            required = [
                "reference_symbol_id",
                "anchor_id",
                "symbol_name",
                "symbol_type",
                "canonical_url",
                "pine_version",
                "segment_order",
                "raw_html",
                "run_id",
                "source_artifact_id",
                "segment_id",
            ]
            missing = [key for key in required if record.get(key) in (None, "")]
            if missing:
                raise ValueError(f"missing_required:{','.join(missing)}")
            if record["pine_version"] != "v6":
                raise ValueError(f"invalid_pine_version:{record['pine_version']}")
            if record["symbol_type"] not in SYMBOL_TYPES:
                raise ValueError(f"invalid_symbol_type:{record['symbol_type']}")
            if reference_symbol_id in seen_ids:
                raise ValueError(f"duplicate_reference_symbol_id:{reference_symbol_id}")

            seen_ids.add(reference_symbol_id)
            if len(sample_ids) < 5:
                sample_ids.append(reference_symbol_id)

            target.write(json.dumps(record, sort_keys=True))
            target.write("\n")
            written += 1

    return written, sample_ids
