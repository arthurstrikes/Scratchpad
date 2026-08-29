"""Self-contained webfont embedding.

Roboto, subset to the glyphs this creative uses (Latin, ₹, en/em dash) and
inlined as base64. The creative therefore renders identically on any machine
with no network fetch and no dependency on installed system fonts - which
matters because the same PNG has to look right whether it is produced in CI
or on a laptop.

Roboto is Apache-2.0 licensed; see assets/fonts/LICENSE.
"""
from __future__ import annotations

import base64
import functools
import os

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts")
_WEIGHTS = {"Regular": 400, "Medium": 500, "Bold": 700, "Black": 900}


@functools.lru_cache(maxsize=1)
def font_face_css() -> str:
    """@font-face blocks with the woff2 payloads inlined, or '' if absent."""
    blocks = []
    for name, weight in _WEIGHTS.items():
        path = os.path.normpath(os.path.join(_DIR, f"Roboto-{name}.woff2"))
        if not os.path.exists(path):
            continue
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        blocks.append(
            f"@font-face{{font-family:'IPOSans';font-style:normal;"
            f"font-weight:{weight};font-display:block;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
        )
    return "".join(blocks)


FONT_STACK = "'IPOSans','Roboto','Liberation Sans','DejaVu Sans',Arial,sans-serif"
