"""Per-IPO enrichment from IPOWatch's own IPO pages.

Two extra reads per published IPO, both on ipowatch.in (same source as the
rest of the report, rule 5.9):

  * the IPO's GMP page  -> a day-by-day GMP history table. We compute the GMP
    trend ourselves from the rupee figures; IPOWatch's trend emoji and its
    "gain" column are never read.
  * the IPO's detail page -> retail minimum lot and amount, basis-of-allotment
    date and listing date.

Everything here is best-effort and fails soft: an unreadable page leaves the
field empty and adds a plain note to the report. It can never abort a run and
never invents a number (rule 5.3). Each page is checked to be about the right
company before anything is taken from it.
"""
from __future__ import annotations

import glob
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from typing import Callable, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .config import BASE_URL
from .merge import Dataset, norm_key
from .models import IPO, Trend, parse_date, to_decimal

SERIES_POINTS = 7          # sparkline length, including today's published GMP

Fetcher = Callable[[str], Optional[str]]   # url -> html, or None when unreadable


def _norm_label(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", s.lower()).strip()


def _tables(html: str) -> list[list[list[str]]]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for t in soup.find_all("table"):
        out.append([[c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
                    for tr in t.find_all("tr")])
    return out


def page_is_about(html: str, name: str) -> bool:
    """True when the page's own heading names this IPO (guards against a
    wrong link ever feeding another company's numbers into this one)."""
    soup = BeautifulSoup(html, "lxml")
    head = soup.h1.get_text(" ", strip=True) if soup.h1 else (
        soup.title.get_text(" ", strip=True) if soup.title else "")
    key = norm_key(name)
    return bool(key) and key in norm_key(head)


# ---------------------------------------------------------------- GMP history

def load_local_history(directory: str, today: date) -> dict[str, list[tuple[date, Optional[Decimal]]]]:
    """Our own earlier reports: {name key: [(run date, GMP)]}, oldest first.

    Fallback for the trend when IPOWatch's history page cannot be read. These
    are figures we already published, so using them is exact, never a guess.
    """
    out: dict[str, list[tuple[date, Optional[Decimal]]]] = {}
    for path in sorted(glob.glob(os.path.join(directory or ".", "ipo-watch-*-dataset.json"))):
        try:
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            continue
        d = parse_date(raw.get("run_date"))
        if d is None or d >= today:
            continue
        for group in ("open", "upcoming"):
            for it in raw.get(group) or []:
                key = norm_key(it.get("name", ""))
                g = it.get("gmp")
                if key:
                    out.setdefault(key, []).append((d, Decimal(g) if g is not None else None))
    return out


def parse_gmp_history(html: str, today: date) -> Optional[list[tuple[date, Optional[Decimal]]]]:
    """Rows of (date, GMP rupees or None) from the per-IPO GMP page.

    None means no history table was found at all. A row whose GMP cell is
    blank or a dash yields (date, None).
    """
    for rows in _tables(html):
        if not rows:
            continue
        head = [_norm_label(c) for c in rows[0]]
        if "date" not in head or not any(h.startswith("ipo gmp") or h == "gmp" for h in head):
            continue
        di = head.index("date")
        gi = next(i for i, h in enumerate(head) if h.startswith("ipo gmp") or h == "gmp")
        out: list[tuple[date, Optional[Decimal]]] = []
        for r in rows[1:]:
            if len(r) <= max(di, gi):
                continue
            d = parse_date(r[di], today.year)
            if d is None:
                continue
            if (d - today).days > 1:          # '28 December' read in January
                d = date(d.year - 1, d.month, d.day)
            out.append((d, to_decimal(r[gi])))
        return out
    return None


def compute_trend(history: Optional[list[tuple[date, Optional[Decimal]]]],
                  today: date, gmp_today: Optional[Decimal]) -> Trend:
    """Published GMP versus the latest earlier day that has a number."""
    if history is None or gmp_today is None:
        return Trend(status="unavailable")
    prior = sorted(((d, g) for d, g in history if d < today and g is not None),
                   key=lambda t: t[0])
    if not prior:
        return Trend(status="new")
    prev_d, prev_g = prior[-1]
    series = [g for _, g in prior[-(SERIES_POINTS - 1):]] + [gmp_today]
    return Trend(status="ok", prev_date=prev_d, prev_gmp=prev_g,
                 change=gmp_today - prev_g, series=series)


# --------------------------------------------------------------- detail facts

def parse_detail_facts(html: str, price_max: Optional[Decimal]) -> dict:
    """Retail minimum lot/amount and the allotment + listing dates."""
    facts: dict = {"lot_shares": None, "min_invest": None,
                   "allotment_date": None, "listing_date": None}
    for rows in _tables(html):
        if not rows:
            continue
        head = [_norm_label(c) for c in rows[0]]
        if head[:4] == ["application", "lot size", "shares", "amount"]:
            for r in rows[1:]:
                if len(r) >= 4 and "retail" in r[0].lower() and "min" in r[0].lower():
                    shares = to_decimal(r[2])
                    amount = to_decimal(r[3])
                    if shares is not None and shares == shares.to_integral_value():
                        facts["lot_shares"] = int(shares)
                    # Present-but-unusable rule: the amount must equal shares x
                    # cap price, otherwise it is not shown.
                    if (shares is not None and amount is not None and price_max
                            and shares * price_max == amount):
                        facts["min_invest"] = amount
            continue
        for r in rows:
            if len(r) < 2:
                continue
            label = _norm_label(r[0])
            if label in ("basis of allotment", "allotment date") and not facts["allotment_date"]:
                facts["allotment_date"] = parse_date(r[1])
            elif label in ("ipo listing date", "listing date") and not facts["listing_date"]:
                facts["listing_date"] = parse_date(r[1])
    return facts


_DETAIL_HREF = re.compile(r"^/?[a-z0-9-]+-ipo/?$")


def find_detail_url(gmp_page_html: str, name: str, gmp_url: str) -> str:
    """The IPO's detail page, from a link on its GMP page naming the company."""
    soup = BeautifulSoup(gmp_page_html, "lxml")
    key = norm_key(name)
    for a in soup.find_all("a", href=True):
        u = urlparse(a["href"])
        if u.netloc not in ("", "ipowatch.in", "www.ipowatch.in"):
            continue
        if _DETAIL_HREF.match(u.path) and norm_key(a.get_text(" ", strip=True)) == key:
            return f"{BASE_URL}/{u.path.strip('/')}/"
    # The page's own "IPO Details" button: the company's real detail page, even
    # when its slug differs from the GMP page's (Tonbo: tonbo-imaging-india-ipo).
    for a in soup.find_all("a", href=True):
        u = urlparse(a["href"])
        if (u.netloc in ("", "ipowatch.in", "www.ipowatch.in") and _DETAIL_HREF.match(u.path)
                and a.get_text(" ", strip=True).lower() == "ipo details"):
            return f"{BASE_URL}/{u.path.strip('/')}/"
    slug = urlparse(gmp_url).path.strip("/")
    derived = re.sub(r"-ipo-gmp.*$", "-ipo", slug)
    return f"{BASE_URL}/{derived}/" if derived.endswith("-ipo") else ""


# ----------------------------------------------------------------- orchestration

def enrich_ipo(ipo: IPO, today: date, get: Fetcher,
               local: Optional[list[tuple[date, Optional[Decimal]]]] = None) -> dict:
    """Fill trend and key facts on one IPO. Returns what went wrong, if anything."""
    problems = {"trend": False, "detail": False}
    gmp_html = get(ipo.gmp_url) if ipo.gmp_url else None
    history = None
    if gmp_html and page_is_about(gmp_html, ipo.name):
        history = parse_gmp_history(gmp_html, today)
    if history is None and local:
        history = local            # IPOWatch page unreadable: use our own record
    ipo.trend = compute_trend(history, today, ipo.gmp)
    if ipo.trend.status == "unavailable":
        problems["trend"] = True

    detail_url = find_detail_url(gmp_html, ipo.name, ipo.gmp_url) if gmp_html else ""
    detail_html = get(detail_url) if detail_url else None
    if detail_html and page_is_about(detail_html, ipo.name):
        f = parse_detail_facts(detail_html, ipo.price_max)
        ipo.lot_shares, ipo.min_invest = f["lot_shares"], f["min_invest"]
        ipo.allotment_date, ipo.listing_date = f["allotment_date"], f["listing_date"]
    else:
        problems["detail"] = True
    return problems


def enrich_dataset(ds: Dataset, today: date, get: Fetcher, workers: int = 1,
                   history_dir: Optional[str] = None,
                   only: Optional[Callable[[IPO], bool]] = None) -> None:
    """Enrich every published IPO that has its own page link (or just those
    `only` selects, e.g. the IPOs closing today for the midday update)."""
    local = load_local_history(history_dir, today) if history_dir else {}
    pool_ = [i for i in ds.published if only is None or only(i)]
    ipos = [i for i in pool_ if i.gmp_url]
    for i in pool_:
        if not i.gmp_url:
            i.trend = compute_trend(local.get(norm_key(i.name)), today, i.gmp)
    if not ipos:
        return
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(
            lambda i: enrich_ipo(i, today, get, local.get(norm_key(i.name))), ipos))
    no_trend = [i.name for i, p in zip(ipos, results) if p["trend"]]
    no_detail = [i.name for i, p in zip(ipos, results) if p["detail"]]
    if no_trend:
        ds.warnings.append("GMP trend not updated for: " + ", ".join(no_trend)
                           + " (IPOWatch page could not be read)")
    if no_detail:
        ds.warnings.append("Lot size and key dates not updated for: " + ", ".join(no_detail)
                           + " (IPOWatch page could not be read)")
