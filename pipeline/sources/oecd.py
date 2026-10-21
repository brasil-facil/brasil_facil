"""OECD data explorer API (SDMX): harmonised monthly statistics.

Used for the OECD average and for unemployment, harmonised to the ILO
definition (people aged 15 and over) and seasonally adjusted.
"""

from datetime import date
from pathlib import Path

import pandas as pd

from pipeline.sources import sdmx

BASE_URL = "https://sdmx.oecd.org/public/rest/data"
FULL_PERIODS = sdmx.FULL_PERIODS
RECENT_PERIODS = sdmx.RECENT_PERIODS

# Our code -> (dataflow, key). {geo} is the ISO 3-letter code, or OECD.
CODES = {
    "cpi-yoy": (
        "OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0",
        "{geo}.M.N.CPI.PA._T.N.GY",
    ),
    "unemployment": (
        "OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0",
        "{geo}.UNE_LF_M.PT_LF_SUB._Z.Y._T.Y_GE15._Z.M",
    ),
}


def build_url(code: str, geo: str, periods: str, today: date) -> str:
    if code not in CODES:
        raise ValueError(f"OECD: unknown code '{code}'. Known: {list(CODES)}")
    flow, key = CODES[code]
    start = sdmx.start_period(periods, today)
    return f"{BASE_URL}/{flow}/{key.format(geo=geo)}?startPeriod={start}&format=csv"


def fetch(
    code: str,
    geo: str,
    periods: str,
    raw_dir: Path = sdmx.RAW_DIR,
    today: date | None = None,
) -> list[Path]:
    url = build_url(code, geo, periods, today or date.today())
    return sdmx.download(url, raw_dir / "oecd" / f"{code}__{geo}.csv")


def parse(files: list[Path], series_id: str) -> pd.DataFrame:
    return sdmx.parse_csv(files, series_id)
