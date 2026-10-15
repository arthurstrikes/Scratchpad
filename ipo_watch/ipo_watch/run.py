"""Daily Mainboard IPO Watch - end to end run.

  python -m ipo_watch.run                    # live: render IPOWatch, publish
  python -m ipo_watch.run --fixture-dir DIR  # replay saved HTML (offline test)
  python -m ipo_watch.run --dataset FILE     # render from a reviewed JSON dataset

Fails closed: if IPOWatch cannot be read, the run aborts with a non-zero exit
and writes nothing. It never emits a report built on guessed numbers.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from decimal import Decimal

from .config import (GMP_URL, IST, OUTPUT_DIR, SOURCE_NAME, SUBSCRIPTION_URL)
from .creative import last_render_info, render_listing_png, render_png
from .enrich import enrich_dataset
from .fetch import FetchError, extract_page_timestamp, fetch_pages, load_fixture
from .merge import Dataset, build_dataset
from .models import Board, IPO, Provenance, Status, Trend, parse_date
from .parse import parse_page
from .listing import (BHAV_URL, ListingResult, find_results, fetch_equities, get_text, load_candidates,
                      load_recent_results, make_bhav_getter, match_symbol, parse_bhav,
                      result_path, save_result)
from .report import (build_caption, build_listing_report, build_midday_report, build_report,
                     closing_today)
from .share import build_share_page
from . import telegram
from .verify import check, check_listing


# "delivered" | "failed" | "not configured" - set by publish()/_midday(), read by main().
TELEGRAM_RESULT = {"status": "not configured"}


def _log(msg: str) -> None:
    print(f"[ipo-watch] {msg}", flush=True)


def collect(fixture_dir: str | None, today: date, snapshot_dir: str | None,
            history_dir: str | None = None, enrich_only=None) -> Dataset:
    """Fetch + parse + merge into the final verified dataset."""
    if fixture_dir:
        sub = load_fixture(SUBSCRIPTION_URL, os.path.join(fixture_dir, "sub_sample.html"))
        gmp = load_fixture(GMP_URL, os.path.join(fixture_dir, "gmp_sample.html"))
        pages, mode = {SUBSCRIPTION_URL: sub, GMP_URL: gmp}, "fixture"
    else:
        _log(f"rendering {SOURCE_NAME} pages in Chromium ...")
        pages = fetch_pages([SUBSCRIPTION_URL, GMP_URL], snapshot_dir=snapshot_dir)
        mode = "live"

    sub_page, gmp_page = pages[SUBSCRIPTION_URL], pages[GMP_URL]
    sub_rows = parse_page(sub_page.html, SUBSCRIPTION_URL, today)
    gmp_rows = parse_page(gmp_page.html, GMP_URL, today)
    _log(f"parsed {len(sub_rows)} subscription rows, {len(gmp_rows)} GMP rows")

    if not sub_rows and not gmp_rows:
        raise FetchError(
            "No IPO rows parsed from either IPOWatch page. The page layout has "
            "probably changed - recalibrate ipo_watch/parse.py against a fresh "
            "snapshot before publishing."
        )

    ds = build_dataset(
        sub_rows, gmp_rows, today,
        sub_ts=extract_page_timestamp(sub_page.html),
        gmp_ts=extract_page_timestamp(gmp_page.html),
        generated_at=datetime.now(IST),
        source_mode=mode,
    )
    _log(f"open={len(ds.open_ipos)} upcoming={len(ds.upcoming_ipos)} "
         f"closed_retained={len(ds.recently_closed)} sme_excluded={len(ds.excluded_sme)}")

    if not fixture_dir:
        enrich_dataset(ds, today, _page_getter(snapshot_dir), history_dir=history_dir,
                       only=enrich_only)
        shown = sum(1 for i in ds.published if i.trend and i.trend.status in ("ok", "new"))
        _log(f"enriched: GMP trend for {shown}/{len(ds.published)} IPOs, "
             f"lot size for {sum(1 for i in ds.published if i.min_invest)}, "
             f"key dates for {sum(1 for i in ds.published if i.allotment_date or i.listing_date)}")
    if history_dir:
        ds.recent_listings = load_recent_results(history_dir, today)
        if ds.recent_listings:
            _log(f"recently listed: {', '.join(r.name for r in ds.recent_listings)}")
    return ds


ENRICH_BUDGET_S = 300      # all per-IPO pages together; the run never waits longer
ENRICH_TIMEOUT_S = 30      # one request


def _page_getter(snapshot_dir: str | None, budget_s: float = ENRICH_BUDGET_S):
    """url -> html for the per-IPO pages. Retries a few times, gives up for
    good once the overall time budget is spent, and never raises: the extras
    are best-effort and must not delay or break the daily report."""
    deadline = time.monotonic() + budget_s
    state = {"announced": False}

    def get(url: str) -> str | None:
        for attempt in (1, 2, 3):
            left = deadline - time.monotonic()
            if left <= 1:
                if not state["announced"]:
                    state["announced"] = True
                    _log(f"enrich: {budget_s:.0f}s time budget used up - skipping the rest")
                return None
            try:
                return fetch_pages([url], snapshot_dir=snapshot_dir,
                                   timeout=min(ENRICH_TIMEOUT_S, left), attempts=1)[url].html
            except Exception as exc:  # noqa: BLE001
                if attempt == 3:
                    _log(f"enrich: could not read {url}: {exc}")
                else:
                    time.sleep(min(1.5 * attempt, max(0.0, left - 1)))
        return None
    return get


def dataset_to_json(ds: Dataset) -> dict:
    def one(i: IPO) -> dict:
        return {
            "name": i.name, "board": i.board.value, "status": i.status.value,
            "open_date": i.open_date.isoformat() if i.open_date else None,
            "close_date": i.close_date.isoformat() if i.close_date else None,
            "price_min": str(i.price_min) if i.price_min is not None else None,
            "price_max": str(i.price_max) if i.price_max is not None else None,
            "gmp": str(i.gmp) if i.gmp is not None else None,
            "gmp_pct": str(i.gmp_pct) if i.gmp_pct is not None else None,
            "retail_sub": str(i.retail_sub) if i.retail_sub is not None else None,
            "total_sub": str(i.total_sub) if i.total_sub is not None else None,
            "unverified": sorted(i.unverified_fields),
            "gmp_url": i.gmp_url or None,
            "trend": ({
                "status": i.trend.status,
                "prev_date": i.trend.prev_date.isoformat() if i.trend.prev_date else None,
                "prev_gmp": str(i.trend.prev_gmp) if i.trend.prev_gmp is not None else None,
                "change": str(i.trend.change) if i.trend.change is not None else None,
                "series": [str(x) for x in i.trend.series],
            } if i.trend else None),
            "lot_shares": i.lot_shares,
            "min_invest": str(i.min_invest) if i.min_invest is not None else None,
            "allotment_date": i.allotment_date.isoformat() if i.allotment_date else None,
            "listing_date": i.listing_date.isoformat() if i.listing_date else None,
        }
    return {
        "run_date": ds.run_date.isoformat() if ds.run_date else None,
        "generated_at": ds.generated_at.isoformat() if ds.generated_at else None,
        "source": SOURCE_NAME, "source_mode": ds.source_mode,
        "subscription_timestamp": ds.subscription_timestamp,
        "gmp_timestamp": ds.gmp_timestamp,
        "open": [one(i) for i in ds.open_ipos],
        "upcoming": [one(i) for i in ds.upcoming_ipos],
        "recently_closed_internal": [one(i) for i in ds.recently_closed],
        "excluded_sme": ds.excluded_sme,
        "recent_listings": [r.to_dict() for r in ds.recent_listings],
        "warnings": ds.warnings,
        "conflicts": [c.__dict__ for c in ds.conflicts],
    }


def dataset_from_json(path: str) -> Dataset:
    """Rebuild a Dataset from reviewed JSON, for re-rendering without refetching."""
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    def dec_in(src: dict, k: str):
        return Decimal(src[k]) if src.get(k) is not None else None

    def one(d: dict, status: Status) -> IPO:
        dec = lambda k: dec_in(d, k)  # noqa: E731
        ipo = IPO(
            name=d["name"], board=Board.MAINBOARD, status=status,
            open_date=parse_date(d.get("open_date")), close_date=parse_date(d.get("close_date")),
            price_min=dec("price_min"), price_max=dec("price_max"),
            gmp=dec("gmp"), retail_sub=dec("retail_sub"), total_sub=dec("total_sub"),
            prov=Provenance(source_url=SOURCE_NAME),
        )
        ipo.unverified_fields = set(d.get("unverified") or [])
        ipo.gmp_url = d.get("gmp_url") or ""
        t = d.get("trend")
        if t:
            ipo.trend = Trend(
                status=t["status"], prev_date=parse_date(t.get("prev_date")),
                prev_gmp=dec_in(t, "prev_gmp"), change=dec_in(t, "change"),
                series=[Decimal(x) for x in t.get("series") or []])
        ipo.lot_shares = d.get("lot_shares")
        ipo.min_invest = dec("min_invest")
        ipo.allotment_date = parse_date(d.get("allotment_date"))
        ipo.listing_date = parse_date(d.get("listing_date"))
        return ipo

    ds = Dataset(
        open_ipos=[one(d, Status.OPEN) for d in raw.get("open", [])],
        upcoming_ipos=[one(d, Status.UPCOMING) for d in raw.get("upcoming", [])],
        excluded_sme=raw.get("excluded_sme", []),
        recent_listings=[ListingResult.from_dict(x) for x in raw.get("recent_listings", [])],
        warnings=raw.get("warnings", []),
        subscription_timestamp=raw.get("subscription_timestamp"),
        gmp_timestamp=raw.get("gmp_timestamp"),
        run_date=parse_date(raw.get("run_date")) or date.today(),
        generated_at=datetime.now(IST),
        source_mode=raw.get("source_mode", "dataset"),
    )
    return ds


def publish(ds: Dataset, outdir: str) -> dict[str, str]:
    """Write text, caption, dataset and the verified PNG. Returns the paths."""
    os.makedirs(outdir, exist_ok=True)
    stamp = (ds.run_date or date.today()).strftime("%Y-%m-%d")

    paths = {
        "report":  os.path.join(outdir, f"ipo-watch-{stamp}.txt"),
        "dataset": os.path.join(outdir, f"ipo-watch-{stamp}-dataset.json"),
        "image":   os.path.join(outdir, f"ipo-watch-{stamp}.png"),
    }

    with open(paths["report"], "w", encoding="utf-8") as fh:
        fh.write(build_report(ds))
    with open(paths["dataset"], "w", encoding="utf-8") as fh:
        json.dump(dataset_to_json(ds), fh, indent=2, ensure_ascii=False)

    # Render, verify against the dataset, and re-render once on mismatch.
    for attempt in (1, 2):
        _, rendered = render_png(ds, paths["image"])
        info = last_render_info()
        bad = check(ds, rendered, strip_rows=info["listings"])
        if not bad:
            _log(f"image data check passed ({len(rendered)} figures verified); "
                 f"{info['width']}x{info['height']} px, layout tier {info['tier']}"
                 + (f", {info['listings']} recently-listed row(s) in the image" if info["listings"] else
                    (", recently-listed left to the text (no room at 4:5)"
                     if ds.recent_listings else "")))
            break
        _log(f"image data check FAILED on attempt {attempt}:")
        for m in bad:
            _log(f"   - {m}")
        if attempt == 2:
            raise SystemExit("Image does not match the verified dataset; not publishing.")

    paths["share"] = build_share_page(
        ds, os.path.basename(paths["image"]), os.path.join(outdir, "share.html"))

    # Telegram is an additional delivery channel, not a data-accuracy control.
    # A Telegram outage must never be reported the same way as a bad number,
    # so failures here are logged plainly and never change the run's exit code.
    if telegram.configured():
        try:
            telegram.send_report(paths["image"], build_report(ds), caption=build_caption(ds))
            TELEGRAM_RESULT["status"] = "delivered"
            _log("telegram  -> delivered")
        except telegram.TelegramError as exc:
            TELEGRAM_RESULT["status"] = "failed"
            _log(f"telegram  -> FAILED: {exc}")
    else:
        _log("telegram  -> not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID unset)")

    return paths


def _midday(ds: Dataset, outdir: str) -> int:
    """Send the closing-day update, or say plainly that there is nothing to send."""
    text = build_midday_report(ds)
    if text is None:
        _log("midday: no Mainboard IPO closes today - nothing to send")
        return 0
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f"ipo-watch-{ds.run_date:%Y-%m-%d}-midday.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    if telegram.configured():
        try:
            telegram.send_text(text)
            TELEGRAM_RESULT["status"] = "delivered"
            _log("telegram  -> delivered (midday)")
        except telegram.TelegramError as exc:
            TELEGRAM_RESULT["status"] = "failed"
            _log(f"telegram  -> FAILED: {exc}")
    else:
        _log("telegram  -> not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID unset)")
    print("\n" + "=" * 62 + "\n" + text + "=" * 62)
    _log(f"midday   -> {path} ({len(closing_today(ds))} IPO(s) closing today)")
    return 0


LISTING_POLL_S = 60          # NSE publishes the day's prices some time after the close
LISTING_POLL_MAX_S = 30 * 60


def _listing_mode(args, today: date) -> int:
    """Evening scorecard for IPOs we reported on that listed on NSE today."""
    outdir = args.outdir
    candidates = load_candidates(outdir, today)
    equities = fetch_equities()
    if not equities:
        reason = "NSE's equity list could not be read"
        _log(f"ABORTED: {reason}")
        _alert(_failure_text(today, reason))
        return 2
    listing_today = [c for c in candidates
                     if (eq := match_symbol(c, equities)) and eq["listing_date"] == today]
    if not listing_today:
        _log("listing: none of the IPOs we reported on lists on NSE today - nothing to send")
        return 0
    _log(f"listing: {', '.join(c.name for c in listing_today)} listed on NSE today")

    url = BHAV_URL.format(d=today.strftime("%d%m%Y"))
    waited, text = 0, get_text(url)
    while text is None and waited < LISTING_POLL_MAX_S:
        _log(f"listing: NSE has not published {today:%d %b} prices yet - waiting")
        time.sleep(LISTING_POLL_S)
        waited += LISTING_POLL_S
        text = get_text(url)
    if text is None:
        reason = f"NSE had not published the {today:%d %b} price file after {waited // 60} minutes"
        _log(f"ABORTED: {reason}")
        _alert(_failure_text(today, reason))
        return 2
    todays = parse_bhav(text)
    other = make_bhav_getter()
    results = [r for r in find_results(candidates, equities,
                                       lambda d: todays if d == today else other(d))
               if r.listing_date == today]
    if not args.force:
        results = [r for r in results if not os.path.exists(result_path(outdir, r))]
    if not results:
        _log("listing: nothing new to send (already sent, or the listing could not be matched safely)")
        return 0

    report = build_listing_report(results, today)
    os.makedirs(outdir, exist_ok=True)
    png = os.path.join(outdir, f"ipo-watch-listing-{today:%Y-%m-%d}.png")
    txt = os.path.join(outdir, f"ipo-watch-listing-{today:%Y-%m-%d}.txt")
    for attempt in (1, 2):
        _, rendered = render_listing_png(results, today, png)
        bad = check_listing(results, rendered)
        if not bad:
            _log(f"listing image check passed ({len(rendered)} figures verified)")
            break
        _log(f"listing image check FAILED on attempt {attempt}: " + "; ".join(str(m) for m in bad))
        if attempt == 2:
            _alert(_failure_text(today, "the listing card did not match the data; not published"))
            raise SystemExit("Listing image does not match the data; not publishing.")
    with open(txt, "w", encoding="utf-8") as fh:
        fh.write(report)

    status = "not configured"
    if telegram.configured():
        try:
            telegram.send_report(png, report, caption=f"🏁 Listing scorecard — {today:%d %b %Y}")
            status = "delivered"
            _log("telegram  -> delivered (listing)")
        except telegram.TelegramError as exc:
            status = "failed"
            _log(f"telegram  -> FAILED: {exc}")
    else:
        _log("telegram  -> not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID unset)")
    if status != "failed":                      # a failed send is retried by the next run
        for r in results:
            save_result(outdir, r)
    print("\n" + "=" * 62 + "\n" + report + "=" * 62)
    _log(f"listing  -> {txt}")
    return 3 if (args.fail_on_telegram_error and status == "failed") else 0


def _alert(msg: str) -> None:
    """Tell the user on Telegram that today's run failed. Never raises."""
    if not telegram.configured():
        return
    try:
        telegram.send_alert(msg)
        _log("telegram  -> failure notice sent")
    except telegram.TelegramError as exc:
        _log(f"telegram  -> failure notice FAILED: {exc}")


def _failure_text(today: date, reason: str) -> str:
    return (f"⚠️ IPO Watch could not run on {today.strftime('%d %b %Y')}.\n"
            "No report was sent and no numbers were guessed.\n\n"
            f"Reason: {reason}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Daily Mainboard IPO Watch")
    ap.add_argument("--fixture-dir", help="replay saved IPOWatch HTML instead of fetching")
    ap.add_argument("--dataset", help="render from an existing reviewed dataset JSON")
    ap.add_argument("--outdir", default=OUTPUT_DIR)
    ap.add_argument("--date", help="override run date (YYYY-MM-DD)")
    ap.add_argument("--fail-on-telegram-error", action="store_true",
                    help="exit 3 if Telegram is configured but delivery failed (for CI, so the "
                         "failure is visible instead of only logged)")
    ap.add_argument("--mode", choices=("daily", "midday", "listing"), default="daily",
                    help="midday = short text update for IPOs closing today (no image); "
                         "listing = evening scorecard for IPOs that listed on NSE today")
    ap.add_argument("--force", action="store_true",
                    help="listing mode: send again even if already sent")
    args = ap.parse_args(argv)

    today = date.fromisoformat(args.date) if args.date else datetime.now(IST).date()

    if args.mode == "listing":
        try:
            return _listing_mode(args, today)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            _alert(_failure_text(today, f"unexpected error ({type(exc).__name__}: {exc})"))
            raise

    try:
        if args.dataset:
            ds = dataset_from_json(args.dataset)
            ds.run_date = today if args.date else ds.run_date
        else:
            ds = collect(args.fixture_dir, today,
                         snapshot_dir=os.path.join(args.outdir, "snapshots"),
                         history_dir=args.outdir,
                         enrich_only=((lambda i: i.close_date == today)
                                      if args.mode == "midday" else None))
    except FetchError as exc:
        _log(f"ABORTED: {exc}")
        _log("No report written. Nothing is ever published from unverified data.")
        _alert(_failure_text(today, str(exc)))
        return 2
    except Exception as exc:  # noqa: BLE001
        _alert(_failure_text(today, f"unexpected error ({type(exc).__name__}: {exc})"))
        raise

    if args.mode == "midday":
        rc = _midday(ds, args.outdir)
        return 3 if (args.fail_on_telegram_error and TELEGRAM_RESULT["status"] == "failed") else rc

    try:
        paths = publish(ds, args.outdir)
    except SystemExit as exc:
        _alert(_failure_text(today, str(exc.code)))
        raise
    except Exception as exc:  # noqa: BLE001
        _alert(_failure_text(today, f"unexpected error ({type(exc).__name__}: {exc})"))
        raise
    print("\n" + "=" * 62 + "\n" + build_report(ds) + "=" * 62)
    for k, v in paths.items():
        _log(f"{k:8s} -> {v}")
    if args.fail_on_telegram_error and TELEGRAM_RESULT["status"] == "failed":
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
