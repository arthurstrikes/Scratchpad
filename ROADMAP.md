# IPO Watch: living roadmap

The one page that answers: where are we, what went wrong, what is open, and
what would make this world class. Written in plain language. `CLAUDE.md` holds
the rules and the technical history; this page holds the plan.

**Keeping it alive:** whoever works on this updates the page in the same change
(done, found, decided, still open). Dated entries, newest first. Nothing here
is ever deleted, only marked done.

Last updated: 15 Oct 2026 (late).

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
| **Learns** | Tracks how reliable GMP turned out to be against the real listing | Not started |

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
| since 16 Sep | Daily report delivered every day through the backup (about 30 days) |

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
| G16 | On 15 Oct IPOWatch's extra pages timed out, so the first GitHub dry run showed "GMP trend: Not updated" for most IPOs | The design degrades honestly, but a real send would look thin | Mitigations shipped (see G13); re-check on the next live run |

## 4. Open actions

| # | Action | Owner | Needs |
|---|---|---|---|
| A1 | Add two GitHub secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`): repo **Settings > Secrets and variables > Actions** | **You** | 3 minutes. I can walk you through it |
| A2 | Run the GitHub workflow once with Telegram on and confirm it arrives | Me + you | A1 |
| A3 | Go live: switch on the three schedules, retire the 5:05 PM backup, delete the dead 5:00 PM routine in the Routines list on claude.ai | Me (code) + **you** (the routine, I am blocked from it) | A2 and your yes |
| A4 | Tell me how tonight's image looks in WhatsApp, whether tap-to-copy pastes with bold, **and whether the photo's caption comes along when you share the photo from Telegram to WhatsApp** (decides step 2 in section 5b) | **You** | Tonight's report. You said you'll share after the 5:05 PM run |
| A5 | ~~Pick the trend baseline~~ **Decided 15 Oct: keep IPOWatch's daily record** | done | |
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
| I9 | **Date reminders** ("allotment tomorrow", "lists tomorrow") | Small, high value; the dates are already collected | Me |
| I10 | **Weekly Sunday summary** (week's listings vs GMP, subscription finals) | Useful recap | I5, I8 |
| I11 | **Subscription momentum** (day-by-day retail multiple, last-day surge) | Shows demand building, not just a number | I5 |
| I12 | **Big-move alert** (GMP jumps or falls sharply versus the morning) | Time-sensitive signal | Runner (I1) |

### Delivery and design
| # | Idea | Value | Needs |
|---|---|---|---|
| I13 | One-IPO share cards (square, one IPO per image) | Easier to forward one IPO | Your wish |
| I14 | Hindi or other-language caption variant | Wider audience | Your audience (ask) |
| I15 | Second source used **only** to flag disagreement | Catches a bad IPOWatch figure | A7 |
| I16 | Telegram channel | Only for recipients who use Telegram (see 5b) | A8 |
| I17 | WhatsApp Business Cloud API (about Rs 60 a year for one message a day; more per recipient) | The only compliant way to post to WhatsApp automatically, to **individual opted-in numbers** (not groups) | Previously declined; see 5b step 3 |

### 5b. Getting it into WhatsApp with less effort (smart options, in order)

WhatsApp cannot be automated for groups, so the aim is fewer taps for you and
nothing lost on the way:

1. **Done 15 Oct: a compact summary now rides on the photo as its caption.**
   If Telegram carries the caption across when you share the photo to WhatsApp
   (I could not verify this from here and it may differ by phone; please test, A4), one long-press -> Share ->
   WhatsApp sends the image **and** the summary together.
2. **If the caption does not travel:** a small share page (the Web Share button
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
| 15 Oct | Trend baseline stays IPOWatch's daily record. Listing results come from NSE: issue to first-day open, and open to close separately. No second GMP website (numbers need not match); NSE is the independent check. **Scope change:** listing results are now published (the old rule was open/upcoming only) |

## 6b. Scheduled follow-ups (so nothing depends on memory)

| When | What | Notes |
|---|---|---|
| 20 Oct 2026, 7:30 PM IST | Run the listing scorecard from the Claude session for **HD Fire Protect** (first real listing under the new feature) | Reminder `trig_01SNDhTcCYzauXQsXpk7aHax`. If the GitHub listing workflow is live by then, skip it and delete the reminder (avoids a duplicate message) |

## 7. Platform facts worth remembering

- The cloud permission classifier blocks the unattended 5 PM routine, and blocks me from pausing it. Only you can, in the Routines list. Details: `CLAUDE.md`, cause 6 and 8.
- "Succeeded" on a routine means the session did not crash, not that anything was delivered.
- IPOWatch changes layout without notice. The parser matches by heading text, never position.
- Heavy testing from the sandbox gets throttled by IPOWatch. Test with saved pages.
