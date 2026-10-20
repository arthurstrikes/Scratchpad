"""Deterministic HTML -> PNG creative (spec section 7).

No generative imaging anywhere. Every figure is interpolated into the DOM as
text from the verified dataset, and each figure element carries a
`data-verify` key so verify.py can read the numbers back out of the rendered
page and prove the image matches the dataset.

Visual language is the Loop / Inner Circle house style shared with the Loop
and India Stock Watch apps: dark #111 ground, the orange striped band as the
masthead, DM Sans for words, Bebas Neue for figures, 4px corners, and colour
used for status only (green = positive GMP, orange = brand / high GMP).
Sizes are roughly 3x the apps' phone tokens because the PNG is 1080px wide
and read at about a third of that in a chat thread.
"""
from __future__ import annotations

import html
import os
from typing import Optional

from .config import CHROMIUM_PATH, GMP_HIGHLIGHT_THRESHOLD_PCT, SOURCE_NAME
from .fonts import DISPLAY_STACK, FONT_STACK, font_face_css
from .listing import strip_listings
from .merge import Dataset, rank_by_gmp
from .report import glance_text, subscription_stale_date
from .models import IPO

CARD_W = 1080
# WhatsApp crops very tall images in the chat thread, so the card is held to
# 4:5 or squarer by stepping through denser layout tiers until it fits.
MAX_H = 1350
TIERS = (0, 1, 2, 3)

CSS = f"""
:root{{
  --bg:#111111; --surface:#1A1A1A; --surface-2:#202020; --line:#2A2A2A;
  --ink:#F5F5F5; --ink-2:#B0B0B0; --ink-3:#8A8A8A;
  --brand:#FF6B35; --brand-soft:#2A1810; --brand-fill:#C94A1A; --brand-fill-2:#9E3410;
  --good:#4CAF50; --bad:#FF4444; --warn:#F5B301; --warn-soft:#2B2410;
  --band-v:24px; --band-b:22px; --h1:44px; --when:60px; --gap:22px;
  --pad:13px; --nm:28px; --sub:20px; --pct:52px; --kv:44px; --fine:17px;
}}
.t1{{--band-v:18px; --band-b:16px; --h1:38px; --when:50px; --gap:16px;
    --pad:10px; --nm:26px; --sub:18px; --pct:46px; --kv:38px; --fine:16px}}
.t2{{--band-v:14px; --band-b:12px; --h1:34px; --when:44px; --gap:12px;
    --pad:7px; --nm:24px; --sub:17px; --pct:41px; --kv:34px; --fine:15px}}
.t3{{--band-v:10px; --band-b:8px; --h1:30px; --when:36px; --gap:8px;
    --pad:7px; --nm:23px; --sub:16.5px; --pct:38px; --kv:30px; --fine:14.5px}}
.t3 .eyebrow{{margin-bottom:4px;font-size:12px}}
.t3 .glance{{padding-top:8px;font-size:17px}}
.t3 .tile .tn{{font-size:13.5px;margin-top:2px}}
.t3 .tile{{padding:9px 14px 8px}}
.t3 .kpi{{padding:7px 16px 6px}}
.t3 .kpi .kn{{margin-top:2px;font-size:16px}}
.t3 .kpis{{margin-top:12px}}
.t3 .ftr{{margin-top:10px;padding-top:8px}}
.t3 .legend{{font-size:13px;line-height:1.45;margin-bottom:6px}}
.t3 .src{{font-size:13px}}
.t3 .sheet,.sheet.t3{{padding-bottom:12px}}
.t3 .sec-h{{margin-bottom:6px}}
.t3 .flag,.t3 .urg{{padding-top:3px;padding-bottom:2px}}
.t3 .tr,.t3 .rs{{font-size:16px}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{CARD_W}px;background:var(--bg);color:var(--ink);font-family:{FONT_STACK};
     -webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums lining-nums}}
.sheet{{background:var(--bg);padding-bottom:22px}}
.num{{font-family:{DISPLAY_STACK};font-weight:400;line-height:1;letter-spacing:.5px}}

/* ---------- signature: the orange band ---------- */
.band{{position:relative;overflow:hidden;color:#fff;padding:var(--band-v) 40px var(--band-b);
      background:linear-gradient(135deg,var(--brand-fill) 0%,var(--brand-fill-2) 100%);
      display:flex;justify-content:space-between;align-items:flex-end;gap:24px}}
.band:after{{content:"";position:absolute;inset:0;opacity:.13;pointer-events:none;
      background:repeating-linear-gradient(45deg,#fff 0 5px,transparent 5px 26px)}}
.band>*{{position:relative;z-index:1}}
.eyebrow{{font-size:14px;font-weight:700;letter-spacing:5px;text-transform:uppercase;
         opacity:.82;margin-bottom:10px}}
h1{{font-size:var(--h1);font-weight:700;line-height:1;letter-spacing:.3px}}
.when{{text-align:right;flex:none}}
.when .num{{font-size:var(--when);display:block}}
.when small{{display:block;font-size:15px;font-weight:700;letter-spacing:4px;
            text-transform:uppercase;opacity:.82;margin-top:6px}}

main{{padding:4px 40px 0}}

/* ---------- section headers ---------- */
.sec-h{{display:flex;align-items:center;gap:12px;margin:var(--gap) 2px 10px}}
.sec-h h2{{font-size:16px;font-weight:500;letter-spacing:4.5px;text-transform:uppercase;
          color:var(--ink-3)}}
.sec-h .dot{{width:11px;height:11px;border-radius:50%;flex:none}}
.dot.open{{background:var(--good)}}
.dot.up{{background:var(--brand)}}
.dot.lst{{background:var(--ink-3)}}
.lrow{{display:flex;align-items:center;gap:20px;padding:calc(var(--pad) - 3px) 24px calc(var(--pad) - 3px) 27px;
      border-top:1px solid var(--line)}}
.lrow:first-child{{border-top:0}}
.lrow .lname{{flex:1;min-width:0;display:flex;align-items:center;gap:12px}}
.lrow .nm{{font-size:calc(var(--nm) - 2px);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.lrow .flag{{color:var(--ink-3);white-space:nowrap}}
.lm{{display:flex;align-items:baseline;gap:8px;flex:none}}
.lm .fl{{font-size:13px}}
.sec-h.slim{{margin-top:calc(var(--gap) - 6px);margin-bottom:6px}}
.sec-h.slim .num{{font-size:22px}}
.sv{{font-size:34px}}
.sv.up{{color:var(--good)}} .sv.down{{color:var(--bad)}} .sv.flat{{color:var(--ink-3)}} .sv.neutral{{color:var(--ink-2)}}
.sec-h .rule{{flex:1;height:1px;background:var(--line)}}
.sec-h .num{{font-size:30px;color:var(--ink-2)}}

/* ---------- IPO rows ----------
   Two lines per IPO inside one list, divided by hairlines - the India Stock
   Watch watchlist pattern. Keeps a full day near a square image. */
.rows{{background:var(--surface);border:1px solid var(--line);border-radius:6px;overflow:hidden}}
.row{{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:24px;
     padding:var(--pad) 24px var(--pad) 22px;border-top:1px solid var(--line);border-left:5px solid transparent}}
.row:first-child{{border-top:0}}
.row.hot{{border-left-color:var(--brand)}}
.nmrow{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;min-width:0}}
.nm{{font-size:var(--nm);font-weight:700;line-height:1.15;letter-spacing:.2px}}
/* urgency: filled amber pills, deliberately unlike the outlined orange High GMP tag */
.urg{{font-size:12.5px;font-weight:700;letter-spacing:2.4px;text-transform:uppercase;
     border-radius:12px;padding:5px 11px 4px;white-space:nowrap}}
.urg.today{{background:var(--warn);color:#111}}
.urg.tomorrow{{background:var(--warn-soft);color:var(--warn)}}
.chg{{font-size:calc(var(--sub) - 3px);font-weight:700;white-space:nowrap}}
.chg.up{{color:var(--good)}} .chg.down{{color:var(--bad)}} .chg.flat{{color:var(--ink-3)}}
.glance{{font-size:20px;font-weight:500;color:var(--ink-2);padding:14px 2px 0;letter-spacing:.2px}}
.tiles{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}}
.tile{{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:12px 16px 11px}}
.tile .kl{{font-size:12.5px;font-weight:500;letter-spacing:2.6px;text-transform:uppercase;color:var(--ink-3)}}
.tile .tv{{font-size:calc(var(--kv) - 2px);margin-top:6px;color:var(--ink)}}
.tile .tv.up{{color:var(--good)}} .tile .tv.down{{color:var(--bad)}}
.tile .tn{{font-size:14.5px;color:var(--ink-3);margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.sec-h.slim2{{margin-top:calc(var(--gap) - 4px);margin-bottom:8px}}
.arow{{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:20px;
      padding:calc(var(--pad) - 2px) 24px calc(var(--pad) - 2px) 27px;border-top:1px solid var(--line)}}
.arow:first-child{{border-top:0}}
.arow .pct{{font-size:calc(var(--pct) - 6px)}}
.flag{{font-size:12.5px;font-weight:700;letter-spacing:2.6px;text-transform:uppercase;
      color:var(--brand);border:1.5px solid currentColor;border-radius:3px;padding:5px 7px 4px}}
.sub{{display:flex;align-items:baseline;flex-wrap:wrap;gap:6px 0;margin-top:5px;
     font-size:var(--sub);color:var(--ink-2)}}
.f{{display:inline-flex;align-items:baseline;gap:8px}}
.f+.f:before{{content:"·";color:var(--ink-3);margin:0 14px}}
.fl{{font-size:14px;font-weight:500;letter-spacing:2.6px;text-transform:uppercase;color:var(--ink-3)}}
.fv{{font-weight:500;color:var(--ink)}}
.fv.na{{color:var(--ink-3);font-weight:400;font-style:italic}}
.gmp{{text-align:right;flex:none}}
.pct{{display:block;font-size:var(--pct);color:var(--good);white-space:nowrap}}
.pct.flat{{color:var(--ink-3)}}
.pct.neg{{color:var(--bad)}}
.gmp2{{display:flex;align-items:center;justify-content:flex-end;gap:11px;margin-top:3px}}
.rs{{font-size:19px;font-weight:500;color:var(--ink-3);white-space:nowrap}}
.tr{{font-size:19px;font-weight:700;white-space:nowrap;font-variant-numeric:tabular-nums}}
.tr.up{{color:var(--good)}} .tr.down{{color:var(--bad)}} .tr.flat{{color:var(--ink-3)}}
.tr.new{{color:var(--brand);font-size:14px;letter-spacing:2.4px;text-transform:uppercase;
        border:1.5px solid currentColor;border-radius:3px;padding:3px 6px 2px}}
.tr.na{{color:var(--ink-3);font-weight:400;font-style:italic;font-size:16px}}
svg.spark{{display:block;flex:none}}
.lab{{display:block;font-size:13px;font-weight:500;letter-spacing:3px;text-transform:uppercase;color:var(--ink-3);margin-bottom:2px}}
.fine{{display:flex;flex-wrap:wrap;gap:2px 0;margin-top:4px;font-size:var(--fine);color:var(--ink-3)}}
.fine .f+.f:before{{margin:0 12px}}
.fine .fl{{font-size:12.5px}}
.fine .fv{{color:var(--ink-2);font-weight:500}}
.empty{{background:var(--surface);border:1px dashed var(--line);border-radius:6px;
       padding:24px;text-align:center;color:var(--ink-3);font-size:19px}}

/* ---------- leaders: the KPI strip ---------- */
.kpis{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:22px}}
.kpi{{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:13px 18px 12px}}
.kpi .kl{{font-size:13.5px;font-weight:500;letter-spacing:3px;text-transform:uppercase;color:var(--ink-3)}}
.kpi .kv{{font-size:var(--kv);margin-top:8px;color:var(--ink)}}
.kpi .kv.good{{color:var(--good)}}
.kpi .kn{{font-size:18px;font-weight:700;color:var(--ink-2);margin-top:6px;
         overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.kpi .kn.na{{color:var(--ink-3);font-weight:400;font-style:italic}}

/* ---------- footer ---------- */
.ftr{{margin-top:20px;padding-top:14px;border-top:1px solid var(--line)}}
.warn{{background:var(--brand-soft);border-left:4px solid var(--brand);border-radius:4px;
      padding:12px 16px;font-size:15px;color:var(--ink);margin-bottom:14px;line-height:1.55}}
.legend{{font-size:15px;color:var(--ink-3);line-height:1.6;margin-bottom:10px}}
.legend span+span:before{{content:"·";margin:0 12px}}
.src{{display:flex;justify-content:space-between;align-items:center;gap:16px;
     font-size:15px;color:var(--ink-3)}}
.src b{{color:var(--ink-2);font-weight:700}}
.src .stale{{color:var(--warn)}}
"""


def _e(s: object) -> str:
    return html.escape(str(s), quote=True)


def _field(label: str, value: str, key: str, na: bool) -> str:
    cls = "fv na" if na else "fv"
    lab = f'<span class="fl">{_e(label)}</span>' if label else ""
    return f'<span class="f">{lab}<span class="{cls}" data-verify="{_e(key)}">{_e(value)}</span></span>'


def _pct_class(ipo: IPO) -> str:
    if ipo.gmp_pct is None or ipo.gmp_pct == 0:
        return "pct num flat"
    return "pct num" if ipo.gmp_pct > 0 else "pct num neg"


_SPARK = {"up": "#4CAF50", "down": "#FF4444", "flat": "#8A8A8A"}


def _spark(ipo: IPO) -> str:
    """Tiny GMP line for the last days. Pure graphic: every number it is
    drawn from is already in the dataset; no text, so nothing to verify."""
    t = ipo.trend
    if not t or t.status != "ok" or len(t.series) < 2:
        return ""
    vals = [float(v) for v in t.series]
    lo, hi = min(vals), max(vals)
    w, h, pad = 76, 28, 3
    span = (hi - lo) or 1.0
    pts = [(pad + i * (w - 2 * pad) / (len(vals) - 1),
            h - pad - (v - lo) / span * (h - 2 * pad) if hi != lo else h / 2)
           for i, v in enumerate(vals)]
    col = _SPARK[t.direction or "flat"]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    lx, ly = pts[-1]
    return (f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<polyline points="{line}" fill="none" stroke="{col}" stroke-width="2.6" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.6" fill="{col}"/></svg>')


def _trend_chip(ipo: IPO, kid: str) -> str:
    text = ipo.trend_text
    if text is None:
        return ""
    t = ipo.trend
    cls = "new" if t.status == "new" else (t.direction or "na")
    return f'<span class="tr {cls}" data-verify="{kid}.trend">{_e(text)}</span>'


def _chg_class(text: str) -> str:
    return "up" if text.startswith("▲") else "down" if text.startswith("▼") else "flat"


def _sub_field(ipo: IPO, kid: str, which: str) -> str:
    """Retail or Total with its change since our last report, only when meaningful."""
    chg = ipo.sub_change_short(which)
    extra = (f'<span class="chg {_chg_class(chg)}" data-verify="{kid}.{which}_chg">{_e(chg)}</span>'
             if chg else "")
    na = (ipo.retail_sub if which == "retail" else ipo.total_sub) is None
    return (f'<span class="f"><span class="fl">{which.title()}</span>'
            f'<span class="{"fv na" if na else "fv"}" data-verify="{kid}.{which}">'
            f'{_e(ipo.retail_text if which == "retail" else ipo.total_text)}</span>{extra}</span>')


def _row(ipo: IPO, idx: int, show_sub: bool, today=None) -> str:
    """One IPO as a two-line row: name above, its figures inline below."""
    kid = f"ipo{idx}"
    hot = " hot" if ipo.is_hot else ""
    flag = '<span class="flag">High GMP</span>' if ipo.is_hot else ""
    closes = ipo.closes_label(today)
    if closes:
        when = "today" if closes == "Closes today" else "tomorrow"
        flag += f'<span class="urg {when}" data-verify="{kid}.closes">{_e(closes)}</span>'

    fields = [
        _field("", ipo.date_range_text, f"{kid}.dates", False),
        _field("", ipo.price_display, f"{kid}.price", False),
    ]
    if show_sub:
        fields.append(_sub_field(ipo, kid, "retail"))
        fields.append(_sub_field(ipo, kid, "total"))
    elif ipo.min_invest_text:
        fields.append(_field("", ipo.min_invest_text, f"{kid}.min", False))

    fine = ""
    if show_sub:
        extra = []
        if ipo.min_invest_text:
            extra.append(_field("", ipo.min_invest_text, f"{kid}.min", False))
        if ipo.allotment_text:
            extra.append(_field("Allotment", ipo.allotment_text, f"{kid}.allot", False))
        if ipo.listing_text:
            extra.append(_field("Listing", ipo.listing_text, f"{kid}.list", False))
        if extra:
            fine = f'<div class="fine">{"".join(extra)}</div>'

    return f"""
    <div class="row{hot}">
      <div>
        <div class="nmrow"><span class="nm" data-verify="{kid}.name">{_e(ipo.name)}</span>{flag}</div>
        <div class="sub">{"".join(fields)}</div>{fine}
      </div>
      <div class="gmp">
        <span class="{_pct_class(ipo)}" data-verify="{kid}.gmppct">{_e(ipo.gmp_pct_text)}</span>
        <div class="gmp2">{_spark(ipo)}<span class="rs">GMP <span data-verify="{kid}.gmp">{_e(ipo.gmp_text)}</span></span>{_trend_chip(ipo, kid)}</div>
      </div>
    </div>"""


def _await_row(ipo: IPO, idx: int) -> str:
    k = f"aw{idx}"
    fields = [_field("", f"Closed {ipo.close_date.strftime('%d %b')}", f"{k}.closed", False),
              _field("Issue", ipo.price_display, f"{k}.price", False),
              _field("Retail", ipo.retail_text, f"{k}.retail", ipo.retail_sub is None),
              _field("Total", ipo.total_text, f"{k}.total", ipo.total_sub is None)]
    dates = []
    if ipo.allotment_text:
        dates.append(_field("Allotment", ipo.allotment_text, f"{k}.allot", False))
    if ipo.listing_text:
        dates.append(_field("Listing", ipo.listing_text, f"{k}.list", False))
    fine = f'<div class="fine">{"".join(dates)}</div>' if dates else ""
    return f"""
    <div class="arow">
      <div>
        <div class="nmrow"><span class="nm" data-verify="{k}.name">{_e(ipo.name)}</span></div>
        <div class="sub">{"".join(fields)}</div>{fine}
      </div>
      <div class="gmp">
        <span class="{_pct_class(ipo)}" data-verify="{k}.gmppct">{_e(ipo.gmp_pct_text)}</span>
        <div class="gmp2"><span class="rs">GMP <span data-verify="{k}.gmp">{_e(ipo.gmp_text)}</span></span></div>
      </div>
    </div>"""


def _track_tiles(tr) -> str:
    def tile(label: str, value: Optional[str], note: str, key: str, tone: str = "") -> str:
        if value is None:
            return ""
        return (f'<div class="tile"><div class="kl">{_e(label)}</div>'
                f'<div class="tv num {tone}" data-verify="{key}">{_e(value)}</div>'
                f'<div class="tn">{_e(note)}</div></div>')
    sign = lambda t: "up" if t.startswith("+") else "down" if t.startswith("-") else ""  # noqa: E731
    return f"""<div class="sec-h slim2"><span class="dot lst"></span><h2 data-verify="trk.title">{_e(tr.title)}</h2><span class="rule"></span></div>
    <div class="tiles">
      {tile("Avg listing gain", tr.gain_text, "issue price → first-day open", "trk.gain", sign(tr.gain_text))}
      {tile("Opened above issue", tr.up_text, "listings that gained on day one", "trk.up")}
      {tile("Avg first day", tr.day1_text, "open → close", "trk.day1", sign(tr.day1_text or ""))}
      {tile("GMP accuracy", tr.acc_text, tr.acc_note or "", "trk.acc") if tr.acc_text else ""}
    </div>"""


def _section(title: str, dot: str, rows: list[str], empty: str) -> str:
    body = f'<div class="rows">{"".join(rows)}</div>' if rows else f'<div class="empty">{_e(empty)}</div>'
    return (f'<div class="sec-h"><span class="dot {dot}"></span><h2>{_e(title)}</h2>'
            f'<span class="rule"></span><span class="num">{len(rows)}</span></div>{body}')


def _leaders(ds: Dataset) -> str:
    from .merge import leader
    ranked = rank_by_gmp(ds)
    top_gmp = next((i for i in ranked if i.gmp_pct is not None), None)
    top_ret = leader(ds, "retail_sub")
    top_tot = leader(ds, "total_sub")

    def box(label: str, ipo: Optional[IPO], value: str, key: str, good: bool) -> str:
        if ipo is None:
            return (f'<div class="kpi"><div class="kl">{_e(label)}</div>'
                    f'<div class="kv num" style="color:var(--ink-3)">—</div>'
                    f'<div class="kn na">Not updated</div></div>')
        cls = "kv num good" if good else "kv num"
        return (f'<div class="kpi"><div class="kl">{_e(label)}</div>'
                f'<div class="{cls}" data-verify="{key}.val">{_e(value)}</div>'
                f'<div class="kn" data-verify="{key}.name">{_e(ipo.name)}</div></div>')

    return f"""<div class="kpis">
      {box("Highest GMP", top_gmp, top_gmp.gmp_pct_text if top_gmp else "", "lead_gmp", True)}
      {box("Top Retail", top_ret, top_ret.retail_text if top_ret else "", "lead_ret", False)}
      {box("Top Total", top_tot, top_tot.total_text if top_tot else "", "lead_tot", False)}
    </div>"""


def build_html(ds: Dataset, tier: int = 0, strip_rows: Optional[int] = None) -> str:
    """strip_rows: how many Recently-listed rows to draw (None = all that qualify, 0 = none)."""
    date_txt = ds.run_date.strftime("%d %b %Y") if ds.run_date else ""

    open_rows = [_row(i, n, True, ds.run_date) for n, i in enumerate(ds.open_ipos)]
    off = len(ds.open_ipos)
    up_rows = [_row(i, off + n, False, ds.run_date) for n, i in enumerate(ds.upcoming_ipos)]

    await_html = ""
    if ds.awaiting:
        await_html = (
            '<div class="sec-h"><span class="dot up"></span><h2>Closed · awaiting listing</h2>'
            f'<span class="rule"></span><span class="num">{len(ds.awaiting)}</span></div>'
            '<div class="rows">' + "".join(_await_row(i, n) for n, i in enumerate(ds.awaiting)) + "</div>")
    track_html = _track_tiles(ds.track_record) if ds.track_record else ""

    strip = strip_listings(ds.recent_listings, ds.run_date)
    strip = strip if strip_rows is None else strip[:strip_rows]
    strip_html = ""
    if strip:
        strip_html = (
            '<div class="sec-h slim"><span class="dot lst"></span><h2>Recently listed · NSE</h2>'
            f'<span class="rule"></span><span class="num">{len(strip)}</span></div>'
            '<div class="rows">' + "".join(_strip_row(r, i) for i, r in enumerate(strip)) + "</div>")

    stamps = []
    if ds.subscription_timestamp:
        stamps.append(f"Subscription {_e(ds.subscription_timestamp)}")
    if ds.gmp_timestamp:
        stamps.append(f"GMP {_e(ds.gmp_timestamp)}")
    cls = ' class="stale"' if subscription_stale_date(ds) else ""
    stamp_html = f'<div{cls}>{" &nbsp;·&nbsp; ".join(stamps)}</div>' if stamps else "<div></div>"

    warn_html = ""
    if ds.warnings:
        items = "<br>".join(_e(w) for w in ds.warnings[:4])
        warn_html = f'<div class="warn">{items}</div>'

    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>{font_face_css()}{CSS}</style></head>
<body><div class="sheet t{tier}">
  <div class="band">
    <div><div class="eyebrow">Daily update · Mainboard</div><h1>IPO Watch</h1></div>
    <div class="when"><span class="num">{_e(date_txt)}</span><small>5:00 PM IST</small></div>
  </div>
  <main>
    <div class="glance" data-verify="glance">{_e(glance_text(ds))}</div>
    {_section("Open now", "open", open_rows, "No Mainboard IPOs are open today.")}
    {_section("Upcoming", "up", up_rows, "No Mainboard IPOs are scheduled yet.")}
    {await_html}
    {strip_html}
    {_leaders(ds)}
    {track_html}
    <div class="ftr">
      {warn_html}
      <div class="legend"><span>GMP = Grey Market Premium</span><span>High GMP = above {GMP_HIGHLIGHT_THRESHOLD_PCT:g}%</span><span>▲/▼ = change since our previous update</span>{"<span>Awaiting listing = closed, GMP above " + f"{GMP_HIGHLIGHT_THRESHOLD_PCT:g}" + "%</span>" if ds.awaiting else ""}<span>GMP % on upper price band</span><span>GMP is unofficial and can change before listing</span>{"<span>Listed = issue to first-day open · Day 1 = open to close · GMP said = last reported</span>" if strip else ""}</div>
      <div class="src"><div>Source: <b>{_e(SOURCE_NAME)}</b></div>{stamp_html}</div>
    </div>
  </main>
</div></body></html>"""


def _sv_class(p) -> str:
    return "flat" if p is None or p == 0 else ("up" if p > 0 else "down")


def _strip_row(r, idx: int) -> str:
    """One slim line per recent listing: name, date, listing gain, day 1, GMP said."""
    k = f"rl{idx}"
    gmp = (f'<div class="lm"><span class="fl">GMP said</span>'
           f'<span class="sv neutral num" data-verify="{k}.gmp">{_e(r.gmp_said_pct_text)}</span></div>'
           if r.gmp_said_pct_text else "")
    return f"""
    <div class="lrow">
      <div class="lname"><span class="nm" data-verify="{k}.name">{_e(r.name)}</span>
        <span class="flag" data-verify="{k}.date">{_e(r.listing_date.strftime("%d %b"))}</span></div>
      <div class="lm"><span class="fl">Listed</span><span class="sv {_sv_class(r.listing_gain_pct)} num" data-verify="{k}.gain">{_e(r.listing_gain_text)}</span></div>
      <div class="lm"><span class="fl">Day 1</span><span class="sv {_sv_class(r.day1_pct)} num" data-verify="{k}.day1">{_e(r.day1_text)}</span></div>
      {gmp}
    </div>"""


def _listing_row(r, idx: int) -> str:
    k = f"l{idx}"
    gain = r.listing_gain_pct
    gcls = "pct num flat" if gain is None or gain == 0 else ("pct num" if gain > 0 else "pct num neg")
    d1 = r.day1_pct
    dcls = "flat" if d1 is None or d1 == 0 else ("up" if d1 > 0 else "down")
    fine = ""
    if r.gmp_said_text:
        extra = [_field("GMP said", r.gmp_said_text, f"{k}.gmp", False)]
        if r.gap_text:
            extra.append(_field("Gap", r.gap_text, f"{k}.gap", False))
        fine = f'<div class="fine">{"".join(extra)}</div>'
    return f"""
    <div class="row">
      <div>
        <div class="nmrow"><span class="nm" data-verify="{k}.name">{_e(r.name)}</span>
          <span class="flag" data-verify="{k}.symbol">{_e(r.symbol)}</span></div>
        <div class="sub">{_field("Issue", r.issue_text, f"{k}.issue", False)}{_field("Open", r.open_text, f"{k}.open", False)}{_field("Close", r.close_text, f"{k}.close", False)}</div>{fine}
      </div>
      <div class="gmp">
        <span class="lab">At listing</span>
        <span class="{gcls}" data-verify="{k}.gain">{_e(r.listing_gain_text)}</span>
        <div class="gmp2"><span class="rs">DAY 1</span><span class="tr {dcls}" data-verify="{k}.day1">{_e(r.day1_text)}</span></div>
      </div>
    </div>"""


def build_listing_html(results: list, run_date, tier: int = 0) -> str:
    """The listing-day scorecard card, in the same house style as the daily image."""
    date_txt = run_date.strftime("%d %b %Y") if run_date else ""
    rows = "".join(_listing_row(r, i) for i, r in enumerate(results))
    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>{font_face_css()}{CSS}</style></head>
<body><div class="sheet t{tier}">
  <div class="band">
    <div><div class="eyebrow">Listing day · NSE</div><h1>Listing Scorecard</h1></div>
    <div class="when"><span class="num">{_e(date_txt)}</span><small>Actual vs GMP</small></div>
  </div>
  <main>
    <div class="sec-h"><span class="dot open"></span><h2>Listed today</h2><span class="rule"></span><span class="num">{len(results)}</span></div>
    <div class="rows">{rows}</div>
    <div class="ftr">
      <div class="legend"><span>Issue = NSE base price</span><span>Listing gain = issue to first-day open</span><span>Day 1 = open to close</span></div>
      <div class="legend"><span>Gap = listing gain minus the GMP % last reported</span><span>GMP is unofficial</span></div>
      <div class="src"><div>Prices: <b>NSE</b> · GMP: <b>{_e(SOURCE_NAME)}</b></div><div></div></div>
    </div>
  </main>
</div></body></html>"""


_LAST: dict = {"tier": 0, "width": CARD_W, "height": 0, "listings": 0}


def last_render_info() -> dict:
    """Layout tier, CSS-pixel size and whether the listings strip made it in."""
    return dict(_LAST)


def _render(candidates, out_path: str, scale: int = 2):
    """Render the first candidate that fits 4:5 (else the last, tightest one) and
    read every figure back out of the live DOM.

    `candidates` is a list of (meta, html_builder) in order of preference.
    Returns (rendered, meta, height)."""
    from playwright.sync_api import sync_playwright

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    html_path = os.path.splitext(out_path)[0] + ".html"
    kwargs = {"args": ["--no-sandbox", "--disable-dev-shm-usage",
                       "--force-color-profile=srgb", "--font-render-hinting=none"]}
    if CHROMIUM_PATH and os.path.exists(CHROMIUM_PATH):
        kwargs["executable_path"] = CHROMIUM_PATH

    with sync_playwright() as p:
        browser = p.chromium.launch(**kwargs)
        page = browser.new_page(viewport={"width": CARD_W, "height": 800},
                                device_scale_factor=scale)
        for n, (meta, build) in enumerate(candidates):
            html_doc = build()
            page.set_content(html_doc, wait_until="load")
            page.wait_for_timeout(300)
            height = page.eval_on_selector(".sheet", "e => Math.ceil(e.getBoundingClientRect().height)")
            if height <= MAX_H or n == len(candidates) - 1:
                break
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(html_doc)
        rendered = page.eval_on_selector_all(
            "[data-verify]",
            "els => Object.fromEntries(els.map(e => [e.dataset.verify, e.textContent.trim()]))",
        )
        # Shoot the sheet element, not the page: the card then crops exactly
        # to its content instead of being padded out to the viewport height.
        page.locator(".sheet").screenshot(path=out_path)
        browser.close()
    return rendered, meta, height


def render_png(ds: Dataset, out_path: str, scale: int = 2) -> tuple[str, dict[str, str]]:
    """Render the daily creative. Returns (png_path, rendered) where `rendered`
    maps each data-verify key to the text actually painted on the image;
    verify.py compares that against the dataset before the PNG is accepted.

    Preference order: roomiest layout tier with the Recently-listed strip, then
    denser tiers with it, and only if none fits 4:5 the same tiers without it
    (the listings are then still in the text report)."""
    n_strip = len(strip_listings(ds.recent_listings, ds.run_date))
    variants = [(n, t) for n in range(n_strip, 0, -1) for t in TIERS]
    variants += [(0, t) for t in TIERS]
    candidates = [((n, t), (lambda n=n, t=t: build_html(ds, t, n))) for n, t in variants]
    rendered, (n, tier), height = _render(candidates, out_path, scale)
    _LAST.update(tier=tier, width=CARD_W, height=height, listings=n)
    return out_path, rendered


def render_listing_png(results: list, run_date, out_path: str,
                       scale: int = 2) -> tuple[str, dict[str, str]]:
    """Render the listing-day scorecard card (checked by verify.check_listing)."""
    candidates = [(t, (lambda t=t: build_listing_html(results, run_date, t))) for t in TIERS]
    rendered, tier, height = _render(candidates, out_path, scale)
    _LAST.update(tier=tier, width=CARD_W, height=height, listings=0)
    return out_path, rendered
