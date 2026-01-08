from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_PATH = os.path.join(PROJECT_ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from tradingview_ingest.segmentation import segment_artifacts, write_failures, write_segments


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Segment raw Pine Script docs.")
    parser.add_argument(
        "--raw-root",
        default="raw",
        help="Root directory containing raw artifacts.",
    )
    parser.add_argument(
        "--segments-out",
        default=None,
        help="Output JSONL path for segments.",
    )
    parser.add_argument(
        "--failures-out",
        default=None,
        help="Output JSONL path for failures.",
    )
    return parser.parse_args()


def build_paths(root: str) -> tuple[str, str]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    segments_out = os.path.join(root, "artifacts", "segments", f"{run_id}.jsonl")
    failures_out = os.path.join(root, "artifacts", "segmentation_runs", f"{run_id}.jsonl")
    return segments_out, failures_out


def main() -> None:
    args = parse_args()
    segments_out, failures_out = build_paths(PROJECT_ROOT)
    if args.segments_out:
        segments_out = args.segments_out
    if args.failures_out:
        failures_out = args.failures_out

    segments, failures = segment_artifacts(os.path.join(PROJECT_ROOT, args.raw_root))
    write_segments(segments_out, segments)
    write_failures(failures_out, failures)

    reference_failed = any(
        failure.doc_type == "reference" for failure in failures
    )

    guide_count = sum(1 for segment in segments if segment.doc_type == "guide")
    reference_count = sum(1 for segment in segments if segment.doc_type == "reference")
    print(f"segments_total={len(segments)}")
    print(f"segments_guide={guide_count}")
    print(f"segments_reference={reference_count}")
    print(f"failures={len(failures)}")
    print(f"segments_out={segments_out}")
    print(f"failures_out={failures_out}")

    if reference_failed:
        raise SystemExit("reference_parsing_failed")


if __name__ == "__main__":
    main()
