import json
from datetime import date
from pathlib import Path

import pandas as pd

import build
from pipeline.export import growth
from pipeline.sources import imf, sdmx

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 21)


def test_weo_keeps_actual_years_and_drops_projections():
    # The IMF marks 2025 as the last actual year; 2026-2028 are projections.
    df = imf.parse([FIXTURES / "imf_gdp-pc-ppp_BRA.csv"], "imf.gdp-pc-ppp.BRA")
    assert list(df["period"]) == ["2023", "2024", "2025"]
    assert round(df["value"].iloc[-1]) == 19968


def test_groups_without_the_marker_stop_before_this_year():
    # Groups such as G110 carry no LATEST_ACTUAL_ANNUAL_DATA.
    df = sdmx.parse_csv(
        [FIXTURES / "imf_gdp-pc-ppp_G110.csv"], "imf.gdp-pc-ppp.G110", today=TODAY
    )
    assert list(df["period"]) == ["2023", "2024", "2025"]


def test_weo_url_keeps_attributes_and_starts_in_1980():
    url = imf.build_url("gdp-pc-ppp", "BRA", imf.FULL_PERIODS, TODAY)
    assert url.endswith("/IMF.RES,WEO/BRA.NGDPRPPPPC.A?startPeriod=1980")
    recent = imf.build_url("gdp-pc-ppp", "BRA", imf.RECENT_PERIODS, TODAY)
    assert recent.endswith("startPeriod=2023")


def test_growth_against_the_year_before():
    table = pd.DataFrame({"period": ["2024", "2025"], "value": [19598.28, 19967.59]})
    assert growth(table) == {"from": "2024", "percent": 1.9}
    assert growth(table.iloc[:1]) is None


def test_dollar_amounts_and_years_on_the_page():
    data = {"unit_prefix": "US$ ", "unit": ""}
    assert build.amount(19967.59, "pt", data) == "US$ 19.968"
    assert build.amount(19967.59, "en", data) == "US$ 19,968"
    assert build.amount(4.58, "pt", {"unit_prefix": "", "unit": "%"}) == "4,58%"
    assert build.period_short("2025", "pt", "year") == "2025"
    assert build.period_long("2025", "en", "year") == "2025"


def test_gdp_page_builds_with_dollars_and_growth(tmp_path):
    build.main(tmp_path)
    page = (tmp_path / "pt" / "economia" / "pib-per-capita" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "US$" in page and "a mais do que no ano anterior" in page
    assert "Sem meta" not in page
    # Yearly data says so: "ano de 2025" next to the number, "Ano" over the table.
    assert "Brasil agora · ano de" in page and '<th scope="col">Ano</th>' in page
    en = (tmp_path / "en" / "economy" / "gdp-per-capita" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "more than the year before" in en and '<th scope="col">Year</th>' in en


def test_peers_carry_a_short_name_for_phones(tmp_path):
    build.main(tmp_path)
    data = json.loads(
        (tmp_path / "data" / "pt" / "pib-per-capita.json").read_text("utf-8")
    )
    short = {peer["geo"]: peer["short_name"] for peer in data["peers"]}
    assert short["G110"] == "Avançadas"
    assert short["MEX"] == "México"  # no short name given: the full name
