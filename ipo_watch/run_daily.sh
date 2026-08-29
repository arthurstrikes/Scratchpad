#!/usr/bin/env bash
# Daily Mainboard IPO Watch - one run. Exits non-zero if IPOWatch was unreadable.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p output logs
STAMP="$(date +%Y-%m-%d)"
python3 -m ipo_watch.run --outdir output 2>&1 | tee -a "logs/run-$STAMP.log"
STATUS="${PIPESTATUS[0]}"
if [ "$STATUS" -ne 0 ]; then
  echo "[ipo-watch] run FAILED (exit $STATUS) - nothing published. See logs/run-$STAMP.log" >&2
  exit "$STATUS"
fi
# Open the share package so the final action is: Share -> pick contacts -> Send.
SHARE="output/share.html"
if [ -f "$SHARE" ]; then
  if   command -v xdg-open >/dev/null 2>&1; then xdg-open "$SHARE" >/dev/null 2>&1 || true
  elif command -v open     >/dev/null 2>&1; then open "$SHARE"     >/dev/null 2>&1 || true
  fi
fi
