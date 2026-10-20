# IPO Watch: living roadmap

The one page that answers: where are we, what went wrong, what is open, and
what would make this world class. Written in plain language. `CLAUDE.md` holds
the rules and the technical history; this page holds the plan.

**Keeping it alive:** whoever works on this updates the page in the same change
(done, found, decided, still open). Dated entries, newest first. Nothing here
is ever deleted, only marked done.

Last updated: 18 Oct 2026. **Fresh session? Read section 0 first.**

---

## 0. Where we left off (18 Oct 2026) - read this first

**Live engine today:** the 5:05 PM backup trigger (`trig_01AnmiV5iED3Xe8jVFkVd7zD`) fires into the long-running
interactive session, which runs `python3 -m ipo_watch.run --outdir output` from `~/Scratchpad`
(= `/root/Scratchpad`), sends the PNG and .txt, pastes the report, and states the Telegram line.
**Capture the whole run log to a file** (`> /tmp/run.log`) - on 16 Oct the Telegram line was lost by piping to `tail`.
The 5:00 PM routine is still dead (classifier) and only the user can delete it in the Routines list.

**GitHub secrets: DONE 18 Oct** (Telegram send from GitHub proven; failure notice arrived). **Go-live is PAUSED**: IPOWatch returned 403 / a reduced page to GitHub's runners on 18 Oct (G24). Re-test with a dry run (`ipo-watch.yml`, `send_telegram` false) on later days; go live only after a dry run parses ~290 subscription rows and the GMP rows. **Waiting on the user:**
(2) their yes to the open proposals (G17 closed-awaiting-listing section; cash-for-lots, upgrade 4).
**Then:** dispatch the daily workflow once with `send_telegram` on, confirm arrival, add the cron lines
(daily `30 11 * * *`, midday `30 8 * * *`, watchdog `55 11 * * *`, listing `30 13 * * 1-5`, weekly `30 12 * * 0`, all UTC),
retire the 5:05 PM backup (classifier may block `update_trigger`), user deletes the 5:00 PM routine.

**Built 16-18 Oct (all merged to main):** Tonbo minimum-investment fix; Data note when a minimum is missing;
trend measured against the figure *we* published; then the decision aids (below).
**Also remember:** reminder `trig_01SNDhTcCYzauXQsXpk7aHax` fires 20 Oct 14:00 UTC to run the listing scorecard for
HD Fire Protect from the session (skip if the GitHub listing workflow is live). Seed the `history` branch with the
backfilled listing results after any merge that changes their format (see section 6b).

**Dry runs no longer e-mail "Run failed" (19 Oct):** the user saw GitHub failure e-mails for the test runs. The daily check now runs with `continue-on-error`, so a dry run never fails the job; **judge PASS/FAIL only from the log** (`parsed N subscription rows, M GMP rows` and `image data check passed`), not from the run conclusion. Real sends still fail loudly.

**Standing duties (the user asked on 19 Oct: do these without being reminded):**
1. **GitHub dry-run check, every day.** Trigger `trig_01P5bUqYnxfojzDfwuMvF7JZ` (12:15 UTC = 5:45 PM IST, fires into the long-running session) dispatches `ipo-watch.yml` with `send_telegram` false, reads the log and adds a line to the table below. PASS = succeeded, at least 100 subscription rows, at least 1 GMP row, image check passed. Say nothing to the user on a FAIL. **After three passes in a row, tell the user and ask for a yes** before going live (schedules, retiring the 5:05 PM backup). Never send a real run from this check.
2. **Sundays:** after the daily report, also run `python3 -m ipo_watch.run --mode weekly --outdir output > /tmp/weekly.log 2>&1` (the weekly wrap) until the GitHub weekly schedule is live; attach nothing, just confirm the Telegram line in the reply.
3. **20 Oct, 7:30 PM IST:** listing scorecard for HD Fire Protect (reminder `trig_01SNDhTcCYzauXQsXpk7aHax`).
4. Every daily run: save the whole log to a file, report the Telegram line, flag oddities in two or three lines.

### GitHub go-live test log (dry runs, nothing sent)

| Date | Result | Notes |
|---|---|---|
| 18 Oct | FAIL | 403 on the plain request; browser fallback got a reduced page (15 subscription rows, 0 GMP); run now aborts in that case |
| 19 Oct | FAIL | Reduced page again (15 subscription rows, 0 GMP rows); run aborted as designed. Pass streak: 0 |

**How the user likes to work:** not a programmer; wants plain language ("explain like a 10th standard student");
decide technical things myself; ask before changing published numbers, design, schedule or delivery; wants
UI/UX and user empathy to drive choices; never investment advice.

---

## 1. What "world class" means here (the bar we measure against)

| Quality | The standard | Where we are |
|---|---|---|
| **Accurate** | Every number traces to the source page; nothing guessed; the image provably equals the data | Met. GMP % is computed by us; the image is read back and checked; 55 rule tests |
| **On time** | The report lands in Telegram by about 5:10 PM IST every day | Met since 16 Sep, but only via the 5:05 PM backup (see gap G5) |
| **Never silent** | A broken day is announced, never mistaken for a quiet one | Half met: failure notices built 15 Oct; the "nothing arrived" alarm is built but not switched on |
| **Hands-off** | Runs with no person and no Claude session | Not yet. **Proven on GitHub (15 Oct dry run succeeded)**; waiting for two secrets (A1) to send from there |
| **Useful at a glance** | Answers "is it moving, what do I need, when does it list" without opening a link | Mostly: trend, minimum investment and dates added 15 Oct. Listing outcomes still missing |
| **Reads well in WhatsApp** | Fits the chat thread, copies cleanly, forwards cleanly | Built (4:5 fit, tap-to-copy, WhatsApp bold). Not yet confirmed on your phone (A4) |
| **Learns** | Tracks how reliable GMP turned out to be against the real listing | Started 18 Oct: one-line GMP track record (last 25 listings) in text and image. Only 10 listings have a GMP on record so far; it sharpens with every listing |

## 2. Achievements

| Date | What |
|---|---|
| 29 Aug 2026 | Pipeline live: reads IPOWatch, verifies, builds image + text, strict accuracy rules |
| 10-11 Sep | Moved to 5 PM; Telegram delivery confirmed end to end |
| 15 Sep | Backup trigger created to get around the permission block on the 5 PM routine |
| 25 Sep - 5 Oct | Kept working through **five** IPOWatch layout changes (timestamp column removed, a name mismatch, an SME leak in the conflicts note, then three name-format changes in three days) |
| 12 Oct | Audited the two routines; confirmed the 5 PM one is still blocked and cannot be paused from inside a session |
| 14 Oct | Fixed the wrong "8:00 PM" label; new look in the Loop / Inner Circle style; WhatsApp bold; tap-to-copy block |
| 15 Oct | **GMP trend with sparkline**, minimum investment, allotment + listing dates, image held to 4:5, Telegram failure notices, closing-day midday update, GitHub runner + watchdog (staged and **proven by a dry run**), history branch, compressed + more patient fetching. Tests 20 -> 56 |
| 15 Oct (later) | **Listing-day scorecard** built and replayed on real NSE data (21 past listings matched, e.g. Nityas Gems listed +6.67% vs GMP 4.00%; Vishal Nirmiti -2.27% vs +9.09%). Compact photo caption. Tests 56 -> 68 |
| 15 Oct (late) | Listing scorecard also **proven on GitHub's runner** (replayed 8 Oct, same result) |
| 15 Oct (night) | Listing results now also in the **daily image** (slim strip: listing gain, day 1, GMP said; 3 rows down to 1 as space allows). High GMP flag raised to above 25%. Tests -> 72 |
| since 16 Sep | Daily report delivered every day through the backup (about 30 days) |
| 16 Oct | Found why Tonbo had no minimum investment (its detail page has a different web address; our guess redirected to the GMP page). Fixed by following the page's own "IPO Details" button. A missing minimum now also shows under Data notes |
| 18 Oct | **Trend baseline fixed:** IPOWatch revised its own 17 Oct figures after we published, so "vs yesterday" showed "no change" while the GMP had moved. The trend now compares against the figure we published |
| 18 Oct | **Decision aids built (user said "all"):** "Closes today / tomorrow / N days left" tag, a counts-only "at a glance" line, subscription change since our previous update, a one-line GMP track record over the last 25 listings, and a Sunday weekly wrap. Backfill saved 21 past listings (10 with a GMP on record). Tests 75 -> 82 |

## 3. Gaps and misses (honest list, including mine)

| # | What | Why it matters | Status |
|---|---|---|---|
| G1 | The "8:00 PM" label stayed wrong for **5 weeks** (10 Sep to 14 Oct) | Nobody looked at the finished image after the schedule changed. You caught it, not a check | Fixed. Lesson: after any schedule or config change, look at the real output and search for the old value |
| G2 | The subscription time (`17:41`) was labelled as *today* even when it was yesterday's | A stale figure looked fresh. Present since launch | Fixed 15 Oct |
| G3 | The page fetch had **no retry** | One dropped connection = no report that day. Present since launch | Fixed 15 Oct (4 tries, waits of 5/15/30 s) |
| G4 | The 5 PM routine has been failing **silently since 9 Sep**, and the platform still shows "succeeded" | Five weeks of a broken job that looked healthy | Understood and documented. Cannot be paused from a session (A3) |
| G5 | **Single point of failure:** the daily report only exists because *this* session stays alive | If the session is archived or reset, reports stop with no warning | Fix staged: the GitHub runner (A1-A3) |
| G6 | No alarm if a day is missed | You found out by checking, not by being told | Built 15 Oct (watchdog), not yet switched on |
| G7 | IPOWatch changed its layout 5 times in 2 weeks; our only defence is "abort if nothing parses" | A subtle change (like the name suffixes) can degrade quality without aborting | Open: layout canary (I4) |
| G8 | No archive of past reports outside a container | History disappears if the container does | **Built 15 Oct:** `history` branch seeded with 28 Sep - 14 Oct, filled by each real GitHub run |
| G9 | `README.md` and `install_schedule.sh` still describe the old 8 PM setup; `CLAUDE.md` still says "20 tests" | Misleading to a newcomer | Open (A9) |
| G10 | The 12 Oct complaint "not working for many days" was never root-caused (the test message arrived; likely phone notifications) | Could recur | Open: the watchdog + failure notices would make it provable |
| G11 | Nothing checks the image *layout* (overflow, clipping); tests only check the figures | A cosmetic regression could ship unseen | Open: visual regression test (I6) |
| G12 | Tap-to-copy and the WhatsApp crop are untested on a real phone (I cannot test inside WhatsApp) | Might not behave as designed | Needs you (A4) |
| G13 | I sent 100+ requests to IPOWatch in one hour while testing, and IPOWatch was slow or timing out for both the sandbox and GitHub that afternoon | Partly my doing, partly the site. Nightly load is only 18 requests | Mitigated: gzip, longer waits, retries, own-history fallback. Test with saved pages |
| G14 | I suggested a **Telegram channel** for your WhatsApp contacts. That was weak: they can only follow it if they use Telegram | Misleading idea | Withdrawn unless your audience uses Telegram (A8) |
| G15 | The trend compares against IPOWatch's own daily record; our own previous report can differ (Jio: 200 vs 220) | Two honest baselines | Needs your preference (A5) |
| G17 | ~~**Closed IPOs disappear~~ (**closed 18 Oct: section built, only for GMP above 25%**) **Closed IPOs disappear between close and listing.** HD Fire Protect closed 15 Oct and lists 20 Oct, but is in no report in between, although allotment and listing are what an applicant cares about then | An applicant loses the very dates they need most | **Proposal to the user:** a small "Closed - awaiting allotment / listing" section (dates only, no subscription). Needs their yes: it changes the published-IPO rule |
| G18 | On 16 Oct Tonbo's minimum investment was missing and nothing said so | A silent gap | Fixed 16 Oct; now a Data note appears |
| G19 | The "vs yesterday" trend used IPOWatch's *revised* row, not what we published (Sahajanand showed no change on a Rs 20 fall) | Misleading trend | Fixed 18 Oct (supersedes G15 and A5) |
| G20 | IPOWatch does not refresh subscription on weekends, so Sat/Sun reports repeat Friday's multiples | Looks fresh, is not | Now visible: the new subscription-change tag reads "no change"; the stamp is in the footer |
| G21 | I lost the Telegram result line on 16 Oct by piping the run log through `tail` | Could not confirm delivery to the user | Process fix: always save the whole log to a file |
| G22 | GMP track record rests on only 10 listings with a GMP on record (our reports began 28 Sep) | Small sample | Text states the real count; shown only from 5 upward; grows daily |
| G31 | **HD Fire Protect's listing scorecard was at risk:** NSE's list of securities lacked it on listing morning (latest entry 14 Oct), and listing mode would have said "nothing lists today" | The very IPO the user cares most about | Fixed 20 Oct: trusts IPOWatch's listing date, keeps polling, sends a "not out yet" note, replay next day |
| G30 | Reports on weekends repeated Friday's figures with only a small footer stamp | Stale numbers looked fresh | Fixed 20 Oct: "⏳ figures are from <date>" line and an amber stamp in the image |
| G29 | No early warning when IPOWatch changes its layout (5+ changes in 3 weeks; 19 Oct nearly cost a report) | Silent degradation | Built 20 Oct: layout canary (operator-only `LAYOUT CHANGE` log lines); closes backlog I4 |
| G28 | The 19 Oct image came out 1433px tall (over 4:5): 7 IPOs + awaiting + track record exceeded the densest tier | WhatsApp crops very tall images | Fixed 19 Oct: a fourth density tier; test added; corrected image re-sent |
| G27 | **19 Oct 5:05 PM run aborted: IPOWatch changed the subscription header "IPO" to "1"** (0 rows parsed; failure notice reached Telegram; the abort rule worked as designed) | A silent layout change nearly cost the day | Fixed same hour (parser treats a numeric/blank first header as the name column) and the report re-run; layout canary (I4) would catch this earlier |
| G26 | **Second feedback round, 18 Oct (late), all four built:** High GMP flag back to the exact value (25.4% is flagged); subscription change only when meaningful (0.1x and 5%), for Retail **and** Total, compact in the image; track-record fourth tile rewritten as plain "GMP accuracy: 5 of 10 within 10 pts"; issue price added to the awaiting-listing section | Plain words and less noise | Done; retested live |
| G25 | **User feedback 18 Oct (evening), all five built:** whole-number GMP %, distinct urgency tags only for today/tomorrow, weekend carry-forward of the last move, GMP track record as a 25-listing scoreboard, "Closed - awaiting listing" for GMP above 25% (closes G17) | The report was cluttered where it should be calm | Done 18 Oct; retested live the same evening |
| G24 | **First real GitHub send (18 Oct) failed: IPOWatch answered GitHub's runner with HTTP 403.** The failure notice reached Telegram (so the secrets work). After the browser fallback the page loaded but was a reduced one (15 subscription rows instead of ~290, no GMP rows), and the run still produced a report full of "Not updated" | GitHub cannot be the main engine while IPOWatch treats its runners as bots; and a half-empty report must never be sent | Run now aborts unless **both** pages parse (fix 18 Oct). Browser fallback kept. Retry GitHub dry runs in a day or two; if still blocked, the session backup stays the engine (go-live paused) |
| G23 | The photo caption does not travel to WhatsApp (tested by the user 15 Oct) | Image and text stay two steps | Answered A4. Options in 5b; caption kept simple |
| G16 | On 15 Oct IPOWatch's extra pages timed out, so the first GitHub dry run showed "GMP trend: Not updated" for most IPOs | The design degrades honestly, but a real send would look thin | Mitigations shipped (see G13); re-check on the next live run |

## 4. Open actions

| # | Action | Owner | Needs |
|---|---|---|---|
| A1 | Add two GitHub secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`): repo **Settings > Secrets and variables > Actions** | **You** | 3 minutes. I can walk you through it |
| A2 | Run the GitHub workflow once with Telegram on and confirm it arrives | Me + you | A1 |
| A3 | Go live: switch on the three schedules, retire the 5:05 PM backup, delete the dead 5:00 PM routine in the Routines list on claude.ai | Me (code) + **you** (the routine, I am blocked from it) | A2 and your yes |
| A4 | ~~Tell me~~ **Answered 15 Oct:** image shares straight to WhatsApp; the caption does not come along; text is copied separately. Original question: tell me how tonight's image looks in WhatsApp, whether tap-to-copy pastes with bold, **and whether the photo's caption comes along when you share the photo from Telegram to WhatsApp** (decides step 2 in section 5b) | **You** | Tonight's report. You said you'll share after the 5:05 PM run |
| A5 | ~~Pick the trend baseline~~ 15 Oct: IPOWatch's record; **changed 18 Oct (user: yes) to the figure we published the day before** | done | |
| A6 | ~~Where listing results come from~~ **Decided 15 Oct:** exchange data (NSE): issue price to first-day open, and separately first-day open to close. Built the same day | done | |
| A7 | ~~Second source~~ **Decided 15 Oct (my call, you said numbers need not match):** NSE's official data is the independent check for listing facts; no second GMP website, because GMP sites differ by nature and a cross-check would add noise, not safety | done | |
| A8 | Who receives the report (individuals or WhatsApp groups) and how many? Decides whether the WhatsApp Business route (5b, step 3) is worth it | **You** | One line |
| A9 | Refresh `README.md`, `install_schedule.sh`, the test count in `CLAUDE.md` | Me | Nothing |

## 5. Innovation and automation backlog

Ordered by value for effort. "Needs" says what blocks it.

### Reliability and automation
| # | Idea | Value | Needs |
|---|---|---|---|
| I1 | **GitHub runner as the real engine** (built, staged) | Removes the single point of failure; no Claude session needed | A1-A3 |
| I2 | **"Nothing arrived" watchdog** (built, staged) | A missed day announces itself | A1-A3 |
| I3 | **Midday closing-day update** (built, staged) | Catches the last-day subscription surge | A1-A3 |
| I4 | **Layout canary:** compare the page's column headings and structure to a pinned fingerprint every day and warn *before* a change degrades the report | Five layout changes in two weeks says this is the biggest accuracy risk | Me |
| I5 | **History branch** (done 15 Oct, seeded; written by the GitHub run once live) | Real history, trend fallback anywhere, feeds I7 and I8 | A1-A3 to start filling |
| I6 | **Visual regression test:** render fixtures and compare pixels | Stops silent layout breakage | Me |
| I7 | **Delivery health line** ("30 of 30 days delivered, median 5:06 PM") in a weekly note | Proof of reliability | I5 |

### More useful content
| # | Idea | Value | Needs |
|---|---|---|---|
| I8 | **Listing-day scorecard** (done 15 Oct, matched 21 past listings): issue price to first-day open, first-day open to close, next to the GMP we last reported and the gap in points. Evening card + text; the daily report shows the last 3 days. Next: a running GMP accuracy score (I8b) | The most differentiating idea here | Evening schedule needs A1-A3 |
| I9 | **Date reminders.** Done 18 Oct for the closing day ("Closes today / tomorrow / N days left" in text and image). Still open: "allotment tomorrow", "lists tomorrow" | Small, high value | Me |
| I10 | **Weekly Sunday summary:** built 18 Oct (`--mode weekly`, workflow `ipo-watch-weekly.yml`, manual-only). Lists the week's listings vs GMP and what is coming up | Useful recap | Schedule needs A1-A3 |
| I11 | **Subscription momentum** (day-by-day retail multiple, last-day surge) | Shows demand building, not just a number | I5 |
| I12 | **Big-move alert** (GMP jumps or falls sharply versus the morning) | Time-sensitive signal | Runner (I1) |

### Next-wave ideas (added 15 Oct, night)
| # | Idea | Value | Needs |
|---|---|---|---|
| I18 | **GMP accuracy scoreboard** in the scorecard and a weekly note: running average gap, how often GMP overstated, accuracy by GMP band. Backfill already possible (see section 5c) | Turns every listing into evidence about how far GMP can be trusted | Me; data exists |
| I19 | **Date reminder lines** in the daily report: "allotment tomorrow", "lists tomorrow" | Small and high value; dates already collected | Me |
| I20 | **GMP freshness stamp per IPO** ("GMP as of 12:10") from the IPO page's own update time | A stale number becomes visible instead of looking fresh | Me |
| I21 | **Big-move alert:** message only when a GMP moves sharply against the morning (checked every 30-60 min on open days) | Time-sensitive; silent otherwise | GitHub live (A1-A3) |
| I22 | **Subscription curve** per open IPO (day by day, last-day surge) from saved pages | Shows demand building, not just today's multiple | I5 (done) |
| I23 | **One-link status page** (Loop style): last delivery, GMP trend per IPO, accuracy scoreboard | One place to look, no scrolling Telegram | Your OK; reads the `history` branch |
| I24 | **Duplicate-aware backup:** the Claude-session backup first checks the `history` branch and skips if GitHub already delivered today | Lets both run safely during and after go-live; true standby | A1-A3 |
| I25 | Hindi (or other language) caption variant | Wider audience | Your audience |

### Delivery and design
| # | Idea | Value | Needs |
|---|---|---|---|
| I13 | One-IPO share cards (square, one IPO per image) | Easier to forward one IPO | Your wish |
| I14 | Hindi or other-language caption variant | Wider audience | Your audience (ask) |
| I15 | Second source used **only** to flag disagreement | Catches a bad IPOWatch figure | A7 |
| I16 | Telegram channel | Only for recipients who use Telegram (see 5b) | A8 |
| I17 | WhatsApp Business Cloud API (about Rs 60 a year for one message a day; more per recipient) | The only compliant way to post to WhatsApp automatically, to **individual opted-in numbers** (not groups) | Previously declined; see 5b step 3 |

### 5d. UI / UX and user-empathy backlog (added 18 Oct)

Guiding question for every item: *what does the person need in the first ten seconds, on a phone, possibly in a hurry?*

| # | Idea | Why it helps the reader | Status |
|---|---|---|---|
| U1 | Closing tag on each open IPO and a counts-only glance line | Answers "what needs me today?" without reading dates | **Done 18 Oct** |
| U2 | Subscription change since the last update | Shows demand moving, not just a number | **Done 18 Oct** |
| U3 | GMP track record sentence | Keeps the reader's trust calibrated: GMP is a rumour, not a promise | **Done 18 Oct** |
| U4 | "Closed - awaiting allotment/listing" section (G17) | The applicant's next dates never vanish | Proposed, needs yes |
| U5 | Cash needed for 1 / 2 / 3 lots | Answers "how much do I put in?" | Proposed (upgrade 4), not requested |
| U6 | "Allotment tomorrow" and "Lists tomorrow" tags | Same logic as the closing tag, for the later dates | Proposed (I9) |
| U7 | One-IPO share cards | Easy to forward just one IPO | Backlog (I13) |
| U8 | Hindi or other-language caption | Wider audience | Backlog (A8) |
| U9 | Quiet-day wording: on weekends say plainly "IPOWatch has not refreshed since Friday" | Honest about stale numbers | Idea; the footer stamp covers it today |
| U10 | Accessibility check of the image (contrast, minimum text size on a phone) | Readable in sunlight and for older eyes | Backlog |

### 5c. Evidence so far: how far GMP missed (15 Oct, from NSE vs our saved reports)

Small samples; read as direction, not proof. Not investment advice.

- **21 listings matched** (28 Sep - 14 Oct): average listing gain +15.4%, median +4.7%;
  14 listed above issue, 3 flat, 4 below. Open-to-close on day 1: average -0.4%,
  closed lower than it opened in 11 of 21.
- **10 of them have a GMP on record:** GMP said +15.2% on average, actual +15.1%,
  but the *average miss per IPO was 13.1 points* and GMP overstated in 6 of 10.
  GMP above 25% (2 IPOs): said +33.8%, actual +63.6%. GMP of 25% or less (8): said
  +10.6%, actual +3.0%, 5 of 8 listed above issue.
- Biggest misses: Orient Cables (+38.97 pts), Moneyview (+20.58), Acevector
  (-17.75), German Green Steel (-15.83).

### 5b. Getting it into WhatsApp with less effort (smart options, in order)

WhatsApp cannot be automated for groups, so the aim is fewer taps for you and
nothing lost on the way:

1. **Done 15 Oct: a compact summary now rides on the photo as its caption.**
   If Telegram carries the caption across when you share the photo to WhatsApp
   (I could not verify this from here and it may differ by phone; please test, A4), one long-press -> Share ->
   WhatsApp sends the image **and** the summary together.
   **Tested 15 Oct by the user: the image shares straight to WhatsApp, the caption
   does NOT travel; the text has to be copied separately (A4 answered).** So step 2
   below is the live question.
2. **The caption does not travel:** a small share page (the Web Share button
   sends image + text together to WhatsApp in one tap), linked from the Telegram
   message. It needs a public GitHub Pages page (your OK, and one setting
   click from you). The page would hold only the day's public IPO figures.
3. **Only if you want zero taps to a fixed list of people:** the WhatsApp
   Business Cloud API. Individuals who have opted in, not groups; roughly
   Rs 0.12-0.15 per message plus tax, a business phone number, Meta verification
   and approved templates. Real effort, so only if the audience justifies it.
4. A Telegram channel only helps recipients who already use Telegram.

## 6. Decisions log

| Date | Decision |
|---|---|
| 29 Aug | Direct WhatsApp delivery declined (terms, ban risk). Telegram chosen |
| 10 Sep | Daily time moved to 5:00 PM IST |
| 15 Sep | Backup trigger bound to an existing session accepted |
| Standing | Only Mainboard, Open/Upcoming; SME excluded; QIB/NII never shown; GMP % computed by us; "Not updated" / "Not verified" wording; never guess a number |
| 14 Oct | Creative follows the Loop / Inner Circle house style; text uses WhatsApp bold; report in a tap-to-copy block |
| 15 Oct | "Take up all proposed changes"; GMP trend and direction is a priority. Image held to 4:5 (my call; one constant to change) |
| 15 Oct | Listing results appear in the same daily creative as a slim strip (your yes to my suggestion); on a very full day it shrinks to one row, and to text only if even that cannot fit 4:5 |
| 15 Oct | **High GMP flag raised from above 10% to above 25%** (your suggestion; I agreed: with GMPs of 11-70% the old line flagged every IPO). Rule printed in the legend |
| 15 Oct | Trend baseline stays IPOWatch's daily record. Listing results come from NSE: issue to first-day open, and open to close separately. No second GMP website (numbers need not match); NSE is the independent check. **Scope change:** listing results are now published (the old rule was open/upcoming only) |

| 18 Oct | Trend baseline = the GMP **we published** the day before (your yes). Decision aids 1, 2, 3, 5, 6 approved ("all"); track record uses the **last 25 listings**; upgrade 4 (cash for 1-3 lots) not requested, left open |
| 20 Oct | User delegated ("you decide and execute"). Built: plain caption, stale-data cue, layout canary, listing robustness. Declined for now with reasons: share page / Business API (audience unknown), cash-for-lots (minimum already shown), allotment/listing tags (user limited urgency tags to closing days), removing the KPI strip (signed-off design) |
| 18 Oct (late) | Second feedback round adopted: exact-value High GMP flag; subscription move shown only if at least 0.1x and 5% (both Retail and Total); "GMP accuracy" tile = listings within 10 points of GMP; issue price in the awaiting section |
| 18 Oct (evening) | User feedback, all adopted: GMP % shown whole from 10% up; urgency tags only for today and tomorrow in a distinct amber pill; weekend shows the last real move; track record = 25-listing scoreboard; "Closed - awaiting listing" section **only for GMP above 25%** (rule exception) |

## 6b. Scheduled follow-ups (so nothing depends on memory)

| When | What | Notes |
|---|---|---|
| Sundays | Weekly wrap from the session (`python3 -m ipo_watch.run --mode weekly --outdir output`) until the GitHub schedule is live | First edition 18 Oct. Needs the listing results on record: run `--mode backfill --outdir output` once after a fresh checkout, and keep the `history` branch copy updated |
| 21 Oct 2026, ~1:51 PM IST | Catch-up check: if HD Fire Protect's scorecard was not sent on 20 Oct, replay it with `--mode listing --date 2026-10-20` (reminder `trig_01GsbsPyVuX4n4NvXoe1bnPy`); also grep the daily log for `LAYOUT CHANGE` | Added 20 Oct |
| 20 Oct 2026, 7:30 PM IST | Run the listing scorecard from the Claude session for **HD Fire Protect** (first real listing under the new feature) | Reminder `trig_01SNDhTcCYzauXQsXpk7aHax`. If the GitHub listing workflow is live by then, skip it and delete the reminder (avoids a duplicate message) |

## 7. Platform facts worth remembering

- The cloud permission classifier blocks the unattended 5 PM routine, and blocks me from pausing it. Only you can, in the Routines list. Details: `CLAUDE.md`, cause 6 and 8.
- "Succeeded" on a routine means the session did not crash, not that anything was delivered.
- IPOWatch changes layout without notice. The parser matches by heading text, never position.
- Heavy testing from the sandbox gets throttled by IPOWatch. Test with saved pages.
