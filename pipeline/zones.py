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


def compute_zones(
    values: pd.DataFrame, rows: list[IndicatorTargetRow], zones: Zones
) -> pd.DataFrame:
    if zones.rule == "band":
        return band_zones(values, rows, zones)
    raise NotImplementedError(f"zone rule '{zones.rule}' is not built yet")
