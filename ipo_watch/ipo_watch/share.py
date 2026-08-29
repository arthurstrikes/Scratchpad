"""Builds the WhatsApp share package (spec section 8).

Writes a small local page next to the creative. Opening it gives:
  Open -> Share -> pick contacts -> Send

It uses the Web Share API with the PNG attached where the browser supports it
(Android Chrome, iOS Safari, Windows Edge), which raises the OS share sheet
with WhatsApp in it. Otherwise it falls back to a wa.me link, which opens
WhatsApp's own contact picker with the caption pre-filled.

Nothing here sends a message. Every path stops at the contact picker and
waits for the user to press Send.
"""
from __future__ import annotations

import html
import json
import os

from .merge import Dataset
from .report import build_caption


def build_share_page(ds: Dataset, image_filename: str, out_path: str) -> str:
    caption = build_caption(ds)
    date_txt = ds.run_date.strftime("%d %b %Y") if ds.run_date else ""
    cap_js = json.dumps(caption)
    img_js = json.dumps(image_filename)

    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IPO Watch — Share {html.escape(date_txt)}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#070E1C;color:#E8F0FB;font-family:"Segoe UI",system-ui,Arial,sans-serif;
     padding:24px;display:flex;flex-direction:column;align-items:center;gap:18px}}
.wrap{{width:100%;max-width:560px;display:flex;flex-direction:column;gap:16px}}
h1{{font-size:20px;font-weight:700;letter-spacing:.3px}}
.sub{{font-size:14px;color:#7D93B4;margin-top:4px}}
img{{width:100%;border-radius:14px;border:1px solid #1C3157;display:block}}
.cap{{background:#101F3A;border:1px solid #1C3157;border-radius:12px;padding:16px;
     white-space:pre-wrap;font-size:14px;line-height:1.6}}
.row{{display:flex;gap:10px;flex-wrap:wrap}}
button,a.btn{{flex:1;min-width:150px;text-align:center;text-decoration:none;
    padding:15px 18px;border-radius:12px;border:0;font-size:15px;font-weight:700;
    cursor:pointer;font-family:inherit}}
.primary{{background:#25D366;color:#06210F}}
.ghost{{background:#132444;color:#CFE0F5;border:1px solid #24406B}}
.note{{font-size:12px;color:#6F86A8;line-height:1.6}}
.ok{{color:#4ADE80}}
</style></head><body><div class="wrap">
<div><h1>IPO Watch — {html.escape(date_txt)}</h1>
<div class="sub">Tap Share, choose your contacts or groups, then press Send.</div></div>

<img src="{html.escape(image_filename)}" alt="IPO Watch creative">
<div class="cap" id="cap">{html.escape(caption)}</div>

<div class="row">
  <button class="primary" id="share">📤 Share image + caption</button>
  <button class="ghost" id="copy">📋 Copy caption</button>
</div>
<div class="row">
  <a class="btn ghost" id="wa" target="_blank" rel="noopener">💬 Open WhatsApp with caption</a>
  <a class="btn ghost" href="{html.escape(image_filename)}" download>⬇️ Save image</a>
</div>

<div class="note" id="note">
  “Share image + caption” opens your device share sheet with the creative attached.
  If your browser does not support it, use “Open WhatsApp with caption”, then attach
  the saved image. Nothing is sent until you press Send in WhatsApp.
</div>
</div>
<script>
const CAPTION = {cap_js}, IMG = {img_js};
const note = document.getElementById('note');
document.getElementById('wa').href =
  'https://wa.me/?text=' + encodeURIComponent(CAPTION);

document.getElementById('copy').onclick = async () => {{
  try {{ await navigator.clipboard.writeText(CAPTION); }}
  catch (e) {{
    const r = document.createRange(); r.selectNode(document.getElementById('cap'));
    getSelection().removeAllRanges(); getSelection().addRange(r);
    document.execCommand('copy');
  }}
  note.innerHTML = '<span class="ok">Caption copied.</span>';
}};

document.getElementById('share').onclick = async () => {{
  try {{
    const blob = await (await fetch(IMG)).blob();
    const file = new File([blob], IMG.split('/').pop(), {{type: 'image/png'}});
    if (navigator.canShare && navigator.canShare({{files: [file]}})) {{
      await navigator.share({{files: [file], text: CAPTION}});
      return;
    }}
    if (navigator.share) {{ await navigator.share({{text: CAPTION}}); return; }}
    throw new Error('unsupported');
  }} catch (e) {{
    if (e && e.name === 'AbortError') return;   // user dismissed the sheet
    note.innerHTML = 'Direct share unavailable here. Use ' +
      '<b>Open WhatsApp with caption</b> and attach the saved image.';
  }}
}};
</script></body></html>"""

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return out_path
