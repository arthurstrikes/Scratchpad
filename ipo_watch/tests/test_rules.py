"""Tests for the accuracy rules in spec sections 3, 4 and 5."""
import sys, os
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipo_watch.models import IPO, Board, Status, parse_price_band, to_decimal
from ipo_watch.merge import build_dataset, norm_key
from ipo_watch.parse import parse_page, detect_board, _clean_name
from ipo_watch.report import build_report
from ipo_watch.verify import check, expected_map

TODAY = date(2026, 8, 29)


def mk(name, gmp=None, pmax=None, retail=None, total=None,
       o=date(2026, 8, 27), c=date(2026, 8, 29), board=Board.MAINBOARD):
    return IPO(name=name, board=board, open_date=o, close_date=c,
               price_min=Decimal("1"), price_max=pmax, gmp=gmp,
               retail_sub=retail, total_sub=total)


# --- Section 4: GMP maths ---------------------------------------------------

def test_gmp_pct_matches_spec_worked_example():
    ipo = mk("X", Decimal("325"), Decimal("429"))
    assert ipo.gmp_pct == Decimal("75.76")        # computed to 2dp, half-up (section 4)
    assert ipo.gmp_pct_text == "76%"              # shown as a whole number from 10% up (18 Oct)


def test_gmp_pct_is_two_dp_half_up():
    assert mk("X", Decimal("1"), Decimal("3")).gmp_pct == Decimal("33.33")
    assert mk("X", Decimal("2"), Decimal("3")).gmp_pct == Decimal("66.67")


def test_gmp_pct_display_is_whole_from_ten_up_and_two_decimals_below():
    assert mk("X", Decimal("1"), Decimal("3")).gmp_pct_text == "33%"
    assert mk("X", Decimal("2"), Decimal("3")).gmp_pct_text == "67%"
    assert mk("X", Decimal("45"), Decimal("200")).gmp_pct_text == "23%"       # 22.50 half-up
    assert mk("X", Decimal("15"), Decimal("344")).gmp_pct_text == "4.36%"     # single digit keeps 2dp
    assert mk("X", Decimal("9996"), Decimal("100000")).gmp_pct_text == "10%"  # 9.996 -> 10.00 -> 10%


def test_high_gmp_flag_uses_the_exact_value_not_the_rounded_display():
    ipo = mk("X", Decimal("2540"), Decimal("10000"))      # 25.40%
    assert ipo.gmp_pct_text == "25%" and ipo.is_hot is True   # above 25 -> flagged, though shown "25%"
    assert mk("X", Decimal("2500"), Decimal("10000")).is_hot is False   # exactly 25 is not flagged


def test_zero_gmp_renders_zero_not_blank():          # rule 5.7
    assert mk("X", Decimal("0"), Decimal("100")).gmp_pct_text == "0.00%"
    assert mk("X", Decimal("0"), Decimal("100")).gmp_text == "₹0"


def test_gmp_pct_is_computed_not_copied():
    """A wrong 'estimated gain' on the page must not influence our number."""
    ipo = mk("X", Decimal("18"), Decimal("126"))
    assert ipo.gmp_pct == Decimal("14.29")           # 18/126 = 14.2857 -> 14.29


def test_highlight_threshold_is_strictly_above_25pct():
    assert mk("X", Decimal("25"), Decimal("100")).is_hot is False    # exactly 25% is not flagged
    assert mk("X", Decimal("26"), Decimal("100")).is_hot is True
    assert mk("X", Decimal("12"), Decimal("100")).is_hot is False    # the old 10% line no longer flags


def test_only_high_gmp_rows_carry_the_flag_in_text_and_image():
    from ipo_watch.creative import build_html
    ds = build_dataset([], [mk("Hot Co", Decimal("40"), Decimal("100")),
                            mk("Mild Co", Decimal("15"), Decimal("100"))], TODAY)
    out = build_report(ds)
    assert "🔥 HOT CO" in out and "🔥 MILD CO" not in out and "*MILD CO*" in out
    html = build_html(ds)
    assert html.count('class="flag">High GMP') == 1
    assert "Flag = GMP above 25%" in out and "High GMP = above 25%" in html


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


def test_name_strips_ipowatch_status_suffix():
    # IPOWatch started appending a bare status letter to the GMP page's
    # company name (seen 2 Oct 2026): "Vishal Nirmiti(O)", "Jio Platform(U)".
    # Left in, it would make the same company's name on this page normalize
    # differently from its plain name on the subscription page.
    assert _clean_name("Vishal Nirmiti(O)") == "Vishal Nirmiti"
    assert _clean_name("Jio Platform(U)") == "Jio Platform"
    # parse.py always cleans the name before merge.py ever sees it, so the
    # merge key only needs to agree once both names have gone through
    # _clean_name - exactly what happens in the real pipeline.
    assert norm_key(_clean_name("Vishal Nirmiti(O)")) == norm_key("Vishal Nirmiti")


def test_name_strips_ipowatch_status_and_board_suffix():
    # One day later (3 Oct 2026) IPOWatch dropped the Type column too and
    # started appending the board type the same way the status letter was:
    # "Vishal Nirmiti (O) Mainboard", "TNA Solutions (O) SME".
    assert _clean_name("Vishal Nirmiti (O) Mainboard") == "Vishal Nirmiti"
    assert _clean_name("TNA Solutions (O) SME") == "TNA Solutions"
    assert _clean_name("Jio Platform(U)Mainboard") == "Jio Platform"
    assert norm_key(_clean_name("Vishal Nirmiti (O) Mainboard")) == norm_key("Vishal Nirmiti")


def test_name_strips_bare_status_word_suffix():
    # Two days later still (5 Oct 2026) IPOWatch dropped the parentheses
    # too: the bare status word now follows the name as a separate text
    # node in the same cell - "Vishal Nirmiti Open", "Nityas Gems Closed"
    # (what `_cell_text()`'s join character actually produces live) - but
    # cover the no-space join too, since this page has changed three days
    # running and the exact join character is not something to rely on.
    assert _clean_name("Jio Platform Upcoming") == "Jio Platform"
    assert _clean_name("Vishal Nirmiti Open") == "Vishal Nirmiti"
    assert _clean_name("Nityas Gems Closed") == "Nityas Gems"
    assert _clean_name("TNA Solutions Open") == "TNA Solutions"
    assert _clean_name("Jio PlatformUpcoming") == "Jio Platform"
    assert _clean_name("Vishal NirmitiOpen") == "Vishal Nirmiti"
    assert norm_key(_clean_name("Vishal Nirmiti Open")) == norm_key("Vishal Nirmiti")


def test_sme_conflict_never_reaches_the_report():    # rules 2 / 5.8
    gmp_row = mk("Tiny Co", Decimal("50"), Decimal("200"), board=Board.SME)
    sub_row = mk("Tiny Co", retail=Decimal("4"), total=Decimal("6"), board=Board.SME)
    sub_row.price_max = Decimal("250")                # disagrees with GMP page
    ds = build_dataset([sub_row], [gmp_row], TODAY,
                       sub_ts="29 Aug 2026, 08:30 PM",
                       gmp_ts="29 Aug 2026, 07:00 PM")
    assert "Tiny Co" in ds.excluded_sme
    assert not ds.conflicts, "an excluded SME's name must not leak into the report"


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


def test_report_uses_whatsapp_markup():
    ds = build_dataset([mk("Acme", retail=Decimal("3.25"))],
                       [mk("Acme", Decimal("325"), Decimal("429"))], TODAY)
    out = build_report(ds)
    assert out.startswith("*📊 DAILY MAINBOARD IPO WATCH*")
    assert "*🔥 ACME*" in out
    assert "| *76%*" in out
    assert "📌 _GMP = Grey Market Premium_" in out


def test_report_names_the_leaders():
    ds = build_dataset([mk("Acme", retail=Decimal("3.25"))],
                       [mk("Acme", Decimal("325"), Decimal("429"))], TODAY)
    out = build_report(ds)
    assert "Highest GMP: Acme — 76%" in out
    assert "Highest Retail Subscription: Acme — 3.25x" in out


# --- Section 5: parsing IPOWatch's real markup ------------------------------
# fixtures/live/ is trimmed from an actual fetch on 2026-08-29. These pin the
# parser to the real page shape: explicit Type / Status columns, a single
# cap price rather than a range, compact "28-1 September" date ranges, and a
# historical GMP table that must be ignored.

import os
LIVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "live")


def _live_dataset():
    from ipo_watch.parse import parse_page
    sub = parse_page(open(os.path.join(LIVE, "sub_sample.html"), encoding="utf-8").read(),
                     "sub", date(2026, 8, 29))
    gmp = parse_page(open(os.path.join(LIVE, "gmp_sample.html"), encoding="utf-8").read(),
                     "gmp", date(2026, 8, 29))
    return build_dataset(sub, gmp, date(2026, 8, 29))


def test_live_markup_selects_the_right_ipos():
    ds = _live_dataset()
    assert [i.name for i in ds.open_ipos] == [
        "ESDS Software", "Lumino Industries", "Priority Jewels"]
    assert [i.name for i in ds.upcoming_ipos] == [
        "Deepa Jewellers", "Rays of Belief", "Purple Style Labs"]


def test_live_markup_gmp_matches_hand_calculation():
    ds = _live_dataset()
    got = {i.name: i.gmp_pct_text for i in ds.published}
    assert got["ESDS Software"] == "84%"      # 360/429 = 83.92, rounded not truncated
    assert got["Lumino Industries"] == "73%"  # 60/82 = 73.17
    assert got["Priority Jewels"] == "23%"    # 45/200 = 22.50, half-up
    assert got["Deepa Jewellers"] == "27%"    # 47/177 = 26.55


def test_live_markup_carries_subscription_from_the_other_page():
    ds = _live_dataset()
    esds = next(i for i in ds.open_ipos if i.name == "ESDS Software")
    assert esds.retail_text == "2.84x" and esds.total_text == "2.21x"


def test_live_markup_excludes_sme_and_history():
    ds = _live_dataset()
    names = {i.name for i in ds.published}
    assert "Paluck Technologies" not in names      # SME, from the Type column
    assert "Kwick Forensic Solutions" not in names  # SME, from the SME GMP table
    assert "Lalithaa Jewellery Mart" not in names   # already-listed history table
    assert all(i.board.value == "Mainboard" for i in ds.published)


def test_live_markup_keeps_the_two_timestamps_apart():
    ds = _live_dataset()
    assert ds.subscription_timestamp == "29 Aug, 17:45"
    assert ds.gmp_timestamp == "29 Aug, 16:50"


# --- Telegram delivery (mocked; no real bot token needed to test) ----------

def test_telegram_skips_silently_when_not_configured(monkeypatch):
    from ipo_watch import telegram
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert telegram.configured() is False
    try:
        telegram.send_report("x.png", "report text")
        assert False, "should have raised"
    except telegram.TelegramError:
        pass


def test_telegram_sends_photo_then_report_text(monkeypatch, tmp_path):
    from ipo_watch import telegram
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:fake")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")

    calls = []

    def fake_post(method, fields, files=None):
        calls.append((method, dict(fields), files))
        return {"ok": True, "result": {}}

    monkeypatch.setattr(telegram, "_post", fake_post)

    png = tmp_path / "ipo-watch-2026-09-03.png"
    png.write_bytes(b"\x89PNG fake bytes")

    telegram.send_report(str(png), "the full report text")

    assert calls[0][0] == "sendPhoto"
    assert calls[0][1]["chat_id"] == "999"
    assert "2026-09-03" in calls[0][1]["caption"]
    assert calls[0][2]["photo"][0] == "ipo-watch-2026-09-03.png"

    assert calls[1][0] == "sendMessage"
    assert calls[1][1]["parse_mode"] == "HTML"
    assert calls[1][1]["text"] == "<pre>the full report text</pre>"


def test_telegram_escapes_report_html_and_keeps_whatsapp_markup(monkeypatch, tmp_path):
    from ipo_watch import telegram
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:fake")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    calls = []
    monkeypatch.setattr(telegram, "_post",
                        lambda method, fields, files=None: calls.append((method, fields)) or {"ok": True})
    png = tmp_path / "ipo-watch-2026-09-03.png"
    png.write_bytes(b"fake")
    telegram.send_report(str(png), "*A & B <Co>* _note_")
    assert calls[1][1]["text"] == "<pre>*A &amp; B &lt;Co&gt;* _note_</pre>"


def test_telegram_chunks_long_reports_under_the_message_limit(monkeypatch, tmp_path):
    from ipo_watch import telegram
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:fake")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")

    calls = []
    monkeypatch.setattr(telegram, "_post",
                        lambda method, fields, files=None: calls.append((method, fields)) or {"ok": True})

    png = tmp_path / "ipo-watch-2026-09-03.png"
    png.write_bytes(b"fake")
    huge_report = "".join(f"line {n:04d} " + "x" * 40 + "\n" for n in range(200))

    telegram.send_report(str(png), huge_report)

    message_calls = [c for c in calls if c[0] == "sendMessage"]
    bodies = [c[1]["text"][len("<pre>"):-len("</pre>")] for c in message_calls]
    assert len(message_calls) == 3
    assert all(len(b) <= 4000 for b in bodies)
    assert all(b.endswith("\n") for b in bodies)  # never split mid-line
    assert "".join(bodies) == huge_report


def test_telegram_lookup_chat_id_reads_latest_update(monkeypatch):
    from ipo_watch import telegram
    import json as _json

    class FakeResp:
        def __init__(self, payload):
            self._payload = _json.dumps(payload).encode()
        def read(self):
            return self._payload
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    payload = {"ok": True, "result": [
        {"message": {"chat": {"id": 111}}},
        {"message": {"chat": {"id": 222}}},
    ]}
    monkeypatch.setattr(telegram.urllib.request, "urlopen", lambda *a, **k: FakeResp(payload))

    assert telegram.lookup_chat_id("123:fake") == 222


# --- GMP trend, key facts, 4:5 fit, alerts (added 15 Oct 2026) --------------

from ipo_watch.enrich import (compute_trend, find_detail_url, page_is_about, parse_detail_facts,
                              parse_gmp_history)
from ipo_watch.models import Trend, _indian

D = date(2026, 10, 15)


def _hist(*pairs):
    return [(date(2026, 10, d), None if g is None else Decimal(str(g))) for d, g in pairs]


def test_trend_up_down_flat_against_previous_day():
    up = compute_trend(_hist((14, 86)), D, Decimal("91"))
    assert up.direction == "up" and up.text() == "▲ ₹5" and up.vs_text(D) == "vs yesterday"
    down = compute_trend(_hist((14, 100)), D, Decimal("91"))
    assert down.direction == "down" and down.text() == "▼ ₹9"
    flat = compute_trend(_hist((14, 91)), D, Decimal("91"))
    assert flat.direction == "flat" and flat.text() == "▬ ₹0"


def test_trend_ignores_todays_own_history_row_and_skips_blank_days():
    # today's row on IPOWatch must not be the baseline; a dash day is skipped
    h = _hist((15, 999), (14, None), (13, 80), (12, 70))
    t = compute_trend(h, D, Decimal("91"))
    assert t.prev_gmp == Decimal("80") and t.change == Decimal("11")
    assert t.vs_text(D) == "vs 13 Oct"          # honest about which day it is
    assert [str(x) for x in t.series] == ["70", "80", "91"]


def test_trend_new_and_unavailable_are_distinct():
    assert compute_trend(_hist((15, 50)), D, Decimal("91")).status == "new"
    assert compute_trend(None, D, Decimal("91")).status == "unavailable"
    assert compute_trend(_hist((14, 80)), D, None).status == "unavailable"
    assert Trend(status="unavailable").text() == "Not updated"


def test_gmp_history_table_parsed_and_dashes_become_none():
    html = ("<table><tr><th>Date</th><th>IPO GMP</th><th>GMP Trend</th><th>Gain</th></tr>"
            "<tr><td>15 October</td><td>₹91</td><td>🟢</td><td>33.58%</td></tr>"
            "<tr><td>6 October</td><td>₹-</td><td>–</td><td>-%</td></tr></table>")
    got = parse_gmp_history(html, D)
    assert got == [(date(2026, 10, 15), Decimal("91")), (date(2026, 10, 6), None)]
    assert parse_gmp_history("<table><tr><th>x</th></tr></table>", D) is None


DETAIL = ("<h1>HD Fire Protect IPO Date, Review</h1>"
          "<table><tr><th>Application</th><th>Lot Size</th><th>Shares</th><th>Amount</th></tr>"
          "<tr><td>Retail Minimum</td><td>1</td><td>55</td><td>₹14,905</td></tr></table>"
          "<table><tr><td>Basis of Allotment:</td><td>October 16, 2026</td></tr>"
          "<tr><td>IPO Listing</td><td>BSE, NSE</td></tr>"
          "<tr><td>IPO Listing Date:</td><td>October 20, 2026</td></tr></table>")


def test_detail_facts_parsed():
    f = parse_detail_facts(DETAIL, Decimal("271"))
    assert f["lot_shares"] == 55 and f["min_invest"] == Decimal("14905")
    assert f["allotment_date"] == date(2026, 10, 16)
    assert f["listing_date"] == date(2026, 10, 20)     # not the 'IPO Listing: BSE, NSE' row


def test_min_investment_hidden_unless_it_equals_shares_times_cap_price():
    assert parse_detail_facts(DETAIL, Decimal("300"))["min_invest"] is None   # 55 x 300 != 14905
    assert parse_detail_facts(DETAIL, None)["min_invest"] is None             # no cap price yet


def test_page_must_name_the_right_company():
    assert page_is_about(DETAIL, "HD Fire Protect")
    assert not page_is_about(DETAIL, "Tonbo Imaging")


def test_indian_digit_grouping():
    assert _indian(Decimal(14905)) == "14,905"
    assert _indian(Decimal(1993765)) == "19,93,765"


def test_stamp_from_the_future_is_dated_yesterday():
    from datetime import datetime
    from ipo_watch.merge import _qualify_stamp
    now = datetime(2026, 10, 15, 14, 25)
    assert _qualify_stamp("17:41", D, now) == "14 Oct, 17:41"   # not refreshed yet today
    assert _qualify_stamp("09:10", D, now) == "15 Oct, 09:10"
    assert _qualify_stamp("17:41", D, None) == "15 Oct, 17:41"  # replay: unchanged behaviour


def _rich():
    ipo = mk("Acme", Decimal("91"), Decimal("271"), retail=Decimal("3.5"), total=Decimal("4"),
             o=date(2026, 10, 13), c=date(2026, 10, 16))
    ipo.price_min = None                      # IPOWatch gives a single cap price
    ipo.trend = compute_trend(_hist((12, 75), (13, 80), (14, 86)), D, Decimal("91"))
    ipo.lot_shares, ipo.min_invest = 55, Decimal("14905")
    ipo.allotment_date, ipo.listing_date = date(2026, 10, 17), date(2026, 10, 21)
    return ipo


def test_report_shows_trend_minimum_and_key_dates():
    out = build_report(build_dataset([], [_rich()], D))
    assert "💰 Price: ₹271 | Min ₹14,905 (55 shares)" in out
    assert "📈 GMP trend: ▲ ₹5 vs yesterday (₹86 → ₹91)" in out
    assert "🗓️ Allotment: 17 Oct | Listing: 21 Oct" in out


def test_report_without_enrichment_is_unchanged_and_never_invents():
    out = build_report(build_dataset([], [mk("Plain", Decimal("5"), Decimal("100"))], TODAY))
    assert "GMP trend" not in out and "Allotment" not in out and "Min ₹" not in out


def test_every_figure_drawn_on_the_image_is_checked_against_the_dataset():
    """The keys the HTML paints must equal the keys verify expects, exactly,
    including the new trend / minimum / allotment / listing figures."""
    import re
    from ipo_watch.creative import build_html
    ds = build_dataset([], [_rich()], D)
    painted = set(re.findall(r'data-verify="([^"]+)"', build_html(ds)))
    assert painted == set(expected_map(ds))
    assert {"ipo0.trend", "ipo0.min", "ipo0.allot", "ipo0.list"} <= painted


def test_telegram_failure_notice_is_plain_text_and_scrubs_the_token(monkeypatch):
    from ipo_watch import telegram
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:secret")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    calls = []
    monkeypatch.setattr(telegram, "_post",
                        lambda method, fields, files=None: calls.append((method, fields)) or {"ok": True})
    telegram.send_alert("boom at https://api.telegram.org/bot123:secret/x")
    assert calls[0][0] == "sendMessage" and "secret" not in calls[0][1]["text"]
    assert "parse_mode" not in calls[0][1]


def test_run_sends_failure_notice_when_ipowatch_cannot_be_read(monkeypatch, tmp_path):
    from ipo_watch import run, telegram
    from ipo_watch.fetch import FetchError
    sent = []
    monkeypatch.setattr(telegram, "configured", lambda: True)
    monkeypatch.setattr(telegram, "send_alert", lambda text: sent.append(text))
    monkeypatch.setattr(run, "collect", lambda *a, **k: (_ for _ in ()).throw(FetchError("blocked")))
    assert run.main(["--outdir", str(tmp_path), "--date", "2026-10-15"]) == 2
    assert len(sent) == 1 and "blocked" in sent[0] and "no numbers were guessed" in sent[0]


def test_core_fetch_retries_a_dropped_connection_then_succeeds(monkeypatch):
    from ipo_watch import fetch
    calls = {"n": 0}

    class Resp:
        status = 200
        headers = {}
        def read(self): return b"<table><tr><td>ok</td></tr></table>"
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def flaky(req, timeout=None, context=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("EOF occurred in violation of protocol")
        return Resp()

    monkeypatch.setattr(fetch.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    pg = fetch.fetch_pages(["https://ipowatch.in/x/"])["https://ipowatch.in/x/"]
    assert calls["n"] == 3 and "<table" in pg.html


def test_core_fetch_gives_up_after_the_last_attempt(monkeypatch):
    from ipo_watch import fetch
    monkeypatch.setattr(fetch.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    try:
        fetch.fetch_pages(["https://ipowatch.in/x/"])
        assert False, "should have raised"
    except fetch.FetchError as exc:
        assert "down" in str(exc)


def test_trend_falls_back_to_our_own_earlier_reports(tmp_path):
    import json
    from ipo_watch.enrich import enrich_ipo, load_local_history
    for day, g in (("2026-10-13", "80"), ("2026-10-14", "86"), ("2026-10-15", "999")):
        (tmp_path / f"ipo-watch-{day}-dataset.json").write_text(json.dumps(
            {"run_date": day, "open": [{"name": "Acme Ltd", "gmp": g}], "upcoming": []}))
    local = load_local_history(str(tmp_path), D)          # today's own file is ignored
    assert [(d.day, str(g)) for d, g in local[norm_key("Acme")]] == [(13, "80"), (14, "86")]
    ipo = mk("Acme", Decimal("91"), Decimal("271"))
    ipo.gmp_url = "https://ipowatch.in/acme-ipo-gmp-grey-market-premium/"
    problems = enrich_ipo(ipo, D, lambda url: None, local[norm_key("Acme")])
    assert ipo.trend.status == "ok" and ipo.trend.text() == "▲ ₹5" and problems["trend"] is False
    assert problems["detail"] is True        # facts have no fallback: omitted, with a note


# --- closing-day midday update ----------------------------------------------

def _closing_ds():
    from datetime import datetime
    from ipo_watch.config import IST
    closing = mk("Closes Today", Decimal("20"), Decimal("100"), retail=Decimal("2.5"),
                 total=Decimal("3"), o=date(2026, 10, 13), c=D)
    later = mk("Closes Friday", Decimal("5"), Decimal("100"), retail=Decimal("1"),
               total=Decimal("1"), o=date(2026, 10, 14), c=date(2026, 10, 16))
    for i in (closing, later):
        i.price_min = None
    return build_dataset([], [closing, later], D, generated_at=datetime(2026, 10, 15, 14, 0, tzinfo=IST))


def test_midday_report_covers_only_ipos_closing_today():
    from ipo_watch.report import build_midday_report
    out = build_midday_report(_closing_ds())
    assert "CLOSING TODAY" in out and "CLOSES TODAY" in out and "CLOSES FRIDAY" not in out
    assert "👥 Retail: 2.5x" in out and "📊 Total: 3x" in out
    assert "📅 15 Oct 2026 | 2:00 PM IST" in out
    assert "QIB" not in out and "NII" not in out


def test_midday_sends_nothing_when_no_ipo_closes_today():
    from ipo_watch.report import build_midday_report
    ds = build_dataset([], [mk("Opens Later", Decimal("5"), Decimal("100"),
                               o=date(2026, 10, 20), c=date(2026, 10, 22))], D)
    assert build_midday_report(ds) is None


def test_midday_mode_delivers_text_only(monkeypatch, tmp_path):
    from ipo_watch import run, telegram
    sent = []
    monkeypatch.setattr(telegram, "configured", lambda: True)
    monkeypatch.setattr(telegram, "send_text", lambda t: sent.append(t))
    monkeypatch.setattr(run, "collect", lambda *a, **k: _closing_ds())
    monkeypatch.setattr(run, "publish", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no image at midday")))
    assert run.main(["--mode", "midday", "--outdir", str(tmp_path), "--date", "2026-10-15"]) == 0
    assert len(sent) == 1 and "CLOSES TODAY" in sent[0]
    assert (tmp_path / "ipo-watch-2026-10-15-midday.txt").exists()


def test_core_fetch_decodes_gzip_pages(monkeypatch):
    import gzip as _gz
    from ipo_watch import fetch
    body = _gz.compress(b"<table><tr><td>zipped</td></tr></table>")
    seen = {}

    class Resp:
        status = 200
        headers = {"Content-Encoding": "gzip"}
        def read(self): return body
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake(req, timeout=None, context=None):
        seen["accept"] = req.get_header("Accept-encoding")
        return Resp()

    monkeypatch.setattr(fetch.urllib.request, "urlopen", fake)
    pg = fetch.fetch_pages(["https://ipowatch.in/x/"])["https://ipowatch.in/x/"]
    assert "zipped" in pg.html and seen["accept"] == "gzip"


# --- listing-day scorecard (NSE data), recent listings, photo caption -------

from ipo_watch import listing as L

EQUITY_CSV = (
    "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE\n"
    "NITYAS,Nityas Gems and Jewellery Limited,BE,08-OCT-2026,5,1,INE0000000001,5\n"
    "VNL,Vishal Nirmiti Limited,BE,08-OCT-2026,10,1,INE0000000002,10\n"
    "LANCER,Lancer Container Lines Limited,EQ,14-OCT-2026,5,1,INE0000000003,5\n"
    "OLDCO,Old Company Limited,EQ,06-OCT-2008,5,1,INE0000000004,5\n")
BHAV_CSV = (
    "SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER\n"
    "NITYAS, BE, 08-Oct-2026, 75.00, 80.00, 84.00, 77.00, 84.00, 83.99, 80.94, 7703838, 6235.19, 22306, -, -\n"
    "VNL, BE, 08-Oct-2026, 220.00, 215.00, 215.00, 204.25, 204.25, 204.25, 213.63, 647931, 1384.15, 4372, -, -\n"
    "LANCER, EQ, 14-Oct-2026, 10.78, 11.00, 11.50, 10.90, 11.20, 11.11, 11.19, 514886, 57.60, 3205, 177764, 34.52\n")
LD = date(2026, 10, 8)


def _cands():
    return [L.Candidate("Nityas Gems", date(2026, 10, 5), Decimal("75"), Decimal("3"), Decimal("4.00"), date(2026, 10, 5)),
            L.Candidate("Vishal Nirmiti", date(2026, 10, 5), Decimal("220"), Decimal("20"), Decimal("9.09"), date(2026, 10, 5))]


def _results():
    eq = L.parse_equity_list(EQUITY_CSV)
    bh = L.parse_bhav(BHAV_CSV)
    return L.find_results(_cands(), eq, lambda d: bh)


def test_nse_files_parse_despite_padded_headers_and_dashes():
    eq = L.parse_equity_list(EQUITY_CSV)
    assert {e["symbol"] for e in eq} >= {"NITYAS", "VNL"} and eq[0]["listing_date"] == LD
    bh = L.parse_bhav(BHAV_CSV)
    assert bh["NITYAS"]["prev_close"] == Decimal("75.00") and bh["VNL"]["close"] == Decimal("204.25")


def test_listing_maths_matches_the_real_8_oct_results():
    r = {x.symbol: x for x in _results()}
    n, v = r["NITYAS"], r["VNL"]
    assert (n.listing_gain_text, n.day1_text, n.close_vs_issue_text) == ("+6.67%", "+4.99%", "+11.99%")
    assert (v.listing_gain_text, v.day1_text, v.close_vs_issue_text) == ("-2.27%", "-5.00%", "-7.16%")
    assert n.gmp_said_text == "₹3 (4.00%)" and n.gap_text == "+2.67 pts"
    assert v.gap_text == "-11.36 pts"
    assert n.close_text == "₹83.99" and n.open_text == "₹80" and v.issue_text == "₹220"


def test_listing_match_prefers_exact_then_unique_prefix_and_never_guesses():
    eq = L.parse_equity_list(EQUITY_CSV)
    assert L.match_symbol(_cands()[1], eq)["symbol"] == "VNL"          # exact after noise words
    assert L.match_symbol(_cands()[0], eq)["symbol"] == "NITYAS"       # unique prefix
    two = eq + [{"symbol": "NITYAS2", "name": "Nityas Gems Two Limited", "series": "EQ",
                 "listing_date": LD}]
    assert L.match_symbol(_cands()[0], two) is None                    # ambiguous -> skip
    late = L.Candidate("Vishal Nirmiti", date(2026, 9, 1))
    assert L.match_symbol(late, eq) is None                            # listed outside the window


def test_a_relisting_with_a_very_different_price_is_not_taken_for_the_ipo():
    eq = L.parse_equity_list(EQUITY_CSV)
    c = L.Candidate("Lancer Container Lines", date(2026, 10, 12), cap_price=Decimal("100"))
    bh = L.parse_bhav(BHAV_CSV)
    assert L.build_result(c, L.match_symbol(c, eq), bh) is None        # 10.78 vs cap 100


def test_exchange_price_differing_from_cap_is_used_and_noted():
    eq = L.parse_equity_list(EQUITY_CSV)
    c = L.Candidate("Vishal Nirmiti", date(2026, 10, 5), cap_price=Decimal("225"))
    r = L.build_result(c, L.match_symbol(c, eq), L.parse_bhav(BHAV_CSV))
    assert r.issue_price == Decimal("220") and "differs from IPOWatch" in r.notes[0]


def test_same_company_under_two_spellings_is_reported_once_keeping_the_gmp():
    eq = L.parse_equity_list(EQUITY_CSV)
    bh = L.parse_bhav(BHAV_CSV)
    plain = L.Candidate("Vishal Nirmiti", date(2026, 10, 5), Decimal("220"))
    rich = L.Candidate("Vishal Nirmiti Ltd", date(2026, 10, 5), Decimal("220"), Decimal("20"), Decimal("9.09"))
    out = L.find_results([plain, rich], eq, lambda d: bh)
    assert len(out) == 1 and out[0].last_gmp == Decimal("20")


def test_candidates_come_from_our_own_saved_reports(tmp_path):
    import json
    def write(day, gmp):
        (tmp_path / f"ipo-watch-{day}-dataset.json").write_text(json.dumps({
            "run_date": day,
            "open": [{"name": "Acme", "close_date": "2026-10-05", "price_max": "100",
                      "gmp": gmp, "gmp_pct": gmp}],
            "upcoming": [], "recently_closed_internal": []}))
    write("2026-10-03", "10"); write("2026-10-05", "12"); write("2026-10-20", "99")   # future: ignored
    c = L.load_candidates(str(tmp_path), date(2026, 10, 8))
    assert len(c) == 1 and c[0].last_gmp == Decimal("12") and c[0].cap_price == Decimal("100")


def test_listing_card_paints_exactly_the_figures_that_are_verified():
    import re
    from ipo_watch.creative import build_listing_html
    from ipo_watch.verify import check_listing, expected_listing_map
    res = _results()
    painted = set(re.findall(r'data-verify="([^"]+)"', build_listing_html(res, LD)))
    assert painted == set(expected_listing_map(res))
    assert check_listing(res, dict(expected_listing_map(res))) == []
    bad = dict(expected_listing_map(res)); bad["l0.gain"] = "+9.99%"
    assert any(m.key == "l0.gain" for m in check_listing(res, bad))


def test_listing_report_text_and_daily_recent_listings_section():
    from ipo_watch.report import build_listing_report
    res = _results()
    txt = build_listing_report(res, LD)
    assert "*🏁 LISTING DAY SCORECARD*" in txt
    assert "💰 Issue ₹75 → Listed ₹80 | *+6.67%*" in txt
    assert "📈 Day 1: Open ₹80 → Close ₹83.99 | *+4.99%*" in txt
    assert "🎯 GMP said ₹3 (4.00%) | Gap +2.67 pts" in txt
    ds = build_dataset([], [mk("Acme", Decimal("5"), Decimal("100"))], date(2026, 10, 9))
    assert "RECENTLY LISTED" not in build_report(ds)
    ds.recent_listings = res
    out = build_report(ds)
    assert "*🏁 RECENTLY LISTED*" in out and "listed 08 Oct" in out
    assert out.index("RECENTLY LISTED") < out.index("CURRENT GMP RANKING")


def _patch_listing_world(monkeypatch, run, sent, polls):
    from ipo_watch import telegram
    from ipo_watch.verify import expected_listing_map
    monkeypatch.setattr(run, "fetch_equities", lambda: L.parse_equity_list(EQUITY_CSV))
    def text(url):
        polls.append(url)
        return None if len(polls) < 3 else BHAV_CSV          # NSE publishes on the 3rd look
    monkeypatch.setattr(run, "get_text", text)
    monkeypatch.setattr(run.time, "sleep", lambda s: None)
    monkeypatch.setattr(run, "render_listing_png", lambda rs, d, path: (path, expected_listing_map(rs)))
    monkeypatch.setattr(telegram, "configured", lambda: True)
    monkeypatch.setattr(telegram, "send_report", lambda png, text, caption=None: sent.append((text, caption)))


def test_listing_mode_waits_for_nse_sends_once_and_remembers(monkeypatch, tmp_path):
    import json
    from ipo_watch import run
    for day in ("2026-10-03", "2026-10-05"):
        (tmp_path / f"ipo-watch-{day}-dataset.json").write_text(json.dumps({
            "run_date": day, "upcoming": [], "recently_closed_internal": [],
            "open": [{"name": "Vishal Nirmiti", "close_date": "2026-10-05", "price_max": "220",
                      "gmp": "20", "gmp_pct": "9.09"},
                     {"name": "Nityas Gems", "close_date": "2026-10-05", "price_max": "75",
                      "gmp": "3", "gmp_pct": "4.00"}]}))
    sent, polls = [], []
    _patch_listing_world(monkeypatch, run, sent, polls)
    argv = ["--mode", "listing", "--date", "2026-10-08", "--outdir", str(tmp_path)]
    assert run.main(argv) == 0
    assert len(polls) == 3 and len(sent) == 1                          # waited, then sent once
    assert "VISHAL NIRMITI" in sent[0][0] and "Listing scorecard" in sent[0][1]
    assert (tmp_path / "ipo-watch-listing-VNL.json").exists()
    assert run.main(argv) == 0 and len(sent) == 1                      # remembered: not sent twice
    assert run.main(argv + ["--force"]) == 0 and len(sent) == 2        # unless forced


def test_listing_mode_is_quiet_when_nothing_lists_today(monkeypatch, tmp_path):
    from ipo_watch import run
    sent, polls = [], []
    _patch_listing_world(monkeypatch, run, sent, polls)
    assert run.main(["--mode", "listing", "--date", "2026-10-09", "--outdir", str(tmp_path)]) == 0
    assert sent == [] and polls == []


def test_photo_caption_is_compact_ranked_and_within_telegram_limit():
    from ipo_watch.report import build_caption
    ipos = [mk(f"Company number {i}", Decimal(i), Decimal("100"), o=date(2026, 10, 13), c=date(2026, 10, 16))
            for i in range(1, 41)]
    ds = build_dataset([], ipos, D)
    cap = build_caption(ds)
    assert len(cap) <= 1024 and cap.startswith("*📊 IPO Watch | 15 Oct*")
    assert cap.index("Company number 40") < cap.index("Company number 39")   # ranked by GMP %
    assert "more in the image" in cap
    small = build_caption(build_dataset([], [mk("Acme", Decimal("5"), Decimal("100"),
                                                o=date(2026, 10, 13), c=D)], D))
    assert "⏰ closes today" in small and "more in the image" not in small


def test_missing_price_band_has_no_rupee_sign_anywhere():
    import re
    from ipo_watch.creative import build_html
    ipo = mk("No Band Co", Decimal("5"), None)
    ipo.price_min = None
    ds = build_dataset([], [ipo], TODAY)
    assert ipo.price_display == "Not updated"
    assert "₹Not" not in build_report(ds) and "₹Not" not in build_html(ds)
    assert expected_map(ds)["ipo0.price"] == "Not updated"
    assert mk("Has Band", Decimal("5"), Decimal("100")).price_display == "₹1–100"


# --- Recently listed strip in the daily image --------------------------------

def _listed(name, symbol, day):
    return L.ListingResult(name=name, symbol=symbol, series="EQ", listing_date=date(2026, 10, day),
                           issue_price=Decimal("100"), open_price=Decimal("110"),
                           close_price=Decimal("104.5"), last_gmp=Decimal("8"),
                           last_gmp_pct=Decimal("8.00"))


def test_image_strip_shows_only_the_last_two_days_newest_first_and_at_most_three():
    rs = [_listed("A", "A", 13), _listed("B", "B", 14), _listed("C", "C", 15), _listed("D", "D", 15),
          _listed("Old", "OLD", 11)]
    got = [r.name for r in L.strip_listings(rs, date(2026, 10, 15))]
    assert got == ["D", "C", "B"]                     # newest first, cap 3; the 13th is 2 days old but cut by the cap
    assert [r.name for r in L.strip_listings(rs[:1], date(2026, 10, 15))] == ["A"]
    assert L.strip_listings([_listed("Old", "OLD", 11)], date(2026, 10, 15)) == []   # 4 days old
    assert L.strip_listings([], date(2026, 10, 15)) == []


def test_strip_figures_are_painted_and_verified_exactly_when_shown():
    import re
    from ipo_watch.creative import build_html
    ds = build_dataset([], [_rich()], D)
    ds.recent_listings = [_listed("Fresh Listing", "FRESH", 14), _listed("Newer Listing", "NEWER", 15)]
    keys = lambda html: set(re.findall(r'data-verify="([^"]+)"', html))  # noqa: E731
    all_rows = keys(build_html(ds, 0))
    assert all_rows == set(expected_map(ds))
    assert {"rl0.name", "rl0.date", "rl0.gain", "rl0.day1", "rl0.gmp", "rl1.name"} <= all_rows
    one_row = keys(build_html(ds, 0, 1))                 # shrunk to fit: only the newest row
    assert one_row == set(expected_map(ds, 1)) and "rl1.name" not in one_row
    no_rows = keys(build_html(ds, 0, 0))
    assert no_rows == set(expected_map(ds, 0)) and not any(k.startswith("rl") for k in no_rows)
    assert "Recently listed" in build_html(ds, 0) and "Recently listed" not in build_html(ds, 0, 0)
    bad = dict(expected_map(ds)); bad["rl0.gain"] = "+99.00%"
    assert any(m.key == "rl0.gain" for m in check(ds, bad))


def test_detail_page_found_via_ipo_details_button_when_slug_differs():
    gmp = ('<a href="/tonbo-imaging-india-ipo/">IPO Details</a>'
           '<a href="/tonbo-imaging-ipo-review-by-dilip-davda/">Review</a>')
    url = find_detail_url(gmp, "Tonbo Imaging",
                          "https://ipowatch.in/tonbo-imaging-ipo-gmp-grey-market-premium/")
    assert url.endswith("/tonbo-imaging-india-ipo/")


def test_missing_minimum_investment_is_flagged_in_data_notes():
    from ipo_watch.enrich import enrich_dataset
    from ipo_watch.merge import Dataset
    a = mk("Alpha Co", Decimal("10"), Decimal("100"))
    a.gmp_url = "https://ipowatch.in/alpha-co-ipo-gmp-grey-market-premium/"
    ds = Dataset(open_ipos=[a])
    gmp = ("<h1>Alpha Co IPO GMP</h1><table><tr><th>Date</th><th>IPO GMP</th></tr></table>"
           "<a href='/alpha-co-ipo/'>IPO Details</a>")
    detail = "<h1>Alpha Co IPO Date</h1><table><tr><td>Basis of Allotment:</td><td>October 21, 2026</td></tr></table>"
    pages = {a.gmp_url: gmp, "https://ipowatch.in/alpha-co-ipo/": detail}
    enrich_dataset(ds, date(2026, 10, 15), pages.get)
    assert any("Minimum investment not available for: Alpha Co" in w for w in ds.warnings)


def test_trend_is_measured_against_the_figure_we_published():
    from ipo_watch.enrich import overlay_published
    today = date(2026, 10, 18)
    ipowatch = [(date(2026, 10, 17), Decimal("15")), (date(2026, 10, 16), Decimal("40"))]
    ours = [(date(2026, 10, 17), Decimal("35"))]          # what we showed on the 17th
    t = compute_trend(overlay_published(ipowatch, ours), today, Decimal("15"))
    assert t.prev_gmp == Decimal("35") and t.change == Decimal("-20")
    assert [str(v) for v in t.series] == ["40", "35", "15"]


# --- 18 Oct 2026 decision aids: urgency tags, glance, subscription change,
# --- GMP track record, awaiting-listing section, weekly wrap -----------------

def _open(name, close, retail=None, prev=None, gmp=None, prev_date=date(2026, 10, 17)):
    from ipo_watch.models import Status
    i = mk(name, gmp, Decimal("100"), retail=retail, total=retail,
           o=date(2026, 10, 15), c=close)
    i.status = Status.OPEN
    i.prev_retail = prev
    i.prev_retail_date = prev_date if prev is not None else None
    return i


def test_urgency_label_only_for_today_and_tomorrow():
    t = date(2026, 10, 18)
    assert _open("A", date(2026, 10, 18)).closes_label(t) == "Closes today"
    assert _open("A", date(2026, 10, 19)).closes_label(t) == "Closes tomorrow"
    assert _open("A", date(2026, 10, 20)).closes_label(t) is None     # nothing further out
    assert mk("U").closes_label(t) is None                            # not Open: no label


def test_subscription_change_shows_only_meaningful_moves():
    t = date(2026, 10, 18)
    up = _open("A", date(2026, 10, 19), Decimal("7.14"), Decimal("5.24"))
    assert up.sub_change_text("retail", t) == "▲ from 5.24x"
    assert up.sub_change_short("retail") == "▲ 1.9x"
    down = _open("A", date(2026, 10, 19), Decimal("1"), Decimal("2"))
    assert down.sub_change_text("retail", t) == "▼ from 2x" and down.sub_change_short("retail") == "▼ 1x"
    # noise is hidden: under 0.1x, or under 5% of the earlier figure, or unchanged
    assert _open("A", date(2026, 10, 19), Decimal("0.37"), Decimal("0.31")).sub_change_text("retail", t) is None
    assert _open("A", date(2026, 10, 19), Decimal("131.73"), Decimal("130.88")).sub_change_short("retail") is None
    assert _open("A", date(2026, 10, 19), Decimal("3"), Decimal("3")).sub_change_text("retail", t) is None
    assert _open("A", date(2026, 10, 19), Decimal("3")).sub_change_text("retail", t) is None   # no earlier figure
    old = _open("A", date(2026, 10, 19), Decimal("3"), Decimal("2"), prev_date=date(2026, 10, 15))
    assert old.sub_change_text("retail", t) == "▲ from 2x on 15 Oct"


def test_total_subscription_gets_the_same_meaningful_change_rule():
    t = date(2026, 10, 18)
    i = _open("A", date(2026, 10, 19), Decimal("3"))
    i.total_sub, i.prev_total, i.prev_total_date = Decimal("9"), Decimal("6"), date(2026, 10, 17)
    assert i.sub_change_text("total", t) == "▲ from 6x" and i.sub_change_short("total") == "▲ 3x"
    i.total_sub = Decimal("6.05")
    assert i.sub_change_short("total") is None


def test_weekend_keeps_showing_the_last_move(tmp_path):
    """IPOWatch does not refresh on weekends: Sunday must still show Friday's move,
    not a meaningless 'no change' against Saturday's identical report."""
    import json
    from ipo_watch.enrich import attach_prev_subscription
    from ipo_watch.merge import Dataset
    for day, retail in (("2026-10-15", "5.24"), ("2026-10-16", "7.14"), ("2026-10-17", "7.14")):
        (tmp_path / f"ipo-watch-{day}-dataset.json").write_text(json.dumps(
            {"run_date": day, "open": [{"name": "Alpha Co", "retail_sub": retail, "total_sub": retail}]}))
    a = _open("Alpha Co", date(2026, 10, 19), Decimal("7.14"))
    attach_prev_subscription(Dataset(open_ipos=[a], run_date=date(2026, 10, 18)), str(tmp_path),
                             date(2026, 10, 18))
    assert a.prev_retail == Decimal("5.24") and a.prev_retail_date == date(2026, 10, 15)
    assert a.sub_change_text("retail", date(2026, 10, 18)) == "▲ from 5.24x on 15 Oct"


def test_glance_line_counts_only():
    from ipo_watch.merge import Dataset
    from ipo_watch.report import glance_text
    ds = Dataset(open_ipos=[_open("A", date(2026, 10, 19), gmp=Decimal("40")),
                            _open("B", date(2026, 10, 18), gmp=Decimal("5"))],
                 upcoming_ipos=[mk("C")], run_date=date(2026, 10, 18))
    assert glance_text(ds) == "2 open (1 closes today, 1 closes tomorrow) · 1 upcoming · 1 above 25% GMP"
    assert glance_text(Dataset(run_date=date(2026, 10, 18))) == \
        "none open · none upcoming · none above 25% GMP"


def _res(sym, d, issue, opn, gmp_pct, close=None):
    from ipo_watch.listing import ListingResult
    return ListingResult(name=sym, symbol=sym, series="EQ", listing_date=d,
                         issue_price=Decimal(issue), open_price=Decimal(opn),
                         close_price=Decimal(close or opn),
                         last_gmp=Decimal("1") if gmp_pct is not None else None,
                         last_gmp_pct=Decimal(gmp_pct) if gmp_pct is not None else None)


def test_track_record_averages_the_latest_25_listings():
    from ipo_watch.listing import track_record
    rs = [_res(f"S{i}", date(2026, 9, 1) + timedelta(days=i), "100", "110", "20", "99")
          for i in range(30)]
    tr = track_record(rs)
    assert tr.n == 25 and tr.title == "GMP track record · last 25 listings"
    assert (tr.gain_text, tr.up_text, tr.day1_text) == ("+10.0%", "25 of 25", "-10.0%")
    assert (tr.miss_text, tr.acc_text, tr.acc_note) == ("10.0 pts", "25 of 25", "within 10 pts of GMP")


def test_track_record_needs_enough_listings_and_gmp_miss_needs_enough_gmps():
    from ipo_watch.listing import track_record
    assert track_record([_res(f"S{i}", date(2026, 10, 1 + i), "100", "110", "10") for i in range(4)]) is None
    rs = [_res(f"S{i}", date(2026, 10, 1 + i), "100", "110", None) for i in range(6)]
    tr = track_record(rs)
    assert tr.n == 6 and tr.miss_text is None and tr.up_text == "6 of 6"   # no GMP on record: no miss figure


def test_awaiting_section_only_closed_unlisted_ipos_above_the_high_gmp_line(tmp_path):
    import json
    from ipo_watch.enrich import find_awaiting
    from ipo_watch.merge import Dataset
    from ipo_watch.models import Status
    (tmp_path / "ipo-watch-2026-10-15-dataset.json").write_text(json.dumps(
        {"run_date": "2026-10-15", "open": [{"name": "Hot Co", "allotment_date": "2026-10-16",
                                              "listing_date": "2026-10-20"}]}))
    def closed(name, gmp, close=date(2026, 10, 15)):
        i = mk(name, Decimal(gmp), Decimal("100"), retail=Decimal("3"), total=Decimal("9"),
               o=date(2026, 10, 13), c=close)
        i.status = Status.CLOSED
        return i
    ds = Dataset(recently_closed=[closed("Hot Co", "30"), closed("Cool Co", "20"),
                                  closed("Old Co", "40", close=date(2026, 9, 1))],
                 run_date=date(2026, 10, 18))
    got = find_awaiting(ds, str(tmp_path), date(2026, 10, 18))
    assert [i.name for i in got] == ["Hot Co"]                       # not Cool (25% or less), not Old
    assert got[0].allotment_text == "16 Oct" and got[0].listing_text == "20 Oct"
    assert find_awaiting(ds, str(tmp_path), date(2026, 10, 21)) == []  # listed on the 20th


def test_awaiting_and_track_record_are_drawn_and_checked_in_the_image():
    from ipo_watch.listing import track_record
    from ipo_watch.merge import Dataset
    from ipo_watch.models import Status
    from ipo_watch.verify import expected_map
    hot = mk("Hot Co", Decimal("30"), Decimal("100"), retail=Decimal("3"), total=Decimal("9"),
             o=date(2026, 10, 13), c=date(2026, 10, 15))
    hot.status = Status.CLOSED
    hot.listing_date = date(2026, 10, 20)
    rs = [_res(f"S{i}", date(2026, 10, 1 + i), "100", "110", "10") for i in range(6)]
    ds = Dataset(open_ipos=[_open("A", date(2026, 10, 19), Decimal("3"), Decimal("2"), gmp=Decimal("40"))],
                 awaiting=[hot], track_record=track_record(rs), run_date=date(2026, 10, 18))
    exp = expected_map(ds)
    assert exp["aw0.gmppct"] == "30%" and exp["aw0.list"] == "20 Oct" and exp["trk.up"] == "6 of 6"
    from ipo_watch.creative import render_png
    out_dir = tmp_path_factory_dir()
    _, rendered = render_png(ds, out_dir + "/t.png")
    assert check(ds, rendered, strip_rows=0) == []


def tmp_path_factory_dir():
    import tempfile
    return tempfile.mkdtemp()


def test_weekly_wrap_lists_this_weeks_listings_and_what_is_coming():
    from ipo_watch.listing import track_record
    from ipo_watch.merge import Dataset
    from ipo_watch.report import build_weekly_report
    a = _open("Alpha Co", date(2026, 10, 19))
    a.allotment_date, a.listing_date = date(2026, 10, 21), date(2026, 10, 23)
    ds = Dataset(open_ipos=[a], run_date=date(2026, 10, 18))
    listed = [_res("BETA", date(2026, 10, 14), "100", "110", "8")]
    tr = track_record([_res(f"S{i}", date(2026, 10, 1 + i), "100", "110", "10") for i in range(6)])
    text = build_weekly_report(date(2026, 10, 18), listed, ds, tr)
    assert "WEEKLY IPO WRAP" in text and "1 Mainboard IPO(s) we covered listed; 1 opened above" in text
    assert "• Alpha Co - bidding closes 19 Oct · allotment 21 Oct · lists 23 Oct" in text
    assert "GMP TRACK RECORD · LAST 6 LISTINGS" in text
    assert "None of the IPOs we covered listed this week." in build_weekly_report(
        date(2026, 10, 18), [], None, None)


def test_a_403_from_ipowatch_falls_back_to_a_real_browser(monkeypatch):
    import urllib.error
    from ipo_watch import fetch
    calls = {"browser": 0}

    def deny(*a, **k):
        raise urllib.error.HTTPError("https://ipowatch.in/x/", 403, "Forbidden", {}, None)

    def browser(urls, snapshot_dir=None):
        calls["browser"] += 1
        return {u: fetch.Page(url=u, html="<table></table>", fetched_at=fetch.datetime.now()) for u in urls}

    monkeypatch.setattr(fetch.urllib.request, "urlopen", deny)
    monkeypatch.setattr(fetch, "render_pages", browser)
    got = fetch.fetch_pages(["https://ipowatch.in/x/"], attempts=4)
    assert calls["browser"] == 1 and "<table" in got["https://ipowatch.in/x/"].html


def test_subscription_table_whose_name_header_became_a_row_number_still_parses():
    """19 Oct 2026: IPOWatch's first header cell changed from 'IPO' to '1'."""
    from ipo_watch.parse import parse_page
    html = ("<table><tr><th>1</th><th>Type</th><th>Closing Date</th><th>QIB (X)</th><th>NII (X)</th>"
            "<th>Retail (X)</th><th>Total (X)</th><th>Last Updated</th></tr>"
            "<tr><td>Tonbo Imaging</td><td>Mainboard</td><td>October 19, 2026</td><td>293.56</td>"
            "<td>170.44</td><td>29.49</td><td>135.00</td><td>16:30</td></tr></table>")
    rows = parse_page(html, "https://ipowatch.in/ipo-subscription-status-today/", date(2026, 10, 19))
    assert [(r.name, r.retail_sub, r.total_sub) for r in rows] == [("Tonbo Imaging", Decimal("29.49"), Decimal("135.00"))]


def test_a_heavy_day_still_fits_four_by_five():
    """19 Oct: 4 open + 3 upcoming + awaiting + track record was 1433px at the old
    densest tier; the extra tier keeps it inside 1350."""
    from ipo_watch.creative import MAX_H, last_render_info, render_png
    from ipo_watch.listing import track_record
    from ipo_watch.merge import Dataset
    from ipo_watch.models import Status
    hot = mk("Hot Co", Decimal("30"), Decimal("100"), retail=Decimal("3"), total=Decimal("9"),
             o=date(2026, 10, 13), c=date(2026, 10, 15))
    hot.status = Status.CLOSED
    open_ = [_open(f"Open {i}", date(2026, 10, 19), Decimal("3"), Decimal("2"), gmp=Decimal("40"))
             for i in range(4)]
    up = [mk(f"Up {i}", Decimal("20"), Decimal("100")) for i in range(3)]
    for u in up:
        u.status = Status.UPCOMING
    rs = [_res(f"S{i}", date(2026, 10, 1 + i), "100", "110", "10") for i in range(6)]
    ds = Dataset(open_ipos=open_, upcoming_ipos=up, awaiting=[hot], track_record=track_record(rs),
                 run_date=date(2026, 10, 19))
    render_png(ds, tmp_path_factory_dir() + "/t.png")
    assert last_render_info()["height"] <= MAX_H
