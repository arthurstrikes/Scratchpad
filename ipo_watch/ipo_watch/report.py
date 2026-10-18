"""WhatsApp-ready text report and share caption (spec sections 6, 8, 9).

Uses WhatsApp's own markup - *bold* and _italic_ - so a straight copy-paste
from Telegram or the .txt file lands in WhatsApp already formatted.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from .config import GMP_HIGHLIGHT_THRESHOLD_PCT, NOT_UPDATED, SOURCE_NAME
from .merge import Dataset, leader, rank_by_gmp
from .models import IPO, _d

HOT = "🔥"


def _title(ipo: IPO) -> str:
    """Name line; GMP above the highlight threshold (config) is flagged."""
    name = f"{HOT} {ipo.name.upper()}" if ipo.is_hot else ipo.name.upper()
    return f"*{name}*"


def _price_line(ipo: IPO) -> str:
    line = f"💰 Price: {ipo.price_display}"
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


def _sub_line(icon: str, label: str, ipo: IPO, which: str, today) -> str:
    value = ipo.retail_text if which == "retail" else ipo.total_text
    change = ipo.sub_change_text(which, today)
    return f"{icon} {label}: {value}" + (f" ({change})" if change else "")


def glance_text(ds: Dataset) -> str:
    """One counts-only line for the top of the report: what is open, what
    closes soon, what is upcoming, how many are above the High GMP line."""
    n_open, n_up = len(ds.open_ipos), len(ds.upcoming_ipos)
    parts = []
    if n_open:
        today = ds.run_date
        c0 = sum(1 for i in ds.open_ipos if i.closes_label(today) == "Closes today")
        c1 = sum(1 for i in ds.open_ipos if i.closes_label(today) == "Closes tomorrow")
        soon = [f"{c} {'closes' if c == 1 else 'close'} {when}"
                for c, when in ((c0, "today"), (c1, "tomorrow")) if c]
        parts.append(f"{n_open} open" + (f" ({', '.join(soon)})" if soon else ""))
    else:
        parts.append("none open")
    parts.append(f"{n_up} upcoming" if n_up else "none upcoming")
    if ds.awaiting:
        parts.append(f"{len(ds.awaiting)} awaiting listing")
    hot = sum(1 for i in ds.published if i.is_hot)
    parts.append(f"{hot} above {GMP_HIGHLIGHT_THRESHOLD_PCT:g}% GMP" if hot
                 else f"none above {GMP_HIGHLIGHT_THRESHOLD_PCT:g}% GMP")
    return " · ".join(parts)


def _block(ipo: IPO, today, with_sub: bool) -> str:
    closes = ipo.closes_label(today)
    dates = f"📅 {ipo.date_range_text}" + (f" | ⏰ {closes}" if closes else "")
    lines = [_title(ipo), dates, _price_line(ipo)]
    if with_sub:
        lines += [_sub_line("👥", "Retail", ipo, "retail", today),
                  _sub_line("📊", "Total", ipo, "total", today)]
    lines.append(f"🟢 GMP: {ipo.gmp_text} | *{ipo.gmp_pct_text}*")
    lines += [x for x in (_trend_line(ipo, today), _dates_line(ipo)) if x]
    return "\n".join(lines)


def build_report(ds: Dataset) -> str:
    d = ds.run_date.strftime("%d %b %Y") if ds.run_date else ""
    L: list[str] = ["*📊 DAILY MAINBOARD IPO WATCH*", f"📅 {d} | 5:00 PM IST",
                    f"🔎 {glance_text(ds)}", ""]

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

    if ds.awaiting:
        L.append(_awaiting(ds))
        L.append("")
    if ds.recent_listings:
        L.append(_recent_listings(ds))
        L.append("")
    L.append(_ranking(ds))
    L.append("")
    if ds.track_record:
        L.append(track_block(ds.track_record))
        L.append("")
    L.append(_footer(ds))
    return "\n".join(L).rstrip() + "\n"


def _awaiting(ds: Dataset) -> str:
    """Closed IPOs with a High GMP that have not listed yet (user's rule, 18 Oct)."""
    L = [f"*🕓 CLOSED, AWAITING LISTING* (GMP above {GMP_HIGHLIGHT_THRESHOLD_PCT:g}%)", ""]
    for ipo in ds.awaiting:
        L += [_title(ipo),
              f"📅 Closed {_d(ipo.close_date)} | 💰 Issue price: {ipo.price_display}",
              f"👥 Final subscription: Retail {ipo.retail_text} | Total {ipo.total_text}",
              f"🟢 GMP: {ipo.gmp_text} | *{ipo.gmp_pct_text}*",
              f"🗓️ Allotment: {ipo.allotment_text or NOT_UPDATED} | Listing: {ipo.listing_text or NOT_UPDATED}",
              ""]
    return "\n".join(L).rstrip()


def track_block(tr) -> str:
    """The GMP track record as a small scoreboard (also drawn in the image)."""
    L = [f"*📊 {tr.title.upper()}*", "",
         f"📈 Average listing gain: *{tr.gain_text}*",
         f"✅ Opened above issue price: *{tr.up_text}*"]
    if tr.day1_text:
        L.append(f"🕘 Average first day (open to close): *{tr.day1_text}*")
    if tr.acc_text:
        L.append(f"🎯 GMP accuracy: listed within {tr.acc_note.split()[1]} points of GMP in "
                 f"*{tr.acc_text}* (average miss {tr.miss_text}; GMP was too high in {tr.over})")
    L.append("_Listing gain = issue price to first-day open, from NSE._")
    return "\n".join(L)


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
        f"🔥 _Flag = GMP above {GMP_HIGHLIGHT_THRESHOLD_PCT:g}%_",
        "👥 _▲/▼ on subscription = change since our previous update._",
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


def closing_today(ds: Dataset) -> list[IPO]:
    """Open Mainboard IPOs whose last day to bid is the run date."""
    return [i for i in ds.open_ipos if i.close_date and i.close_date == ds.run_date]


def build_midday_report(ds: Dataset) -> Optional[str]:
    """Short mid-afternoon update for IPOs closing today; None when none are."""
    closing = closing_today(ds)
    if not closing:
        return None
    d = ds.run_date.strftime("%d %b %Y") if ds.run_date else ""
    when = ds.generated_at.strftime("%I:%M %p").lstrip("0") if ds.generated_at else ""
    L = ["*⏰ CLOSING TODAY: SUBSCRIPTION UPDATE*", f"📅 {d} | {when} IST".replace(" |  IST", ""), ""]
    for ipo in closing:
        L.append(_title(ipo))
        L.append(f"👥 Retail: {ipo.retail_text}")
        L.append(f"📊 Total: {ipo.total_text}")
        L.append(f"🟢 GMP: {ipo.gmp_text} | *{ipo.gmp_pct_text}*")
        tl = _trend_line(ipo, ds.run_date)
        if tl:
            L.append(tl)
        L.append("")
    L.append("_Final numbers follow in the 5:00 PM update._")
    L.append(f"Source: {SOURCE_NAME}")
    if ds.subscription_timestamp:
        L.append(f"🕒 Subscription data: {ds.subscription_timestamp}")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------ listing results

def _listing_lines(r, compact: bool) -> list[str]:
    head = f"*{r.name.upper()}*" + (f" - listed {r.listing_date.strftime('%d %b')}" if compact
                                    else f" (NSE: {r.symbol})")
    L = [head,
         f"💰 Issue {r.issue_text} → Listed {r.open_text} | *{r.listing_gain_text}*"]
    if compact:
        L.append(f"📈 Day 1 close {r.close_text} ({r.day1_text} from open)")
    else:
        L += [f"📈 Day 1: Open {r.open_text} → Close {r.close_text} | *{r.day1_text}*",
              f"📊 Close vs issue: {r.close_vs_issue_text}"]
    if r.gmp_said_text:
        gap = f" | Gap {r.gap_text}" if r.gap_text else ""
        L.append(f"🎯 GMP said {r.gmp_said_text}{gap}")
    return L


def _recent_listings(ds: Dataset) -> str:
    L = ["*🏁 RECENTLY LISTED*", ""]
    for r in ds.recent_listings:
        L += _listing_lines(r, compact=True) + [""]
    L.append("_Prices from NSE. Gap = actual listing gain minus the GMP % we last reported._")
    return "\n".join(L)


def build_listing_report(results: list, run_date) -> str:
    """The evening scorecard for IPOs that listed today."""
    d = run_date.strftime("%d %b %Y") if run_date else ""
    L = ["*🏁 LISTING DAY SCORECARD*", f"📅 {d} | NSE", ""]
    for r in results:
        L += _listing_lines(r, compact=False) + [""]
    L.append("_Issue = NSE base price. Listing gain = issue to first-day open. "
             "Day 1 = first-day open to close. Gap = listing gain minus the GMP % we last reported. "
             "GMP is unofficial._")
    L.append("Source: NSE (prices), IPOWatch (GMP shown before listing)")
    notes = [n for r in results for n in r.notes]
    if notes:
        L += ["", "ℹ️ Data notes:"] + [f"• {n}" for n in notes]
    return "\n".join(L) + "\n"


def _coming_line(ipo: IPO) -> str:
    bits = []
    if ipo.status.value == "Open":
        bits.append(f"bidding closes {_d(ipo.close_date)}" if ipo.close_date else "bidding open")
    elif ipo.status.value == "Closed":
        bits.append(f"closed {_d(ipo.close_date)}")
    else:
        bits.append(f"opens {_d(ipo.open_date)}" if ipo.open_date else "dates awaited")
        if ipo.close_date:
            bits.append(f"closes {_d(ipo.close_date)}")
    if ipo.allotment_date:
        bits.append(f"allotment {_d(ipo.allotment_date)}")
    if ipo.listing_date:
        bits.append(f"lists {_d(ipo.listing_date)}")
    return f"• {ipo.name} - " + " · ".join(bits)


def build_weekly_report(week_end: date, listed: list, ds: Optional[Dataset],
                        track: Optional[str]) -> str:
    """Sunday wrap: what listed in the last 7 days (NSE prices next to the GMP
    we reported) and what is open or upcoming, from our latest update."""
    L = ["*📅 WEEKLY IPO WRAP*", f"🗓️ Week ending {week_end.strftime('%d %b %Y')}", ""]
    L.append("*🏁 LISTED THIS WEEK*")
    L.append("")
    if listed:
        up = sum(1 for r in listed if r.listing_gain_pct is not None and r.listing_gain_pct > 0)
        L.append(f"{len(listed)} Mainboard IPO(s) we covered listed; {up} opened above the issue price.")
        L.append("")
        for r in listed:
            L += _listing_lines(r, compact=True) + [""]
        L.append("_Gap = actual listing gain minus the GMP % we last reported._")
    else:
        L.append("None of the IPOs we covered listed this week.")
    L.append("")
    L.append("*🔜 COMING UP*")
    coming = (ds.published + ds.awaiting) if ds is not None else []
    if coming:
        when = ds.run_date.strftime("%d %b") if ds.run_date else ""
        L.append(f"_From our {when} update._")
        L.append("")
        for ipo in coming:
            L.append(_coming_line(ipo))
    else:
        L += ["", "Nothing open or announced in our latest update."]
    L.append("")
    if track:
        L += [track_block(track), ""]
    L += ["⚠️ _GMP is unofficial and can change before listing._",
          f"Source: NSE (prices), {SOURCE_NAME} (GMP and dates)"]
    return "\n".join(L) + "\n"


CAPTION_LIMIT = 960          # Telegram allows 1024 characters on a photo caption


def build_caption(ds: Dataset) -> str:
    """Compact WhatsApp-ready summary to ride along with the image.

    Telegram passes a photo's caption on when it is shared to another app, so
    one share can carry the picture and these lines together. One line per
    IPO, ranked by GMP %, trimmed to fit the caption limit.
    """
    d = ds.run_date.strftime("%d %b") if ds.run_date else ""
    head = f"*📊 IPO Watch | {d}*"
    tail = "_Full numbers in the image. GMP is unofficial._"
    lines = []
    for ipo in rank_by_gmp(ds):
        dot = "🟢" if ipo.status.value == "Open" else "🔵"
        arrow = f" {ipo.trend.text()}" if ipo.trend and ipo.trend.status == "ok" else ""
        label = ipo.closes_label(ds.run_date)
        closing = f" ⏰ {label.lower()}" if label in ("Closes today", "Closes tomorrow") else ""
        lines.append(f"{dot} {ipo.name} | *{ipo.gmp_pct_text}* ({ipo.gmp_text}){arrow}{closing}")
    out = [head, ""]
    used = len(head) + len(tail) + 4
    shown = 0
    for line in lines:
        if used + len(line) + 1 > CAPTION_LIMIT:
            break
        out.append(line)
        used += len(line) + 1
        shown += 1
    if shown < len(lines):
        out.append(f"+{len(lines) - shown} more in the image")
    return "\n".join(out + ["", tail])
