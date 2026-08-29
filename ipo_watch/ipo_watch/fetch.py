"""Rendered-page fetching for IPOWatch (rule 5.2: read the rendered DOM).

Uses a real Chromium via Playwright rather than plain HTTP, because IPOWatch
fills its subscription table client-side. Every fetch snapshots the raw HTML
next to the report so any published number can be traced back to the exact
bytes it came from.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .config import (CHROMIUM_PATH, IST, PAGE_TIMEOUT_MS, SETTLE_MS, USER_AGENT)


class FetchError(RuntimeError):
    """Raised when a page could not be rendered. Never falls back to a guess."""


@dataclass
class Page:
    url: str
    html: str
    fetched_at: datetime
    # "live" when rendered from the network, "fixture" when replayed from disk.
    mode: str = "live"

    @property
    def fetched_at_ist(self) -> str:
        return self.fetched_at.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")


def fetch_pages(urls: list[str], snapshot_dir: Optional[str] = None) -> dict[str, Page]:
    """Render each URL in one browser session and return its final DOM HTML."""
    from playwright.sync_api import sync_playwright

    pages: dict[str, Page] = {}
    launch_args = ["--no-sandbox", "--disable-dev-shm-usage"]
    kwargs = {"args": launch_args}
    if CHROMIUM_PATH and os.path.exists(CHROMIUM_PATH):
        kwargs["executable_path"] = CHROMIUM_PATH

    with sync_playwright() as p:
        browser = p.chromium.launch(**kwargs)
        ctx = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 2000},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        try:
            for url in urls:
                page = ctx.new_page()
                try:
                    page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
                    try:
                        page.wait_for_load_state("networkidle", timeout=SETTLE_MS * 2)
                    except Exception:
                        pass  # networkidle is best-effort; the DOM is what matters
                    try:
                        page.wait_for_selector("table", timeout=SETTLE_MS)
                    except Exception:
                        pass
                    page.wait_for_timeout(SETTLE_MS)
                    html = page.content()
                except Exception as exc:  # noqa: BLE001
                    raise FetchError(f"Could not render {url}: {exc}") from exc
                finally:
                    page.close()

                pg = Page(url=url, html=html, fetched_at=datetime.now(IST))
                pages[url] = pg
                if snapshot_dir:
                    _snapshot(pg, snapshot_dir)
        finally:
            browser.close()
    return pages


def load_fixture(url: str, path: str) -> Page:
    """Replay a saved page. Used by tests and by --fixture dry runs."""
    with open(path, "r", encoding="utf-8") as fh:
        html = fh.read()
    return Page(url=url, html=html, fetched_at=datetime.now(IST), mode="fixture")


def _snapshot(page: Page, snapshot_dir: str) -> None:
    os.makedirs(snapshot_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", page.url.lower()).strip("-")[:80]
    stamp = page.fetched_at.strftime("%Y%m%d-%H%M%S")
    with open(os.path.join(snapshot_dir, f"{stamp}-{slug}.html"), "w", encoding="utf-8") as fh:
        fh.write(page.html)


# ---- page-level "last updated" stamp (rule 5.5: sub and GMP stamps differ) ----

# A timestamp token: "29 Aug 2026, 07:45 PM" / "29 August 2026 19:45" / "29 Aug 2026".
_STAMP_TOKEN = (
    r"\d{1,2}\s+[A-Za-z]{3,9},?\s+\d{4}"
    r"(?:\s*(?:,|at|-)?\s*\d{1,2}[:.]\d{2}\s*(?:[AaPp]\.?[Mm]\.?)?)?"
)
# Only trust a timestamp that sits next to an explicit "updated"/"as on" label,
# otherwise fall back to any timestamp-shaped token on the page.
_LABELLED = re.compile(
    r"(?:last\s+updated|updated\s+on|updated\s+at|updated|as\s+on|as\s+of)\s*"
    r"[:\-]?\s*(" + _STAMP_TOKEN + r")", re.I)
_BARE = re.compile("(" + _STAMP_TOKEN + r"\s*(?:[AaPp]\.?[Mm]\.?))", re.I)


def extract_page_timestamp(html: str) -> Optional[str]:
    """Best-effort scrape of IPOWatch's own update stamp. None if absent.

    Matches only a date/time-shaped token so neighbouring table text can never
    bleed into the stamp that gets printed on the report and the creative.
    """
    text = re.sub(r"<(?:script|style)[^>]*>.*?</(?:script|style)>", " ", html,
                  flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;?", " ", text)
    text = re.sub(r"\s+", " ", text)
    for pat in (_LABELLED, _BARE):
        m = pat.search(text)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip(" :-,.")
    return None
