"""World Bank API (World Development Indicators): yearly data, no key needed.

The price level is computed from two published series of the same country and
year: the purchasing power parity (PPP) for household consumption, in local
currency per international dollar, and the market exchange rate, in local
currency per US dollar. PPP / exchange rate x 100 says what a basket of goods
that costs US$ 100 in the United States costs in that country (US = 100).
"""

import json
from datetime import date
from pathlib import Path

import pandas as pd

from pipeline.http_client import TIMEOUT_SECONDS, make_session

BASE_URL = "https://api.worldbank.org/v2/country/{geo}/indicator/{indicator}"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
FULL_PERIODS = "all"
RECENT_PERIODS = "recent"
FIRST_YEAR = 1990  # the PPP series starts here
RECENT_YEARS = 5  # the World Bank revises recent PPPs: enough overlap to catch it

PPP = "PA.NUS.PRVT.PP"  # PPP, household final consumption (LCU per international $)
EXCHANGE_RATE = "PA.NUS.FCRF"  # official exchange rate (LCU per US$, period average)

# Euro countries: the World Bank gives their PPP in euros for every year, but
# the exchange rate before 1999 in the old currency (francs, marks). Those years
# are converted with the fixed rate the euro was created with (EU Council, 1998).
EURO_START = 1999
EURO_RATES = {"FRA": 6.55957, "DEU": 1.95583}

# Our code -> the World Bank indicators it needs.
CODES = {"price-level": [PPP, EXCHANGE_RATE]}


def build_url(indicator: str, geo: str, periods: str, today: date) -> str:
    first = FIRST_YEAR if periods == FULL_PERIODS else today.year - RECENT_YEARS
    return (
        BASE_URL.format(geo=geo, indicator=indicator)
        + f"?format=json&per_page=1000&date={first}:{today.year}"
    )


def fetch(
    code: str,
    geo: str,
    periods: str,
    raw_dir: Path = RAW_DIR,
    today: date | None = None,
) -> list[Path]:
    if code not in CODES:
        raise ValueError(f"World Bank: unknown code '{code}'. Known: {list(CODES)}")
    today = today or date.today()
    session = make_session()
    files = []
    for indicator in CODES[code]:
        response = session.get(
            build_url(indicator, geo, periods, today), timeout=TIMEOUT_SECONDS
        )
        response.raise_for_status()
        out = raw_dir / "worldbank" / f"{code}__{geo}__{indicator}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(response.content)
        files.append(out)
    return files


def read_values(file: Path) -> dict[str, float]:
    """{"2025": 2.58, ...}. The answer is [page info, rows]; an error has no rows."""
    answer = json.loads(file.read_text(encoding="utf-8"))
    if len(answer) < 2 or answer[1] is None:
        raise ValueError(f"World Bank returned no data in {file.name}: {answer[0]}")
    return {row["date"]: row["value"] for row in answer[1] if row["value"] is not None}


def parse(files: list[Path], series_id: str) -> pd.DataFrame:
    by_indicator = {
        indicator: read_values(file)
        for file in files
        for indicator in (PPP, EXCHANGE_RATE)
        if file.stem.endswith(indicator)
    }
    ppp, rate = by_indicator[PPP], by_indicator[EXCHANGE_RATE]
    geo = series_id.split(".")[-1]
    if geo in EURO_RATES:
        rate = {
            year: value / EURO_RATES[geo] if int(year) < EURO_START else value
            for year, value in rate.items()
        }
    years = sorted(set(ppp) & set(rate))  # only years with both numbers
    return pd.DataFrame(
        {
            "series_id": series_id,
            "period": years,
            "value": [round(ppp[year] / rate[year] * 100, 1) for year in years],
        }
    )
