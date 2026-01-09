from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_PATH = os.path.join(PROJECT_ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from tradingview_ingest.rendered_reference import (
    REFERENCE_URL,
    RenderConfig,
    anchor_prefix_counts,
    drift_recommended_action,
    drift_severity,
    ensure_directories,
    read_manifest,
    render_reference,
    segment_reference_html,
    sha256_hex,
    utc_now_iso,
    write_jsonl,
    write_manifest,
)


def run_id_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def manifest_path(run_id: str) -> str:
    return os.path.join(
        PROJECT_ROOT,
        "raw",
        "rendered",
        "v6",
        "reference",
        run_id,
        "manifest.json",
    )


def reference_html_path(run_id: str) -> str:
    return os.path.join(
        PROJECT_ROOT,
        "raw",
        "rendered",
        "v6",
        "reference",
        run_id,
        "reference.html",
    )


def acquisition_log_path(run_id: str) -> str:
    return os.path.join(
        PROJECT_ROOT,
        "artifacts",
        "acquisition_runs",
        "v6",
        f"{run_id}.jsonl",
    )


def segment_log_path(run_id: str) -> str:
    return os.path.join(
        PROJECT_ROOT,
        "artifacts",
        "segmentation_runs",
        "v6",
        f"{run_id}.jsonl",
    )


def segment_output_path(run_id: str) -> str:
    return os.path.join(
        PROJECT_ROOT,
        "artifacts",
        "segments",
        "v6",
        f"{run_id}.jsonl",
    )


def drift_report_path(baseline: str, candidate: str) -> str:
    return os.path.join(
        PROJECT_ROOT,
        "artifacts",
        "drift_reports",
        "v6",
        f"{baseline}__{candidate}.json",
    )


def latest_manifest(run_id: str | None = None) -> str | None:
    base = Path(PROJECT_ROOT) / "raw" / "rendered" / "v6" / "reference"
    if not base.exists():
        return None
    manifests = sorted(base.glob("*/manifest.json"))
    if not manifests:
        return None
    if run_id:
        for manifest in manifests:
            if manifest.parent.name == run_id:
                return str(manifest)
    return str(manifests[-1])


def previous_manifest(current_run_id: str) -> str | None:
    base = Path(PROJECT_ROOT) / "raw" / "rendered" / "v6" / "reference"
    manifests = sorted(base.glob("*/manifest.json"))
    if len(manifests) < 2:
        return None
    manifests_sorted = sorted(manifests, key=lambda item: item.parent.name)
    for idx, manifest in enumerate(manifests_sorted):
        if manifest.parent.name == current_run_id and idx > 0:
            return str(manifests_sorted[idx - 1])
    return None


def render_and_manifest(run_id: str) -> dict:
    config = RenderConfig(
        viewport={"width": 1400, "height": 900},
        locale="en-US",
        timezone="UTC",
        user_agent="PineScript-Builder rendered acquisition/0.1",
        render_wait_strategy="anchor_stability",
        max_wait_seconds=120,
        post_render_delay_ms=1000,
        anchor_min_threshold=200,
        stabilize_checks=3,
        stabilize_interval_seconds=1.0,
        max_scrolls=5,
    )

    result = render_reference(REFERENCE_URL, config)
    html_path = reference_html_path(run_id)
    os.makedirs(os.path.dirname(html_path), exist_ok=True)
    html_bytes = result.html.encode("utf-8")
    with open(html_path, "wb") as handle:
        handle.write(html_bytes)

    checksum = sha256_hex(html_bytes)
    manifest = {
        "manifest_version": "1.0",
        "canonical_url": REFERENCE_URL,
        "doc_type": "reference",
        "pine_version": "v6",
        "run_id": run_id,
        "capture_method": "rendered_playwright",
        "capture_timestamp": utc_now_iso(),
        "render_engine": "playwright",
        "browser_name": result.browser_name,
        "browser_version": result.browser_version,
        "user_agent": config.user_agent,
        "viewport": config.viewport,
        "locale": config.locale,
        "timezone": config.timezone,
        "render_wait_strategy": config.render_wait_strategy,
        "max_wait_seconds": config.max_wait_seconds,
        "post_render_delay_ms": config.post_render_delay_ms,
        "anchor_count_total": len(result.anchor_ids),
        "anchor_counts_by_prefix": result.anchor_counts_by_prefix,
        "artifact_path": os.path.relpath(html_path, PROJECT_ROOT),
        "artifact_size_bytes": len(html_bytes),
        "artifact_checksum_sha256": checksum,
        "status": result.status,
        "notes": result.notes,
    }

    write_manifest(manifest_path(run_id), manifest)
    write_jsonl(
        acquisition_log_path(run_id),
        {
            "run_id": run_id,
            "status": result.status,
            "anchor_count_total": len(result.anchor_ids),
            "artifact_path": manifest["artifact_path"],
        },
    )
    return manifest


def segment_reference(run_id: str, manifest: dict) -> None:
    if manifest["status"] != "complete":
        raise SystemExit("render_incomplete")

    html_path = os.path.join(PROJECT_ROOT, manifest["artifact_path"])
    html = open(html_path, "r", encoding="utf-8").read()
    segments, qc = segment_reference_html(
        html=html,
        canonical_url=manifest["canonical_url"],
        run_id=run_id,
        source_artifact_id=manifest["artifact_checksum_sha256"],
    )

    anchor_total = manifest["anchor_count_total"]
    if qc["segment_count"] != anchor_total:
        write_jsonl(
            segment_log_path(run_id),
            {
                "run_id": run_id,
                "status": "failed",
                "reason": "segment_count_mismatch",
                "segment_count": qc["segment_count"],
                "anchor_count_total": anchor_total,
            },
        )
        raise SystemExit("segment_count_mismatch")

    empty_limit = max(5, int(anchor_total * 0.1))
    if qc["empty_symbol_names"] > empty_limit:
        write_jsonl(
            segment_log_path(run_id),
            {
                "run_id": run_id,
                "status": "failed",
                "reason": "empty_symbol_names",
                "empty_symbol_names": qc["empty_symbol_names"],
                "anchor_count_total": anchor_total,
            },
        )
        raise SystemExit("empty_symbol_names")

    if qc["empty_raw_html"] > 0:
        write_jsonl(
            segment_log_path(run_id),
            {
                "run_id": run_id,
                "status": "failed",
                "reason": "empty_raw_html",
                "empty_raw_html": qc["empty_raw_html"],
            },
        )
        raise SystemExit("empty_raw_html")

    output_path = segment_output_path(run_id)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "a", encoding="utf-8") as handle:
        for segment in segments:
            handle.write(json.dumps(segment, sort_keys=True))
            handle.write("\n")

    write_jsonl(
        segment_log_path(run_id),
        {
            "run_id": run_id,
            "status": "complete",
            "segment_count": qc["segment_count"],
            "empty_symbol_names": qc["empty_symbol_names"],
            "empty_raw_html": qc["empty_raw_html"],
        },
    )


def generate_drift_report(baseline_manifest: dict, candidate_manifest: dict) -> dict:
    env_delta = {
        "browser_version": (
            baseline_manifest["browser_version"],
            candidate_manifest["browser_version"],
        ),
        "user_agent": (baseline_manifest["user_agent"], candidate_manifest["user_agent"]),
        "viewport": (baseline_manifest["viewport"], candidate_manifest["viewport"]),
        "locale": (baseline_manifest["locale"], candidate_manifest["locale"]),
        "timezone": (baseline_manifest["timezone"], candidate_manifest["timezone"]),
    }
    env_changed = any(value[0] != value[1] for value in env_delta.values())
    anchor_delta = candidate_manifest["anchor_count_total"] - baseline_manifest["anchor_count_total"]
    prefix_delta = {}
    for prefix, count in baseline_manifest["anchor_counts_by_prefix"].items():
        prefix_delta[prefix] = candidate_manifest["anchor_counts_by_prefix"].get(prefix, 0) - count

    checksum_changed = (
        baseline_manifest["artifact_checksum_sha256"]
        != candidate_manifest["artifact_checksum_sha256"]
    )
    size_delta = candidate_manifest["artifact_size_bytes"] - baseline_manifest["artifact_size_bytes"]

    severity = drift_severity(anchor_delta, env_changed)
    report = {
        "baseline_run_id": baseline_manifest["run_id"],
        "candidate_run_id": candidate_manifest["run_id"],
        "canonical_url": candidate_manifest["canonical_url"],
        "pine_version": candidate_manifest["pine_version"],
        "environment_deltas": env_delta,
        "artifact_checksum_changed": checksum_changed,
        "artifact_size_delta": size_delta,
        "anchor_count_delta": anchor_delta,
        "anchor_prefix_deltas": prefix_delta,
        "drift_severity": severity,
        "recommended_action": drift_recommended_action(severity),
    }
    return report


def main() -> None:
    ensure_directories(
        [
            os.path.join(PROJECT_ROOT, "raw", "rendered", "v6", "reference"),
            os.path.join(PROJECT_ROOT, "artifacts", "acquisition_runs", "v6"),
            os.path.join(PROJECT_ROOT, "artifacts", "segmentation_runs", "v6"),
            os.path.join(PROJECT_ROOT, "artifacts", "segments", "v6"),
            os.path.join(PROJECT_ROOT, "artifacts", "drift_reports", "v6"),
        ]
    )

    run_id = run_id_now()
    manifest = render_and_manifest(run_id)
    if manifest["status"] != "complete":
        raise SystemExit("render_failed")

    segment_reference(run_id, manifest)

    baseline_path = previous_manifest(run_id)
    if baseline_path:
        baseline_manifest = read_manifest(baseline_path)
        candidate_manifest = manifest
        report = generate_drift_report(baseline_manifest, candidate_manifest)
        report_path = drift_report_path(baseline_manifest["run_id"], run_id)
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"drift_report={report_path}")
    else:
        print("drift_report=no_baseline_available")

    print(f"run_id={run_id}")
    print(f"manifest={manifest_path(run_id)}")
    print(f"segments={segment_output_path(run_id)}")


if __name__ == "__main__":
    main()
