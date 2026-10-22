import json
from pathlib import Path

import pytest

from pipeline import store
from pipeline.export import chart_data
from pipeline.models import load_indicator
from pipeline.sources.sidra import parse

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "sidra_1737-v2265.json"
INDICATOR = load_indicator(ROOT / "config" / "economia" / "inflacao.yaml")


@pytest.fixture
def series_dir(tmp_path: Path) -> Path:
    sid = INDICATOR.series.brazil.series_id
    store.update_series(sid, parse([FIXTURE], sid), "2026-10-19", tmp_path)
    return tmp_path


def test_title_follows_the_language(series_dir):
    assert chart_data(INDICATOR, "pt", series_dir)["title"] == INDICATOR.name.pt
    assert chart_data(INDICATOR, "en", series_dir)["title"] == INDICATOR.name.en


def test_latest_is_september_2026_yellow(series_dir):
    latest = chart_data(INDICATOR, "pt", series_dir)["latest"]
    assert latest == {
        "period": "2026-09",
        "value": 4.58,
        "zone": "yellow",
        "zone_since": "2026-09",
        "lower": 1.5,
        "upper": 4.5,
        "change": None,
        "reference": None,  # only for the vs_peer_average rule
    }


def test_points_start_at_show_from(series_dir):
    points = chart_data(INDICATOR, "pt", series_dir)["points"]
    assert points[0] == ["1995-06", 33.03]
    assert points[-1] == ["2026-09", 4.58]
    assert len(points) == 376


def test_bands_follow_the_target_history(series_dir):
    bands = chart_data(INDICATOR, "pt", series_dir)["bands"]
    assert bands[0] == {"from": "1999-01", "to": "1999-12", "lower": 6.0, "upper": 10.0}
    assert {"from": "2006-01", "to": "2016-12", "lower": 2.5, "upper": 6.5} in bands
    assert bands[-1] == {"from": "2024-01", "to": "2026-09", "lower": 1.5, "upper": 4.5}


def test_output_is_valid_json(series_dir):
    data = chart_data(INDICATOR, "en", series_dir)
    assert data["unit"] == "%"
    json.dumps(data, allow_nan=False)


def test_indicator_without_zones_has_no_colour(series_dir):
    no_zones = INDICATOR.model_copy(update={"zones": None})
    data = chart_data(no_zones, "pt", series_dir)
    assert data["latest"]["zone"] is None
    assert data["latest"]["lower"] is None
    assert data["bands"] == []
    assert data["margin"] is None
    json.dumps(data, allow_nan=False)


def test_compare_line_uses_the_other_indicator(series_dir):
    inpc = load_indicator(ROOT / "config" / "economia" / "inpc.yaml")
    sid = inpc.series.brazil.series_id
    store.update_series(sid, parse([FIXTURE], sid), "2026-10-19", series_dir)
    data = chart_data(inpc, "en", series_dir, others={"inflacao": INDICATOR})
    assert data["compare"]["label"] == "IPCA"
    assert data["compare"]["points"][0] == ["1995-06", 33.03]
    assert data["compare"]["latest"] == 4.58


def test_compare_with_unknown_indicator_fails(series_dir):
    inpc = load_indicator(ROOT / "config" / "economia" / "inpc.yaml")
    sid = inpc.series.brazil.series_id
    store.update_series(sid, parse([FIXTURE], sid), "2026-10-19", series_dir)
    with pytest.raises(ValueError, match="unknown indicator"):
        chart_data(inpc, "pt", series_dir, others={})
