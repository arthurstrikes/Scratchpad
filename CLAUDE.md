# Daily Mainboard IPO Watch

A recurring 8:00 PM IST workflow that reads IPOWatch, verifies the numbers,
and produces a WhatsApp-shareable IPO update. Code lives in `ipo_watch/`.

**If you are a fresh session picking this up, read this whole file first.**

## Run it

```bash
cd ipo_watch
pip install -r requirements.txt          # playwright, bs4, lxml, pytest
python3 -m ipo_watch.run                 # live -> ipo_watch/output/
python3 -m ipo_watch.run --fixture-dir fixtures/busy --outdir /tmp/x   # offline
python3 -m pytest tests/ -q              # 20 rule tests
```

Chromium is preinstalled at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`;
`config.CHROMIUM_PATH` points there and `IPOWATCH_CHROMIUM` overrides it.
Do **not** run `playwright install` in a cloud session - use the existing binary.

## Current status

The pipeline is complete and tested. Whether it can run depends on one thing:

**`ipowatch.in` must be reachable.** In a cloud session that requires the
environment's Network access to be **Custom** with `ipowatch.in` and
`*.ipowatch.in` allowed, *and* "Also include default list of common package
managers" ticked. Check first:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" --max-time 20 https://ipowatch.in/
```

`000` means still blocked - say so and stop. Do not substitute another site,
do not fall back to web search, and do not write a report. The run aborts
with exit 2 by design.

## First live run

Nothing has yet parsed IPOWatch's real markup - every sample so far came from
the synthetic fixtures. On the first successful live run:

1. Check the parsed row counts in the log look plausible.
2. Read the saved HTML in `ipo_watch/output/snapshots/`.
3. If a column was missed, add its header wording to `ALIASES` in
   `ipo_watch/parse.py`. Columns are matched by header text, not position,
   so that is normally the only change needed.
4. Copy a snapshot into `ipo_watch/fixtures/` to pin the parser.

## Rules that must not be broken

These come from the user and are enforced by tests in `tests/test_rules.py`:

- Only **Mainboard** IPOs that are **Open** or **Upcoming** are published.
  SME is excluded; closed IPOs are kept in the dataset for validation only.
- **QIB and NII are never shown.** The parser drops those columns.
- **GMP % is always computed** as `GMP / upper price band * 100`, half-up to
  2dp. Never copy IPOWatch's "estimated listing gain".
- Missing number -> `Not updated`. Present but unusable -> `Not verified`.
  GMP of zero -> `0.00%`, never blank.
- Subscription and GMP timestamps are tracked and displayed **separately**.
- On conflict between the two pages, the newer timestamp wins and the
  discarded figure is listed at the bottom of the report.
- **Never guess a number, ever.** Failing closed is always correct.

## Output

Written to `ipo_watch/output/` (gitignored):

| File | Purpose |
|---|---|
| `ipo-watch-<date>.png` | the creative |
| `ipo-watch-<date>.txt` | the full WhatsApp text report |
| `ipo-watch-<date>-dataset.json` | the verified dataset behind both |
| `share.html` | open to share: Share -> pick contacts -> Send |
| `snapshots/` | raw HTML of each page read, for audit |

Send the user the PNG **and** the .txt together - both are the deliverable.
There is deliberately no separate caption file: the text report already ends
with the ranking and the highest GMP / retail / total lines.

## Creative

`creative.py` renders HTML to PNG via Chromium. Every figure carries a
`data-verify` key; after rendering, `verify.py` reads the numbers back out of
the live DOM and diffs them against the dataset. A mismatch re-renders once,
then fails the run. Never loosen that check.

Design decisions the user has already signed off, do not undo without asking:
two-line rows (not cards), no GMP ranking block in the image (it is in the
text), no per-row comparison bars, embedded Roboto from `assets/fonts/`.
Height is the priority - it is read on a phone. A realistic 8-IPO day should
stay near a 1:1 aspect ratio.

## Scheduling

Not yet scheduled. 8:00 PM IST = **14:30 UTC**. Two routes:
- A Routine firing a fresh cloud session daily (works with the user on
  mobile only; needs the allowlisted environment).
- `ipo_watch/install_schedule.sh` for a local 20:00 cron on their own machine.

Confirm with the user before creating either.
