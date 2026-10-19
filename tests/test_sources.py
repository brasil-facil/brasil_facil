from pathlib import Path

import pytest

from pipeline.sources.sidra import build_url, parse

FIXTURE = Path(__file__).parent / "fixtures" / "sidra_1737-v2265.json"
SERIES_ID = "sidra.1737-v2265.BRA"


def test_parse_returns_standard_columns():
    df = parse([FIXTURE], SERIES_ID)
    assert list(df.columns) == ["series_id", "period", "value"]


def test_parse_drops_missing_values():
    df = parse([FIXTURE], SERIES_ID)
    assert len(df) == 550
    assert df["value"].notna().all()


def test_parse_reads_known_values():
    df = parse([FIXTURE], SERIES_ID)
    first = df.iloc[0]
    last = df.iloc[-1]
    assert first["period"] == "1980-12"
    assert first["value"] == 99.25
    assert last["period"] == "2026-09"
    assert last["value"] == 4.58


def test_parse_periods_are_sorted_and_unique():
    df = parse([FIXTURE], SERIES_ID)
    periods = df["period"]
    assert periods.is_monotonic_increasing
    assert periods.is_unique
    assert periods.str.fullmatch(r"\d{4}-\d{2}").all()


def test_build_url_for_full_history():
    url = build_url("1737-v2265", "BRA", "all")
    assert url.startswith("https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2265/p/")
    assert "formato=json" in url


def test_build_url_rejects_unknown_geo():
    with pytest.raises(ValueError) as e:
        build_url(code="1737-v2265", geo="ARG", periods="all")
    assert "SIDRA: unknown geo 'ARG'" in str(e.value)
