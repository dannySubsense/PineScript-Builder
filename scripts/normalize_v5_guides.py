from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_PATH = os.path.join(PROJECT_ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from tradingview_ingest.normalization import normalize_guides


def main() -> None:
    pages_written, sections_written, fallback_count, warnings = normalize_guides(PROJECT_ROOT)
    print(f"guide_pages_written={pages_written}")
    print(f"guide_sections_written={sections_written}")
    print(f"fallback_sections={fallback_count}")
    print(f"warnings={len(warnings)}")


if __name__ == "__main__":
    main()
