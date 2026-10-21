"""Banco Central SGS (Sistema Gerenciador de Séries Temporais).

Daily series such as 432 (Meta Selic) are turned into one value per month:
the value in force on the last day of that month.
"""

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from pipeline.http_client import TIMEOUT_SECONDS, make_session

BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
FULL_PERIODS = "all"
RECENT_PERIODS = "recent"
FIRST_DAY = date(1986, 1, 1)  # SGS series start no earlier than this
RECENT_DAYS = 200  # about 6 months, so revisions are caught
WINDOW_YEARS = 10  # SGS refuses longer windows for daily series


def windows(periods: str, today: date) -> list[tuple[date, date]]:
    if periods == RECENT_PERIODS:
        return [(today - timedelta(days=RECENT_DAYS), today)]
    result = []
    start = FIRST_DAY
    while start <= today:
        end = min(date(start.year + WINDOW_YEARS, 1, 1) - timedelta(days=1), today)
        result.append((start, end))
        start = end + timedelta(days=1)
    return result


def build_url(code: str, start: date, end: date) -> str:
    return (
        BASE_URL.format(code=code)
        + f"?formato=json&dataInicial={start:%d/%m/%Y}&dataFinal={end:%d/%m/%Y}"
    )


def fetch(
    code: str,
    geo: str,
    periods: str,
    raw_dir: Path = RAW_DIR,
    today: date | None = None,
) -> list[Path]:
    if geo != "BRA":
        raise ValueError(f"SGS only has Brazil, not '{geo}'")
    today = today or date.today()
    session = make_session()
    files = []
    for number, (start, end) in enumerate(windows(periods, today)):
        response = session.get(build_url(code, start, end), timeout=TIMEOUT_SECONDS)
        # 404: no data in this window (before the series began).
        if response.status_code == 404:
            continue
        response.raise_for_status()
        out = raw_dir / "sgs" / f"{code}__{geo}__{number}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(response.content)
        files.append(out)
    return files


def read_rows(files: list[Path]) -> list[dict]:
    rows = []
    for file in files:
        text = file.read_text(encoding="utf-8")
        try:
            rows.extend(json.loads(text))
        except json.JSONDecodeError as error:
            # The BCB answers with an HTML error page when it blocks a request.
            raise ValueError(f"SGS did not return JSON in {file.name}") from error
    return rows


def parse(files: list[Path], series_id: str, today: date | None = None) -> pd.DataFrame:
    today = today or date.today()
    table = pd.DataFrame(read_rows(files), columns=["data", "valor"])
    table["day"] = pd.to_datetime(table["data"], format="%d/%m/%Y").dt.date
    # Series 432 lists the current Meta Selic up to the next Copom meeting.
    table = table[table["day"] <= today].sort_values("day")
    table["period"] = [f"{d:%Y-%m}" for d in table["day"]]
    table["value"] = pd.to_numeric(table["valor"], errors="coerce")
    monthly = table.dropna(subset=["value"]).drop_duplicates("period", keep="last")
    return pd.DataFrame(
        {"series_id": series_id, "period": monthly["period"], "value": monthly["value"]}
    ).reset_index(drop=True)
