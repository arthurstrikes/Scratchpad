"""Deterministic HTML -> PNG creative (spec section 7).

No generative imaging anywhere. Every figure is interpolated into the DOM as
text from the verified dataset, and each figure element carries a
`data-verify` key so verify.py can read the numbers back out of the rendered
page and prove the image matches the dataset.
"""
from __future__ import annotations

import html
import os
from typing import Optional

from .config import CHROMIUM_PATH, SOURCE_NAME
from .merge import Dataset, leader, rank_by_gmp
from .models import IPO

CARD_W = 1080

# Premium equity-research palette: deep navy ground, high-contrast type.
CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{width:1080px;background:#070E1C;
     font-family:"Liberation Sans","DejaVu Sans",Arial,sans-serif;
     -webkit-font-smoothing:antialiased}
.sheet{background:linear-gradient(168deg,#0B1730 0%,#0A1428 55%,#080F20 100%);
       padding:44px 40px 34px}
.hdr{display:flex;justify-content:space-between;align-items:flex-start;
     padding-bottom:24px;border-bottom:2px solid #1B3157}
.brand{display:flex;align-items:center;gap:14px}
.mark{width:52px;height:52px;border-radius:13px;
      background:linear-gradient(140deg,#2E6BFF,#17C3F2);
      display:flex;align-items:center;justify-content:center}
h1{font-size:38px;font-weight:700;color:#fff;letter-spacing:.4px;line-height:1.1}
.sub{font-size:17px;color:#7D93B4;margin-top:6px;letter-spacing:.3px}
.datebox{text-align:right}
.datebox .d{font-size:23px;font-weight:700;color:#fff}
.datebox .t{font-size:15px;color:#7D93B4;margin-top:5px}
.sect{display:flex;align-items:center;gap:12px;margin:32px 0 18px}
.dot{width:13px;height:13px;border-radius:50%}
.dot.open{background:#25D366;box-shadow:0 0 0 5px rgba(37,211,102,.16)}
.dot.up{background:#3B9BFF;box-shadow:0 0 0 5px rgba(59,155,255,.16)}
.sect h2{font-size:21px;font-weight:700;color:#fff;letter-spacing:1.5px}
.sect .rule{flex:1;height:1px;background:linear-gradient(90deg,#1E3358,transparent)}
.card{background:#101F3A;border:1px solid #1C3157;border-radius:15px;
      padding:22px 24px;margin-bottom:14px;position:relative;overflow:hidden}
.card.hot{border-color:#1F7A4D;background:linear-gradient(100deg,#12283D,#101F3A 42%)}
.card.hot:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:#25D366}
.crow{display:flex;justify-content:space-between;align-items:center;gap:18px}
.nm{font-size:25px;font-weight:700;color:#fff;line-height:1.22;letter-spacing:.2px}
.hotpill{display:inline-block;margin-top:9px;padding:4px 11px;border-radius:6px;
         background:rgba(37,211,102,.14);border:1px solid rgba(37,211,102,.42);
         color:#4ADE80;font-size:12px;font-weight:700;letter-spacing:1.1px}
.gmpbox{text-align:right;flex-shrink:0;min-width:150px}
.gmprs{font-size:27px;font-weight:700;color:#fff;white-space:nowrap}
.gmppct{font-size:19px;font-weight:700;margin-top:3px;color:#4ADE80;white-space:nowrap}
.gmppct.flat{color:#8497B5}
.gmplbl{font-size:11px;color:#6F86A8;letter-spacing:1.4px;margin-bottom:5px}
.meta{display:flex;flex-wrap:wrap;gap:11px;margin-top:17px;
      padding-top:16px;border-top:1px solid #1B2F52}
.chip{display:flex;align-items:center;gap:8px;background:#0B1830;
      border:1px solid #1B2F52;border-radius:9px;padding:9px 13px}
.chip .k{font-size:11px;color:#6F86A8;letter-spacing:1px}
.chip .v{font-size:16px;font-weight:700;color:#E8F0FB;white-space:nowrap}
.chip.na .v{color:#7D8FA8;font-weight:400;font-style:italic}
.empty{background:#0D1A31;border:1px dashed #22395F;border-radius:13px;
       padding:26px;text-align:center;color:#7D93B4;font-size:17px}
.ftr{margin-top:30px;padding-top:20px;border-top:2px solid #1B3157}
.legend{display:flex;flex-wrap:wrap;gap:9px 22px;margin-bottom:14px}
.legend div{font-size:13px;color:#8AA0BE}
.warn{background:rgba(234,179,8,.07);border:1px solid rgba(234,179,8,.26);
      border-radius:9px;padding:12px 15px;font-size:13px;color:#D9B84F;margin-bottom:13px}
.src{display:flex;justify-content:space-between;align-items:center;
     font-size:13px;color:#6F86A8}
.src b{color:#9FB4D2;font-weight:700}
.stamp{font-size:12px;color:#5E769B}
"""

# Inline SVG icons: no icon font, so the render is byte-stable anywhere.
ICONS = {
    "cal": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#4D8FE0" stroke-width="2.1" stroke-linecap="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/></svg>',
    "price": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#E0B84D" stroke-width="2.1" stroke-linecap="round"><path d="M6 4h12M6 9h12M15 4c0 5-3.5 5-9 5l9 10"/></svg>',
    "retail": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#4DD0C0" stroke-width="2.1" stroke-linecap="round"><circle cx="9" cy="8" r="3.2"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6"/><path d="M17 11.2A3 3 0 0 0 17 5.4M18.6 20c0-2.4-1-4.3-2.6-5.4"/></svg>',
    "total": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#8B8FE8" stroke-width="2.1" stroke-linecap="round"><path d="M4 20V11M10 20V5M16 20v-6M22 20H2"/></svg>',
    "logo": '<svg width="27" height="27" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17l5.5-5.5 3.5 3.5L21 6"/><path d="M15 6h6v6"/></svg>',
}


def _e(s: object) -> str:
    return html.escape(str(s), quote=True)


def _chip(icon: str, key: str, value: str, verify_key: str, na: bool) -> str:
    cls = "chip na" if na else "chip"
    return (f'<div class="{cls}">{ICONS[icon]}<div><div class="k">{_e(key)}</div>'
            f'<div class="v" data-verify="{_e(verify_key)}">{_e(value)}</div></div></div>')


def _card(ipo: IPO, idx: int, show_sub: bool) -> str:
    kid = f"ipo{idx}"
    hot = " hot" if ipo.is_hot else ""
    pill = '<div class="hotpill">HIGH GMP</div>' if ipo.is_hot else ""
    pct_cls = "gmppct" if (ipo.gmp_pct and ipo.gmp_pct > 0) else "gmppct flat"

    chips = [
        _chip("cal", "OPEN – CLOSE", ipo.date_range_text, f"{kid}.dates", False),
        _chip("price", "PRICE BAND", f"₹{ipo.price_band_text}", f"{kid}.price", False),
    ]
    if show_sub:
        chips.append(_chip("retail", "RETAIL", ipo.retail_text, f"{kid}.retail",
                           ipo.retail_sub is None))
        chips.append(_chip("total", "TOTAL", ipo.total_text, f"{kid}.total",
                           ipo.total_sub is None))

    return f"""
    <div class="card{hot}">
      <div class="crow">
        <div><div class="nm" data-verify="{kid}.name">{_e(ipo.name)}</div>{pill}</div>
        <div class="gmpbox">
          <div class="gmplbl">GMP</div>
          <div class="gmprs" data-verify="{kid}.gmp">{_e(ipo.gmp_text)}</div>
          <div class="{pct_cls}" data-verify="{kid}.gmppct">{_e(ipo.gmp_pct_text)}</div>
        </div>
      </div>
      <div class="meta">{''.join(chips)}</div>
    </div>"""


def build_html(ds: Dataset) -> str:
    date_txt = ds.run_date.strftime("%d %b %Y") if ds.run_date else ""

    open_html = ("".join(_card(i, n, True) for n, i in enumerate(ds.open_ipos))
                 or '<div class="empty">No Mainboard IPOs are open today.</div>')
    up_start = len(ds.open_ipos)
    up_html = ("".join(_card(i, up_start + n, False) for n, i in enumerate(ds.upcoming_ipos))
               or '<div class="empty">No Mainboard IPOs are scheduled yet.</div>')

    stamps = []
    if ds.subscription_timestamp:
        stamps.append(f"Subscription: {_e(ds.subscription_timestamp)}")
    if ds.gmp_timestamp:
        stamps.append(f"GMP: {_e(ds.gmp_timestamp)}")
    stamp_html = (f'<div class="stamp">{" &nbsp;|&nbsp; ".join(stamps)}</div>'
                  if stamps else "")

    warn_html = ""
    if ds.warnings:
        items = "<br>".join(f"• {_e(w)}" for w in ds.warnings[:4])
        warn_html = f'<div class="warn">{items}</div>'

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body><div class="sheet">
  <div class="hdr">
    <div class="brand">
      <div class="mark">{ICONS['logo']}</div>
      <div><h1>IPO WATCH — DAILY UPDATE</h1>
           <div class="sub">MAINBOARD IPOs &nbsp;•&nbsp; GMP &amp; SUBSCRIPTION TRACKER</div></div>
    </div>
    <div class="datebox"><div class="d">{_e(date_txt)}</div><div class="t">8:00 PM IST</div></div>
  </div>

  <div class="sect"><span class="dot open"></span><h2>OPEN MAINBOARD IPOs</h2><span class="rule"></span></div>
  {open_html}

  <div class="sect"><span class="dot up"></span><h2>UPCOMING MAINBOARD IPOs</h2><span class="rule"></span></div>
  {up_html}

  <div class="ftr">
    {warn_html}
    <div class="legend">
      <div>📌 GMP = Grey Market Premium</div>
      <div>📈 GMP % calculated on upper price band</div>
    </div>
    <div class="legend"><div>⚠️ GMP is unofficial and can change before listing.</div></div>
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
        page.wait_for_timeout(350)
        rendered = page.eval_on_selector_all(
            "[data-verify]",
            "els => Object.fromEntries(els.map(e => [e.dataset.verify, e.textContent.trim()]))",
        )
        # Shoot the sheet element, not the page: the creative then crops exactly
        # to its content instead of being padded out to the viewport height.
        page.locator(".sheet").screenshot(path=out_path)
        browser.close()
    return out_path, rendered
