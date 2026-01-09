from __future__ import annotations

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_PATH = os.path.join(PROJECT_ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from tradingview_ingest.rendered_reference import drift_recommended_action, drift_severity, read_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate drift report for v6 reference manifests.")
    parser.add_argument("--baseline", required=True, help="Path to baseline manifest.json")
    parser.add_argument("--candidate", required=True, help="Path to candidate manifest.json")
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for drift report JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    baseline = read_manifest(args.baseline)
    candidate = read_manifest(args.candidate)

    env_delta = {
        "browser_version": (baseline["browser_version"], candidate["browser_version"]),
        "user_agent": (baseline["user_agent"], candidate["user_agent"]),
        "viewport": (baseline["viewport"], candidate["viewport"]),
        "locale": (baseline["locale"], candidate["locale"]),
        "timezone": (baseline["timezone"], candidate["timezone"]),
    }
    env_changed = any(value[0] != value[1] for value in env_delta.values())
    anchor_delta = candidate["anchor_count_total"] - baseline["anchor_count_total"]
    prefix_delta = {}
    for prefix, count in baseline["anchor_counts_by_prefix"].items():
        prefix_delta[prefix] = candidate["anchor_counts_by_prefix"].get(prefix, 0) - count

    checksum_changed = baseline["artifact_checksum_sha256"] != candidate["artifact_checksum_sha256"]
    size_delta = candidate["artifact_size_bytes"] - baseline["artifact_size_bytes"]

    severity = drift_severity(anchor_delta, env_changed)
    report = {
        "baseline_run_id": baseline["run_id"],
        "candidate_run_id": candidate["run_id"],
        "canonical_url": candidate["canonical_url"],
        "pine_version": candidate["pine_version"],
        "environment_deltas": env_delta,
        "artifact_checksum_changed": checksum_changed,
        "artifact_size_delta": size_delta,
        "anchor_count_delta": anchor_delta,
        "anchor_prefix_deltas": prefix_delta,
        "drift_severity": severity,
        "recommended_action": drift_recommended_action(severity),
    }
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()
