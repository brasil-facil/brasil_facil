from pathlib import Path
from typing import Literal

import pandas as pd

from pipeline import store
from pipeline.models import Indicator, SeriesRef, load_indicator_targets
from pipeline.transforms import real_rate
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
    values = current_table(indicator, series_dir)
    if indicator.zones is None:
        return values.assign(target=None, lower=None, upper=None, zone=None)
    targets = (
        []
        if indicator.zones.target is None
        else load_indicator_targets(targets_dir / f"{indicator.zones.target}.csv")
    )
    return compute_zones(values, targets, indicator.zones)


def current_table(
    indicator: Indicator, series_dir: Path = store.SERIES_DIR
) -> pd.DataFrame:
    if indicator.transform == "real_rate":
        inputs = indicator.series.inputs
        return real_rate(
            stored_values(inputs["selic"], series_dir),
            stored_values(inputs["expected_inflation"], series_dir),
        )
    return stored_values(indicator.series.brazil, series_dir)


def stored_values(ref: SeriesRef, series_dir: Path = store.SERIES_DIR) -> pd.DataFrame:
    path = store.series_path(ref.series_id, series_dir)
    return store.current_values(store.read_history(path)).reset_index()


def compare_line(
    indicator: Indicator,
    others: dict[str, Indicator],
    lang: Lang,
    series_dir: Path = store.SERIES_DIR,
) -> dict | None:
    compare = indicator.chart.compare_with
    if compare is None:
        return None
    if compare.indicator not in others:
        raise ValueError(
            f"{indicator.id}: compare_with names unknown indicator '{compare.indicator}'"
        )
    table = visible(
        current_table(others[compare.indicator], series_dir), indicator.chart.show_from
    )
    own_latest = current_table(indicator, series_dir)["period"].iloc[-1]
    same_month = table.loc[table["period"] == own_latest, "value"]
    return {
        "label": getattr(compare.label, lang),
        "latest": float(same_month.iloc[0]) if len(same_month) else None,
        "points": [
            [period, float(value)]
            for period, value in zip(table["period"], table["value"])
        ],
    }


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
    others: dict[str, Indicator] | None = None,
) -> dict:
    table = visible(
        zone_table(indicator, series_dir, targets_dir), indicator.chart.show_from
    )
    last = table.iloc[-1]
    zones = indicator.zones
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
            "change": (
                None
                if "change" not in table or pd.isna(last["change"])
                else round(float(last["change"]), 2)
            ),
        },
        "period_kind": indicator.period_kind,
        "points": [
            [period, float(value)]
            for period, value in zip(table["period"], table["value"])
        ],
        "bands": bands(table),
        "margin": None if zones is None else zones.yellow_margin,
        "basis": None if zones is None else zones.basis,
        "citation": None if zones is None else zones.citation,
        "compare": compare_line(indicator, others or {}, lang, series_dir),
        "chart": {
            "default_years": DEFAULT_YEARS,
            "windows": WINDOWS_YEARS,
            "no_target_pill": indicator.chart.no_target_pill,
        },
        "source": {
            "name": indicator.source.name,
            "table": indicator.source.table,
            "url": str(indicator.source.url),
        },
    }
