"""WhatsApp-ready text report and share caption (spec sections 6, 8, 9).

Uses WhatsApp's own markup - *bold* and _italic_ - so a straight copy-paste
from Telegram or the .txt file lands in WhatsApp already formatted.
"""
from __future__ import annotations

from typing import Optional

from .config import NOT_UPDATED, SOURCE_NAME
from .merge import Dataset, leader, rank_by_gmp
from .models import IPO

HOT = "🔥"


def _title(ipo: IPO) -> str:
    """Name line; GMP above 10% is flagged (section 6)."""
    name = f"{HOT} {ipo.name.upper()}" if ipo.is_hot else ipo.name.upper()
    return f"*{name}*"


def _price_line(ipo: IPO) -> str:
    line = f"💰 Price: ₹{ipo.price_band_text}"
    if ipo.min_invest_text and ipo.lot_shares:
        line += f" | {ipo.min_invest_text} ({ipo.lot_shares} shares)"
    return line


def _trend_line(ipo: IPO, today) -> str:
    t = ipo.trend
    if t is None:
        return ""
    if t.status == "new":
        return "📈 GMP trend: New (first GMP today)"
    if t.status != "ok":
        return f"📈 GMP trend: {NOT_UPDATED}"
    gone = f"₹{t.prev_gmp.normalize():f}" if t.prev_gmp is not None else ""
    if t.direction == "flat":
        return f"📈 GMP trend: ▬ No change {t.vs_text(today)} ({gone})"
    return f"📈 GMP trend: {t.text()} {t.vs_text(today)} ({gone} → {ipo.gmp_text})"


def _dates_line(ipo: IPO) -> str:
    if not (ipo.allotment_text or ipo.listing_text):
        return ""
    return (f"🗓️ Allotment: {ipo.allotment_text or NOT_UPDATED}"
            f" | Listing: {ipo.listing_text or NOT_UPDATED}")


def _block(ipo: IPO, today, with_sub: bool) -> str:
    lines = [_title(ipo), f"📅 {ipo.date_range_text}", _price_line(ipo)]
    if with_sub:
        lines += [f"👥 Retail: {ipo.retail_text}", f"📊 Total: {ipo.total_text}"]
    lines.append(f"🟢 GMP: {ipo.gmp_text} | *{ipo.gmp_pct_text}*")
    lines += [x for x in (_trend_line(ipo, today), _dates_line(ipo)) if x]
    return "\n".join(lines)


def build_report(ds: Dataset) -> str:
    d = ds.run_date.strftime("%d %b %Y") if ds.run_date else ""
    L: list[str] = ["*📊 DAILY MAINBOARD IPO WATCH*", f"📅 {d} | 5:00 PM IST", ""]

    L.append("*🟢 OPEN MAINBOARD IPOs*")
    L.append("")
    if ds.open_ipos:
        for ipo in ds.open_ipos:
            L.append(_block(ipo, ds.run_date, True))
            L.append("")
    else:
        L += ["No Mainboard IPOs are open today.", ""]

    L.append("*🔵 UPCOMING MAINBOARD IPOs*")
    L.append("")
    if ds.upcoming_ipos:
        for ipo in ds.upcoming_ipos:
            L.append(_block(ipo, ds.run_date, False))
            L.append("")
    else:
        L += ["No Mainboard IPOs are scheduled yet.", ""]

    L.append(_ranking(ds))
    L.append("")
    L.append(_footer(ds))
    return "\n".join(L).rstrip() + "\n"


def _ranking(ds: Dataset) -> str:
    """Section 9. Ranks every Open + Upcoming Mainboard IPO by GMP %."""
    L = ["*🏆 CURRENT GMP RANKING*", ""]
    ranked = rank_by_gmp(ds)
    if not ranked:
        L.append("No IPOs to rank.")
        return "\n".join(L)

    for n, ipo in enumerate(ranked, 1):
        tag = " 🟢" if ipo.status.value == "Open" else " 🔵"
        arrow = ""
        if ipo.trend and ipo.trend.status == "ok":
            arrow = f" {ipo.trend.text()}"
        L.append(f"{n}. {ipo.name} — *{ipo.gmp_pct_text}* ({ipo.gmp_text}){tag}{arrow}")

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
        "📌 _GMP = Grey Market Premium_",
        "📈 _GMP % calculated on upper price band_",
        "⚠️ _GMP is unofficial and can change before listing._",
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
