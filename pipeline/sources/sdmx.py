"""Shared helpers for SDMX sources (IMF, OECD, BIS).

SDMX is the data format statistical agencies share. Asked for CSV, they all
answer with one row per observation, with TIME_PERIOD and OBS_VALUE columns.
"""

import re
from datetime import date
from pathlib import Path

import pandas as pd

from pipeline.http_client import TIMEOUT_SECONDS, make_session

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
FULL_PERIODS = "all"
RECENT_PERIODS = "recent"
FULL_START = "1990-01"
RECENT_MONTHS = 8  # enough overlap to catch revisions
CSV = "application/vnd.sdmx.data+csv;version=1.0.0"

MONTH = re.compile(r"^(\d{4})-M?(\d{2})$")  # "2026-09" (OECD, BIS) or "2026-M09" (IMF)


def start_period(periods: str, today: date) -> str:
    if periods == FULL_PERIODS:
        return FULL_START
    index = today.year * 12 + today.month - 1 - RECENT_MONTHS
    return f"{index // 12}-{index % 12 + 1:02d}"


def download(url: str, out: Path, accept: str = CSV) -> list[Path]:
    """Save the answer as received. A 404 means "no data", not an error."""
    response = make_session().get(
        url, timeout=TIMEOUT_SECONDS, headers={"Accept": accept}
    )
    if response.status_code == 404:
        return []
    response.raise_for_status()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(response.content)
    return [out]


def parse_csv(files: list[Path], series_id: str) -> pd.DataFrame:
    frames = [pd.read_csv(file, dtype={"TIME_PERIOD": str}) for file in files]
    rows = (
        pd.concat(frames)
        if frames
        else pd.DataFrame(columns=["TIME_PERIOD", "OBS_VALUE"])
    )
    periods, values = [], []
    for period, value in zip(rows["TIME_PERIOD"], rows["OBS_VALUE"]):
        match = MONTH.match(str(period))
        if match is None or pd.isna(value):
            continue  # skip quarters, years and empty cells
        periods.append(f"{match.group(1)}-{match.group(2)}")
        values.append(float(value))
    table = pd.DataFrame({"series_id": series_id, "period": periods, "value": values})
    return table.drop_duplicates("period", keep="last").sort_values(
        "period", ignore_index=True
    )
