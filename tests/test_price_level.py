import json
from datetime import date
from pathlib import Path

import pytest

import build
from pipeline.export import chart_data
from pipeline.models import load_indicator
from pipeline.sources import worldbank

CONFIG = Path(__file__).parents[1] / "config" / "economia" / "nivel-de-precos.yaml"


def answer(tmp_path, geo, indicator, values):
    """A World Bank answer: [page info, one row per year]."""
    rows = [{"date": year, "value": value} for year, value in values.items()]
    file = tmp_path / f"price-level__{geo}__{indicator}.json"
    file.write_text(json.dumps([{"page": 1}, rows]), encoding="utf-8")
    return file


def test_price_level_is_ppp_over_exchange_rate(tmp_path):
    files = [
        answer(
            tmp_path, "BRA", worldbank.PPP, {"2024": 2.52, "2025": 2.58, "2026": None}
        ),
        answer(tmp_path, "BRA", worldbank.EXCHANGE_RATE, {"2024": 5.39, "2025": 5.58}),
    ]
    table = worldbank.parse(files, "worldbank.price-level.BRA")
    assert list(table["period"]) == ["2024", "2025"]  # 2026 has no value yet
    assert table["value"].iloc[-1] == pytest.approx(46.2)


def test_euro_countries_convert_the_old_currency_before_1999(tmp_path):
    files = [
        answer(tmp_path, "FRA", worldbank.PPP, {"1995": 1.010, "2000": 0.935}),
        answer(
            tmp_path, "FRA", worldbank.EXCHANGE_RATE, {"1995": 4.991, "2000": 1.083}
        ),
    ]
    table = worldbank.parse(files, "worldbank.price-level.FRA").set_index("period")
    assert table.loc["1995", "value"] == pytest.approx(
        132.7, abs=0.1
    )  # francs -> euros
    assert table.loc["2000", "value"] == pytest.approx(86.3, abs=0.1)  # euros already


def test_world_bank_url_and_an_empty_answer(tmp_path):
    url = worldbank.build_url(
        worldbank.PPP, "BRA", worldbank.RECENT_PERIODS, date(2026, 10, 24)
    )
    assert url.endswith(
        "/country/BRA/indicator/PA.NUS.PRVT.PP?format=json&per_page=1000&date=2021:2026"
    )
    error = tmp_path / "price-level__BRA__PA.NUS.FCRF.json"
    error.write_text(json.dumps([{"message": "not found"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="no data"):
        worldbank.read_values(error)


def test_price_level_page(tmp_path):
    data = chart_data(load_indicator(CONFIG), "pt")
    assert data["chart"]["reference_line"] == {"value": 100, "label": "EUA = 100"}
    assert data["points"][0][0] == "1995"
    assert {p["geo"] for p in data["peers"] if p["role"] == "reference"} == {
        "DEU",
        "FRA",
    }
    build.main(tmp_path)
    page = (tmp_path / "pt" / "economia" / "nivel-de-precos" / "index.html").read_text(
        "utf-8"
    )
    assert "custavam o equivalente a US$" in page and "Sem meta" not in page
