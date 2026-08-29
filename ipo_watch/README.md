# Daily Mainboard IPO Watch

Automated 8:00 PM IST IPO update: reads IPOWatch, verifies the numbers,
calculates GMP % independently, and produces a WhatsApp-ready text report,
a share-ready image creative, and a one-tap share page.

## Status

Validated against live IPOWatch on 29 Aug 2026: it parses the real page and
produces correct output. `fixtures/live/` holds trimmed real markup, and five
tests assert the figures parsed from it.

## Quick start

```bash
pip install -r requirements.txt
playwright install chromium      # skip if Chromium is already provisioned
python3 -m ipo_watch.run         # live run -> output/
```

Outputs land in `output/`:

| File | What it is |
|---|---|
| `ipo-watch-<date>.png` | the WhatsApp creative |
| `ipo-watch-<date>.txt` | the full WhatsApp text report |
| `ipo-watch-<date>-caption.txt` | the short forwarding caption |
| `ipo-watch-<date>-dataset.json` | the verified dataset behind both |
| `share.html` | open this to share: Share → pick contacts → Send |
| `snapshots/` | raw HTML of every page read, for audit |

## Scheduling (8:00 PM IST daily)

```bash
./install_schedule.sh     # adds a 20:00 local-time cron entry
```

`run_daily.sh` runs the pipeline, logs to `logs/`, and opens `share.html`
when it finishes. On a non-IST machine, convert the hour: 8:00 PM IST is
14:30 UTC.

## Design rules this implements

**Fetching** — Both IPOWatch pages are server-rendered, so `fetch.py` makes a
plain HTTPS request and parses the delivered HTML. It is the live page every
run, never a cache or a search snippet. A browser path remains in
`fetch.render_pages()` for a future redesign that needs JavaScript.

**Scope** — Only Mainboard IPOs that are Open or Upcoming are published. SME
issues are excluded (detected from the IPO name, the link URL, *and* the
section heading). Recently closed Mainboard IPOs are retained inside the
dataset for validation but never printed. QIB and NII are never captured.

**GMP %** — Always computed as `GMP ÷ upper price band × 100`, rounded
half-up to 2dp. IPOWatch's own "estimated listing gain" column is
deliberately ignored. GMP of ₹0 prints as `0.00%`.

**Accuracy** — Every field is optional and nothing is ever defaulted or
carried forward:

- A number that is absent prints **"Not updated"**.
- A number that is present but unusable prints **"Not verified"** (e.g. a GMP
  with no price band to divide by).
- Subscription and GMP timestamps are captured and displayed **separately**.
- When the two pages disagree, the figure with the newer timestamp wins and
  the conflict is listed at the bottom of the report rather than hidden.
- If neither page yields any rows, the run **aborts with a non-zero exit and
  writes nothing**. It never publishes a report built on guesses.

**Image integrity** — No generative imaging. The creative is HTML rendered by
headless Chromium, with every figure interpolated from the dataset. Each
figure carries a `data-verify` key; after rendering, `verify.py` reads the
numbers back out of the live DOM and diffs them against the dataset. Any
mismatch re-renders once, then fails the run.

## Network access

The pipeline needs outbound HTTPS to `ipowatch.in`. In the environment this
was built in, that host returns 403 at the egress proxy, so no live run has
been possible. Two ways to fix:

1. **Run it on your own machine**, where the site is reachable. This is the
   simplest path and is what `install_schedule.sh` sets up.
2. **Allowlist `ipowatch.in`** for the Claude Code environment, then the
   scheduled cloud run works too.

## Calibrating the parser

Column positions are matched by *header text*, not index, so the parser
tolerates layout changes. But it has never seen IPOWatch's real markup. On
the first live run, check `output/snapshots/` and confirm the parsed row
count looks right. If a column is missed, add its header wording to
`ALIASES` in `ipo_watch/parse.py` — no other change should be needed.

## Creative sizing

The image is tuned for being read at roughly a third of its native width in
a chat thread, so type is larger than a screen design would use and the
layout is dense: upcoming IPOs (which carry no subscription data) use a
compact single-line card, and ranking is shown once in the ranking strip
rather than repeated on every card. A busy day of 5 open + 3 upcoming IPOs
renders at 1080x2333, a 1:2.16 ratio that WhatsApp still shows legibly.
`fixtures/busy/` exercises that case.

## Tests

```bash
python3 -m pytest tests/ -q     # 20 tests
```

They cover the GMP formula (including the ₹325 / ₹429 → 75.76% worked
example), the 0.00% rule, "Not updated" / "Not verified", SME exclusion,
QIB/NII never reaching the output, timestamp-based conflict resolution, and
the image-vs-dataset check catching an altered number.

## Layout

```
ipo_watch/
  config.py    URLs, sentinels, thresholds
  fonts.py     subset Roboto, inlined so the creative needs no system font
  fetch.py     rendered-DOM fetching + HTML snapshots + timestamp scraping
  parse.py     header-driven table parsing, SME detection
  models.py    IPO record, GMP maths, all number formatting
  merge.py     joins the two pages, resolves conflicts, filters scope
  report.py    WhatsApp text report + caption
  creative.py  HTML -> PNG creative
  verify.py    image-vs-dataset consistency check
  share.py     one-tap share page
  run.py       orchestrator / CLI
```
