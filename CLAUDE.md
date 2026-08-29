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

Validated against live IPOWatch on 29 Aug 2026. It parses the real page and
produces correct output.

**`ipowatch.in` must be reachable.** In a cloud session that needs the
environment's Network access set to **Custom** with `ipowatch.in` and
`*.ipowatch.in` allowed, *and* "Also include default list of common package
managers" ticked. Check first:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" --max-time 20 https://ipowatch.in/
```

`000` means blocked - say so and stop. Do not substitute another site, do not
fall back to web search, and do not write a report. The run aborts with exit 2
by design.

## How IPOWatch is actually laid out

Learned from the live page; `fixtures/live/` pins it and five tests assert it.

**Subscription page** - one table:
`IPO | Type | Closing Date | QIB (X) | NII (X) | Retail (X) | Total (X) | Last Updated`
- `Type` says "Mainboard" or "SME" outright. Authoritative; do not re-derive.
- Only a *closing* date. Open dates come from the GMP page.
- `Last Updated` is a bare time per row, e.g. `17:45`.
- ~190 rows going back months, mostly closed.

**GMP page** - three tables:
- Table 0, under "Mainboard IPO GMP", and table 1, under "SME IPO GMP":
  `IPO Name | IPO GMP* | Trend | Price Band | Est. Listing | Date | Status | Last Updated`
  - `Status` says "Open"/"Upcoming"/"Closed" outright. Authoritative.
  - `Price Band` is a single cap price (`₹429`), not a range.
  - `Date` is compact: `28-1 September` means 28 Aug to 1 Sep. When the first
    number is larger it belongs to the previous month.
  - `Est. Listing` is IPOWatch's own estimate - **banned**, section 4 requires
    computing GMP % ourselves.
- Table 2, "Mainboard IPO GMP Performance": already-listed history, no Status
  or Date. Skipped, because a table with no date and no status cannot be
  placed in time and its names could collide with live rows.

Both pages are **server-rendered** - the tables are complete in the delivered
HTML. `fetch.py` uses a plain HTTPS request, not a browser. Chromium in this
sandbox does not trust the egress proxy's CA (a known-good host fails with
`ERR_CERT_AUTHORITY_INVALID`), and disabling TLS verification is not
acceptable. `fetch.render_pages()` keeps a browser path if a redesign ever
needs JavaScript.

If a column moves, add its header wording to `ALIASES` in `parse.py` - columns
are matched by header text, never by position.

## Working agreement with the user

The user is not a programmer and has asked to be kept out of technical
decisions. So:

- **Decide, then explain.** Make the technical call yourself. Explain what you
  did in plain language - no jargon, no assumed background - and say why.
- **Ask first for anything hard to undo**, and for anything that changes the
  published numbers, the creative design, the schedule, or how the update is
  delivered. Explain the options in simple words and wait for a clear yes.
- **Merge low-risk work yourself**: documentation, bug fixes, parser repairs
  after an IPOWatch layout change. Open the PR, merge it, and tell them what
  changed. Do not make them click through it.
- **Never give investment advice or rank IPOs as buys.** Report the numbers.

## Delivery is manual on purpose

The user asked for the update to post itself to WhatsApp with no interaction.
This was researched on 29 Aug 2026 and declined; do not rebuild it without a
fresh decision from them.

- WhatsApp has no free, terms-compliant way for software to post into a
  personal chat or group. That is Meta's product decision.
- The official Cloud API bills per business-initiated message (India: roughly
  ₹0.115-0.145 + GST, about ₹60/year for one a day), needs a phone number
  never registered on normal WhatsApp, business verification, and template
  approval.
- Its group support, added in 2026, caps groups at 8 members and appears to
  cover only groups the business number itself owns - not an existing
  personal group.
- Unofficial libraries (whatsapp-web.js and similar) break WhatsApp's terms
  and risk a ban on the user's own number. They also need a session that
  stays logged in, which cannot survive a fresh container every night.
  **Do not build this.**

So the run sends the user the PNG and the .txt, and they forward it by hand:
notification -> open session -> long-press image -> Share -> WhatsApp. Free,
permitted, and it keeps a human eye on the figures before they reach anyone
else. Telegram remains the free fully-automatic option if they ever accept a
different app.

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

**Live since 29 Aug 2026.** A Routine fires a fresh cloud session every day at
`30 14 * * *` UTC — 8:00 PM IST — in the allowlisted environment, runs the
pipeline, and sends the user the PNG and the .txt with a push notification.

- Trigger id: `trig_01EReco6VzLZHTxJ5tdFADpG`
- Environment: `env_01Vf2kqsvn722zF65XjRQxQj` (Network access: Custom,
  `ipowatch.in` + `*.ipowatch.in`, package-manager defaults included)

To change the time, pause it, or edit what it says, use `update_trigger` with
that id, or the Routines UI on claude.ai. Do not create a second Routine for
this — the user would get two updates a night.

`ipo_watch/install_schedule.sh` still exists for a local 20:00 cron if they
ever want it running on their own machine instead.

## If a scheduled run reports a problem

The run fails closed, so a failure means no report was sent — not a wrong
report. Usual causes, in order of likelihood:

1. **IPOWatch layout changed** — parse counts drop to zero and the run aborts.
   Read the snapshot, extend `ALIASES`, re-pin `fixtures/live/`.
2. **Egress blocked again** — `curl` returns 000. The environment's network
   settings changed; nothing to fix in code.
3. **Image check failed** — the creative disagreed with the dataset. This
   should be impossible; investigate rather than loosening the check.
