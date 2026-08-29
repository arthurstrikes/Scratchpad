"""IMAGE DATA == FINAL VERIFIED DATA (spec section 7).

Builds the map of figures the creative *should* show straight from the
dataset, then diffs it against what was actually read back out of the
rendered DOM. Any mismatch fails the run; the caller re-renders rather than
publishing an image that disagrees with the report.
"""
from __future__ import annotations

from dataclasses import dataclass

from .merge import Dataset, leader, rank_by_gmp


@dataclass
class Mismatch:
    key: str
    expected: str
    actual: str

    def __str__(self) -> str:
        return f"{self.key}: expected {self.expected!r}, image shows {self.actual!r}"


def expected_map(ds: Dataset) -> dict[str, str]:
    """The single source of truth for what the image must display."""
    out: dict[str, str] = {}
    for idx, ipo in enumerate(ds.open_ipos):
        k = f"ipo{idx}"
        out[f"{k}.name"] = ipo.name
        out[f"{k}.gmp"] = ipo.gmp_text
        out[f"{k}.gmppct"] = ipo.gmp_pct_text
        out[f"{k}.dates"] = ipo.date_range_text
        out[f"{k}.price"] = f"₹{ipo.price_band_text}"
        out[f"{k}.retail"] = ipo.retail_text
        out[f"{k}.total"] = ipo.total_text
    for n, ipo in enumerate(ds.upcoming_ipos):
        k = f"ipo{len(ds.open_ipos) + n}"
        out[f"{k}.name"] = ipo.name
        out[f"{k}.gmp"] = ipo.gmp_text
        out[f"{k}.gmppct"] = ipo.gmp_pct_text
        out[f"{k}.dates"] = ipo.date_range_text
        out[f"{k}.price"] = f"₹{ipo.price_band_text}"

    ranked = rank_by_gmp(ds)
    top_gmp = next((i for i in ranked if i.gmp_pct is not None), None)
    top_ret, top_tot = leader(ds, "retail_sub"), leader(ds, "total_sub")
    for key, ipo, val in (
        ("lead_gmp", top_gmp, top_gmp.gmp_pct_text if top_gmp else None),
        ("lead_ret", top_ret, top_ret.retail_text if top_ret else None),
        ("lead_tot", top_tot, top_tot.total_text if top_tot else None),
    ):
        if ipo is not None:
            out[f"{key}.name"] = ipo.name
            out[f"{key}.val"] = val
    return out


def _norm(s: str) -> str:
    # The DOM collapses whitespace and normalises dashes; compare on that basis.
    return " ".join(str(s).split()).replace("–", "–").replace("—", "–")


def check(ds: Dataset, rendered: dict[str, str]) -> list[Mismatch]:
    exp = expected_map(ds)
    bad: list[Mismatch] = []
    for key, want in exp.items():
        got = rendered.get(key)
        if got is None:
            bad.append(Mismatch(key, want, "<missing from image>"))
        elif _norm(got) != _norm(want):
            bad.append(Mismatch(key, want, got))
    for key in rendered:
        if key not in exp:
            bad.append(Mismatch(key, "<not in dataset>", rendered[key]))
    return bad
