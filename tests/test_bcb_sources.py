from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pipeline.models import IndicatorSeries, SeriesRef
from pipeline.sources import focus, sgs
from pipeline.transforms import real_rate

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 21)


def test_sgs_keeps_the_value_in_force_at_month_end():
    df = sgs.parse([FIXTURES / "sgs_432.json"], "sgs.432.BRA", today=TODAY)
    assert list(df.columns) == ["series_id", "period", "value"]
    # The Copom cut the rate from 14.00 to 13.75 on 17 Sep 2026.
    assert df.set_index("period")["value"].to_dict() == {
        "2026-08": 14.0,
        "2026-09": 13.75,
        "2026-10": 13.75,
    }


def test_sgs_drops_dates_after_today():
    # Series 432 lists the current rate up to the next Copom meeting (November).
    df = sgs.parse([FIXTURES / "sgs_432.json"], "sgs.432.BRA", today=TODAY)
    assert "2026-11" not in set(df["period"])


def test_sgs_full_history_is_split_into_ten_year_windows():
    windows = sgs.windows(sgs.FULL_PERIODS, TODAY)
    assert windows[0] == (date(1986, 1, 1), date(1995, 12, 31))
    assert windows[-1][1] == TODAY
    assert all((end - start).days < 3653 for start, end in windows)


def test_sgs_build_url_uses_brazilian_dates():
    url = sgs.build_url("432", date(1999, 3, 5), date(2008, 12, 31))
    assert url.endswith("dataInicial=05/03/1999&dataFinal=31/12/2008")


def test_sgs_html_error_page_gives_a_clear_error(tmp_path):
    page = tmp_path / "blocked.json"
    page.write_text("<html>Requisição inválida!</html>", encoding="utf-8")
    with pytest.raises(ValueError, match="did not return JSON"):
        sgs.parse([page], "sgs.432.BRA", today=TODAY)


def test_focus_keeps_the_last_survey_of_each_month():
    df = focus.parse([FIXTURES / "focus_ipca-12m.json"], "focus.ipca-12m.BRA")
    values = df.set_index("period")["value"]
    assert list(values.index) == ["2026-08", "2026-09", "2026-10"]
    assert values["2026-10"] == 4.5146


def test_focus_rejects_unknown_codes():
    with pytest.raises(ValueError, match="unknown code"):
        focus.build_url("pib-12m", focus.FULL_PERIODS, TODAY)


def test_real_rate():
    selic = pd.DataFrame({"period": ["2026-09", "2026-10"], "value": [13.75, 13.75]})
    expected = pd.DataFrame({"period": ["2026-10"], "value": [4.5146]})
    result = real_rate(selic, expected)
    assert list(result["period"]) == ["2026-10"]  # only months in both series
    assert result["value"].iloc[0] == pytest.approx(8.84, abs=0.01)


def test_series_needs_brazil_or_inputs():
    ref = SeriesRef(source="sgs", code="432", geo="BRA")
    with pytest.raises(ValueError, match="either 'brazil' or 'inputs'"):
        IndicatorSeries()
    with pytest.raises(ValueError, match="either 'brazil' or 'inputs'"):
        IndicatorSeries(brazil=ref, inputs={"selic": ref})
    assert IndicatorSeries(inputs={"selic": ref}).all_refs() == [ref]
