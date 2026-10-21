import pandas as pd

from pipeline.models import IndicatorTargetRow, Zones


def classify(value: float, lower: float, upper: float, margin: float) -> str:
    if lower <= value <= upper:
        return "green"
    if lower - margin <= value <= upper + margin:
        return "yellow"
    return "red"


def targets_table(rows: list[IndicatorTargetRow]) -> pd.DataFrame:
    table = pd.DataFrame(
        {
            "valid_from": [row.valid_from for row in rows],
            "decided_on": [row.decided_on for row in rows],
            "target": [row.target for row in rows],
            "lower": [row.lower for row in rows],
            "upper": [row.upper for row in rows],
        }
    )
    current = table.sort_values(["valid_from", "decided_on"]).drop_duplicates(
        "valid_from", keep="last"
    )
    current["valid_from"] = pd.to_datetime(current["valid_from"]).astype(
        "datetime64[ns]"
    )
    return current.drop(columns="decided_on").reset_index(drop=True)


def band_zones(
    values: pd.DataFrame, rows: list[IndicatorTargetRow], zones: Zones
) -> pd.DataFrame:
    frame = values[["period", "value"]].copy()
    frame["month"] = pd.to_datetime(frame["period"] + "-01").astype("datetime64[ns]")
    frame = frame.sort_values("month")
    joined = pd.merge_asof(
        frame,
        targets_table(rows),
        left_on="month",
        right_on="valid_from",
        direction="backward",
    )
    joined["zone"] = [
        None if pd.isna(lower) else classify(value, lower, upper, zones.yellow_margin)
        for value, lower, upper in zip(
            joined["value"], joined["lower"], joined["upper"]
        )
    ]
    return joined[["period", "value", "target", "lower", "upper", "zone"]]


def classify_change(change: float, green_below: float, red_from: float) -> str:
    if change < green_below:
        return "green"
    if change < red_from:
        return "yellow"
    return "red"


def year_before(period: str) -> str:
    year, month = period.split("-")
    return f"{int(year) - 1}-{month}"


def change_from_year_before_zones(values: pd.DataFrame, zones: Zones) -> pd.DataFrame:
    """Colour by how much the rate moved since the same months a year earlier.

    Comparing March with March cancels out the seasons (in Brazil unemployment
    rises every January to March), which IBGE does not adjust for.
    """
    frame = values[["period", "value"]].sort_values("period").reset_index(drop=True)
    lookup = dict(zip(frame["period"], frame["value"]))
    frame["change"] = [
        value - lookup[year_before(period)] if year_before(period) in lookup else None
        for period, value in zip(frame["period"], frame["value"])
    ]
    frame["zone"] = [
        None
        if pd.isna(change)
        else classify_change(change, zones.green_below, zones.red_from)
        for change in frame["change"]
    ]
    return frame.assign(target=None, lower=None, upper=None)[
        ["period", "value", "target", "lower", "upper", "change", "zone"]
    ]


def compute_zones(
    values: pd.DataFrame, rows: list[IndicatorTargetRow], zones: Zones
) -> pd.DataFrame:
    if zones.rule == "band":
        return band_zones(values, rows, zones)
    if zones.rule == "change_from_year_before":
        return change_from_year_before_zones(values, zones)
    raise NotImplementedError(f"zone rule '{zones.rule}' is not built yet")
