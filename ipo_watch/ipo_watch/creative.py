"""Deterministic HTML -> PNG creative (spec section 7).

No generative imaging anywhere. Every figure is interpolated into the DOM as
text from the verified dataset, and each figure element carries a
`data-verify` key so verify.py can read the numbers back out of the rendered
page and prove the image matches the dataset.

Design notes - this is read at roughly a third of its native width in a chat
thread, so the layout is tuned for that: large hierarchy jumps, GMP % as the
hero figure rather than GMP in rupees, tabular figures so columns of numbers
align, and a comparison bar on every card so the set can be ranked by eye
without reading a single digit.
"""
from __future__ import annotations

import html
import os
from decimal import Decimal
from typing import Optional

from .config import CHROMIUM_PATH, SOURCE_NAME
from .fonts import FONT_STACK, font_face_css
from .merge import Dataset, rank_by_gmp
from .models import IPO

CARD_W = 1080

CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{CARD_W}px;background:#05090F;font-family:{FONT_STACK};
     -webkit-font-smoothing:antialiased;
     font-variant-numeric:tabular-nums lining-nums;
     font-feature-settings:"tnum" 1,"lnum" 1}}
.sheet{{background:
   radial-gradient(1100px 420px at 78% -10%,rgba(45,110,255,.15),transparent 60%),
   linear-gradient(172deg,#0A1526 0%,#08111F 48%,#060C16 100%);
   padding:30px 32px 24px}}

/* ---------- masthead ---------- */
.hdr{{display:flex;justify-content:space-between;align-items:center;
     padding-bottom:16px;border-bottom:1px solid #17263F;position:relative}}
.hdr:after{{content:"";position:absolute;left:0;bottom:-1px;width:110px;height:3px;
     background:linear-gradient(90deg,#16E07E,#3D8BFF);border-radius:2px}}
.brand{{display:flex;align-items:center;gap:13px}}
.mark{{width:44px;height:44px;border-radius:12px;flex-shrink:0;
      background:linear-gradient(140deg,#2D6EFF,#12C8F0);
      display:flex;align-items:center;justify-content:center}}
h1{{font-size:33px;font-weight:900;color:#fff;letter-spacing:-.5px;line-height:1}}
.tag{{font-size:12px;font-weight:500;color:#6E86A8;margin-top:6px;letter-spacing:2.2px}}
.datebox{{text-align:right;flex-shrink:0}}
.datebox .d{{font-size:22px;font-weight:900;color:#fff;letter-spacing:-.2px}}
.datebox .t{{font-size:12px;font-weight:500;color:#6E86A8;margin-top:4px;letter-spacing:1.4px}}

/* ---------- section headers ---------- */
.sect{{display:flex;align-items:center;gap:11px;margin:20px 0 10px}}
.dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
.dot.open{{background:#16E07E;box-shadow:0 0 12px rgba(22,224,126,.7)}}
.dot.up{{background:#3D8BFF;box-shadow:0 0 12px rgba(61,139,255,.7)}}
.sect h2{{font-size:18px;font-weight:900;color:#EAF2FF;letter-spacing:2.4px}}
.sect .n{{font-size:13px;font-weight:700;color:#5D74A0}}
.sect .rule{{flex:1;height:1px;background:linear-gradient(90deg,#1B2B47,transparent)}}

/* ---------- IPO row ----------
   Two lines per IPO rather than a card. A card carries ~130px of height for
   six numbers; this carries the same six in ~84px, which is what keeps a
   full day legible on a phone instead of scrolling past the fold. */
.row{{display:flex;align-items:center;justify-content:space-between;gap:18px;
     background:linear-gradient(180deg,#0E1A2E,#0B1524);border:1px solid #1A2A44;
     border-radius:13px;padding:14px 20px;margin-bottom:8px;position:relative}}
.row.hot{{border-color:#1C6B48;
     background:linear-gradient(110deg,#0F2A24 0%,#0D1D30 42%,#0B1524 100%)}}
.row.hot:before{{content:"";position:absolute;left:-1px;top:12px;bottom:12px;width:3px;
     background:linear-gradient(180deg,#16E07E,#0B9B57);border-radius:3px}}
.main{{min-width:0;flex:1}}
.nmrow{{display:flex;align-items:center;gap:11px;flex-wrap:wrap}}
.nm{{font-size:26px;font-weight:700;color:#fff;letter-spacing:-.4px;line-height:1.1}}
.pill{{padding:3px 9px;border-radius:5px;background:rgba(22,224,126,.14);
      border:1px solid rgba(22,224,126,.42);color:#16E07E;
      font-size:10px;font-weight:900;letter-spacing:1.3px}}
.sub{{display:flex;align-items:center;gap:11px;margin-top:9px;flex-wrap:wrap}}
.f{{display:flex;align-items:center;gap:7px}}
.fl{{font-size:12px;font-weight:700;color:#63799A;letter-spacing:1.1px}}
.fv{{font-size:18px;font-weight:700;color:#DDE8F7;letter-spacing:-.1px}}
.fv.na{{color:#6A7E9E;font-weight:400;font-style:italic;font-size:16px}}
.sep{{width:3px;height:3px;border-radius:50%;background:#2A4165;flex-shrink:0}}

.gmp{{text-align:right;flex-shrink:0;display:flex;align-items:baseline;gap:10px}}
.pct{{font-size:30px;font-weight:900;color:#16E07E;letter-spacing:-.8px;white-space:nowrap}}
.pct.flat{{color:#7E93B2}}
.rs{{font-size:17px;font-weight:500;color:#8CA1C0;white-space:nowrap}}

.empty{{background:#0A1424;border:1px dashed #1E3050;border-radius:12px;
       padding:20px;text-align:center;color:#6E86A8;font-size:16px;font-weight:500}}

/* ---------- leaders + footer ---------- */
.leaders{{display:flex;gap:9px;margin-top:9px}}
.lead{{flex:1;background:#0A1322;border:1px solid #17263F;border-radius:12px;
      padding:12px 15px;min-width:0}}
.lead .k{{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:700;
      color:#63799A;letter-spacing:1.1px;margin-bottom:7px}}
.lead .lv{{font-size:17px;font-weight:700;color:#EAF2FF;
      overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.lead .lx{{font-size:16px;font-weight:900;color:#16E07E;margin-top:3px}}

.ftr{{margin-top:16px;padding-top:13px;border-top:1px solid #17263F}}
.warn{{background:rgba(224,178,58,.06);border:1px solid rgba(224,178,58,.24);
      border-radius:9px;padding:10px 13px;font-size:12.5px;font-weight:500;
      color:#D2B45E;margin-bottom:11px;line-height:1.6}}
.legend{{display:flex;flex-wrap:wrap;gap:6px 22px;margin-bottom:9px}}
.legend div{{display:flex;align-items:center;gap:6px;font-size:12.5px;
      font-weight:500;color:#7E93B2}}
.src{{display:flex;justify-content:space-between;align-items:center;
     font-size:12px;font-weight:500;color:#5D74A0}}
.src b{{color:#93A7C4;font-weight:900}}
"""

# Inline SVG only: no icon font, so the render is byte-stable anywhere.
def _ico(path: str, color: str, size: int = 13) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="2.2" stroke-linecap="round" '
            f'stroke-linejoin="round">{path}</svg>')


ICONS = {
    "cal":    _ico('<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/>', "#4E85D8"),
    "price":  _ico('<path d="M6 4h12M6 9h12M15 4c0 5-3.5 5-9 5l9 10"/>', "#D8A94E"),
    "retail": _ico('<circle cx="9" cy="8" r="3.2"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6"/><path d="M17 11.2A3 3 0 0 0 17 5.4M18.6 20c0-2.4-1-4.3-2.6-5.4"/>', "#4EC9BC"),
    "total":  _ico('<path d="M4 20V11M10 20V5M16 20v-6M22 20H2"/>', "#8B8FE8"),
    "fire":   _ico('<path d="M12 22a7 7 0 0 0 7-7c0-5-4-6-4-10 0 0-3 2-3 6 0-2-1-3-1-3-2 2-3 4.5-3 7a7 7 0 0 0 4 7z"/>', "#16E07E"),
    "pin":    _ico('<path d="M12 17v5M9 3h6l-1 6 3 3H7l3-3-1-6z"/>', "#6E86A8", 12),
    "chart":  _ico('<path d="M3 17l5.5-5.5 3.5 3.5L21 6"/><path d="M15 6h6v6"/>', "#6E86A8", 12),
    "alert":  _ico('<path d="M12 9v4M12 17h.01M10.3 3.9 1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>', "#6E86A8", 12),
    "logo":   _ico('<path d="M3 17l5.5-5.5 3.5 3.5L21 6"/><path d="M15 6h6v6"/>', "#fff", 28),
}


def _e(s: object) -> str:
    return html.escape(str(s), quote=True)


def _bar_pct(ipo: IPO, peak: Optional[Decimal]) -> float:
    """Bar length as a share of the highest GMP % in the set."""
    pct = ipo.gmp_pct
    if pct is None or peak is None or peak <= 0:
        return 0.0
    return max(1.5, min(100.0, float(pct / peak * 100)))


def _field(icon: str, label: str, value: str, key: str, na: bool) -> str:
    cls = "fv na" if na else "fv"
    lab = f'<span class="fl">{_e(label)}</span>' if label else ""
    return (f'<div class="f">{ICONS[icon]}{lab}'
            f'<span class="{cls}" data-verify="{_e(key)}">{_e(value)}</span></div>')


SEP = '<div class="sep"></div>'


def _row(ipo: IPO, idx: int, show_sub: bool) -> str:
    """One IPO as a two-line row: name above, its figures inline below."""
    kid = f"ipo{idx}"
    hot = " hot" if ipo.is_hot else ""
    pill = '<span class="pill">HIGH GMP</span>' if ipo.is_hot else ""
    positive = ipo.gmp_pct is not None and ipo.gmp_pct > 0
    pct_cls = "pct" if positive else "pct flat"

    fields = [
        _field("cal", "", ipo.date_range_text, f"{kid}.dates", False),
        _field("price", "", f"₹{ipo.price_band_text}", f"{kid}.price", False),
    ]
    if show_sub:
        fields.append(_field("retail", "RETAIL", ipo.retail_text, f"{kid}.retail",
                             ipo.retail_sub is None))
        fields.append(_field("total", "TOTAL", ipo.total_text, f"{kid}.total",
                             ipo.total_sub is None))

    return f"""
    <div class="row{hot}">
      <div class="main">
        <div class="nmrow"><span class="nm" data-verify="{kid}.name">{_e(ipo.name)}</span>{pill}</div>
        <div class="sub">{SEP.join(fields)}</div>
      </div>
      <div class="gmp">
        <span class="{pct_cls}" data-verify="{kid}.gmppct">{_e(ipo.gmp_pct_text)}</span>
        <span class="rs" data-verify="{kid}.gmp">{_e(ipo.gmp_text)}</span>
      </div>
    </div>"""


def _leaders(ds: Dataset) -> str:
    from .merge import leader
    ranked = rank_by_gmp(ds)
    top_gmp = next((i for i in ranked if i.gmp_pct is not None), None)
    top_ret = leader(ds, "retail_sub")
    top_tot = leader(ds, "total_sub")

    def box(icon: str, label: str, ipo: Optional[IPO], value: str, key: str) -> str:
        if ipo is None:
            return (f'<div class="lead"><div class="k">{ICONS[icon]}{_e(label)}</div>'
                    f'<div class="lv">Not updated</div></div>')
        return (f'<div class="lead"><div class="k">{ICONS[icon]}{_e(label)}</div>'
                f'<div class="lv" data-verify="{key}.name">{_e(ipo.name)}</div>'
                f'<div class="lx" data-verify="{key}.val">{_e(value)}</div></div>')

    return f"""<div class="leaders">
      {box("fire", "HIGHEST GMP", top_gmp, top_gmp.gmp_pct_text if top_gmp else "", "lead_gmp")}
      {box("retail", "HIGHEST RETAIL", top_ret, top_ret.retail_text if top_ret else "", "lead_ret")}
      {box("total", "HIGHEST TOTAL", top_tot, top_tot.total_text if top_tot else "", "lead_tot")}
    </div>"""


def build_html(ds: Dataset) -> str:
    date_txt = ds.run_date.strftime("%d %b %Y") if ds.run_date else ""
    ranked = rank_by_gmp(ds)
    peak = next((i.gmp_pct for i in ranked if i.gmp_pct is not None), None)

    open_html = ("".join(_row(i, n, True)
                         for n, i in enumerate(ds.open_ipos))
                 or '<div class="empty">No Mainboard IPOs are open today.</div>')
    off = len(ds.open_ipos)
    up_html = ("".join(_row(i, off + n, False)
                       for n, i in enumerate(ds.upcoming_ipos))
               or '<div class="empty">No Mainboard IPOs are scheduled yet.</div>')

    stamps = []
    if ds.subscription_timestamp:
        stamps.append(f"Subscription: {_e(ds.subscription_timestamp)}")
    if ds.gmp_timestamp:
        stamps.append(f"GMP: {_e(ds.gmp_timestamp)}")
    stamp_html = f'<div>{" &nbsp;·&nbsp; ".join(stamps)}</div>' if stamps else "<div></div>"

    warn_html = ""
    if ds.warnings:
        items = "<br>".join(f"{_e(w)}" for w in ds.warnings[:4])
        warn_html = f'<div class="warn">{items}</div>'

    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>{font_face_css()}{CSS}</style></head>
<body><div class="sheet">
  <div class="hdr">
    <div class="brand">
      <div class="mark">{ICONS['logo']}</div>
      <div><h1>IPO WATCH</h1><div class="tag">DAILY UPDATE · MAINBOARD</div></div>
    </div>
    <div class="datebox"><div class="d">{_e(date_txt)}</div><div class="t">8:00 PM IST</div></div>
  </div>

  <div class="sect"><span class="dot open"></span><h2>OPEN MAINBOARD IPOs</h2>
       <span class="n">{len(ds.open_ipos)}</span><span class="rule"></span></div>
  {open_html}

  <div class="sect"><span class="dot up"></span><h2>UPCOMING MAINBOARD IPOs</h2>
       <span class="n">{len(ds.upcoming_ipos)}</span><span class="rule"></span></div>
  {up_html}

  {_leaders(ds)}

  <div class="ftr">
    {warn_html}
    <div class="legend">
      <div>{ICONS['pin']}GMP = Grey Market Premium</div>
      <div>{ICONS['chart']}GMP % calculated on upper price band</div>
      <div>{ICONS['alert']}GMP is unofficial and can change before listing.</div>
    </div>
    <div class="src"><div>Source: <b>{_e(SOURCE_NAME)}</b></div>{stamp_html}</div>
  </div>
</div></body></html>"""


def render_png(ds: Dataset, out_path: str, scale: int = 2) -> tuple[str, dict[str, str]]:
    """Render the creative and read every figure back out of the live DOM.

    Returns (png_path, rendered) where `rendered` maps each data-verify key to
    the text actually painted on the image. verify.py compares that against
    the dataset before the PNG is accepted.
    """
    from playwright.sync_api import sync_playwright

    html_doc = build_html(ds)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    html_path = os.path.splitext(out_path)[0] + ".html"
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html_doc)

    kwargs = {"args": ["--no-sandbox", "--disable-dev-shm-usage",
                       "--force-color-profile=srgb", "--font-render-hinting=none"]}
    if CHROMIUM_PATH and os.path.exists(CHROMIUM_PATH):
        kwargs["executable_path"] = CHROMIUM_PATH

    with sync_playwright() as p:
        browser = p.chromium.launch(**kwargs)
        page = browser.new_page(viewport={"width": CARD_W, "height": 800},
                                device_scale_factor=scale)
        page.set_content(html_doc, wait_until="load")
        page.wait_for_timeout(400)
        rendered = page.eval_on_selector_all(
            "[data-verify]",
            "els => Object.fromEntries(els.map(e => [e.dataset.verify, e.textContent.trim()]))",
        )
        # Shoot the sheet element, not the page: the creative then crops exactly
        # to its content instead of being padded out to the viewport height.
        page.locator(".sheet").screenshot(path=out_path)
        browser.close()
    return out_path, rendered
