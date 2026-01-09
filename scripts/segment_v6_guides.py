from __future__ import annotations

import json
import os
from pathlib import Path

from bs4 import BeautifulSoup


HEADING_TAGS = ("h1", "h2", "h3")


def serialize_nodes(nodes) -> str:
    return "".join(str(node) for node in nodes).strip()


def heading_text(tag) -> str:
    return tag.get_text(" ", strip=True)


def build_section_path(title_stack: list[str]) -> str:
    return " > ".join([title for title in title_stack if title])


def main() -> None:
    run_id = "20260109T135601Z"
    root = Path(__file__).resolve().parent.parent
    render_root = root / "raw" / "rendered" / "v6" / "guides" / run_id
    output_path = root / "artifacts" / "segments" / "v6" / "guides" / f"{run_id}.jsonl"

    if output_path.exists() and output_path.stat().st_size > 0:
        raise SystemExit(f"output_exists:{output_path}")

    manifests = sorted(render_root.glob("*.manifest.json"))
    if not manifests:
        raise SystemExit("no_manifests")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    segment_ids: set[str] = set()
    total_segments = 0

    with output_path.open("a", encoding="utf-8") as out:
        for manifest_path in manifests:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("status") != "complete":
                raise SystemExit(f"manifest_incomplete:{manifest_path.name}")
            if manifest.get("doc_type") != "guide":
                raise SystemExit(f"manifest_doc_type:{manifest_path.name}")
            if manifest.get("pine_version") != "v6":
                raise SystemExit(f"manifest_pine_version:{manifest_path.name}")

            html_path = root / manifest["artifact_path"]
            if not html_path.exists():
                raise SystemExit(f"missing_html:{html_path}")

            html = html_path.read_text(encoding="utf-8")
            soup = BeautifulSoup(html, "html.parser")
            container = (
                soup.select_one("main#tv-content")
                or soup.select_one("main.content")
                or soup.select_one("main.main-pane")
                or soup.select_one("main")
                or soup.body
            )
            if container is None:
                raise SystemExit(f"guide_container_missing:{html_path.name}")

            headings = container.find_all(HEADING_TAGS)
            if not headings:
                raise SystemExit(f"guide_no_headings:{html_path.name}")

            title_stack: list[str] = []
            segment_order = 1
            for heading in headings:
                level = heading.name
                title = heading_text(heading)
                if level == "h1":
                    title_stack = [title]
                elif level == "h2":
                    title_stack = [title_stack[0] if title_stack else "", title]
                else:
                    if not title_stack:
                        title_stack = ["", "", title]
                    elif len(title_stack) == 1:
                        title_stack = [title_stack[0], "", title]
                    else:
                        title_stack = [title_stack[0], title_stack[1], title]

                nodes = [heading]
                for sibling in list(heading.next_siblings):
                    if getattr(sibling, "name", None) in HEADING_TAGS:
                        break
                    nodes.append(sibling)

                raw_html = serialize_nodes(nodes)
                if not raw_html:
                    raise SystemExit(f"empty_raw_html:{html_path.name}:{segment_order}")

                source_artifact_id = manifest["artifact_checksum_sha256"]
                segment_id = f"{manifest['canonical_url']}:{segment_order}"
                if segment_id in segment_ids:
                    raise SystemExit(f"duplicate_segment_id:{segment_id}")
                segment_ids.add(segment_id)

                record = {
                    "segment_id": segment_id,
                    "canonical_url": manifest["canonical_url"],
                    "doc_type": "guide",
                    "pine_version": "v6",
                    "section_title": title,
                    "section_path": build_section_path(title_stack),
                    "segment_order": segment_order,
                    "raw_html": raw_html,
                    "run_id": manifest["run_id"],
                    "source_artifact_id": source_artifact_id,
                }

                out.write(json.dumps(record, sort_keys=True))
                out.write("\n")

                segment_order += 1
                total_segments += 1

    if total_segments <= 10:
        raise SystemExit(f"segment_count_below_threshold:{total_segments}")

    print(f"segments_out={output_path}")
    print(f"segment_count={total_segments}")


if __name__ == "__main__":
    main()
