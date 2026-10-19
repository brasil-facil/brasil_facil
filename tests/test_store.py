from pathlib import Path

import pandas as pd

from pipeline.store import (
    COLUMNS,
    merge,
    read_history,
    series_path,
    update_series,
)

SERIES_ID = "sidra.1737-v2265.BRA"


def parsed_rows(values: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"series_id": SERIES_ID, "period": list(values), "value": list(values.values())}
    )


def empty_history() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def test_series_path():
    actual_path = series_path(SERIES_ID, Path("x"))
    assert actual_path == Path("x") / "sidra" / "1737-v2265__BRA.csv"


def test_read_history_missing_file_is_empty(tmp_path):
    missing_file = tmp_path / "missing.csv"
    df = read_history(missing_file)
    assert df.empty
    assert list(df.columns) == ["period", "value", "retrieved_at"]


def test_merge_first_run_adds_everything():
    parsed = parsed_rows({"2026-08": 4.22, "2026-09": 4.58})
    history, new, revised = merge(empty_history(), parsed, "2026-10-19")
    assert (new, revised) == (2, 0)
    assert len(history) == 2


def test_merge_same_data_adds_nothing():
    parsed = parsed_rows({"2026-08": 4.22, "2026-09": 4.58})
    history, _, _ = merge(empty_history(), parsed, "2026-10-19")
    history, new, revised = merge(history, parsed, "2026-10-26")
    assert (new, revised) == (0, 0)
    assert len(history) == 2


def test_merge_revision_keeps_old_row():
    first = parsed_rows({"2026-08": 4.22, "2026-09": 4.58})
    history, _, _ = merge(empty_history(), first, "2026-10-19")
    revised_data = parsed_rows({"2026-08": 4.22, "2026-09": 4.60})
    history, new, revised = merge(history, revised_data, "2026-11-16")
    assert (new, revised) == (0, 1)
    assert len(history) == 3
    september = history[history["period"] == "2026-09"]
    assert sorted(september["value"]) == [4.58, 4.60]


def test_merge_new_period_after_revision_counts_as_new():
    first = parsed_rows({"2026-09": 4.58})
    history, _, _ = merge(empty_history(), first, "2026-10-19")
    history, new, revised = merge(
        history, parsed_rows({"2026-09": 4.58, "2026-10": 4.80}), "2026-11-16"
    )
    assert (new, revised) == (1, 0)


def test_update_series_writes_file_and_is_safe_to_repeat(tmp_path):
    parsed = parsed_rows({"2026-08": 4.22, "2026-09": 4.58})
    assert update_series(SERIES_ID, parsed, "2026-10-19", tmp_path) == (2, 0)
    path = series_path(SERIES_ID, tmp_path)
    first_text = path.read_text(encoding="utf-8")
    assert first_text.splitlines()[0] == "period,value,retrieved_at"

    assert update_series(SERIES_ID, parsed, "2026-10-26", tmp_path) == (0, 0)
    assert path.read_text(encoding="utf-8") == first_text
