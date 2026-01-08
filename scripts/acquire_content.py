from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_PATH = os.path.join(PROJECT_ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from tradingview_ingest.acquisition import acquire_inventory, load_inventory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Acquire raw Pine Script docs.")
    parser.add_argument(
        "--inventory",
        default="artifacts/discovery_inventory.json",
        help="Path to discovery inventory JSON.",
    )
    parser.add_argument(
        "--output-root",
        default="raw",
        help="Output root directory for raw artifacts.",
    )
    parser.add_argument(
        "--run-log",
        default=None,
        help="Optional run log path. If omitted, uses artifacts/acquisition_runs/<run_id>.jsonl.",
    )
    parser.add_argument("--retries", type=int, default=2, help="Retry count for fetches.")
    parser.add_argument(
        "--backoff-seconds",
        type=float,
        default=1.0,
        help="Base backoff seconds between retries.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=1.0,
        help="Delay between requests.",
    )
    return parser.parse_args()


def build_run_log_path(root: str) -> str:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return os.path.join(root, "artifacts", "acquisition_runs", f"{run_id}.jsonl")


def main() -> None:
    args = parse_args()
    inventory = load_inventory(args.inventory)
    run_log = args.run_log or build_run_log_path(PROJECT_ROOT)
    counts = acquire_inventory(
        inventory=inventory,
        output_root=os.path.join(PROJECT_ROOT, args.output_root),
        run_log_path=run_log,
        retries=args.retries,
        backoff_seconds=args.backoff_seconds,
        sleep_seconds=args.sleep_seconds,
    )

    print(f"attempted={counts['attempted']}")
    print(f"written={counts['written']}")
    print(f"skipped={counts['skipped']}")
    print(f"failed_guide={counts['failed_guide']}")
    print(f"failed_reference={counts['failed_reference']}")
    print(f"run_log={run_log}")


if __name__ == "__main__":
    main()
