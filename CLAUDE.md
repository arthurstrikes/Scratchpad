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

## Delivery: Telegram, plus the Claude session as a backup

**Direct WhatsApp delivery was researched on 29 Aug 2026 and declined** - do
not rebuild it without a fresh decision from the user:

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

**The original plan - the Routine sends the PNG and .txt into a Claude
session, the user forwards it by hand - turned out not to work reliably**,
for two independent reasons discovered between 29 Aug and 3 Sep 2026:

1. Push notifications from the Routine failed silently on multiple confirmed
   *successful* runs (see "If a scheduled run reports a problem" below). The
   user could not tell a quiet night from a broken one without opening the
   app to check.
2. The Claude mobile app's own image viewer for a file sent via
   `SendUserFile` has no share, save, or download option - confirmed by
   screenshot on 29 Aug 2026. Neither switching `display` to `"attach"` nor
   publishing the image as a Claude Artifact fixed this: an Artifact link
   opens inside the same app's own restricted in-app browser (Android treats
   `claude.ai` as an app link), even after the user changed their phone's
   "open by default" setting for the Claude app. The only thing that worked
   was manually copying the link and pasting it into a separate browser app -
   more manual steps than the problem it was meant to solve.

**So `ipo_watch/telegram.py` sends the image and the full report directly to
a personal Telegram bot**, via `python3 -m ipo_watch.run` itself - not
something the Routine's prompt has to remember to do. A Telegram photo
message is a normal, fully-native message: long-press it and the phone's own
share sheet offers WhatsApp directly, the same as any other photo. This
fixes both problems in one move, since neither limitation exists on
Telegram.

**Setup** (one-time, done by the user - I cannot do this part; there is no
tool to set environment variables on a cloud environment):

1. In Telegram, message **@BotFather**, send `/newbot`, give it a name and a
   username ending in "bot". It replies with a bot token.
2. Search for that new bot by username and send it any message (e.g. "hi") -
   required once, since a bot cannot message someone who has never messaged
   it first.
3. Get the numeric chat id either by messaging **@userinfobot** directly (it
   replies with the id, keeping the bot token out of any conversation with
   Claude), or by giving Claude the token and having it call
   `telegram.lookup_chat_id()` to read it from the bot's own pending updates.
4. Add both as environment variables on the environment the Routine runs in
   (`env_01Vf2kqsvn722zF65XjRQxQj`) - **never commit them to this repo**:
   ```
   TELEGRAM_BOT_TOKEN=<from BotFather>
   TELEGRAM_CHAT_ID=<numeric id>
   ```

Without both variables set, `telegram.configured()` is `False` and sending
is silently skipped - this keeps every existing fixture-based test and
offline run working exactly as before. Telegram delivery is additive, not a
data-accuracy control: a Telegram outage is logged plainly
(`telegram -> FAILED: ...`) but never changes the run's exit code, and must
never be treated as if the underlying numbers were wrong.

The Routine still also does the original `SendUserFile` + paste-in-chat
delivery on top of this - kept as a free backup, not because it is expected
to be the primary way the user gets the update.

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

On the scheduled run specifically (not necessarily an ad-hoc one run by hand),
also paste the complete report text into the chat reply itself, in a code
block, in addition to attaching the .txt file. The user reads this on a
phone and long-presses the message to copy it straight into WhatsApp; making
them open the attachment first was needless friction. This lives in the
Routine's own prompt (`trig_01EReco6VzLZHTxJ5tdFADpG`), not in this repo's
code - if the Routine is ever recreated, carry this instruction over too.

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

- Trigger id: `trig_01RLth6vAxrBZNfhHCXmWNDV`
- Environment: `env_01Vf2kqsvn722zF65XjRQxQj` (Network access: Custom,
  `ipowatch.in` + `*.ipowatch.in`, package-manager defaults included)
- Notifications: push AND email. Email was added on 29 Aug 2026 as a second
  channel after push notifications did not reach the user's phone on two
  separate real, successful test runs - both confirmed
  `ROUTINE_RUN_STATUS_SUCCEEDED`, so the break is in notification delivery,
  not the pipeline. `update_trigger` cannot change notification settings -
  it has no such parameter - so changing this means delete + recreate,
  which is why the trigger id above differs from earlier in this file's
  history. If the user says push notifications are working reliably again,
  email can be dropped the same way (delete + recreate with
  `{"push": true}` only).

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
4. **The Routine's own prompt is missing the `git clone` step.** Every firing
   starts on a completely bare computer - nothing survives between nights.
   The stored prompt MUST open with cloning
   `https://github.com/arthurstrikes/Scratchpad.git` before it does anything
   else; CLAUDE.md being "read at the repo root" only works once that clone
   has happened. This bit the very first scheduled run (29 Aug 2026) - the
   prompt assumed the code would already be there. If the trigger is ever
   deleted and recreated (e.g. to change the time), copy the clone step from
   `update_trigger`'s current prompt - do not write a fresh one from memory.
5. **Notification silent, but the run itself succeeded.** Check
   `list_triggers` for `last_run.status` - if it says
   `ROUTINE_RUN_STATUS_SUCCEEDED`, the pipeline is fine and the problem is
   notification delivery, which lives outside this repo entirely (Routines
   are in research preview). This has now happened twice with two different
   notification configurations: push-only failed to notify during testing on
   29 Aug 2026 (which is why email was added as a second channel), and then
   on 1 Sep 2026 the real scheduled 8 PM run succeeded but *neither* push nor
   email arrived. Two failures across two configurations means this is a
   platform reliability issue, not a settings problem - do not keep adding
   channels or "fixing" the pipeline in response to a silent night. Tell the
   user plainly that the run succeeded and where to find it (their session
   list, titled after this Routine), and suggest they check the app directly
   around 8:05 PM IST until Anthropic's notification delivery is reliable.
