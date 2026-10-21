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

# Our code -> (dataflow, key, yearly?). {geo} is the ISO 3-letter country code,
# or an IMF group such as G110 (advanced economies).
CODES = {
    "cpi-yoy": ("IMF.STA,CPI", "{geo}.CPI._T.YOY_PCH_PA_PT.M", False),
    # World Economic Outlook: real GDP per person, constant 2021 PPP dollars.
    "gdp-pc-ppp": ("IMF.RES,WEO", "{geo}.NGDPRPPPPC.A", True),
}


def build_url(code: str, geo: str, periods: str, today: date) -> str:
    if code not in CODES:
        raise ValueError(f"IMF: unknown code '{code}'. Known: {list(CODES)}")
    flow, key, annual = CODES[code]
    start = sdmx.start_period(periods, today, annual)
    url = f"{BASE_URL}/{flow}/{key.format(geo=geo)}?startPeriod={start}"
    # Yearly WEO data keeps its attributes: LATEST_ACTUAL_ANNUAL_DATA says where
    # actual data ends and projections begin (about 110 KB per country).
    return url if annual else url + "&detail=dataonly"


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
