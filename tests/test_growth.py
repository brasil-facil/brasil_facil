from datetime import date
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import pytest

import build
from pipeline import store
from pipeline.export import chart_data, forecast_points, peer_average
from pipeline.models import Zones, load_indicator
from pipeline.sources import focus, imf, sdmx
from pipeline.zones import classify_vs_peers, vs_peer_average_zones

CONFIG = Path(__file__).parents[1] / "config" / "economia" / "crescimento.yaml"


@pytest.mark.parametrize(
    ("value", "average", "expected"),
    [
        (3.0, 2.0, "green"),
        (2.0, 2.0, "yellow"),  # the same as the others is not "more than"
        (1.0, 2.0, "yellow"),
        (0.0, 2.0, "yellow"),  # zero: did not shrink
        (-0.1, -2.2, "red"),  # shrank, even if less than the others (2009)
        (-3.3, None, "red"),  # shrank: red even without an average
        (2.0, None, None),  # no average that year: no colour
    ],
)
def test_classify_vs_peers(value, average, expected):
    assert classify_vs_peers(value, average) == expected


def test_each_year_uses_that_years_average():
    values = pd.DataFrame(
        {"period": ["2019", "2020", "2025"], "value": [1.2, -3.3, 2.3]}
    )
    average = pd.DataFrame(
        {"period": ["2019", "2020", "2025"], "value": [1.0, -7.2, 1.4]}
    )
    result = vs_peer_average_zones(values, average).set_index("period")
    assert list(result["zone"]) == ["green", "red", "green"]
    assert result.loc["2025", "reference"] == pytest.approx(1.4)


def test_rule_needs_its_peers():
    with pytest.raises(ValueError, match="needs: peers"):
        Zones(rule="vs_peer_average", basis="brasilfacil_rule", checked_on="2026-10-22")


def save(series_dir: Path, geo: str, rows: dict[str, float]) -> None:
    table = pd.DataFrame(
        {
            "series_id": f"imf.gdp-growth.{geo}",
            "period": list(rows),
            "value": list(rows.values()),
        }
    )
    store.update_series(f"imf.gdp-growth.{geo}", table, "2026-10-22", series_dir)


def test_average_only_for_years_where_every_country_has_data(tmp_path):
    save(tmp_path, "MEX", {"2024": 1.5, "2025": 0.5})
    save(tmp_path, "COL", {"2024": 1.5, "2025": 2.6})
    save(tmp_path, "ZAF", {"2024": 0.6})  # 2025 not published yet
    average = peer_average(load_indicator(CONFIG), ["MEX", "COL", "ZAF"], tmp_path)
    assert list(average["period"]) == ["2024"]
    assert average["value"].iloc[0] == pytest.approx(1.2)


def test_growth_page_shows_the_average_and_no_growth_of_growth(tmp_path):
    indicator = load_indicator(CONFIG)
    data = chart_data(indicator, "pt")
    assert data["latest"]["zone"] in {"green", "yellow", "red"}
    assert data["latest"]["reference"] is not None
    assert data["growth"] is None  # a growth rate has no "x% more than last year"
    build.main(tmp_path)
    page = (tmp_path / "pt" / "economia" / "crescimento" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "Média de México, Colômbia e África do Sul no mesmo ano" in page
    assert "a média de México, Colômbia e África do Sul no mesmo ano" in page
    en = (tmp_path / "en" / "economy" / "growth" / "index.html").read_text("utf-8")
    assert "Average of Mexico, Colombia and South Africa in the same year" in en


FIXTURES = Path(__file__).parent / "fixtures"


def test_forecast_keeps_only_the_years_after_the_actual_ones():
    # Same file as the actual data: 2023-2025 actual, 2026-2028 projections.
    actual = imf.parse([FIXTURES / "imf_gdp-pc-ppp_BRA.csv"], "imf.gdp-growth.BRA")
    forecast = imf.parse(
        [FIXTURES / "imf_gdp-pc-ppp_BRA.csv"], "imf.gdp-growth-forecast.BRA"
    )
    assert list(actual["period"]) == ["2023", "2024", "2025"]
    assert list(forecast["period"]) == ["2026", "2027", "2028"]


def test_groups_without_the_marker_forecast_from_this_year():
    forecast = sdmx.parse_csv(
        [FIXTURES / "imf_gdp-pc-ppp_G110.csv"],
        "imf.gdp-growth-forecast.G110",
        today=date(2026, 10, 22),
        projections=True,
    )
    assert forecast["period"].iloc[0] == "2026"


def test_chart_shows_two_forecast_years_after_the_last_result(tmp_path):
    save(tmp_path, "BRA", {"2024": 3.4, "2025": 2.3})
    forecast = {"2025": 2.4, "2026": 2.2, "2027": 1.9, "2028": 2.4}
    table = pd.DataFrame(
        {
            "series_id": "imf.gdp-growth-forecast.BRA",
            "period": list(forecast),
            "value": list(forecast.values()),
        }
    )
    store.update_series("imf.gdp-growth-forecast.BRA", table, "2026-10-22", tmp_path)
    points = forecast_points(load_indicator(CONFIG), "2025", tmp_path)
    assert points == [["2026", 2.2], ["2027", 1.9]]


def test_forecast_sentence_in_both_languages():
    data = {
        "forecast": [["2026", 2.18], ["2027", 1.86]],
        "unit_prefix": "",
        "unit": "%",
    }
    pt = build.forecast_text(data, {"forecast": "Previsão do FMI: {items}"}, "pt")
    assert pt == "Previsão do FMI: 2,18% em 2026 e 1,86% em 2027"
    en = build.forecast_text(data, {"forecast": "IMF forecast: {items}"}, "en")
    assert en == "IMF forecast: 2.18% in 2026 and 1.86% in 2027"
    assert build.forecast_text({"forecast": None}, {}, "pt") is None


def test_focus_january_keeps_the_first_survey_about_its_own_year():
    rows = [
        {"Data": "2024-12-30", "DataReferencia": "2025", "Mediana": 1.9},  # December
        {"Data": "2025-01-02", "DataReferencia": "2024", "Mediana": 3.49},  # past year
        {"Data": "2025-01-02", "DataReferencia": "2025", "Mediana": 2.0155},
        {"Data": "2025-01-02", "DataReferencia": "2026", "Mediana": 1.8},  # next year
        {"Data": "2025-01-03", "DataReferencia": "2025", "Mediana": 2.02},  # later day
        {"Data": "2025-02-03", "DataReferencia": "2025", "Mediana": 2.1},  # February
    ]
    table = focus.parse_january(rows, "focus.pib-janeiro.BRA")
    assert list(table["period"]) == ["2025"]
    assert table["value"].iloc[0] == pytest.approx(2.0155)


def test_focus_january_url_asks_for_this_years_surveys():
    url = unquote(
        focus.build_url("pib-janeiro", focus.RECENT_PERIODS, date(2026, 10, 22))
    )
    assert "ExpectativasMercadoAnuais" in url
    assert "Indicador eq 'PIB Total'" in url and "Suavizada" not in url
    assert "Data ge '2026-01-01'" in url and "DataReferencia" in url


def test_bar_chart_data_has_a_colour_per_year_and_the_expectations():
    data = chart_data(load_indicator(CONFIG), "pt")
    assert data["chart"]["kind"] == "bar"
    assert len(data["point_zones"]) == len(data["points"])
    assert set(data["point_zones"]) <= {"green", "yellow", "red", None}
    expected = dict(data["expected"])
    assert expected["2020"] == pytest.approx(2.3)  # before the pandemic
    assert data["points"][0][0] <= min(expected)  # only years the chart shows


def test_expected_sentence_for_the_latest_year():
    data = {
        "latest": {"period": "2025"},
        "expected": [["2024", 1.55], ["2025", 2.0155]],
        "unit_prefix": "",
        "unit": "%",
    }
    s = {"expected": "Em janeiro de {year}, os economistas esperavam {value}"}
    assert build.expected_text(data, s, "pt") == (
        "Em janeiro de 2025, os economistas esperavam 2,02%"
    )
    assert build.expected_text({**data, "expected": None}, s, "pt") is None
