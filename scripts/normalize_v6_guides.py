from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    run_id = "20260109T135601Z"
    root = Path(__file__).resolve().parent.parent
    segments_path = (
        root / "artifacts" / "segments" / "v6" / "guides" / f"{run_id}.jsonl"
    )
    output_path = root / "normalized" / "v6" / "guide_sections.jsonl"

    if output_path.exists() and output_path.stat().st_size > 0:
        raise SystemExit(f"output_exists:{output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    seen_ids: set[str] = set()
    written = 0
    sample_ids: list[str] = []

    with segments_path.open("r", encoding="utf-8") as source, output_path.open(
        "a", encoding="utf-8"
    ) as target:
        for line in source:
            if not line.strip():
                continue
            segment = json.loads(line)
            guide_section_id = segment["segment_id"]

            record = {
                "guide_section_id": guide_section_id,
                "section_title": segment.get("section_title", ""),
                "section_path": segment.get("section_path", ""),
                "canonical_url": segment.get("canonical_url"),
                "pine_version": "v6",
                "segment_order": segment.get("segment_order"),
                "raw_html": segment.get("raw_html"),
                "run_id": segment.get("run_id"),
                "source_artifact_id": segment.get("source_artifact_id"),
                "segment_id": segment.get("segment_id"),
                "summary": "",
                "keywords": "",
                "notes": "",
            }

            required = [
                "guide_section_id",
                "section_title",
                "section_path",
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
            if guide_section_id in seen_ids:
                raise ValueError(f"duplicate_guide_section_id:{guide_section_id}")

            seen_ids.add(guide_section_id)
            if len(sample_ids) < 5:
                sample_ids.append(guide_section_id)

            target.write(json.dumps(record, sort_keys=True))
            target.write("\n")
            written += 1

    print(f"output={output_path}")
    print(f"rows_written={written}")
    print(f"sample_guide_section_ids={sample_ids}")


if __name__ == "__main__":
    main()
