"""Join the subscription and GMP pages into one validated dataset.

Each page is authoritative for different fields. Where the two disagree on
the same field, the value carrying the newer IPOWatch timestamp wins and the
disagreement is recorded on the record (rule 5.8) rather than hidden.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from .models import Board, IPO, Provenance, Status, classify_status

_NOISE = re.compile(r"\b(ipo|limited|ltd|pvt|private|india|industries|enterprises)\b", re.I)


def norm_key(name: str) -> str:
    """Match key for the same company across pages, tolerant of name drift."""
    n = _NOISE.sub(" ", name or "")
    n = re.sub(r"[^a-z0-9]+", "", n.lower())
    return n


@dataclass
class Conflict:
    ipo: str
    field_name: str
    kept: str
    discarded: str
    reason: str


@dataclass
class Dataset:
    """The final verified dataset. Everything downstream renders from this."""
    open_ipos: list[IPO] = field(default_factory=list)
    upcoming_ipos: list[IPO] = field(default_factory=list)
    recently_closed: list[IPO] = field(default_factory=list)   # kept for validation only
    excluded_sme: list[str] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    subscription_timestamp: Optional[str] = None
    gmp_timestamp: Optional[str] = None
    generated_at: Optional[datetime] = None
    run_date: Optional[date] = None
    source_mode: str = "live"

    @property
    def published(self) -> list[IPO]:
        """Exactly the IPOs that reach the text report and the image."""
        return self.open_ipos + self.upcoming_ipos


def _newer(ts_a: Optional[str], ts_b: Optional[str]) -> bool:
    """True if ts_a looks strictly newer than ts_b. Unparseable -> False."""
    da, db = _parse_stamp(ts_a), _parse_stamp(ts_b)
    if da and db:
        return da > db
    return False


_STAMP_FMTS = [
    "%d %b %Y, %I:%M %p", "%d %b %Y %I:%M %p", "%d %B %Y, %I:%M %p",
    "%d %b %Y, %H:%M", "%d %b %Y", "%d %B %Y",
]


def _parse_stamp(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    t = re.sub(r"\s+", " ", s).strip().strip(".,")
    t = re.sub(r"\b(IST|GMT|UTC)\b", "", t, flags=re.I).strip().strip(",")
    for fmt in _STAMP_FMTS:
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    return None


def _merge_field(dst: IPO, src: IPO, attr: str, dst_ts: Optional[str],
                 src_ts: Optional[str], conflicts: list[Conflict]) -> None:
    """Copy `attr` from src into dst, resolving any disagreement by timestamp."""
    sval, dval = getattr(src, attr), getattr(dst, attr)
    if sval is None:
        return
    if dval is None:
        setattr(dst, attr, sval)
        return
    if sval == dval:
        return
    if _newer(src_ts, dst_ts):
        conflicts.append(Conflict(dst.name, attr, str(sval), str(dval),
                                  f"kept newer figure stamped {src_ts}"))
        setattr(dst, attr, sval)
    else:
        conflicts.append(Conflict(dst.name, attr, str(dval), str(sval),
                                  f"kept figure stamped {dst_ts or 'unknown'}"))


def build_dataset(
    sub_rows: list[IPO],
    gmp_rows: list[IPO],
    today: date,
    sub_ts: Optional[str] = None,
    gmp_ts: Optional[str] = None,
    generated_at: Optional[datetime] = None,
    source_mode: str = "live",
) -> Dataset:
    ds = Dataset(subscription_timestamp=sub_ts, gmp_timestamp=gmp_ts,
                 generated_at=generated_at, run_date=today, source_mode=source_mode)

    merged: dict[str, IPO] = {}

    # GMP page seeds the record: it carries price band, GMP and clean dates.
    for row in gmp_rows:
        key = norm_key(row.name)
        if not key:
            continue
        row.prov.gmp_timestamp = gmp_ts
        merged[key] = row

    # Subscription page is authoritative for retail/total.
    for row in sub_rows:
        key = norm_key(row.name)
        if not key:
            continue
        if key not in merged:
            row.prov.subscription_timestamp = sub_ts
            merged[key] = row
            continue
        tgt = merged[key]
        tgt.prov.subscription_timestamp = sub_ts
        tgt.retail_sub = row.retail_sub if row.retail_sub is not None else tgt.retail_sub
        tgt.total_sub = row.total_sub if row.total_sub is not None else tgt.total_sub
        for attr in ("open_date", "close_date", "price_min", "price_max"):
            _merge_field(tgt, row, attr, gmp_ts, sub_ts, ds.conflicts)
        if row.board == Board.SME:      # an SME marker on either page is decisive
            tgt.board = Board.SME

    # Re-derive status from the merged dates so it can never contradict them.
    for ipo in merged.values():
        ipo.status = classify_status(ipo.open_date, ipo.close_date, today)

    for ipo in merged.values():
        if ipo.board == Board.SME:
            ds.excluded_sme.append(ipo.name)
            continue
        if ipo.board == Board.UNKNOWN:
            ds.warnings.append(f"{ipo.name}: could not confirm Mainboard vs SME - excluded")
            continue
        _flag_unverified(ipo, ds)
        if ipo.status == Status.OPEN:
            ds.open_ipos.append(ipo)
        elif ipo.status == Status.UPCOMING:
            ds.upcoming_ipos.append(ipo)
        elif ipo.status == Status.CLOSED:
            ds.recently_closed.append(ipo)   # retained internally only (section 2)

    ds.open_ipos.sort(key=_gmp_sort_key, reverse=True)
    ds.upcoming_ipos.sort(key=_gmp_sort_key, reverse=True)
    return ds


def _flag_unverified(ipo: IPO, ds: Dataset) -> None:
    """Mark fields that are present-but-unusable, per rule 5.10."""
    if ipo.gmp is not None and (ipo.price_max is None or ipo.price_max == 0):
        ipo.unverified_fields.add("gmp")
        ds.warnings.append(
            f"{ipo.name}: GMP present but no upper price band - GMP % not verifiable")
    if ipo.open_date is None or ipo.close_date is None:
        ds.warnings.append(f"{ipo.name}: incomplete IPO dates on IPOWatch")


def _gmp_sort_key(ipo: IPO) -> Decimal:
    pct = ipo.gmp_pct
    return pct if pct is not None else Decimal("-1")


def rank_by_gmp(ds: Dataset) -> list[IPO]:
    return sorted(ds.published, key=_gmp_sort_key, reverse=True)


def leader(ds: Dataset, attr: str) -> Optional[IPO]:
    """Highest value of `attr` across published IPOs, or None if nobody has one."""
    pool = [i for i in ds.published if getattr(i, attr) is not None]
    if not pool:
        return None
    return max(pool, key=lambda i: getattr(i, attr))
