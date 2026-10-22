"""Banco Central Focus survey (Olinda API): the market's median expectations.

Two kinds of series:
- "monthly": daily medians turned into one value per month, the last survey
  of the month (e.g. expected inflation over the next 12 months);
- "january": one value per year, what economists expected for that year in the
  first survey of its January (e.g. GDP growth), to compare with the result.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from pipeline.http_client import TIMEOUT_SECONDS, make_session

BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
FULL_PERIODS = "all"
RECENT_PERIODS = "recent"
RECENT_DAYS = 200

# Our code -> (Olinda endpoint, indicator, kind). baseCalculo 0 = all answers of
# the last 30 days, the series the BCB headlines.
CODES = {
    # Smoothed ("Suavizada") 12-month inflation expectation.
    "ipca-12m": ("ExpectativasMercadoInflacao12Meses", "IPCA", "monthly"),
    # Expected GDP growth for the calendar year (history since July 1999).
    "pib-janeiro": ("ExpectativasMercadoAnuais", "PIB Total", "january"),
}


def build_url(code: str, periods: str, today: date) -> str:
    if code not in CODES:
        raise ValueError(f"Focus: unknown code '{code}'. Known: {list(CODES)}")
    endpoint, indicator, kind = CODES[code]
    conditions = [f"Indicador eq '{indicator}'", "baseCalculo eq 0"]
    if kind == "monthly":
        conditions.append("Suavizada eq 'S'")
    if periods == RECENT_PERIODS:
        # "january" needs this year's January; "monthly" the last 200 days.
        since = (
            date(today.year, 1, 1)
            if kind == "january"
            else today - timedelta(days=RECENT_DAYS)
        )
        conditions.append(f"Data ge '{since:%Y-%m-%d}'")
    query = {
        "$filter": " and ".join(conditions),
        "$select": "Data,DataReferencia,Mediana"
        if kind == "january"
        else "Data,Mediana",
        "$orderby": "Data",
        "$top": "100000",
        "$format": "json",
    }
    return f"{BASE_URL}/{endpoint}?" + "&".join(
        f"{key}={quote(value)}" for key, value in query.items()
    )


def fetch(
    code: str,
    geo: str,
    periods: str,
    raw_dir: Path = RAW_DIR,
    today: date | None = None,
) -> list[Path]:
    if geo != "BRA":
        raise ValueError(f"Focus only has Brazil, not '{geo}'")
    url = build_url(code, periods, today or date.today())
    response = make_session().get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    out = raw_dir / "focus" / f"{code}__{geo}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(response.content)
    return [out]


def parse(files: list[Path], series_id: str) -> pd.DataFrame:
    rows = []
    for file in files:
        rows.extend(json.loads(file.read_text(encoding="utf-8"))["value"])
    code = series_id.split(".")[1]  # "focus.pib-janeiro.BRA" -> the code
    if CODES[code][2] == "january":
        return parse_january(rows, series_id)
    table = pd.DataFrame(rows, columns=["Data", "Mediana"]).sort_values("Data")
    table["period"] = table["Data"].str[:7]
    table["value"] = pd.to_numeric(table["Mediana"], errors="coerce").round(4)
    monthly = table.dropna(subset=["value"]).drop_duplicates("period", keep="last")
    return pd.DataFrame(
        {"series_id": series_id, "period": monthly["period"], "value": monthly["value"]}
    ).reset_index(drop=True)


def parse_january(rows: list[dict], series_id: str) -> pd.DataFrame:
    """One row per year: the median of the first January survey about that year.

    Each survey day has answers for several years (2025, 2026, 2027...); only
    the answer about the survey's own year counts: in January 2025, for 2025.
    """
    table = pd.DataFrame(rows, columns=["Data", "DataReferencia", "Mediana"])
    year = table["Data"].str[:4]
    january = table["Data"].str[5:7] == "01"
    same_year = table["DataReferencia"].astype(str) == year
    table = table[january & same_year].assign(period=year).sort_values("Data")
    table["value"] = pd.to_numeric(table["Mediana"], errors="coerce").round(4)
    first = table.dropna(subset=["value"]).drop_duplicates("period", keep="first")
    return pd.DataFrame(
        {"series_id": series_id, "period": first["period"], "value": first["value"]}
    ).reset_index(drop=True)
