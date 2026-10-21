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
YEAR = re.compile(r"^(\d{4})$")  # yearly data, e.g. the IMF World Economic Outlook


def start_period(periods: str, today: date, annual: bool = False) -> str:
    if annual:
        return "1980" if periods == FULL_PERIODS else str(today.year - 3)
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


def parse_csv(
    files: list[Path], series_id: str, today: date | None = None
) -> pd.DataFrame:
    frames = [
        pd.read_csv(file, dtype={"TIME_PERIOD": str}, low_memory=False)
        for file in files
    ]
    rows = (
        pd.concat(frames)
        if frames
        else pd.DataFrame(columns=["TIME_PERIOD", "OBS_VALUE"])
    )
    # The IMF marks the last year of actual data; later years are projections.
    # Groups (e.g. G110) have no such mark: keep only years before this one.
    today = today or date.today()
    if "LATEST_ACTUAL_ANNUAL_DATA" in rows:
        last_actual = pd.to_numeric(rows["LATEST_ACTUAL_ANNUAL_DATA"], errors="coerce")
        year = pd.to_numeric(rows["TIME_PERIOD"].str[:4], errors="coerce")
        yearly = rows["TIME_PERIOD"].str.fullmatch(r"\d{4}")
        last_actual = last_actual.where(last_actual.notna() | ~yearly, today.year - 1)
        rows = rows[last_actual.isna() | (year <= last_actual)]
    periods, values = [], []
    for period, value in zip(rows["TIME_PERIOD"], rows["OBS_VALUE"]):
        month, year = MONTH.match(str(period)), YEAR.match(str(period))
        if pd.isna(value) or (month is None and year is None):
            continue  # skip quarters and empty cells
        periods.append(f"{month.group(1)}-{month.group(2)}" if month else year.group(1))
        values.append(float(value))
    table = pd.DataFrame({"series_id": series_id, "period": periods, "value": values})
    return table.drop_duplicates("period", keep="last").sort_values(
        "period", ignore_index=True
    )
