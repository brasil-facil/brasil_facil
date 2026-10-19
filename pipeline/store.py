from pathlib import Path

import pandas as pd

SERIES_DIR = Path(__file__).resolve().parents[1] / "data" / "series"
COLUMNS = ["period", "value", "retrieved_at"]


def series_path(series_id: str, series_dir: Path = SERIES_DIR) -> Path:
    source, rest = series_id.split(".", 1)
    code, geo = rest.rsplit(".", 1)
    return series_dir / source / f"{code}__{geo}.csv"


def read_history(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(path, dtype={"period": str, "retrieved_at": str})


def current_values(history: pd.DataFrame) -> pd.Series:
    latest = history.sort_values(["period", "retrieved_at"]).drop_duplicates(
        "period", keep="last"
    )
    return latest.set_index("period")["value"]


def merge(
    history: pd.DataFrame, parsed: pd.DataFrame, retrieved_at: str
) -> tuple[pd.DataFrame, int, int]:
    known = parsed["period"].map(current_values(history))
    is_new = known.isna()
    is_revised = ~is_new & (parsed["value"] != known)
    changed = parsed[is_new | is_revised]
    added = pd.DataFrame(
        {
            "period": changed["period"],
            "value": changed["value"],
            "retrieved_at": retrieved_at,
        }
    )
    merged = added if history.empty else pd.concat([history, added])
    return merged.reset_index(drop=True), int(is_new.sum()), int(is_revised.sum())


def save(history: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = history.sort_values(["period", "retrieved_at"], kind="stable")
    ordered.to_csv(path, index=False, columns=COLUMNS, lineterminator="\n")


def update_series(
    series_id: str,
    parsed: pd.DataFrame,
    retrieved_at: str,
    series_dir: Path = SERIES_DIR,
) -> tuple[int, int]:
    path = series_path(series_id, series_dir)
    history, new, revised = merge(read_history(path), parsed, retrieved_at)
    if new or revised:
        save(history, path)
    return new, revised
