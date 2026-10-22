import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

import build
from pipeline.export import chart_data, compare_line
from pipeline.models import load_indicator
from pipeline.run import load_all_indicators
from pipeline.sources import sidra
from pipeline.transforms import real_value

CONFIG = Path(__file__).parents[1] / "config" / "economia" / "renda.yaml"


def test_sidra_url_with_one_classification_category():
    url = sidra.build_url("7536-v10841-c1043-49304", "BRA", "all")
    assert url.endswith("/t/7536/n1/all/v/10841/p/all/c1043/49304?formato=json")
    plain = sidra.build_url("1736-v2289", "BRA", "all")
    assert plain.endswith("/t/1736/n1/all/v/2289/p/all?formato=json")


def test_sidra_keeps_yearly_periods_as_years():
    header = {"D3C": "Ano (Código)", "V": "Valor"}
    rows = [header, {"D3C": "2024", "V": "1991"}, {"D3C": "2025", "V": "2037"}]
    with tempfile.TemporaryDirectory() as folder:
        file = Path(folder) / "t.json"
        file.write_text(json.dumps(rows), encoding="utf-8")
        table = sidra.parse([file], "sidra.7536-v10841-c1043-49304.BRA")
    assert list(table["period"]) == ["2024", "2025"]


def test_yearly_amounts_use_the_year_average_and_the_latest_month():
    months = [f"2024-{m:02d}" for m in range(1, 13)] + ["2025-01"]
    index = pd.DataFrame({"period": months, "value": [100.0] * 12 + [110.0]})
    nominal = pd.DataFrame({"period": ["2024", "2025"], "value": [2000.0, 2100.0]})
    table = real_value(nominal, index)
    # 2024: average index 100, latest month 110 -> x 1.1. 2025 is not complete.
    assert list(table["period"]) == ["2024"]
    assert table["value"].iloc[0] == pytest.approx(2200.0)


def test_monthly_comparison_line_covers_only_the_charts_years():
    indicators = {i.id: i for i in load_all_indicators()}
    line = compare_line(indicators["renda"], indicators, "pt")
    periods = [period for period, _ in line["points"]]
    assert periods[0] == "2012-01" and periods[-1] == "2025-12"
    assert line["latest"] is None  # "2025" is not a month: no "same month" link


def test_fan_chart_data_and_page(tmp_path):
    data = chart_data(
        load_indicator(CONFIG), "pt", others={i.id: i for i in load_all_indicators()}
    )
    assert data["chart"]["kind"] == "fan"
    lower, upper = dict(data["band"]["lower"]), dict(data["band"]["upper"])
    for period, median in data["points"]:
        assert lower[period] < median < upper[period]
    build.main(tmp_path)
    json_file = tmp_path / "data" / "pt" / "renda.json"
    labels = json.loads(json_file.read_text("utf-8"))["fan_labels"]
    assert labels["median"] == "Metade ganha menos de"
    page = (tmp_path / "pt" / "economia" / "renda" / "index.html").read_text("utf-8")
    assert '<th scope="col">10% ganham menos de</th>' in page
    assert "metade das pessoas que trabalham ganhava menos de R$" in page
