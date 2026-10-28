"""Listing-day scorecard: what the IPO actually did against what GMP said.

Source: NSE's own public files (the official record), not a grey-market site.
  * EQUITY_L.csv  - every NSE equity with its DATE OF LISTING; used to find the
                    exchange symbol of an IPO we reported on.
  * sec_bhavdata_full_<ddmmyyyy>.csv - the day's prices. On a listing day the
                    PREV_CLOSE column is the exchange base price, i.e. the
                    issue price; OPEN_PRICE and CLOSE_PRICE are the first-day
                    open and close.

Candidates are the IPOs we ourselves reported (our saved daily datasets), so a
demerger or re-listing that happens to share a date can never be mistaken for
an IPO. Matching is by company name inside a date window after the IPO closed;
anything ambiguous is skipped, never guessed (rule 5.3). The last GMP shown is
read back from our own published reports, so the comparison is exact.
"""
from __future__ import annotations

import csv
import glob
import gzip
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Optional

from .merge import norm_key
from .models import _num, parse_date

EQUITY_LIST_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
BHAV_URL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d}.csv"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

LISTING_WINDOW_DAYS = 14      # how long after closing an IPO may list
LOOKBACK_DAYS = 30            # how far back our own reports are searched
PRICE_SANITY = Decimal("0.15")  # exchange issue price vs IPOWatch cap price
Q2 = Decimal("0.01")


def _pct(num: Decimal, den: Decimal) -> Optional[Decimal]:
    if den is None or den == 0 or num is None:
        return None
    return (num / den * Decimal(100)).quantize(Q2, rounding=ROUND_HALF_UP)


def _signed(p: Optional[Decimal], places: int = 2) -> str:
    if p is None:
        return "Not updated"
    return f"{p:+.{places}f}%" if p != 0 else f"{0:.{places}f}%"


def _price(v: Optional[Decimal]) -> str:
    """₹80 for whole rupees, ₹146.30 otherwise (exchange prices have paise)."""
    if v is None:
        return "Not updated"
    return f"₹{_num(v)}" if v == v.to_integral_value() else f"₹{v.quantize(Q2, rounding=ROUND_HALF_UP):,.2f}"


@dataclass
class Candidate:
    """An IPO we reported on, as recorded in our own saved datasets."""
    name: str
    close_date: date
    cap_price: Optional[Decimal] = None
    last_gmp: Optional[Decimal] = None
    last_gmp_pct: Optional[Decimal] = None
    last_gmp_date: Optional[date] = None
    listing_date: Optional[date] = None     # what IPOWatch told us when we reported it


@dataclass
class ListingResult:
    name: str
    symbol: str
    series: str
    listing_date: date
    issue_price: Decimal                      # NSE base price on listing day
    open_price: Optional[Decimal]
    close_price: Optional[Decimal]
    cap_price: Optional[Decimal] = None       # IPOWatch cap price, for the cross-check
    last_gmp: Optional[Decimal] = None
    last_gmp_pct: Optional[Decimal] = None
    last_gmp_date: Optional[date] = None
    notes: list[str] = field(default_factory=list)

    # ---- derived, computed here and nowhere else ----
    @property
    def listing_gain_pct(self) -> Optional[Decimal]:        # issue -> first-day open
        return _pct(self.open_price - self.issue_price, self.issue_price) if self.open_price else None

    @property
    def day1_pct(self) -> Optional[Decimal]:                # first-day open -> close
        return _pct(self.close_price - self.open_price, self.open_price) \
            if self.open_price and self.close_price else None

    @property
    def close_vs_issue_pct(self) -> Optional[Decimal]:
        return _pct(self.close_price - self.issue_price, self.issue_price) if self.close_price else None

    @property
    def gap_pts(self) -> Optional[Decimal]:
        """Actual listing gain minus the GMP % we last published, in points."""
        if self.listing_gain_pct is None or self.last_gmp_pct is None:
            return None
        return (self.listing_gain_pct - self.last_gmp_pct).quantize(Q2, rounding=ROUND_HALF_UP)

    # ---- display strings (shared by text, image and verification) ----
    @property
    def issue_text(self) -> str: return _price(self.issue_price)
    @property
    def open_text(self) -> str: return _price(self.open_price)
    @property
    def close_text(self) -> str: return _price(self.close_price)
    @property
    def listing_gain_text(self) -> str: return _signed(self.listing_gain_pct)
    @property
    def day1_text(self) -> str: return _signed(self.day1_pct)
    @property
    def close_vs_issue_text(self) -> str: return _signed(self.close_vs_issue_pct)

    @property
    def gmp_said_text(self) -> Optional[str]:
        """'₹20 (9.09%)' - what we last published; None when we never had a GMP."""
        if self.last_gmp is None or self.last_gmp_pct is None:
            return None
        return f"₹{_num(self.last_gmp)} ({self.last_gmp_pct:.2f}%)"

    @property
    def gmp_said_pct_text(self) -> Optional[str]:
        """'4.00%' - the GMP % we last published, for the slim image row."""
        return None if self.last_gmp_pct is None else f"{self.last_gmp_pct:.2f}%"

    @property
    def gap_text(self) -> Optional[str]:
        g = self.gap_pts
        return None if g is None else (f"{g:+.2f} pts" if g != 0 else "0.00 pts")

    # ---- persistence (one small file per listing, in the history folder) ----
    def to_dict(self) -> dict:
        s = lambda v: str(v) if v is not None else None  # noqa: E731
        return {"name": self.name, "symbol": self.symbol, "series": self.series,
                "listing_date": self.listing_date.isoformat(),
                "issue_price": s(self.issue_price), "open_price": s(self.open_price),
                "close_price": s(self.close_price), "cap_price": s(self.cap_price),
                "last_gmp": s(self.last_gmp), "last_gmp_pct": s(self.last_gmp_pct),
                "last_gmp_date": self.last_gmp_date.isoformat() if self.last_gmp_date else None,
                "notes": self.notes}

    @classmethod
    def from_dict(cls, d: dict) -> "ListingResult":
        dec = lambda k: Decimal(d[k]) if d.get(k) is not None else None  # noqa: E731
        return cls(name=d["name"], symbol=d["symbol"], series=d.get("series", ""),
                   listing_date=parse_date(d["listing_date"]), issue_price=dec("issue_price"),
                   open_price=dec("open_price"), close_price=dec("close_price"),
                   cap_price=dec("cap_price"), last_gmp=dec("last_gmp"),
                   last_gmp_pct=dec("last_gmp_pct"),
                   last_gmp_date=parse_date(d.get("last_gmp_date")),
                   notes=list(d.get("notes") or []))


# ------------------------------------------------------------------ parsing

def _dec(s: Optional[str]) -> Optional[Decimal]:
    s = (s or "").strip().replace(",", "")
    if not s or s == "-":
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def parse_equity_list(text: str) -> list[dict]:
    """[{symbol, name, series, listing_date}] from NSE's EQUITY_L.csv."""
    out = []
    for r in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
        d = None
        try:
            d = datetime.strptime(r.get("DATE OF LISTING", ""), "%d-%b-%Y").date()
        except ValueError:
            pass
        if r.get("SYMBOL") and r.get("NAME OF COMPANY") and d:
            out.append({"symbol": r["SYMBOL"], "name": r["NAME OF COMPANY"],
                        "series": r.get("SERIES", ""), "listing_date": d})
    return out


def parse_bhav(text: str) -> dict[str, dict]:
    """{symbol: {series, prev_close, open, close}} from sec_bhavdata_full."""
    out = {}
    for r in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
        sym = r.get("SYMBOL")
        if sym:
            out[sym] = {"series": r.get("SERIES", ""), "prev_close": _dec(r.get("PREV_CLOSE")),
                        "open": _dec(r.get("OPEN_PRICE")), "close": _dec(r.get("CLOSE_PRICE"))}
    return out


# --------------------------------------------------- our own saved reports

def load_candidates(directory: str, today: date,
                    lookback_days: int = LOOKBACK_DAYS) -> list[Candidate]:
    """IPOs we reported on that have closed, newest information per IPO."""
    seen: dict[str, Candidate] = {}
    gmp_seen: dict[str, tuple[date, Decimal, Optional[Decimal]]] = {}
    files = sorted(glob.glob(os.path.join(directory or ".", "ipo-watch-*-dataset.json")))
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            continue
        run = parse_date(raw.get("run_date"))
        if run is None or run > today or (today - run).days > lookback_days:
            continue
        for group in ("open", "upcoming", "recently_closed_internal"):
            for it in raw.get(group) or []:
                key = norm_key(it.get("name", ""))
                close = parse_date(it.get("close_date"))
                if not key or close is None:
                    continue
                c = seen.setdefault(key, Candidate(name=it["name"], close_date=close))
                c.name, c.close_date = it["name"], close
                if it.get("price_max") is not None:
                    c.cap_price = Decimal(it["price_max"])
                if it.get("listing_date"):
                    c.listing_date = parse_date(it["listing_date"])
                if it.get("gmp") is not None and group in ("open", "upcoming"):
                    pct = Decimal(it["gmp_pct"]) if it.get("gmp_pct") is not None else None
                    gmp_seen[key] = (run, Decimal(it["gmp"]), pct)
    for key, c in seen.items():
        if key in gmp_seen:
            c.last_gmp_date, c.last_gmp, c.last_gmp_pct = gmp_seen[key]
    return [c for c in seen.values() if c.close_date <= today]


# ------------------------------------------------------------------ matching

def match_symbol(c: Candidate, equities: list[dict]) -> Optional[dict]:
    """The NSE row for this IPO, or None. Exact normalised-name match first;
    otherwise a name that merely *starts with* ours, and only if exactly one
    such listing falls in the window - never a guess between several."""
    lo, hi = c.close_date, c.close_date + timedelta(days=LISTING_WINDOW_DAYS)
    pool = [e for e in equities if lo <= e["listing_date"] <= hi]
    key = norm_key(c.name)
    exact = [e for e in pool if norm_key(e["name"]) == key]
    if len(exact) == 1:
        return exact[0]
    if exact:
        return None
    prefix = [e for e in pool if key and norm_key(e["name"]).startswith(key)]
    return prefix[0] if len(prefix) == 1 else None


def build_result(c: Candidate, eq: dict, bhav: Optional[dict]) -> Optional[ListingResult]:
    """Combine the NSE listing-day row with our own record. None if the day's
    prices are not available yet."""
    row = (bhav or {}).get(eq["symbol"])
    if not row or row["prev_close"] is None:
        return None
    r = ListingResult(name=c.name, symbol=eq["symbol"], series=eq["series"],
                      listing_date=eq["listing_date"], issue_price=row["prev_close"],
                      open_price=row["open"], close_price=row["close"], cap_price=c.cap_price,
                      last_gmp=c.last_gmp, last_gmp_pct=c.last_gmp_pct, last_gmp_date=c.last_gmp_date)
    if c.cap_price:
        diff = abs(r.issue_price - c.cap_price) / c.cap_price
        if diff > PRICE_SANITY:
            return None            # too far from the IPO's price band: not this IPO
        if r.issue_price != c.cap_price:
            r.notes.append(f"{c.name}: exchange issue price ₹{_num(r.issue_price)} differs from "
                           f"IPOWatch's cap price ₹{_num(c.cap_price)} (exchange figure used)")
    return r


def _gmp_rank(r: ListingResult) -> tuple:
    return (r.last_gmp_pct is not None, r.last_gmp is not None, r.last_gmp_date or date.min)


def find_results(candidates: list[Candidate], equities: list[dict],
                 bhav_for: Callable[[date], Optional[dict]]) -> list[ListingResult]:
    by_symbol: dict[str, ListingResult] = {}
    for c in candidates:
        eq = match_symbol(c, equities)
        if eq is None:
            continue
        res = build_result(c, eq, bhav_for(eq["listing_date"]))
        if not res:
            continue
        # The same company can appear under two spellings in our records
        # (IPOWatch renamed one on 28 Sep); keep the one with the most usable GMP:
        # a GMP % first (the gap needs it), then any GMP, then the most recent.
        old = by_symbol.get(res.symbol)
        if old is None or _gmp_rank(res) > _gmp_rank(old):
            by_symbol[res.symbol] = res
    return sorted(by_symbol.values(), key=lambda r: (r.listing_date, r.name))


# ----------------------------------------------------------------- network

def get_text(url: str, timeout: float = 30, attempts: int = 3) -> Optional[str]:
    """GET a text file, None on 404 or after repeated failure. Never raises."""
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if (resp.headers.get("Content-Encoding") or "").lower() == "gzip":
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
        except Exception:  # noqa: BLE001
            pass
        if attempt < attempts:
            time.sleep(3 * attempt)
    return None


def fetch_equities(getter: Callable[[str], Optional[str]] = get_text) -> list[dict]:
    text = getter(EQUITY_LIST_URL)
    return parse_equity_list(text) if text else []


def make_bhav_getter(getter: Callable[[str], Optional[str]] = get_text):
    cache: dict[date, Optional[dict]] = {}

    def bhav_for(d: date) -> Optional[dict]:
        if d not in cache:
            text = getter(BHAV_URL.format(d=d.strftime("%d%m%Y")))
            cache[d] = parse_bhav(text) if text else None
        return cache[d]
    return bhav_for


# -------------------------------------------------- stored results (history)

def result_path(directory: str, r: ListingResult) -> str:
    return os.path.join(directory, f"ipo-watch-listing-{r.symbol}.json")


def save_result(directory: str, r: ListingResult) -> str:
    os.makedirs(directory, exist_ok=True)
    path = result_path(directory, r)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(r.to_dict(), fh, indent=2, ensure_ascii=False)
    return path


def load_recent_results(directory: str, today: date, days: int = 3) -> list[ListingResult]:
    """Stored listing results from the last few days (for the daily report)."""
    out = []
    for path in glob.glob(os.path.join(directory or ".", "ipo-watch-listing-*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                r = ListingResult.from_dict(json.load(fh))
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if r.listing_date and 0 <= (today - r.listing_date).days <= days:
            out.append(r)
    return sorted(out, key=lambda r: (r.listing_date, r.name), reverse=True)


def nse_listing_date(name: str, close_date: Optional[date], equities: list[dict]) -> Optional[date]:
    """The listing date NSE itself shows for this IPO (exact or unique-prefix name
    match inside 14 days of the close), else None. NSE's list already carries
    upcoming listings, so this can overrule a third-party date."""
    if not close_date or not equities:
        return None
    eq = match_symbol(Candidate(name=name, close_date=close_date), equities)
    return eq["listing_date"] if eq else None


# ------------------------------------------------------- GMP track record

RECORD_LISTINGS = 25         # the track record looks at the most recent listings
RECORD_CLOSE_PTS = Decimal("10")   # "close call": listing within this many points of the GMP
RECORD_MIN_LISTINGS = 5      # nothing is said until this many listings are on record
RECORD_MIN_WITH_GMP = 5      # the GMP-miss figure needs this many with a GMP on record


def load_all_results(directory: str, today: Optional[date] = None) -> list[ListingResult]:
    """Every stored listing result (newest first)."""
    out = []
    for path in glob.glob(os.path.join(directory or ".", "ipo-watch-listing-*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                r = ListingResult.from_dict(json.load(fh))
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if r.listing_date and (today is None or r.listing_date <= today):
            out.append(r)
    return sorted(out, key=lambda r: (r.listing_date, r.name), reverse=True)


@dataclass
class TrackRecord:
    """Averages over the most recent listings. Display strings live here so the
    text report, the image and the image check all use the same words."""
    n: int                              # listings in the window
    avg_gain: Decimal                   # average listing gain (issue -> open), %
    up: int                             # opened above the issue price
    avg_day1: Optional[Decimal]         # average first-day open -> close, %
    n_gmp: int                          # listings where we had published a GMP
    avg_miss: Optional[Decimal]         # average |listing gain - GMP %|, points
    over: int                           # GMP was higher than the real gain
    close: int = 0                      # listed within RECORD_CLOSE_PTS points of the GMP

    @property
    def title(self) -> str:
        return f"GMP track record · last {self.n} listings"

    @property
    def gain_text(self) -> str: return _signed(self.avg_gain, 1)
    @property
    def up_text(self) -> str: return f"{self.up} of {self.n}"
    @property
    def day1_text(self) -> Optional[str]:
        return None if self.avg_day1 is None else _signed(self.avg_day1, 1)
    @property
    def acc_text(self) -> Optional[str]:
        """'4 of 10': listings that landed within 10 points of the GMP."""
        return None if self.avg_miss is None else f"{self.close} of {self.n_gmp}"
    @property
    def acc_note(self) -> Optional[str]:
        return None if self.avg_miss is None else f"within {RECORD_CLOSE_PTS} pts of GMP"
    @property
    def miss_text(self) -> Optional[str]:
        return None if self.avg_miss is None else f"{self.avg_miss} pts"

    def to_dict(self) -> dict:
        s = lambda v: str(v) if v is not None else None  # noqa: E731
        return {"n": self.n, "avg_gain": s(self.avg_gain), "up": self.up,
                "avg_day1": s(self.avg_day1), "n_gmp": self.n_gmp,
                "avg_miss": s(self.avg_miss), "over": self.over, "close": self.close}

    @classmethod
    def from_dict(cls, d: dict) -> "TrackRecord":
        dec = lambda k: Decimal(d[k]) if d.get(k) is not None else None  # noqa: E731
        return cls(n=d["n"], avg_gain=dec("avg_gain"), up=d["up"], avg_day1=dec("avg_day1"),
                   n_gmp=d["n_gmp"], avg_miss=dec("avg_miss"), over=d["over"], close=d.get("close", 0))


def track_record(results: list, limit: int = RECORD_LISTINGS) -> Optional[TrackRecord]:
    """Average performance of the most recent `limit` listings, and how far GMP
    was from reality where we had published one. None until there are enough
    (fails closed, never a guess). Gap = listing gain minus GMP %, so a
    negative gap means GMP was higher than what happened."""
    recent = [r for r in sorted(results, key=lambda r: (r.listing_date, r.name), reverse=True)
              if r.listing_gain_pct is not None][:limit]
    if len(recent) < RECORD_MIN_LISTINGS:
        return None
    q1 = Decimal("0.1")
    avg = lambda xs: (sum(xs) / len(xs)).quantize(q1, rounding=ROUND_HALF_UP)  # noqa: E731
    day1 = [r.day1_pct for r in recent if r.day1_pct is not None]
    gap = [r.gap_pts for r in recent if r.gap_pts is not None]
    return TrackRecord(
        n=len(recent), avg_gain=avg([r.listing_gain_pct for r in recent]),
        up=sum(1 for r in recent if r.listing_gain_pct > 0),
        avg_day1=avg(day1) if day1 else None, n_gmp=len(gap),
        avg_miss=avg([abs(g) for g in gap]) if len(gap) >= RECORD_MIN_WITH_GMP else None,
        over=sum(1 for g in gap if g < 0),
        close=sum(1 for g in gap if abs(g) <= RECORD_CLOSE_PTS))


def backfill_results(directory: str, today: date, equities: list[dict],
                     bhav_for: Callable[[date], Optional[dict]]) -> list[ListingResult]:
    """Save a result for every past listing of an IPO we reported (no message
    is sent). Existing files are left alone. Returns the ones newly saved."""
    candidates = load_candidates(directory, today, lookback_days=10_000)
    found = [r for r in find_results(candidates, equities, bhav_for) if r.listing_date <= today]
    new = []
    for r in found:
        if not os.path.exists(result_path(directory, r)):
            save_result(directory, r)
            new.append(r)
    return new


def backfill_older(directory: str, today: date, equities: list[dict],
                   bhav_for: Callable[[date], Optional[dict]], sub_rows: list,
                   want: int = RECORD_LISTINGS) -> list[ListingResult]:
    """Top the record up to `want` listings using Mainboard IPOs that IPOWatch's
    subscription page still lists but that closed before our own reports began.
    Prices come from NSE; there is no GMP on record for these (we never
    published one), so they count towards the averages but not the GMP-miss
    figure. Matching is the same exact-or-unique-prefix rule as everywhere."""
    have = {r.symbol for r in load_all_results(directory, today)}
    if len(have) >= want:
        return []
    from .models import Board
    cands = [Candidate(name=r.name, close_date=r.close_date)
             for r in sub_rows
             if r.board == Board.MAINBOARD and r.close_date and r.close_date < today]
    cands.sort(key=lambda c: c.close_date, reverse=True)
    new = []
    for res in find_results(cands, equities, bhav_for):
        if res.symbol in have or res.listing_date > today:
            continue
        new.append(res)
    new.sort(key=lambda r: (r.listing_date, r.name), reverse=True)
    out = []
    for r in new[: max(0, want - len(have))]:
        if not os.path.exists(result_path(directory, r)):
            save_result(directory, r)
            out.append(r)
    return out


IMAGE_LISTING_DAYS = 2       # the daily image shows listings from the last two days
IMAGE_LISTING_MAX = 3        # and at most this many rows (the text shows all of the last 3 days)


def strip_listings(recent: list, run_date: Optional[date]) -> list:
    """Which recent listings get a row in the daily image (newest first)."""
    if not recent or run_date is None:
        return []
    rows = [r for r in recent if 0 <= (run_date - r.listing_date).days <= IMAGE_LISTING_DAYS]
    rows.sort(key=lambda r: (r.listing_date, r.name), reverse=True)
    return rows[:IMAGE_LISTING_MAX]
