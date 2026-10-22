from datetime import date
from pathlib import Path

import build
from pipeline.export import chart_data
from pipeline.models import load_indicator
from pipeline.sources import imf

CONFIG = Path(__file__).parents[1] / "config" / "economia" / "conta-corrente.yaml"


def test_current_account_codes_split_results_and_forecasts():
    assert "current-account-forecast" in imf.PROJECTIONS
    assert "current-account" not in imf.PROJECTIONS
    url = imf.build_url("current-account", "BRA", imf.FULL_PERIODS, date(2026, 10, 22))
    assert "/IMF.RES,WEO/BRA.BCA_NGDPD.A?" in url


def test_current_account_page(tmp_path):
    data = chart_data(load_indicator(CONFIG), "pt")
    assert data["chart"]["kind"] == "bar"
    assert data["latest"]["zone"] is None  # no colours: no official target
    assert data["growth"] is None  # a % of GDP: no "x% more than a year earlier"
    assert len(data["forecast"]) == 2
    build.main(tmp_path)
    page = tmp_path / "pt" / "economia" / "conta-corrente" / "index.html"
    text = page.read_text(encoding="utf-8")
    assert "Previsão do FMI:" in text and "Sem meta" not in text
    en = tmp_path / "en" / "economy" / "current-account" / "index.html"
    assert "of GDP" in en.read_text(encoding="utf-8")
