from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_PATH = os.path.join(PROJECT_ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from tradingview_ingest.reference_normalization import normalize_reference_symbols


def main() -> None:
    segments_path = os.path.join(
        PROJECT_ROOT, "artifacts", "segments", "v6", "manual_baseline.jsonl"
    )
    output_path = os.path.join(
        PROJECT_ROOT, "normalized", "v6", "reference_symbols.jsonl"
    )

    written, sample_ids = normalize_reference_symbols(segments_path, output_path)
    print(f"output={output_path}")
    print(f"rows_written={written}")
    print(f"sample_reference_symbol_ids={sample_ids}")


if __name__ == "__main__":
    main()
