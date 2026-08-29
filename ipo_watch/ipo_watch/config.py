"""Central configuration for the Daily Mainboard IPO Watch workflow."""
from __future__ import annotations

import os
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# --- Primary data source: IPOWatch only (rule 5.9 forbids silent substitution) ---
SOURCE_NAME = "IPOWatch"
SUBSCRIPTION_URL = "https://ipowatch.in/ipo-subscription-status-today/"
GMP_URL = "https://ipowatch.in/ipo-grey-market-premium-latest-ipo-gmp/"
BASE_URL = "https://ipowatch.in"

# Chromium shipped with the image. Overridable for other machines.
CHROMIUM_PATH = os.environ.get(
    "IPOWATCH_CHROMIUM",
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
)

# A real desktop UA: IPOWatch serves a different (lighter) table to bot UAs.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

PAGE_TIMEOUT_MS = 45_000
# IPOWatch hydrates subscription numbers client-side; wait for the network to settle.
SETTLE_MS = 2_500

# Sentinels required by the accuracy rules (section 5).
NOT_UPDATED = "Not updated"      # rule 5.6 - data not published yet
NOT_VERIFIED = "Not verified"    # rule 5.10 - present but unconfirmable

GMP_HIGHLIGHT_THRESHOLD_PCT = 10.0  # section 6: highlight GMP > 10%

OUTPUT_DIR = os.environ.get("IPOWATCH_OUTPUT", "output")
