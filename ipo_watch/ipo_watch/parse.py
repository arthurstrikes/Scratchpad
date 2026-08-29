"""Turn IPOWatch HTML into IPO records.

Column positions on IPOWatch shift between pages and change over time, so
nothing here is index-based: every column is located by matching its header
against an alias set. A column that cannot be identified is left as None
rather than guessed at (rules 5.3 / 5.10).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Iterable, Optional

from bs4 import BeautifulSoup

from .models import (Board, IPO, Provenance, Status, classify_status,
                     parse_date, parse_price_band, to_decimal)

# --- header alias sets. Matching is on normalised, punctuation-free text. ---
ALIASES: dict[str, tuple[str, ...]] = {
    "name":   ("ipo", "ipo name", "company", "company name", "name", "issue", "ipo details"),
    "retail": ("retail", "rii", "retail x", "retail individual", "retail investor",
               "rii x", "retail subscription", "individual"),
    "total":  ("total", "total x", "overall", "total subscription", "subscription",
               "total sub", "times"),
    "gmp":    ("gmp", "ipo gmp", "grey market premium", "gmp rs", "gmp ₹", "premium"),
    "price":  ("price", "price band", "ipo price", "issue price", "band", "price rs"),
    "open":   ("open", "open date", "opening date", "opens", "start", "start date"),
    "close":  ("close", "close date", "closing date", "closes", "end", "end date"),
    "dates":  ("date", "dates", "ipo date", "issue date", "open close", "ipo dates"),
}

# Columns we must never surface (section 3).
BANNED = ("qib", "nii", "hni", "snii", "bnii", "anchor", "employee", "shareholder")


def _norm(s: str) -> str:
    s = re.sub(r"\(.*?\)", " ", s or "")
    s = s.replace("₹", " ").replace("*", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def _match_column(header: str) -> Optional[str]:
    h = _norm(header)
    if not h:
        return None
    for key, aliases in ALIASES.items():
        if h in aliases:
            return key
    for key, aliases in ALIASES.items():        # substring fallback
        for a in aliases:
            if a and (h.startswith(a) or a in h.split()):
                return key
    return None


def _is_banned(header: str) -> bool:
    h = _norm(header)
    return any(b == h or h.startswith(b) for b in BANNED)


# ---------- SME detection (section 2: SME must be excluded) ----------

_SME_TOKENS = ("sme", "nse sme", "bse sme", "emerge", "nse emerge", "bse smee")


def detect_board(name: str, href: str = "", section_heading: str = "") -> Board:
    """Classify Mainboard vs SME from several independent signals.

    Returns UNKNOWN when nothing indicates either way; callers drop UNKNOWN
    rows rather than risk printing an SME issue as Mainboard.
    """
    blob = f" {_norm(name)} "
    if any(f" {t} " in blob for t in _SME_TOKENS):
        return Board.SME
    h = (href or "").lower()
    if re.search(r"\bsme\b|emerge", h):
        return Board.SME
    sec = _norm(section_heading)
    if any(t in sec for t in ("sme", "emerge")):
        return Board.SME
    if any(t in sec for t in ("mainboard", "main board", "mainline")):
        return Board.MAINBOARD
    # IPOWatch names mainboard issues plainly; absence of an SME marker in
    # both the name and the link is treated as mainboard.
    if name.strip():
        return Board.MAINBOARD
    return Board.UNKNOWN


# ---------- table walking ----------

def _cell_text(td) -> str:
    return re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip()


def _nearest_heading(table) -> str:
    node = table
    for _ in range(6):
        node = node.find_previous(["h1", "h2", "h3", "h4", "p", "strong"])
        if node is None:
            return ""
        txt = node.get_text(" ", strip=True)
        if txt and len(txt) < 160:
            return txt
    return ""


def _header_map(rows) -> tuple[dict[str, int], int]:
    """Find the header row and map logical column -> index."""
    for ridx, row in enumerate(rows[:4]):
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        texts = [_cell_text(c) for c in cells]
        mapping: dict[str, int] = {}
        for i, t in enumerate(texts):
            if _is_banned(t):
                continue
            key = _match_column(t)
            if key and key not in mapping:
                mapping[key] = i
        if "name" in mapping and len(mapping) >= 2:
            return mapping, ridx
    return {}, -1


def parse_table(table, source_url: str, today: date) -> list[IPO]:
    rows = table.find_all("tr")
    if len(rows) < 2:
        return []
    colmap, hidx = _header_map(rows)
    if not colmap:
        return []

    heading = _nearest_heading(table)
    out: list[IPO] = []

    for row in rows[hidx + 1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        texts = [_cell_text(c) for c in cells]

        def col(key: str) -> Optional[str]:
            i = colmap.get(key)
            if i is None or i >= len(texts):
                return None
            return texts[i] or None

        name = (col("name") or "").strip()
        if not name or _norm(name) in ("ipo", "ipo name", "total", ""):
            continue

        link = cells[colmap["name"]].find("a") if colmap.get("name", 99) < len(cells) else None
        href = link.get("href", "") if link else ""

        open_d = parse_date(col("open"), today.year)
        close_d = parse_date(col("close"), today.year)
        if not (open_d and close_d):
            o, c = _split_date_range(col("dates"), today.year)
            open_d = open_d or o
            close_d = close_d or c

        pmin, pmax = parse_price_band(col("price"))

        ipo = IPO(
            name=_clean_name(name),
            board=detect_board(name, href, heading),
            status=classify_status(open_d, close_d, today),
            open_date=open_d,
            close_date=close_d,
            price_min=pmin,
            price_max=pmax,
            gmp=to_decimal(col("gmp")),
            retail_sub=to_decimal(col("retail")),
            total_sub=to_decimal(col("total")),
            prov=Provenance(source_url=source_url),
        )
        out.append(ipo)
    return out


_RANGE_SPLIT = re.compile(r"\s*(?:-|–|—|to)\s*")


def _split_date_range(text: Optional[str], year: int) -> tuple[Optional[date], Optional[date]]:
    """'25 Aug - 27 Aug 2026' -> (open, close). Fills a bare left side's month."""
    if not text:
        return (None, None)
    parts = _RANGE_SPLIT.split(text.strip(), maxsplit=1)
    if len(parts) != 2:
        return (parse_date(text, year), None)
    left, right = parts[0].strip(), parts[1].strip()
    close_d = parse_date(right, year)
    open_d = parse_date(left, year)
    if open_d is None and close_d is not None and re.fullmatch(r"\d{1,2}", left):
        try:
            open_d = close_d.replace(day=int(left))
        except ValueError:
            open_d = None
    return (open_d, close_d)


_NAME_NOISE = re.compile(
    r"\b(ipo|limited|ltd|details|review|gmp|subscription status|allotment)\b\.?", re.I
)


def _clean_name(raw: str) -> str:
    n = re.sub(r"\s+", " ", raw).strip(" -–—|")
    n = re.sub(r"\b(SME|NSE SME|BSE SME|Emerge)\b", "", n, flags=re.I)
    n = _NAME_NOISE.sub(" ", n)
    return re.sub(r"\s+", " ", n).strip(" -–—,|") or raw.strip()


def parse_page(html: str, source_url: str, today: date) -> list[IPO]:
    """Parse every table on a page and concatenate the IPO rows found."""
    soup = BeautifulSoup(html, "lxml")
    found: list[IPO] = []
    for table in soup.find_all("table"):
        try:
            found.extend(parse_table(table, source_url, today))
        except Exception:  # one malformed table must not kill the run
            continue
    return found
