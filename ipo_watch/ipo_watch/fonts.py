"""Self-contained webfont embedding.

The creative uses the Loop / Inner Circle house type: DM Sans for text and
Bebas Neue for figures, the same pairing as the Loop and India Stock Watch
apps. Both are subset to the glyphs this creative uses (Latin, ₹, dashes,
quotes, arrows) and inlined as base64, so the PNG renders identically on any
machine with no network fetch and no dependency on installed system fonts.

Both fonts are SIL Open Font License 1.1; see assets/fonts/OFL-*.txt.
"""
from __future__ import annotations

import base64
import functools
import os

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts")
_FACES = (
    ("LoopSans", 400, "DMSans-400.woff2"),
    ("LoopSans", 500, "DMSans-500.woff2"),
    ("LoopSans", 700, "DMSans-700.woff2"),
    ("LoopDisplay", 400, "BebasNeue-Regular.woff2"),
)


@functools.lru_cache(maxsize=1)
def font_face_css() -> str:
    """@font-face blocks with the woff2 payloads inlined, or '' if absent."""
    blocks = []
    for family, weight, filename in _FACES:
        path = os.path.normpath(os.path.join(_DIR, filename))
        if not os.path.exists(path):
            continue
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        blocks.append(
            f"@font-face{{font-family:'{family}';font-style:normal;"
            f"font-weight:{weight};font-display:block;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
        )
    return "".join(blocks)


FONT_STACK = "'LoopSans','DM Sans','Liberation Sans','DejaVu Sans',Arial,sans-serif"
DISPLAY_STACK = "'LoopDisplay','Bebas Neue',Impact,'Liberation Sans Narrow',sans-serif"
