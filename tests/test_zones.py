from pathlib import Path

import pandas as pd
import pytest

from pipeline.models import Zones, load_indicator_targets
from pipeline.zones import (
    band_zones,
    change_from_year_before_zones,
    classify,
    classify_change,
)

TARGETS = Path(__file__).parents[1] / "data" / "targets" / "meta-inflacao.csv"
ZONES = Zones(
    rule="band", target="meta-inflacao", yellow_margin=1.5, basis="official_target"
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (3.0, "green"),
        (4.5, "green"),
        (4.51, "yellow"),
        (6.0, "yellow"),
        (6.01, "red"),
        (1.5, "green"),
        (1.49, "yellow"),
        (0.0, "yellow"),
        (-0.01, "red"),
    ],
)
def test_classify_edges_for_today_target(value, expected):
    assert classify(value, lower=1.5, upper=4.5, margin=1.5) == expected


def zones_for(values: dict[str, float]) -> pd.DataFrame:
    frame = pd.DataFrame({"period": list(values), "value": list(values.values())})
    result = band_zones(frame, load_indicator_targets(TARGETS), ZONES)
    return result.set_index("period")


def test_no_zone_before_targets_existed():
    result = zones_for({"1998-12": 1.65, "1999-01": 1.71})
    assert pd.isna(result.loc["1998-12", "zone"])
    assert result.loc["1999-01", "zone"] == "red"


def test_each_month_uses_the_target_valid_at_that_time():
    result = zones_for({"2015-12": 10.67, "2026-09": 4.58})
    assert (result.loc["2015-12", "lower"], result.loc["2015-12", "upper"]) == (
        2.5,
        6.5,
    )
    assert result.loc["2015-12", "zone"] == "red"
    assert (result.loc["2026-09", "lower"], result.loc["2026-09", "upper"]) == (
        1.5,
        4.5,
    )
    assert result.loc["2026-09", "zone"] == "yellow"


def test_revised_target_replaces_the_original():
    result = zones_for({"2003-06": 6.0})
    assert result.loc["2003-06", "target"] == 4.0
    assert result.loc["2003-06", "zone"] == "green"


UNEMPLOYMENT = Zones(
    rule="change_from_year_before",
    basis="brasilfacil_rule",
    green_below=0.2,
    red_from=0.5,
    citation="Sahm (2019), adapted",
    checked_on="2026-10-21",
)


@pytest.mark.parametrize(
    ("change", "expected"),
    [(-0.3, "green"), (0.19, "green"), (0.2, "yellow"), (0.49, "yellow"), (0.5, "red")],
)
def test_classify_change_edges(change, expected):
    assert classify_change(change, green_below=0.2, red_from=0.5) == expected


def test_change_from_year_before_compares_same_months():
    frame = pd.DataFrame(
        {
            "period": ["2025-03", "2025-08", "2026-03", "2026-08"],
            "value": [7.0, 5.6, 7.1, 5.3],
        }
    )
    result = change_from_year_before_zones(frame, UNEMPLOYMENT).set_index("period")
    assert pd.isna(result.loc["2025-03", "zone"])
    assert result.loc["2026-03", "change"] == pytest.approx(0.1)
    assert result.loc["2026-03", "zone"] == "green"
    assert result.loc["2026-08", "change"] == pytest.approx(-0.3)


def test_zones_rule_needs_its_own_fields():
    with pytest.raises(ValueError, match="needs: green_below"):
        Zones(rule="change_from_year_before", basis="brasilfacil_rule", red_from=0.5)
    with pytest.raises(ValueError, match="needs: target"):
        Zones(rule="band", basis="official_target", yellow_margin=1.5)
