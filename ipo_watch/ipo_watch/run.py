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
from datetime import date, datetime
from decimal import Decimal

from .config import (GMP_URL, IST, OUTPUT_DIR, SOURCE_NAME, SUBSCRIPTION_URL)
from .creative import render_png
from .fetch import FetchError, extract_page_timestamp, fetch_pages, load_fixture
from .merge import Dataset, build_dataset
from .models import Board, IPO, Provenance, Status, parse_date
from .parse import parse_page
from .report import build_caption, build_report
from .share import build_share_page
from .verify import check


def _log(msg: str) -> None:
    print(f"[ipo-watch] {msg}", flush=True)


def collect(fixture_dir: str | None, today: date, snapshot_dir: str | None) -> Dataset:
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
    return ds


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
        "warnings": ds.warnings,
        "conflicts": [c.__dict__ for c in ds.conflicts],
    }


def dataset_from_json(path: str) -> Dataset:
    """Rebuild a Dataset from reviewed JSON, for re-rendering without refetching."""
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    def one(d: dict, status: Status) -> IPO:
        dec = lambda k: Decimal(d[k]) if d.get(k) is not None else None  # noqa: E731
        ipo = IPO(
            name=d["name"], board=Board.MAINBOARD, status=status,
            open_date=parse_date(d.get("open_date")), close_date=parse_date(d.get("close_date")),
            price_min=dec("price_min"), price_max=dec("price_max"),
            gmp=dec("gmp"), retail_sub=dec("retail_sub"), total_sub=dec("total_sub"),
            prov=Provenance(source_url=SOURCE_NAME),
        )
        ipo.unverified_fields = set(d.get("unverified") or [])
        return ipo

    ds = Dataset(
        open_ipos=[one(d, Status.OPEN) for d in raw.get("open", [])],
        upcoming_ipos=[one(d, Status.UPCOMING) for d in raw.get("upcoming", [])],
        excluded_sme=raw.get("excluded_sme", []),
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
        "caption": os.path.join(outdir, f"ipo-watch-{stamp}-caption.txt"),
        "dataset": os.path.join(outdir, f"ipo-watch-{stamp}-dataset.json"),
        "image":   os.path.join(outdir, f"ipo-watch-{stamp}.png"),
    }

    report, caption = build_report(ds), build_caption(ds)
    with open(paths["report"], "w", encoding="utf-8") as fh:
        fh.write(report)
    with open(paths["caption"], "w", encoding="utf-8") as fh:
        fh.write(caption + "\n")
    with open(paths["dataset"], "w", encoding="utf-8") as fh:
        json.dump(dataset_to_json(ds), fh, indent=2, ensure_ascii=False)

    # Render, verify against the dataset, and re-render once on mismatch.
    for attempt in (1, 2):
        _, rendered = render_png(ds, paths["image"])
        bad = check(ds, rendered)
        if not bad:
            _log(f"image data check passed ({len(rendered)} figures verified)")
            break
        _log(f"image data check FAILED on attempt {attempt}:")
        for m in bad:
            _log(f"   - {m}")
        if attempt == 2:
            raise SystemExit("Image does not match the verified dataset; not publishing.")

    paths["share"] = build_share_page(
        ds, os.path.basename(paths["image"]), os.path.join(outdir, "share.html"))
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Daily Mainboard IPO Watch")
    ap.add_argument("--fixture-dir", help="replay saved IPOWatch HTML instead of fetching")
    ap.add_argument("--dataset", help="render from an existing reviewed dataset JSON")
    ap.add_argument("--outdir", default=OUTPUT_DIR)
    ap.add_argument("--date", help="override run date (YYYY-MM-DD)")
    args = ap.parse_args(argv)

    today = date.fromisoformat(args.date) if args.date else datetime.now(IST).date()

    try:
        if args.dataset:
            ds = dataset_from_json(args.dataset)
            ds.run_date = today if args.date else ds.run_date
        else:
            ds = collect(args.fixture_dir, today,
                         snapshot_dir=os.path.join(args.outdir, "snapshots"))
    except FetchError as exc:
        _log(f"ABORTED: {exc}")
        _log("No report written. Nothing is ever published from unverified data.")
        return 2

    paths = publish(ds, args.outdir)
    print("\n" + "=" * 62 + "\n" + build_report(ds) + "=" * 62)
    print("\nWHATSAPP CAPTION\n" + "-" * 62 + "\n" + build_caption(ds) + "\n")
    for k, v in paths.items():
        _log(f"{k:8s} -> {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
