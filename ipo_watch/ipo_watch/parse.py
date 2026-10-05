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

from .models import (Board, IPO, Provenance, Status, _MONTHS, classify_status,
                     parse_date, parse_price_band, to_decimal)

# --- header alias sets. Matching is on normalised, punctuation-free text. ---
ALIASES: dict[str, tuple[str, ...]] = {
    "name":   ("ipo", "ipo name", "company", "company name", "name", "issue", "ipo details"),
    "board":  ("type", "ipo type", "board", "category", "segment"),
    "status": ("status", "ipo status"),
    "updated": ("last updated", "updated", "update time", "updated at"),
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
BANNED = ("qib", "nii", "hni", "snii", "bnii", "anchor", "employee", "shareholder",
          "est listing", "estimated listing", "listing price", "listing gain",
          "expected listing", "trend", "est gain", "estimated gain")


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


def board_from_cell(text: Optional[str]) -> Optional[Board]:
    """Read IPOWatch's own Type column. Authoritative when present."""
    if not text:
        return None
    t = _norm(text)
    if not t:
        return None
    if "sme" in t.split() or "emerge" in t:
        return Board.SME
    if "mainboard" in t or "main board" in t or "mainline" in t:
        return Board.MAINBOARD
    return None


def status_from_cell(text: Optional[str]) -> Optional[Status]:
    """Read IPOWatch's own Status column. Authoritative when present."""
    if not text:
        return None
    t = _norm(text)
    if t.startswith("open") or t == "live":
        return Status.OPEN
    if t.startswith("upcoming") or t.startswith("soon"):
        return Status.UPCOMING
    if t.startswith("closed") or t.startswith("listed"):
        return Status.CLOSED
    return None


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

    # A table with no date and no status column cannot be placed in time -
    # IPOWatch's "Mainboard IPO GMP Performance" table of already-listed IPOs
    # is one of these. Parsing it would inject rows with no status that could
    # collide by name with live ones.
    if not ({"dates", "open", "close", "status"} & set(colmap)):
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
            o, c = parse_compact_range(col("dates"), today)
            if not (o or c):
                o, c = _split_date_range(col("dates"), today.year)
            open_d = open_d or o
            close_d = close_d or c

        pmin, pmax = parse_price_band(col("price"))

        board = board_from_cell(col("board")) or detect_board(name, href, heading)
        page_status = status_from_cell(col("status"))

        ipo = IPO(
            name=_clean_name(name),
            board=board,
            status=page_status or classify_status(open_d, close_d, today),
            open_date=open_d,
            close_date=close_d,
            price_min=pmin,
            price_max=pmax,
            gmp=to_decimal(col("gmp")),
            retail_sub=to_decimal(col("retail")),
            total_sub=to_decimal(col("total")),
            row_updated=col("updated"),
            status_from_page=page_status is not None,
            prov=Provenance(source_url=source_url),
        )
        out.append(ipo)
    return out


# IPOWatch writes ranges as "27-31 August" or, across a month boundary,
# "28-1 September" - the month belongs to the CLOSING day, and when the first
# number is the larger one the opening day sits in the previous month.
_COMPACT_RANGE = re.compile(
    r"^\s*(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\s+([A-Za-z]{3,9})\.?\s*(\d{4})?\s*$", re.I)


def parse_compact_range(text: Optional[str], today: date):
    """'28-1 September' -> (28 Aug, 1 Sep). Returns (None, None) if not this shape."""
    if not text:
        return (None, None)
    m = _COMPACT_RANGE.match(str(text))
    if not m:
        return (None, None)
    d1, d2, mon_txt, yr = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
    mon = mon_txt[:3].lower()
    if mon not in _MONTHS:
        return (None, None)
    close_month = _MONTHS.index(mon) + 1
    year = int(yr) if yr else today.year
    # A range printed in Jan for a Dec opening belongs to the previous year.
    if not yr and close_month == 1 and today.month == 12:
        year = today.year + 1
    try:
        close_d = date(year, close_month, d2)
    except ValueError:
        return (None, None)
    if d1 <= d2:
        try:
            return (date(year, close_month, d1), close_d)
        except ValueError:
            return (None, close_d)
    # d1 > d2: the opening day is in the month before the closing month.
    om, oy = (close_month - 1, year) if close_month > 1 else (12, year - 1)
    try:
        return (date(oy, om, d1), close_d)
    except ValueError:
        return (None, close_d)


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
    # IPOWatch's GMP page appends a one-letter status marker directly onto
    # the company name instead of a separate Status column - "Jio
    # Platform(U)" (seen 2 Oct 2026) - and a day later dropped the Type
    # column too, appending the board type the same way - "Vishal Nirmiti
    # (O) Mainboard", "TNA Solutions (O) SME" (seen 3 Oct 2026). Strip both:
    # neither marker's meaning is ever interpreted here. Status still comes
    # from an explicit Status column when present, or classify_status() via
    # dates otherwise (rule 5.3). Board still comes from board_from_cell()
    # when a board column exists, or detect_board()'s SME-token fallback
    # otherwise - which runs on the raw, unstripped name in parse_table(),
    # so stripping "SME" here first does not blind that fallback. Left in
    # the cleaned name, either marker would make this page's name normalize
    # differently from the plain name on the subscription page, splitting
    # one IPO into two partial rows (norm_key in merge.py).
    n = re.sub(r"\(\s*[A-Za-z]\s*\)\s*(mainboard|main\s*board|mainline|sme)?\s*$",
                "", n, flags=re.I)
    # Two days after that, IPOWatch dropped the parentheses too and just
    # appends the bare status word straight after the name - "Vishal
    # Nirmiti Open", "Nityas Gems Closed" (seen 5 Oct 2026). The source HTML
    # has the name and the status word as separate text nodes in the same
    # cell with no punctuation between them, so whether a space ends up
    # between them depends on `_cell_text()`'s join character - it does
    # insert one, but this is written to tolerate either, since relying on
    # exact whitespace from a site that has changed this three days running
    # is not something to bet on. The lookbehind requires either a lowercase
    # letter or whitespace immediately before the status word, so this
    # cannot eat the last word of a name that already ends in a capital
    # letter or punctuation with nothing separating it. Same reasoning as
    # above: status is never derived from this text, only stripped so
    # cross-page name matching keeps working.
    n = re.sub(r"(?:(?<=[a-z])|(?<=\s))(open|closed|upcoming)\s*$", "", n, flags=re.I)
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
