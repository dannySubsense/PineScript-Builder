from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_PATH = os.path.join(PROJECT_ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from tradingview_ingest.discovery import discover_urls, write_excluded, write_inventory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Pine Script URL inventory.")
    parser.add_argument(
        "--entry-point",
        action="append",
        required=True,
        dest="entry_points",
        help="Authoritative entry point URL (repeatable).",
    )
    parser.add_argument(
        "--output",
        default="artifacts/discovery_inventory.json",
        help="Path for inventory JSON output.",
    )
    parser.add_argument(
        "--excluded-output",
        default="artifacts/discovery_excluded.jsonl",
        help="Path for excluded URL log output.",
    )
    return parser.parse_args()


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def main() -> None:
    args = parse_args()
    inventory, excluded = discover_urls(args.entry_points)
    ensure_parent_dir(args.output)
    ensure_parent_dir(args.excluded_output)
    write_inventory(args.output, inventory)
    write_excluded(args.excluded_output, excluded)

    doc_counts = Counter(item.doc_type for item in inventory)
    version_counts = Counter(item.pine_version for item in inventory)

    print(f"inventory_count={len(inventory)}")
    print(f"excluded_count={len(excluded)}")
    print(f"doc_type_counts={dict(sorted(doc_counts.items()))}")
    print(f"pine_version_counts={dict(sorted(version_counts.items()))}")


if __name__ == "__main__":
    main()
