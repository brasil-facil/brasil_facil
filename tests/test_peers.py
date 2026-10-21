from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pipeline import store
from pipeline.export import peer_lines
from pipeline.models import PeerGroup, load_countries, load_indicator
from pipeline.sources import bis, imf, oecd, sdmx
from pipeline.sources.sidra import parse as sidra_parse

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
TODAY = date(2026, 10, 21)
COUNTRIES = load_countries(ROOT / "config" / "countries.yaml")


def test_imf_periods_like_2026_m09_become_2026_09():
    df = imf.parse([FIXTURES / "imf_cpi-yoy_MEX.csv"], "imf.cpi-yoy.MEX")
    assert list(df["period"]) == ["2026-06", "2026-07", "2026-08", "2026-09"]
    assert df["value"].iloc[-1] == pytest.approx(3.4547, abs=1e-4)


def test_oecd_rows_out_of_order_are_sorted():
    # The OECD sends its rows out of date order; the latest is not the last row.
    df = oecd.parse([FIXTURES / "oecd_cpi-yoy_OECD.csv"], "oecd.cpi-yoy.OECD")
    assert list(df["period"]) == ["2026-05", "2026-06", "2026-07", "2026-08"]
    assert df["value"].iloc[-1] == pytest.approx(4.267103)


def test_bis_policy_rate():
    df = bis.parse([FIXTURES / "bis_policy-rate_MEX.csv"], "bis.policy-rate.MEX")
    assert df["period"].iloc[0] == "2026-06"
    assert df["value"].notna().all()


def test_no_files_means_an_empty_table():
    df = sdmx.parse_csv([], "imf.cpi-yoy.MEX")
    assert df.empty and list(df.columns) == ["series_id", "period", "value"]


def test_urls():
    assert imf.build_url("cpi-yoy", "MEX", imf.RECENT_PERIODS, TODAY).endswith(
        "/IMF.STA,CPI/MEX.CPI._T.YOY_PCH_PA_PT.M?startPeriod=2026-02&detail=dataonly"
    )
    assert "/OECD.M.N.CPI.PA._T.N.GY?startPeriod=1990-01" in oecd.build_url(
        "cpi-yoy", "OECD", oecd.FULL_PERIODS, TODAY
    )
    assert "/WS_CBPOL/1.0/M.MX?" in bis.build_url(
        "policy-rate", "MEX", bis.FULL_PERIODS, TODAY
    )
    with pytest.raises(ValueError, match="unknown geo"):
        bis.build_url("policy-rate", "ARG", bis.FULL_PERIODS, TODAY)


def test_peer_group_expands_to_one_series_per_country():
    group = PeerGroup(
        source="imf", code="cpi-yoy", geo=["MEX", "COL"], source_name="FMI"
    )
    assert [ref.series_id for ref in group.refs()] == [
        "imf.cpi-yoy.MEX",
        "imf.cpi-yoy.COL",
    ]


def test_countries_file():
    assert COUNTRIES["OECD"].role == "reference"
    assert [code for code, c in COUNTRIES.items() if c.default_on] == ["MEX", "COL"]


def test_peer_lines_order_defaults_and_start(tmp_path):
    indicator = load_indicator(ROOT / "config" / "economia" / "inflacao.yaml")
    sid = indicator.series.brazil.series_id
    store.update_series(
        sid,
        sidra_parse([FIXTURES / "sidra_1737-v2265.json"], sid),
        "2026-10-21",
        tmp_path,
    )
    peer = pd.DataFrame({"period": ["1990-01", "2026-09"], "value": [20.0, 3.45]})
    for geo in ["USA", "MEX", "OECD"]:  # stored in a different order on purpose
        source = "oecd" if geo == "OECD" else "imf"
        store.update_series(f"{source}.cpi-yoy.{geo}", peer, "2026-10-21", tmp_path)

    lines = peer_lines(indicator, COUNTRIES, "pt", tmp_path)
    assert [line["geo"] for line in lines] == [
        "OECD",
        "MEX",
        "USA",
    ]  # countries.yaml order
    assert [line["default_on"] for line in lines] == [True, True, False]
    # Peers start where Brazil's line starts (show_from 1995-06), not in 1990.
    assert all(line["points"][0][0] == "2026-09" for line in lines)
    assert lines[1]["name"] == "México" and lines[1]["source"] == "FMI"


def test_unknown_country_fails(tmp_path):
    indicator = load_indicator(ROOT / "config" / "economia" / "inflacao.yaml")
    sid = indicator.series.brazil.series_id
    store.update_series(
        sid,
        sidra_parse([FIXTURES / "sidra_1737-v2265.json"], sid),
        "2026-10-21",
        tmp_path,
    )
    with pytest.raises(ValueError, match="not in countries.yaml"):
        peer_lines(indicator, {}, "pt", tmp_path)
