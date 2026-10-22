from pathlib import Path

import pandas as pd
import pytest

import build
from pipeline.export import chart_data, growth, year_earlier
from pipeline.models import load_indicator
from pipeline.transforms import real_value

CONFIG = Path(__file__).parents[1] / "config" / "economia" / "salario-minimo.yaml"


def test_real_value_is_in_money_of_the_latest_month():
    nominal = pd.DataFrame({"period": ["1994-07", "2026-09"], "value": [64.79, 1621.0]})
    index = pd.DataFrame(
        {
            "period": ["1994-07", "2026-09", "2026-10"],
            "value": [925.72, 7874.13, 7900.0],
        }
    )
    table = real_value(nominal, index).set_index("period")["value"]
    assert table["1994-07"] == pytest.approx(551.1, abs=0.1)  # 64.79 x 7874.13 / 925.72
    assert table["2026-09"] == 1621.0  # the latest month: the official value
    assert "2026-10" not in table  # no minimum wage that month: left out


def test_growth_compares_with_the_same_month_a_year_earlier():
    assert year_earlier("2026-09") == "2025-09"
    assert year_earlier("2025") == "2024"
    table = pd.DataFrame(
        {
            "period": ["2025-08", "2025-09", "2026-08", "2026-09"],
            "value": [1500.0, 1510.0, 1600.0, 1585.5],
        }
    )
    assert growth(table) == {"from": "2025-09", "percent": 5.0}
    assert growth(table.iloc[2:]) is None  # no September 2025


def test_money_has_no_decimals():
    data = {"unit_prefix": "R$ ", "unit": ""}
    assert build.amount(551.1, "pt", data) == "R$ 551"
    assert build.amount(1621.0, "pt", data) == "R$ 1.621"
    assert build.amount(4.58, "pt", {"unit_prefix": "", "unit": "%"}) == "4,58%"


def test_minimum_wage_page(tmp_path):
    data = chart_data(load_indicator(CONFIG), "pt")
    assert data["points"][0][0] == "1994-07"  # starts with the real
    assert data["latest"]["zone"] is None and data["growth"] is not None
    build.main(tmp_path)
    page = (tmp_path / "pt" / "economia" / "salario-minimo" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "R$" in page and "um ano antes" in page and "Sem meta" not in page
    en = tmp_path / "en" / "economy" / "minimum-wage" / "index.html"
    assert "a month" in en.read_text(encoding="utf-8")
