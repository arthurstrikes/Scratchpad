"""Data model for a single IPO plus all number formatting / GMP maths.

Design rule: every numeric field is Optional. `None` means "we do not know",
and the renderers turn that into "Not updated" / "Not verified". Nothing in
this module ever invents, defaults, or carries forward a value.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional

from .config import NOT_UPDATED, NOT_VERIFIED


class Board(str, Enum):
    MAINBOARD = "Mainboard"
    SME = "SME"
    UNKNOWN = "Unknown"


class Status(str, Enum):
    OPEN = "Open"
    UPCOMING = "Upcoming"
    CLOSED = "Closed"
    UNKNOWN = "Unknown"


@dataclass
class Provenance:
    """Where a number came from and when the source last refreshed it."""
    source_url: str = ""
    # IPOWatch stamps subscription and GMP at different times (rule 5.5).
    subscription_timestamp: Optional[str] = None
    gmp_timestamp: Optional[str] = None
    notes: list[str] = field(default_factory=list)


@dataclass
class IPO:
    name: str
    board: Board = Board.UNKNOWN
    status: Status = Status.UNKNOWN

    open_date: Optional[date] = None
    close_date: Optional[date] = None

    price_min: Optional[Decimal] = None
    price_max: Optional[Decimal] = None

    gmp: Optional[Decimal] = None            # rupees
    retail_sub: Optional[Decimal] = None     # times (x)
    total_sub: Optional[Decimal] = None      # times (x)

    # IPOWatch stamps each row with its own update time; kept per-row because
    # the two pages refresh independently (rule 5.5).
    row_updated: Optional[str] = None
    # True when IPOWatch printed the status itself rather than us deriving it
    # from dates. An explicit status always wins.
    status_from_page: bool = False

    prov: Provenance = field(default_factory=Provenance)
    # Set when a value existed but failed verification (rule 5.10).
    unverified_fields: set[str] = field(default_factory=set)

    # ---------- GMP maths (section 4) ----------

    @property
    def gmp_pct(self) -> Optional[Decimal]:
        """GMP % = GMP / UPPER PRICE BAND * 100, half-up to 2dp.

        Computed here and nowhere else; IPOWatch's own "estimated listing
        gain" column is deliberately never read.
        """
        if self.gmp is None or self.price_max is None or self.price_max == 0:
            return None
        raw = (Decimal(self.gmp) / Decimal(self.price_max)) * Decimal(100)
        return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def gmp_pct_text(self) -> str:
        pct = self.gmp_pct
        if pct is None:
            return NOT_VERIFIED if "gmp" in self.unverified_fields else NOT_UPDATED
        return f"{pct:.2f}%"          # rule 5.7: GMP 0 renders as 0.00%

    @property
    def gmp_text(self) -> str:
        if self.gmp is None:
            return NOT_VERIFIED if "gmp" in self.unverified_fields else NOT_UPDATED
        return f"₹{_num(self.gmp)}"

    @property
    def is_hot(self) -> bool:
        pct = self.gmp_pct
        return pct is not None and pct > Decimal("10")

    # ---------- display helpers ----------

    @property
    def price_band_text(self) -> str:
        if self.price_min is None or self.price_max is None:
            if self.price_max is not None:
                return f"{_num(self.price_max)}"
            return NOT_VERIFIED if "price" in self.unverified_fields else NOT_UPDATED
        return f"{_num(self.price_min)}–{_num(self.price_max)}"

    @property
    def date_range_text(self) -> str:
        if not self.open_date or not self.close_date:
            return NOT_VERIFIED
        return f"{_d(self.open_date)} – {_d(self.close_date)}"

    def sub_text(self, which: str) -> str:
        """Subscription display. Absent -> 'Not updated' (rule 5.6)."""
        val = self.retail_sub if which == "retail" else self.total_sub
        if val is None:
            return NOT_VERIFIED if which in self.unverified_fields else NOT_UPDATED
        return f"{_num(val)}x"

    @property
    def retail_text(self) -> str:
        return self.sub_text("retail")

    @property
    def total_text(self) -> str:
        return self.sub_text("total")


def _num(v: Decimal) -> str:
    """Trim trailing zeros: 429.00 -> 429, 2.50 -> 2.5, 0.00 -> 0."""
    d = Decimal(v).normalize()
    if d == d.to_integral_value():
        d = d.to_integral_value()
    s = format(d, "f")
    return s


def _d(d: date) -> str:
    return d.strftime("%d %b")


# ---------- tolerant scalar parsers (used by parse.py) ----------

_MONEY_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def to_decimal(text: Optional[str]) -> Optional[Decimal]:
    """Pull a number out of messy cell text. Returns None, never a guess.

    '₹1,234.50' -> 1234.50 | '2.35x' -> 2.35 | '--' / 'NA' / '' -> None
    """
    if text is None:
        return None
    t = str(text).strip()
    if not t:
        return None
    low = t.lower()
    if low in {"-", "--", "---", "na", "n/a", "nil", "tbd", "to be announced", "coming soon", "not updated"}:
        return None
    m = _MONEY_RE.search(t.replace("−", "-"))
    if not m:
        return None
    try:
        return Decimal(m.group(0).replace(",", ""))
    except Exception:
        return None


_BAND_RE = re.compile(
    r"(\d[\d,]*\.?\d*)\s*(?:-|–|—|to)\s*(\d[\d,]*\.?\d*)", re.I
)


def parse_price_band(text: Optional[str]) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """'₹402-429' -> (402, 429). A single number becomes the upper band."""
    if not text:
        return (None, None)
    t = str(text).replace("₹", " ").replace("Rs.", " ").replace("Rs", " ")
    m = _BAND_RE.search(t)
    if m:
        lo, hi = to_decimal(m.group(1)), to_decimal(m.group(2))
        if lo is not None and hi is not None and lo > hi:
            lo, hi = hi, lo
        return (lo, hi)
    single = to_decimal(t)
    return (None, single) if single is not None else (None, None)


_MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
_DATE_PATTERNS = [
    "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%B-%Y",
    "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d",
    "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y",
]


def parse_date(text: Optional[str], default_year: Optional[int] = None) -> Optional[date]:
    """Tolerant date parsing across IPOWatch's several formats.

    Year-less forms ('25 Aug') are resolved against `default_year`, chosen so
    an IPO near a year boundary does not jump 12 months.
    """
    if not text:
        return None
    t = re.sub(r"\s+", " ", str(text).strip().replace(",", ", ")).strip(" ,")
    t = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", t, flags=re.I)
    t = re.sub(r"\s*,\s*", ", ", t)
    for fmt in _DATE_PATTERNS:
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    # Year-less: '25 Aug' / 'Aug 25'
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,})\b", t)
    if not m:
        m2 = re.search(r"\b([A-Za-z]{3,})\s+(\d{1,2})\b", t)
        if m2:
            mon_txt, day_txt = m2.group(1), m2.group(2)
        else:
            return None
    else:
        day_txt, mon_txt = m.group(1), m.group(2)
    mon = mon_txt[:3].lower()
    if mon not in _MONTHS:
        return None
    year = default_year or date.today().year
    try:
        return date(year, _MONTHS.index(mon) + 1, int(day_txt))
    except ValueError:
        return None


def classify_status(ipo_open: Optional[date], ipo_close: Optional[date], today: date) -> Status:
    """Status purely from dates, so it never disagrees with the printed dates."""
    if ipo_open and ipo_close:
        if ipo_open <= today <= ipo_close:
            return Status.OPEN
        if today < ipo_open:
            return Status.UPCOMING
        return Status.CLOSED
    if ipo_open and not ipo_close:
        return Status.OPEN if ipo_open <= today else Status.UPCOMING
    if ipo_close and not ipo_open:
        # The subscription table gives only a closing date. A row there already
        # carries bid numbers, so it has opened; only the close date decides.
        return Status.CLOSED if today > ipo_close else Status.OPEN
    return Status.UNKNOWN
