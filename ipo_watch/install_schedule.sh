#!/usr/bin/env bash
# Installs the 8:00 PM IST daily schedule via the system scheduler.
# Run this on a machine whose clock is IST (or adjust the hour accordingly).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
LINE="0 20 * * * cd $DIR && ./run_daily.sh >> $DIR/logs/cron.log 2>&1"
mkdir -p "$DIR/logs"
( crontab -l 2>/dev/null | grep -v "ipo_watch/run_daily.sh\|$DIR/run_daily.sh" ; echo "$LINE" ) | crontab -
echo "Installed. Daily at 20:00 local time:"
crontab -l | grep run_daily.sh
