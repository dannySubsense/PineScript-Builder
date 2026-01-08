from __future__ import annotations

import gzip
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse


EXCLUDED_PATH_SEGMENTS = (
    "/blog/",
    "/support/",
    "/community/",
    "/ideas/",
    "/pricing/",
    "/markets/",
    "/brokers/",
    "/accounts/",
    "/login/",
)

PINE_DOCS_PREFIX = "/pine-script-docs"
PINE_REFERENCE_PREFIX = "/pine-script-reference"
PINE_REFERENCE_V6_PREFIX = "/pine-script-reference/v6"


@dataclass(frozen=True)
class DiscoveredUrl:
    canonical_url: str
    source_entry_point: str
    doc_type: str
    pine_version: str
    discovered_at: str
    discovery_method: str
    segmentation_strategy: str | None = None


@dataclass(frozen=True)
class ExcludedUrl:
    raw_url: str
    resolved_url: str
    source_entry_point: str
    reason: str


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for key, value in attrs:
            if key == "href" and value:
                self.hrefs.append(value)


class ScriptSrcExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.srcs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        for key, value in attrs:
            if key == "src" and value:
                self.srcs.append(value)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_entry_point(url: str) -> str:
    canonical = canonicalize_url(url)
    if canonical is None:
        raise ValueError(f"Entry point not canonicalizable: {url}")
    return canonical


def canonicalize_url(raw_url: str) -> str | None:
    parsed = urlparse(raw_url)
    if not parsed.scheme and not parsed.netloc:
        return None
    scheme = "https"
    netloc = parsed.netloc or "www.tradingview.com"
    if netloc == "tradingview.com":
        netloc = "www.tradingview.com"
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", "", ""))


def resolve_and_canonicalize(raw_href: str, base_url: str) -> str | None:
    if raw_href.startswith("#") or raw_href.startswith("?"):
        return None
    if raw_href.startswith("mailto:") or raw_href.startswith("javascript:"):
        return None
    resolved = urljoin(base_url, raw_href)
    parsed = urlparse(resolved)
    if not parsed.scheme or not parsed.netloc:
        return None
    return canonicalize_url(resolved)


def extract_links(html: str, base_url: str) -> list[str]:
    parser = LinkExtractor()
    parser.feed(html)
    links: list[str] = []
    for href in parser.hrefs:
        canonical = resolve_and_canonicalize(href, base_url)
        if canonical:
            links.append(canonical)
    return links


def is_in_scope(canonical_url: str, entry_prefixes: list[str]) -> bool:
    parsed = urlparse(canonical_url)
    if parsed.netloc != "www.tradingview.com":
        return False
    path = parsed.path
    for prefix in entry_prefixes:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def is_excluded_path(canonical_url: str) -> bool:
    path = urlparse(canonical_url).path.lower()
    return any(segment in path for segment in EXCLUDED_PATH_SEGMENTS)


def detect_doc_type(canonical_url: str) -> str | None:
    path = urlparse(canonical_url).path
    if path.startswith(PINE_DOCS_PREFIX):
        return "guide"
    if path.startswith(PINE_REFERENCE_PREFIX):
        return "reference"
    return None


def detect_pine_version(canonical_url: str) -> str | None:
    path = urlparse(canonical_url).path
    if "/v6/" in path or path.endswith("/v6"):
        return "v6"
    if "/v5/" in path or path.endswith("/v5"):
        return "v5"
    return None


def fetch_bytes(url: str) -> bytes:
    from urllib.request import Request, urlopen

    request = Request(url, headers={"User-Agent": "pine-script-discovery/0.1"})
    with urlopen(request, timeout=20) as response:
        return response.read()


def decode_text(payload: bytes) -> str:
    if payload[:2] == b"\x1f\x8b":
        payload = gzip.decompress(payload)
    return payload.decode("utf-8", errors="replace")


def parse_sitemap_urls(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    urls: list[str] = []
    for elem in root.iter():
        if elem.tag.endswith("loc") and elem.text:
            urls.append(elem.text.strip())
    return urls


def discover_guide_urls(
    sitemap_index_url: str, entry_point: str, discovered_at: str
) -> tuple[list[DiscoveredUrl], list[ExcludedUrl]]:
    sitemap_index_text = decode_text(fetch_bytes(sitemap_index_url))
    sitemap_urls = parse_sitemap_urls(sitemap_index_text)
    discovered: dict[str, DiscoveredUrl] = {}
    excluded: list[ExcludedUrl] = []

    for sitemap_url in sitemap_urls:
        sitemap_text = decode_text(fetch_bytes(sitemap_url))
        loc_urls = parse_sitemap_urls(sitemap_text)
        for raw_url in loc_urls:
            canonical = canonicalize_url(raw_url)
            if not canonical:
                continue
            path = urlparse(canonical).path
            if not path.startswith(PINE_DOCS_PREFIX):
                excluded.append(
                    ExcludedUrl(
                        raw_url=raw_url,
                        resolved_url=canonical,
                        source_entry_point=entry_point,
                        reason="out_of_scope",
                    )
                )
                continue
            if path == PINE_DOCS_PREFIX:
                excluded.append(
                    ExcludedUrl(
                        raw_url=raw_url,
                        resolved_url=canonical,
                        source_entry_point=entry_point,
                        reason="out_of_scope",
                    )
                )
                continue
            if is_excluded_path(canonical):
                excluded.append(
                    ExcludedUrl(
                        raw_url=raw_url,
                        resolved_url=canonical,
                        source_entry_point=entry_point,
                        reason="out_of_scope",
                    )
                )
                continue
            pine_version = detect_pine_version(canonical)
            if pine_version is None:
                excluded.append(
                    ExcludedUrl(
                        raw_url=raw_url,
                        resolved_url=canonical,
                        source_entry_point=entry_point,
                        reason="non_explicit_version",
                    )
                )
                continue
            if pine_version not in {"v5", "v6"}:
                excluded.append(
                    ExcludedUrl(
                        raw_url=raw_url,
                        resolved_url=canonical,
                        source_entry_point=entry_point,
                        reason="out_of_scope",
                    )
                )
                continue
            discovered[canonical] = DiscoveredUrl(
                canonical_url=canonical,
                source_entry_point=entry_point,
                doc_type="guide",
                pine_version=pine_version,
                discovered_at=discovered_at,
                discovery_method="sitemap",
            )

    return sorted(discovered.values(), key=lambda item: item.canonical_url), excluded


def extract_script_sources(html: str, base_url: str) -> list[str]:
    parser = ScriptSrcExtractor()
    parser.feed(html)
    sources: list[str] = []
    for src in parser.srcs:
        resolved = urljoin(base_url, src)
        canonical = canonicalize_url(resolved)
        if canonical:
            sources.append(canonical)
    return sources


def choose_reference_assets(sources: list[str]) -> list[str]:
    scored: list[tuple[int, str]] = []
    for src in sources:
        score = 0
        lower = src.lower()
        if "pine_script_reference" in lower:
            score += 10
        if "reference" in lower:
            score += 5
        if "pine" in lower:
            score += 3
        if score > 0:
            scored.append((score, src))
    if scored:
        top_score = max(score for score, _ in scored)
        return sorted({src for score, src in scored if score == top_score})
    return sorted(set(sources))


def discover_reference_urls(
    entry_point: str, discovered_at: str
) -> tuple[list[DiscoveredUrl], list[ExcludedUrl]]:
    canonical = canonicalize_url(entry_point)
    if not canonical:
        return [], [
            ExcludedUrl(
                raw_url=entry_point,
                resolved_url=entry_point,
                source_entry_point=entry_point,
                reason="out_of_scope",
            )
        ]

    if not urlparse(canonical).path.startswith(PINE_REFERENCE_V6_PREFIX):
        return [], [
            ExcludedUrl(
                raw_url=entry_point,
                resolved_url=canonical,
                source_entry_point=entry_point,
                reason="out_of_scope",
            )
        ]

    return [
        DiscoveredUrl(
            canonical_url=canonical,
            source_entry_point=entry_point,
            doc_type="reference",
            pine_version="v6",
            discovered_at=discovered_at,
            discovery_method="single_page_reference",
            segmentation_strategy="anchor_based",
        )
    ], []


def discover_urls(entry_points: Iterable[str]) -> tuple[list[DiscoveredUrl], list[ExcludedUrl]]:
    normalized_entries = [normalize_entry_point(url) for url in entry_points]
    discovered_at = utc_now_iso()
    discovered: dict[str, DiscoveredUrl] = {}
    excluded: list[ExcludedUrl] = []

    for entry_point in normalized_entries:
        if entry_point.endswith("/pine-script-docs"):
            sitemap_index_url = "https://www.tradingview.com/pine-script-docs/sitemap-index.xml"
            guides, guide_excluded = discover_guide_urls(
                sitemap_index_url, entry_point, discovered_at
            )
            for item in guides:
                discovered[item.canonical_url] = item
            excluded.extend(guide_excluded)
            continue

        if entry_point.endswith("/pine-script-reference/v6"):
            refs, ref_excluded = discover_reference_urls(entry_point, discovered_at)
            for item in refs:
                discovered[item.canonical_url] = item
            excluded.extend(ref_excluded)
            continue

        excluded.append(
            ExcludedUrl(
                raw_url=entry_point,
                resolved_url=entry_point,
                source_entry_point=entry_point,
                reason="out_of_scope",
            )
        )

    return sorted(discovered.values(), key=lambda item: item.canonical_url), sorted(
        excluded, key=lambda item: item.resolved_url
    )


def write_inventory(path: str, items: list[DiscoveredUrl]) -> None:
    payload = [item.__dict__ for item in items]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_excluded(path: str, items: list[ExcludedUrl]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item.__dict__, sort_keys=True))
            handle.write("\n")
