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
   radial-gradient(1200px 520px at 78% -8%,rgba(45,110,255,.16),transparent 60%),
   linear-gradient(172deg,#0A1526 0%,#08111F 48%,#060C16 100%);
   padding:48px 44px 36px}}

/* ---------- masthead ---------- */
.hdr{{display:flex;justify-content:space-between;align-items:flex-end;
     padding-bottom:26px;border-bottom:1px solid #17263F;position:relative}}
.hdr:after{{content:"";position:absolute;left:0;bottom:-1px;width:132px;height:3px;
     background:linear-gradient(90deg,#16E07E,#3D8BFF);border-radius:2px}}
.brand{{display:flex;align-items:center;gap:16px}}
.mark{{width:56px;height:56px;border-radius:15px;flex-shrink:0;
      background:linear-gradient(140deg,#2D6EFF,#12C8F0);
      display:flex;align-items:center;justify-content:center;
      box-shadow:0 8px 22px rgba(45,110,255,.32)}}
h1{{font-size:41px;font-weight:900;color:#fff;letter-spacing:-.6px;line-height:1}}
.tag{{font-size:13px;font-weight:500;color:#6E86A8;margin-top:9px;letter-spacing:2.6px}}
.datebox{{text-align:right;flex-shrink:0}}
.datebox .d{{font-size:26px;font-weight:900;color:#fff;letter-spacing:-.3px}}
.datebox .t{{font-size:13px;font-weight:500;color:#6E86A8;margin-top:6px;letter-spacing:1.6px}}

/* ---------- section headers ---------- */
.sect{{display:flex;align-items:center;gap:13px;margin:28px 0 14px}}
.dot{{width:11px;height:11px;border-radius:50%;flex-shrink:0}}
.dot.open{{background:#16E07E;box-shadow:0 0 14px rgba(22,224,126,.75)}}
.dot.up{{background:#3D8BFF;box-shadow:0 0 14px rgba(61,139,255,.75)}}
.sect h2{{font-size:21px;font-weight:900;color:#EAF2FF;letter-spacing:2.8px}}
.sect .n{{font-size:14px;font-weight:700;color:#5D74A0}}
.sect .rule{{flex:1;height:1px;background:linear-gradient(90deg,#1B2B47,transparent)}}

/* ---------- IPO card ---------- */
.card{{background:linear-gradient(180deg,#0E1A2E,#0B1524);border:1px solid #1A2A44;
      border-radius:16px;padding:20px 26px 18px;margin-bottom:11px;position:relative}}
.card.hot{{border-color:#1C6B48;
      background:linear-gradient(115deg,#0F2A24 0%,#0D1D30 38%,#0B1524 100%)}}
.card.hot:before{{content:"";position:absolute;left:-1px;top:16px;bottom:16px;width:3px;
      background:linear-gradient(180deg,#16E07E,#0B9B57);border-radius:3px}}

.top{{display:flex;justify-content:space-between;align-items:center;gap:20px}}
.left{{display:flex;gap:15px;align-items:flex-start;min-width:0}}
.nm{{font-size:32px;font-weight:700;color:#fff;line-height:1.14;letter-spacing:-.5px}}
.nmrow{{display:flex;align-items:center;gap:13px;flex-wrap:wrap}}
.pill{{display:inline-block;padding:5px 12px;border-radius:6px;
      background:rgba(22,224,126,.13);border:1px solid rgba(22,224,126,.4);
      color:#16E07E;font-size:11px;font-weight:900;letter-spacing:1.6px}}

.gmpbox{{text-align:right;flex-shrink:0}}
.gmplbl{{font-size:12px;font-weight:700;color:#5D74A0;letter-spacing:2.4px;margin-bottom:7px}}
.gmppct{{font-size:39px;font-weight:900;color:#16E07E;line-height:1;letter-spacing:-1px;
     white-space:nowrap}}
.gmppct.flat{{color:#7E93B2}}
.gmpval{{display:flex;align-items:baseline;justify-content:flex-end;gap:12px}}
.gmprs{{font-size:20px;font-weight:500;color:#93A7C4;white-space:nowrap}}


/* data row: hairline dividers instead of boxed chips - reads faster */
.data{{display:flex;margin-top:16px;padding-top:15px;border-top:1px solid #16243C}}
.cell{{flex:1;padding-left:18px;border-left:1px solid #16243C;min-width:0}}
.cell:first-child{{padding-left:0;border-left:0}}
.k{{display:flex;align-items:center;gap:7px;font-size:12px;font-weight:700;
   color:#6580AC;letter-spacing:1.2px;margin-bottom:8px}}
.v{{font-size:24px;font-weight:700;color:#E9F1FC;white-space:nowrap;letter-spacing:-.2px}}
.v.na{{color:#6A7E9E;font-weight:400;font-size:18px;font-style:italic}}

/* Upcoming IPOs carry no subscription data, so their dates and price band sit
   inline beside the name instead of in a full data row. That roughly halves
   the card height, which matters: at 8 live IPOs a full-height layout runs
   past 5000px and WhatsApp shrinks it below readability. */
.inline{{display:flex;align-items:center;gap:20px;margin-top:13px;flex-wrap:wrap}}
.inline .it{{display:flex;align-items:center;gap:8px}}
.inline .il{{font-size:12px;font-weight:700;color:#6580AC;letter-spacing:1.2px}}
.inline .iv{{font-size:22px;font-weight:700;color:#E9F1FC;letter-spacing:-.2px}}
.inline .sep{{width:4px;height:4px;border-radius:50%;background:#28405f}}
.empty{{background:#0A1424;border:1px dashed #1E3050;border-radius:14px;
       padding:30px;text-align:center;color:#6E86A8;font-size:17px;font-weight:500}}

/* ---------- ranking strip ---------- */
.rankstrip{{margin-top:16px;background:#0A1322;border:1px solid #17263F;
      border-radius:16px;padding:22px 26px}}
.rrow{{display:flex;align-items:center;gap:16px;padding:11px 0}}
.rrow+.rrow{{border-top:1px solid #12203A}}
.rn{{font-size:14px;font-weight:900;color:#5D74A0;width:22px;flex-shrink:0}}
.rnm{{font-size:19px;font-weight:700;color:#DCE7F6;flex:0 1 330px;min-width:150px;
     overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.rbarwrap{{flex:1;height:7px;background:#122039;border-radius:4px;overflow:hidden}}
.rbar{{height:100%;border-radius:4px;background:linear-gradient(90deg,#0B9B57,#16E07E)}}
.rbar.flat{{background:#26385A}}
.rpct{{font-size:20px;font-weight:900;color:#16E07E;width:116px;text-align:right;flex-shrink:0}}
.rpct.flat{{color:#7E93B2}}
.rtag{{font-size:10px;font-weight:900;letter-spacing:1.2px;width:40px;flex-shrink:0;
      text-align:right}}
.rtag.o{{color:#16E07E}} .rtag.u{{color:#3D8BFF}}

/* ---------- leaders + footer ---------- */
.leaders{{display:flex;gap:12px;margin-top:16px}}
.lead{{flex:1;background:#0A1322;border:1px solid #17263F;border-radius:14px;padding:17px 19px}}
.lead .k{{margin-bottom:9px}}
.lead .lv{{font-size:19px;font-weight:700;color:#EAF2FF;line-height:1.3;
      overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.lead .lx{{font-size:18px;font-weight:900;color:#16E07E;margin-top:5px}}

.ftr{{margin-top:26px;padding-top:19px;border-top:1px solid #17263F}}
.warn{{background:rgba(224,178,58,.06);border:1px solid rgba(224,178,58,.24);
      border-radius:10px;padding:13px 16px;font-size:13.5px;font-weight:500;
      color:#D2B45E;margin-bottom:14px;line-height:1.65}}
.legend{{display:flex;flex-wrap:wrap;gap:9px 26px;margin-bottom:13px}}
.legend div{{display:flex;align-items:center;gap:7px;font-size:13.5px;
      font-weight:500;color:#7E93B2}}
.src{{display:flex;justify-content:space-between;align-items:center;
     font-size:13px;font-weight:500;color:#5D74A0;letter-spacing:.2px}}
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


def _cell(icon: str, label: str, value: str, key: str, na: bool) -> str:
    cls = "v na" if na else "v"
    return (f'<div class="cell"><div class="k">{ICONS[icon]}{_e(label)}</div>'
            f'<div class="{cls}" data-verify="{_e(key)}">{_e(value)}</div></div>')


def _card(ipo: IPO, idx: int, show_sub: bool) -> str:
    kid = f"ipo{idx}"
    hot = " hot" if ipo.is_hot else ""
    pill = '<div class="pill">HIGH GMP</div>' if ipo.is_hot else ""
    positive = ipo.gmp_pct is not None and ipo.gmp_pct > 0
    pct_cls = "gmppct" if positive else "gmppct flat"

    cells = []
    if show_sub:
        cells = [
            _cell("cal", "OPEN – CLOSE", ipo.date_range_text, f"{kid}.dates", False),
            _cell("price", "PRICE BAND", f"₹{ipo.price_band_text}", f"{kid}.price", False),
            _cell("retail", "RETAIL", ipo.retail_text, f"{kid}.retail",
                  ipo.retail_sub is None),
            _cell("total", "TOTAL", ipo.total_text, f"{kid}.total",
                  ipo.total_sub is None),
        ]

    gmp_block = f"""<div class="gmpbox">
          <div class="gmplbl">GMP</div>
          <div class="gmpval">
            <div class="{pct_cls}" data-verify="{kid}.gmppct">{_e(ipo.gmp_pct_text)}</div>
            <div class="gmprs" data-verify="{kid}.gmp">{_e(ipo.gmp_text)}</div>
          </div>
        </div>"""

    if show_sub:
        body = f'<div class="data">{"".join(cells)}</div>'
        inline = ""
    else:
        body = ""
        inline = f"""<div class="inline">
            <div class="it">{ICONS['cal']}<span class="iv"
                 data-verify="{kid}.dates">{_e(ipo.date_range_text)}</span></div>
            <div class="sep"></div>
            <div class="it">{ICONS['price']}<span class="iv"
                 data-verify="{kid}.price">₹{_e(ipo.price_band_text)}</span></div>
          </div>"""

    return f"""
    <div class="card{hot}">
      <div class="top">
        <div class="left">
          <div><div class="nmrow"><div class="nm" data-verify="{kid}.name">{_e(ipo.name)}</div>{pill}</div>{inline}</div>
        </div>
        {gmp_block}
      </div>
      {body}
    </div>"""


def _ranking_strip(ds: Dataset, peak: Optional[Decimal]) -> str:
    ranked = rank_by_gmp(ds)
    if not ranked:
        return ""
    rows = []
    for n, ipo in enumerate(ranked, 1):
        positive = ipo.gmp_pct is not None and ipo.gmp_pct > 0
        tag = ("o", "OPEN") if ipo.status.value == "Open" else ("u", "SOON")
        rows.append(f"""
      <div class="rrow">
        <div class="rn">{n:02d}</div>
        <div class="rnm" data-verify="rank{n}.name">{_e(ipo.name)}</div>
        <div class="rbarwrap"><div class="rbar{'' if positive else ' flat'}"
             style="width:{_bar_pct(ipo, peak):.1f}%"></div></div>
        <div class="rpct{'' if positive else ' flat'}"
             data-verify="rank{n}.pct">{_e(ipo.gmp_pct_text)}</div>
        <div class="rtag {tag[0]}">{tag[1]}</div>
      </div>""")
    return f"""
  <div class="sect"><span class="dot open"></span><h2>CURRENT GMP RANKING</h2>
       <span class="rule"></span></div>
  <div class="rankstrip">{''.join(rows)}</div>"""


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

    open_html = ("".join(_card(i, n, True)
                         for n, i in enumerate(ds.open_ipos))
                 or '<div class="empty">No Mainboard IPOs are open today.</div>')
    off = len(ds.open_ipos)
    up_html = ("".join(_card(i, off + n, False)
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

  {_ranking_strip(ds, peak)}
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
