from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


URL = "https://www.tradingview.com/pine-script-reference/v6/"
OUTPUT_PATH = Path("raw/rendered/v6/reference/manual_baseline/reference.html")


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="UTC",
            user_agent="PineScript-Builder CI renderer/0.1",
        )
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(2000)
        for _ in range(5):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            page.wait_for_timeout(1500)
        html = page.content()
        browser.close()

    OUTPUT_PATH.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
