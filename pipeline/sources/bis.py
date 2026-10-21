"""BIS data portal API (SDMX): central bank policy rates.

The BIS uses 2-letter country codes, so ours are translated here.
"""

from datetime import date
from pathlib import Path

import pandas as pd

from pipeline.sources import sdmx

BASE_URL = "https://stats.bis.org/api/v2/data/dataflow/BIS"
FULL_PERIODS = sdmx.FULL_PERIODS
RECENT_PERIODS = sdmx.RECENT_PERIODS
ISO2 = {"BRA": "BR", "MEX": "MX", "COL": "CO", "ZAF": "ZA", "USA": "US"}

# Our code -> (dataflow, key). {geo} is the BIS 2-letter code.
CODES = {
    "policy-rate": ("WS_CBPOL", "M.{geo}"),
}


def build_url(code: str, geo: str, periods: str, today: date) -> str:
    if code not in CODES:
        raise ValueError(f"BIS: unknown code '{code}'. Known: {list(CODES)}")
    if geo not in ISO2:
        raise ValueError(f"BIS: unknown geo '{geo}'. Known: {list(ISO2)}")
    flow, key = CODES[code]
    start = sdmx.start_period(periods, today)
    return f"{BASE_URL}/{flow}/1.0/{key.format(geo=ISO2[geo])}?startPeriod={start}&format=csv"


def fetch(
    code: str,
    geo: str,
    periods: str,
    raw_dir: Path = sdmx.RAW_DIR,
    today: date | None = None,
) -> list[Path]:
    url = build_url(code, geo, periods, today or date.today())
    return sdmx.download(url, raw_dir / "bis" / f"{code}__{geo}.csv")


def parse(files: list[Path], series_id: str) -> pd.DataFrame:
    return sdmx.parse_csv(files, series_id)
