from pathlib import Path
from typing import Literal

import pandas as pd

from pipeline import store
from pipeline.models import Indicator, load_indicator_targets
from pipeline.zones import compute_zones

TARGETS_DIR = Path(__file__).resolve().parents[1] / "data" / "targets"
UNIT_SYMBOLS = {"percent": "%"}
DEFAULT_YEARS = 30
WINDOWS_YEARS = [8, 15, 30]

Lang = Literal["pt", "en"]


def zone_table(
    indicator: Indicator,
    series_dir: Path = store.SERIES_DIR,
    targets_dir: Path = TARGETS_DIR,
) -> pd.DataFrame:
    path = store.series_path(indicator.series.brazil.series_id, series_dir)
    values = store.current_values(store.read_history(path)).reset_index()
    targets = load_indicator_targets(targets_dir / f"{indicator.zones.target}.csv")
    return compute_zones(values, targets, indicator.zones)


def zone_or_none(zone: object) -> str | None:
    return None if pd.isna(zone) else str(zone)


def visible(table: pd.DataFrame, show_from: str | None) -> pd.DataFrame:
    if show_from is None:
        return table.reset_index(drop=True)
    return table[table["period"] >= show_from].reset_index(drop=True)


def bands(table: pd.DataFrame) -> list[dict]:
    result: list[dict] = []
    for period, lower, upper in zip(table["period"], table["lower"], table["upper"]):
        if pd.isna(lower):
            continue
        if result and (result[-1]["lower"], result[-1]["upper"]) == (lower, upper):
            result[-1]["to"] = period
        else:
            result.append(
                {
                    "from": period,
                    "to": period,
                    "lower": float(lower),
                    "upper": float(upper),
                }
            )
    return result


def zone_since(table: pd.DataFrame) -> str:
    zones = table["zone"].tolist()
    start = len(zones) - 1
    while start > 0 and zones[start - 1] == zones[-1]:
        start -= 1
    return table["period"].iloc[start]


def chart_data(
    indicator: Indicator,
    lang: Lang,
    series_dir: Path = store.SERIES_DIR,
    targets_dir: Path = TARGETS_DIR,
) -> dict:
    table = visible(
        zone_table(indicator, series_dir, targets_dir), indicator.chart.show_from
    )
    last = table.iloc[-1]
    return {
        "id": indicator.id,
        "lang": lang,
        "title": getattr(indicator.name, lang),
        "unit": UNIT_SYMBOLS[indicator.unit],
        "latest": {
            "period": last["period"],
            "value": float(last["value"]),
            "zone": zone_or_none(last["zone"]),
            "zone_since": zone_since(table),
            "lower": None if pd.isna(last["lower"]) else float(last["lower"]),
            "upper": None if pd.isna(last["upper"]) else float(last["upper"]),
        },
        "points": [
            [period, float(value)]
            for period, value in zip(table["period"], table["value"])
        ],
        "bands": bands(table),
        "margin": indicator.zones.yellow_margin,
        "chart": {"default_years": DEFAULT_YEARS, "windows": WINDOWS_YEARS},
        "source": {
            "name": indicator.source.name,
            "table": indicator.source.table,
            "url": str(indicator.source.url),
        },
    }
