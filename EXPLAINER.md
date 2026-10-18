# IPO Watch explained simply

Written like you are in 10th standard. If a word is new, it is explained right there.

## What is this?

Every day at 5 PM, a small robot reads a website about new company share
sales (called **IPOs**), checks the numbers, makes one neat picture and one
message, and sends them to your Telegram. You then forward them to WhatsApp.

- **IPO**: a company sells its shares to the public for the first time.
- **Mainboard**: the big companies' section of the stock exchange. (The small
  ones are called SME. We leave them out on purpose.)
- **GMP (Grey Market Premium)**: the extra price people are *unofficially*
  willing to pay for a share before it lists. It is a rumour, not a promise.
  We show it as a percentage of the price: GMP / price x 100.
- **Subscription**: how many times the shares on offer were asked for.
  `7x` means seven times as many people wanted shares as were available.
- **Listing**: the day the shares start trading on the exchange.
- **Allotment**: the day you find out whether you got shares.

## Why does it exist?

So you do not have to open a website, find the tables, do the maths and
type a message every day. It also **never guesses**: if a number is missing it
says "Not updated". A wrong number is worse than no number.

## Who does what?

| Who | Job |
|---|---|
| **IPOWatch** (website) | Source of IPO dates, prices, GMP and subscription |
| **NSE** (the stock exchange) | Source of the real listing prices after listing |
| **The robot** (this code, in the `ipo_watch/` folder) | Reads, checks, calculates, draws, sends |
| **Claude** | Built the robot, repairs it when the website changes, runs it each evening as a backup |
| **GitHub** | A free place that stores the code and can run the robot by itself |
| **Telegram** | Delivers the picture and message to you |
| **You** | Read it, forward it, decide what you like |

## How does a day go? (the "how")

1. The robot opens two IPOWatch pages and reads the tables.
2. It opens a page for each IPO to get the day-by-day GMP and the lot size.
3. It does all the maths itself (never copies IPOWatch's percentages).
4. It draws the picture, then **reads the picture back** and checks every number
   against its data. If one is different, nothing is sent.
5. It sends the picture and the message to Telegram.
6. If anything fails, it tells you it could not run. It does not send a wrong report.

## What is new in the report?

- **Closes today / tomorrow / 3 days left**: a tag on each open IPO.
- **A one-line summary at the top**: how many are open, how many close soon, how many have a high GMP.
- **Subscription change**: `▲ from 5.24x` means it was 5.24 at our last update and is higher now.
- **GMP trend**: how GMP moved since our last report, with a tiny line chart.
- **High GMP tag**: only when GMP is above 25%.
- **GMP track record**: a sentence saying how far GMP has been from the real listing gain in the last 25 listings. It reminds everyone GMP is a guess.
- **Sunday weekly wrap**: what listed this week and what is coming.
- **Listing scorecard**: on listing day, the real price at which it opened and closed.

## When does things happen? (the "when")

| When | What |
|---|---|
| 5:05 PM IST every day | Today's report (sent by Claude from its long session) |
| Planned: 5:00 PM by GitHub | The same report, with no Claude needed |
| Planned: closing days, midday | A short update on IPOs closing that day |
| Planned: ~7 PM on listing days | The listing scorecard |
| Planned: Sunday 6 PM | The weekly wrap |

"Planned" means built and tested, but switched off until you add two secrets on
GitHub (below) and say yes.

## Where is everything? (the "where")

- Code and notes: GitHub, `arthurstrikes/Scratchpad`.
- Today's files: `ipo_watch/output/` (not saved on GitHub).
- Past daily data: the GitHub `history` branch.
- Notes for the next person (or the next Claude): `CLAUDE.md` (the rules) and `ROADMAP.md` (the plan, what went wrong, what is next).

## The one thing only you can do: GitHub secrets

A **secret** is a password-like value GitHub keeps hidden. The robot needs two
so it can send to *your* Telegram:

1. `TELEGRAM_BOT_TOKEN`: the bot's key. You get it from **@BotFather** on Telegram (the same one already used for the daily report).
2. `TELEGRAM_CHAT_ID`: your chat number, `8521825324`.

**Steps (phone browser or computer):**

1. Open **github.com/arthurstrikes/Scratchpad** and sign in.
2. Tap **Settings** (top row of the repository, not your profile settings). On a phone you may need to scroll the top row sideways.
3. On the left (or in the menu) choose **Secrets and variables**, then **Actions**.
4. Tap **New repository secret**.
5. Name: `TELEGRAM_BOT_TOKEN`. Secret: paste the token. Tap **Add secret**.
6. Tap **New repository secret** again. Name: `TELEGRAM_CHAT_ID`. Secret: `8521825324`. Tap **Add secret**.
7. Tell Claude "done". **Do not paste the token into the chat.** Claude never needs to see it.

If you do not have the token any more: in Telegram, message **@BotFather**, send `/mybots`, choose your bot, then **API Token**.

## Safety rules we keep

- Never guess a number. Missing means "Not updated".
- Never tell anyone to buy or avoid an IPO. We only report numbers.
- The picture must match the data, or nothing is sent.
- The two secrets are never written into the code.
