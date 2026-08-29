"""Tests for the accuracy rules in spec sections 3, 4 and 5."""
import sys, os
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipo_watch.models import IPO, Board, Status, parse_price_band, to_decimal
from ipo_watch.merge import build_dataset, norm_key
from ipo_watch.parse import parse_page, detect_board
from ipo_watch.report import build_report, build_caption
from ipo_watch.verify import check, expected_map

TODAY = date(2026, 8, 29)


def mk(name, gmp=None, pmax=None, retail=None, total=None,
       o=date(2026, 8, 27), c=date(2026, 8, 29), board=Board.MAINBOARD):
    return IPO(name=name, board=board, open_date=o, close_date=c,
               price_min=Decimal("1"), price_max=pmax, gmp=gmp,
               retail_sub=retail, total_sub=total)


# --- Section 4: GMP maths ---------------------------------------------------

def test_gmp_pct_matches_spec_worked_example():
    assert mk("X", Decimal("325"), Decimal("429")).gmp_pct_text == "75.76%"


def test_gmp_pct_is_two_dp_half_up():
    assert mk("X", Decimal("1"), Decimal("3")).gmp_pct_text == "33.33%"
    assert mk("X", Decimal("2"), Decimal("3")).gmp_pct_text == "66.67%"


def test_zero_gmp_renders_zero_not_blank():          # rule 5.7
    assert mk("X", Decimal("0"), Decimal("100")).gmp_pct_text == "0.00%"
    assert mk("X", Decimal("0"), Decimal("100")).gmp_text == "₹0"


def test_gmp_pct_is_computed_not_copied():
    """A wrong 'estimated gain' on the page must not influence our number."""
    ipo = mk("X", Decimal("18"), Decimal("126"))
    assert ipo.gmp_pct == Decimal("14.29")           # 18/126 = 14.2857 -> 14.29


def test_highlight_threshold_is_strictly_above_10pct():
    assert mk("X", Decimal("10"), Decimal("100")).is_hot is False
    assert mk("X", Decimal("11"), Decimal("100")).is_hot is True


# --- Section 5: accuracy rules ---------------------------------------------

def test_missing_subscription_says_not_updated():    # rule 5.6
    ipo = mk("X", Decimal("5"), Decimal("100"))
    assert ipo.retail_text == "Not updated"
    assert ipo.total_text == "Not updated"


def test_unverifiable_gmp_says_not_verified():       # rule 5.10
    ipo = mk("X", Decimal("5"), None)
    ipo.unverified_fields.add("gmp")
    assert ipo.gmp_pct_text == "Not verified"


def test_no_number_is_ever_invented():               # rule 5.3
    assert to_decimal("--") is None and to_decimal("NA") is None
    assert to_decimal("") is None and to_decimal(None) is None


def test_newer_timestamp_wins_on_conflict():         # rules 5.4 / 5.8
    gmp_row = mk("Acme", Decimal("50"), Decimal("200"))
    sub_row = mk("Acme", retail=Decimal("4"), total=Decimal("6"))
    sub_row.price_max = Decimal("250")               # disagrees with GMP page
    ds = build_dataset([sub_row], [gmp_row], TODAY,
                       sub_ts="29 Aug 2026, 08:30 PM",
                       gmp_ts="29 Aug 2026, 07:00 PM")
    assert ds.open_ipos[0].price_max == Decimal("250")
    assert ds.conflicts and "price_max" in ds.conflicts[0].field_name


def test_older_timestamp_does_not_overwrite():
    gmp_row = mk("Acme", Decimal("50"), Decimal("200"))
    sub_row = mk("Acme", retail=Decimal("4"))
    sub_row.price_max = Decimal("250")
    ds = build_dataset([sub_row], [gmp_row], TODAY,
                       sub_ts="29 Aug 2026, 06:00 PM",
                       gmp_ts="29 Aug 2026, 07:00 PM")
    assert ds.open_ipos[0].price_max == Decimal("200")


def test_separate_subscription_and_gmp_timestamps():  # rule 5.5
    ds = build_dataset([], [mk("A", Decimal("1"), Decimal("10"))], TODAY,
                       sub_ts="29 Aug 2026, 07:45 PM", gmp_ts="29 Aug 2026, 08:10 PM")
    out = build_report(ds)
    assert "Subscription data: 29 Aug 2026, 07:45 PM" in out
    assert "GMP data: 29 Aug 2026, 08:10 PM" in out


# --- Section 2 / 3: scope ---------------------------------------------------

def test_sme_is_excluded_from_published_set():
    sme = mk("Tiny SME", Decimal("5"), Decimal("50"), board=Board.SME)
    main = mk("Big Co", Decimal("5"), Decimal("50"))
    ds = build_dataset([], [sme, main], TODAY)
    assert [i.name for i in ds.published] == ["Big Co"]
    assert "Tiny SME" in ds.excluded_sme


def test_sme_detected_from_section_heading_alone():
    html = ("<h2>SME IPO Subscription Status</h2><table>"
            "<tr><th>IPO</th><th>Retail</th><th>Total</th><th>Date</th></tr>"
            "<tr><td>Plain Name</td><td>2x</td><td>3x</td><td>27 Aug - 29 Aug 2026</td></tr>"
            "</table>")
    assert parse_page(html, "u", TODAY)[0].board == Board.SME


def test_qib_and_nii_are_never_captured():           # section 3
    html = ("<table><tr><th>IPO</th><th>QIB</th><th>NII</th><th>Retail</th>"
            "<th>Total</th><th>Date</th></tr>"
            "<tr><td>Acme</td><td>99x</td><td>88x</td><td>3x</td><td>7x</td>"
            "<td>27 Aug - 29 Aug 2026</td></tr></table>")
    ipo = parse_page(html, "u", TODAY)[0]
    assert ipo.retail_sub == Decimal("3") and ipo.total_sub == Decimal("7")
    report = build_report(build_dataset([ipo], [], TODAY))
    assert "99" not in report and "88" not in report
    assert "QIB" not in report and "NII" not in report


def test_closed_ipos_retained_internally_but_not_published():
    closed = mk("Old Co", Decimal("5"), Decimal("50"),
                o=date(2026, 8, 20), c=date(2026, 8, 22))
    ds = build_dataset([], [closed], TODAY)
    assert ds.published == [] and [i.name for i in ds.recently_closed] == ["Old Co"]


# --- Section 7: image must equal the dataset --------------------------------

def test_image_check_flags_any_altered_number():
    ds = build_dataset([], [mk("Acme", Decimal("325"), Decimal("429"))], TODAY)
    good = expected_map(ds)
    assert check(ds, dict(good)) == []
    tampered = dict(good); tampered["ipo0.gmppct"] = "75.70%"
    assert any(m.key == "ipo0.gmppct" for m in check(ds, tampered))


def test_image_check_flags_missing_figure():
    ds = build_dataset([], [mk("Acme", Decimal("325"), Decimal("429"))], TODAY)
    partial = expected_map(ds); partial.pop("ipo0.gmp")
    assert any("missing" in m.actual for m in check(ds, partial))


# --- misc -------------------------------------------------------------------

def test_price_band_parsing():
    assert parse_price_band("₹402-429") == (Decimal("402"), Decimal("429"))
    assert parse_price_band("Rs 86 to 91") == (Decimal("86"), Decimal("91"))


def test_name_matching_across_pages():
    assert norm_key("Vidya Wires IPO") == norm_key("Vidya Wires Limited")


def test_caption_reports_leaders():
    ds = build_dataset([mk("Acme", retail=Decimal("3.25"))],
                       [mk("Acme", Decimal("325"), Decimal("429"))], TODAY)
    cap = build_caption(ds)
    assert "75.76%" in cap and "3.25x" in cap
