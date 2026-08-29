"""WhatsApp-ready text report and share caption (spec sections 6, 8, 9)."""
from __future__ import annotations

from typing import Optional

from .config import NOT_UPDATED, SOURCE_NAME
from .merge import Dataset, leader, rank_by_gmp
from .models import IPO, _num

HOT = "🔥"


def _title(ipo: IPO) -> str:
    """Name line; GMP above 10% is flagged (section 6)."""
    return f"{HOT} {ipo.name.upper()}" if ipo.is_hot else ipo.name.upper()


def _open_block(ipo: IPO) -> str:
    return (
        f"{_title(ipo)}\n"
        f"📅 {ipo.date_range_text}\n"
        f"💰 Price: ₹{ipo.price_band_text}\n"
        f"👥 Retail: {ipo.retail_text}\n"
        f"📊 Total: {ipo.total_text}\n"
        f"🟢 GMP: {ipo.gmp_text} | {ipo.gmp_pct_text}"
    )


def _upcoming_block(ipo: IPO) -> str:
    return (
        f"{_title(ipo)}\n"
        f"📅 {ipo.date_range_text}\n"
        f"💰 Price: ₹{ipo.price_band_text}\n"
        f"🟢 GMP: {ipo.gmp_text} | {ipo.gmp_pct_text}"
    )


def build_report(ds: Dataset) -> str:
    d = ds.run_date.strftime("%d %b %Y") if ds.run_date else ""
    L: list[str] = ["📊 DAILY MAINBOARD IPO WATCH", f"📅 {d} | 8:00 PM", ""]

    L.append("🟢 OPEN MAINBOARD IPOs")
    L.append("")
    if ds.open_ipos:
        for ipo in ds.open_ipos:
            L.append(_open_block(ipo))
            L.append("")
    else:
        L += ["No Mainboard IPOs are open today.", ""]

    L.append("🔵 UPCOMING MAINBOARD IPOs")
    L.append("")
    if ds.upcoming_ipos:
        for ipo in ds.upcoming_ipos:
            L.append(_upcoming_block(ipo))
            L.append("")
    else:
        L += ["No Mainboard IPOs are scheduled yet.", ""]

    L.append(_ranking(ds))
    L.append("")
    L.append(_footer(ds))
    return "\n".join(L).rstrip() + "\n"


def _ranking(ds: Dataset) -> str:
    """Section 9. Ranks every Open + Upcoming Mainboard IPO by GMP %."""
    L = ["🏆 CURRENT GMP RANKING", ""]
    ranked = rank_by_gmp(ds)
    if not ranked:
        L.append("No IPOs to rank.")
        return "\n".join(L)

    for n, ipo in enumerate(ranked, 1):
        tag = " 🟢" if ipo.status.value == "Open" else " 🔵"
        L.append(f"{n}. {ipo.name} — {ipo.gmp_pct_text} ({ipo.gmp_text}){tag}")

    L.append("")
    top_gmp = next((i for i in ranked if i.gmp_pct is not None), None)
    top_ret = leader(ds, "retail_sub")
    top_tot = leader(ds, "total_sub")

    L.append(f"🔥 Highest GMP: {top_gmp.name} — {top_gmp.gmp_pct_text}"
             if top_gmp else f"🔥 Highest GMP: {NOT_UPDATED}")
    L.append(f"👥 Highest Retail Subscription: {top_ret.name} — {top_ret.retail_text}"
             if top_ret else f"👥 Highest Retail Subscription: {NOT_UPDATED}")
    L.append(f"📊 Highest Total Subscription: {top_tot.name} — {top_tot.total_text}"
             if top_tot else f"📊 Highest Total Subscription: {NOT_UPDATED}")
    return "\n".join(L)


def _footer(ds: Dataset) -> str:
    L = [
        "📌 GMP = Grey Market Premium",
        "📈 GMP % calculated on upper price band",
        "⚠️ GMP is unofficial and can change before listing.",
        f"Source: {SOURCE_NAME}",
    ]
    stamps = []
    if ds.subscription_timestamp:
        stamps.append(f"Subscription data: {ds.subscription_timestamp}")
    if ds.gmp_timestamp:
        stamps.append(f"GMP data: {ds.gmp_timestamp}")
    if stamps:
        L.append("🕒 " + " | ".join(stamps))   # rule 5.5: stamps kept separate
    if ds.warnings:
        L.append("")
        L.append("ℹ️ Data notes:")
        L += [f"• {w}" for w in ds.warnings]
    if ds.conflicts:
        L.append("")
        L.append("⚖️ Source conflicts resolved (newest figure kept):")
        L += [f"• {c.ipo} {c.field_name}: kept {c.kept}, dropped {c.discarded} — {c.reason}"
              for c in ds.conflicts]
    return "\n".join(L)


def build_caption(ds: Dataset) -> str:
    """Short forwarding caption that sits under the image (section 8)."""
    d = ds.run_date.strftime("%d %b %Y") if ds.run_date else ""
    ranked = rank_by_gmp(ds)
    top_gmp = next((i for i in ranked if i.gmp_pct is not None), None)
    top_ret = leader(ds, "retail_sub")

    gmp_line = (f"🔥 Highest GMP: {top_gmp.name} — {top_gmp.gmp_pct_text}"
                if top_gmp else f"🔥 Highest GMP: {NOT_UPDATED}")
    ret_line = (f"📈 Highest Retail Subscription: {top_ret.name} — {_num(top_ret.retail_sub)}x"
                if top_ret else f"📈 Highest Retail Subscription: {NOT_UPDATED}")

    return (
        f"📊 Daily Mainboard IPO Watch — {d}\n\n"
        f"{gmp_line}\n"
        f"{ret_line}\n\n"
        "Full details in the attached creative.\n\n"
        "⚠️ GMP is unofficial and subject to change."
    )
