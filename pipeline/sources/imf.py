"""IMF data API (SDMX): monthly national CPIs, collected by the IMF.

detail=dataonly leaves out the long descriptions the IMF otherwise repeats on
every row (about 1.5 MB per country instead of about 50 KB).
"""

from datetime import date
from pathlib import Path

import pandas as pd

from pipeline.sources import sdmx

BASE_URL = "https://api.imf.org/external/sdmx/2.1/data"
FULL_PERIODS = sdmx.FULL_PERIODS
RECENT_PERIODS = sdmx.RECENT_PERIODS

# Our code -> (dataflow, key). {geo} is the ISO 3-letter country code.
CODES = {
    "cpi-yoy": ("IMF.STA,CPI", "{geo}.CPI._T.YOY_PCH_PA_PT.M"),
}


def build_url(code: str, geo: str, periods: str, today: date) -> str:
    if code not in CODES:
        raise ValueError(f"IMF: unknown code '{code}'. Known: {list(CODES)}")
    flow, key = CODES[code]
    start = sdmx.start_period(periods, today)
    return (
        f"{BASE_URL}/{flow}/{key.format(geo=geo)}?startPeriod={start}&detail=dataonly"
    )


def fetch(
    code: str,
    geo: str,
    periods: str,
    raw_dir: Path = sdmx.RAW_DIR,
    today: date | None = None,
) -> list[Path]:
    url = build_url(code, geo, periods, today or date.today())
    return sdmx.download(url, raw_dir / "imf" / f"{code}__{geo}.csv")


def parse(files: list[Path], series_id: str) -> pd.DataFrame:
    return sdmx.parse_csv(files, series_id)
