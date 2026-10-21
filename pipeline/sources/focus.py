"""Banco Central Focus survey (Olinda API): the market's median expectations.

Daily medians are turned into one value per month: the last survey of the month.
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

# Our code -> (Olinda endpoint, indicator). Smoothed series ("Suavizada"), and
# baseCalculo 0 = all answers of the last 30 days, the series the BCB headlines.
CODES = {"ipca-12m": ("ExpectativasMercadoInflacao12Meses", "IPCA")}


def build_url(code: str, periods: str, today: date) -> str:
    if code not in CODES:
        raise ValueError(f"Focus: unknown code '{code}'. Known: {list(CODES)}")
    endpoint, indicator = CODES[code]
    conditions = [
        f"Indicador eq '{indicator}'",
        "Suavizada eq 'S'",
        "baseCalculo eq 0",
    ]
    if periods == RECENT_PERIODS:
        since = today - timedelta(days=RECENT_DAYS)
        conditions.append(f"Data ge '{since:%Y-%m-%d}'")
    query = {
        "$filter": " and ".join(conditions),
        "$select": "Data,Mediana",
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
    table = pd.DataFrame(rows, columns=["Data", "Mediana"]).sort_values("Data")
    table["period"] = table["Data"].str[:7]
    table["value"] = pd.to_numeric(table["Mediana"], errors="coerce").round(4)
    monthly = table.dropna(subset=["value"]).drop_duplicates("period", keep="last")
    return pd.DataFrame(
        {"series_id": series_id, "period": monthly["period"], "value": monthly["value"]}
    ).reset_index(drop=True)
