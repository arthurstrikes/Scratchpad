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

from .config import CHROMIUM_PATH, SOURCE_NAME
from .fonts import DISPLAY_STACK, FONT_STACK, font_face_css
from .merge import Dataset, rank_by_gmp
from .models import IPO

CARD_W = 1080

CSS = f"""
:root{{
  --bg:#111111; --surface:#1A1A1A; --surface-2:#202020; --line:#2A2A2A;
  --ink:#F5F5F5; --ink-2:#B0B0B0; --ink-3:#8A8A8A;
  --brand:#FF6B35; --brand-soft:#2A1810; --brand-fill:#C94A1A; --brand-fill-2:#9E3410;
  --good:#4CAF50; --bad:#FF4444;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{CARD_W}px;background:var(--bg);color:var(--ink);font-family:{FONT_STACK};
     -webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums lining-nums}}
.sheet{{background:var(--bg);padding-bottom:22px}}
.num{{font-family:{DISPLAY_STACK};font-weight:400;line-height:1;letter-spacing:.5px}}

/* ---------- signature: the orange band ---------- */
.band{{position:relative;overflow:hidden;color:#fff;padding:24px 40px 22px;
      background:linear-gradient(135deg,var(--brand-fill) 0%,var(--brand-fill-2) 100%);
      display:flex;justify-content:space-between;align-items:flex-end;gap:24px}}
.band:after{{content:"";position:absolute;inset:0;opacity:.13;pointer-events:none;
      background:repeating-linear-gradient(45deg,#fff 0 5px,transparent 5px 26px)}}
.band>*{{position:relative;z-index:1}}
.eyebrow{{font-size:14px;font-weight:700;letter-spacing:5px;text-transform:uppercase;
         opacity:.82;margin-bottom:10px}}
h1{{font-size:44px;font-weight:700;line-height:1;letter-spacing:.3px}}
.when{{text-align:right;flex:none}}
.when .num{{font-size:60px;display:block}}
.when small{{display:block;font-size:15px;font-weight:700;letter-spacing:4px;
            text-transform:uppercase;opacity:.82;margin-top:6px}}

main{{padding:4px 40px 0}}

/* ---------- section headers ---------- */
.sec-h{{display:flex;align-items:center;gap:12px;margin:22px 2px 10px}}
.sec-h h2{{font-size:16px;font-weight:500;letter-spacing:4.5px;text-transform:uppercase;
          color:var(--ink-3)}}
.sec-h .dot{{width:11px;height:11px;border-radius:50%;flex:none}}
.dot.open{{background:var(--good)}}
.dot.up{{background:var(--brand)}}
.sec-h .rule{{flex:1;height:1px;background:var(--line)}}
.sec-h .num{{font-size:30px;color:var(--ink-2)}}

/* ---------- IPO rows ----------
   Two lines per IPO inside one list, divided by hairlines - the India Stock
   Watch watchlist pattern. Keeps a full day near a square image. */
.rows{{background:var(--surface);border:1px solid var(--line);border-radius:6px;overflow:hidden}}
.row{{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:24px;
     padding:13px 24px 13px 22px;border-top:1px solid var(--line);border-left:5px solid transparent}}
.row:first-child{{border-top:0}}
.row.hot{{border-left-color:var(--brand)}}
.nmrow{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;min-width:0}}
.nm{{font-size:28px;font-weight:700;line-height:1.15;letter-spacing:.2px}}
.flag{{font-size:12.5px;font-weight:700;letter-spacing:2.6px;text-transform:uppercase;
      color:var(--brand);border:1.5px solid currentColor;border-radius:3px;padding:5px 7px 4px}}
.sub{{display:flex;align-items:baseline;flex-wrap:wrap;gap:6px 0;margin-top:5px;
     font-size:20px;color:var(--ink-2)}}
.f{{display:inline-flex;align-items:baseline;gap:8px}}
.f+.f:before{{content:"·";color:var(--ink-3);margin:0 14px}}
.fl{{font-size:14px;font-weight:500;letter-spacing:2.6px;text-transform:uppercase;color:var(--ink-3)}}
.fv{{font-weight:500;color:var(--ink)}}
.fv.na{{color:var(--ink-3);font-weight:400;font-style:italic}}
.gmp{{text-align:right;flex:none;display:flex;align-items:baseline;gap:12px}}
.pct{{font-size:52px;color:var(--good);white-space:nowrap}}
.pct.flat{{color:var(--ink-3)}}
.pct.neg{{color:var(--bad)}}
.rs{{font-size:19px;font-weight:500;color:var(--ink-3);white-space:nowrap}}
.empty{{background:var(--surface);border:1px dashed var(--line);border-radius:6px;
       padding:24px;text-align:center;color:var(--ink-3);font-size:19px}}

/* ---------- leaders: the KPI strip ---------- */
.kpis{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:22px}}
.kpi{{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:13px 18px 12px}}
.kpi .kl{{font-size:13.5px;font-weight:500;letter-spacing:3px;text-transform:uppercase;color:var(--ink-3)}}
.kpi .kv{{font-size:44px;margin-top:8px;color:var(--ink)}}
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


def _row(ipo: IPO, idx: int, show_sub: bool) -> str:
    """One IPO as a two-line row: name above, its figures inline below."""
    kid = f"ipo{idx}"
    hot = " hot" if ipo.is_hot else ""
    flag = '<span class="flag">High GMP</span>' if ipo.is_hot else ""

    fields = [
        _field("", ipo.date_range_text, f"{kid}.dates", False),
        _field("", f"₹{ipo.price_band_text}", f"{kid}.price", False),
    ]
    if show_sub:
        fields.append(_field("Retail", ipo.retail_text, f"{kid}.retail", ipo.retail_sub is None))
        fields.append(_field("Total", ipo.total_text, f"{kid}.total", ipo.total_sub is None))

    return f"""
    <div class="row{hot}">
      <div>
        <div class="nmrow"><span class="nm" data-verify="{kid}.name">{_e(ipo.name)}</span>{flag}</div>
        <div class="sub">{"".join(fields)}</div>
      </div>
      <div class="gmp">
        <span class="{_pct_class(ipo)}" data-verify="{kid}.gmppct">{_e(ipo.gmp_pct_text)}</span>
        <span class="rs">GMP <span data-verify="{kid}.gmp">{_e(ipo.gmp_text)}</span></span>
      </div>
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


def build_html(ds: Dataset) -> str:
    date_txt = ds.run_date.strftime("%d %b %Y") if ds.run_date else ""

    open_rows = [_row(i, n, True) for n, i in enumerate(ds.open_ipos)]
    off = len(ds.open_ipos)
    up_rows = [_row(i, off + n, False) for n, i in enumerate(ds.upcoming_ipos)]

    stamps = []
    if ds.subscription_timestamp:
        stamps.append(f"Subscription {_e(ds.subscription_timestamp)}")
    if ds.gmp_timestamp:
        stamps.append(f"GMP {_e(ds.gmp_timestamp)}")
    stamp_html = f'<div>{" &nbsp;·&nbsp; ".join(stamps)}</div>' if stamps else "<div></div>"

    warn_html = ""
    if ds.warnings:
        items = "<br>".join(_e(w) for w in ds.warnings[:4])
        warn_html = f'<div class="warn">{items}</div>'

    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>{font_face_css()}{CSS}</style></head>
<body><div class="sheet">
  <div class="band">
    <div><div class="eyebrow">Daily update · Mainboard</div><h1>IPO Watch</h1></div>
    <div class="when"><span class="num">{_e(date_txt)}</span><small>5:00 PM IST</small></div>
  </div>
  <main>
    {_section("Open now", "open", open_rows, "No Mainboard IPOs are open today.")}
    {_section("Upcoming", "up", up_rows, "No Mainboard IPOs are scheduled yet.")}
    {_leaders(ds)}
    <div class="ftr">
      {warn_html}
      <div class="legend"><span>GMP = Grey Market Premium</span><span>GMP % on upper price band</span><span>GMP is unofficial and can change before listing</span></div>
      <div class="src"><div>Source: <b>{_e(SOURCE_NAME)}</b></div>{stamp_html}</div>
    </div>
  </main>
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
