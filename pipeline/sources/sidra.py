"""IBGE SIDRA API.

Codes are "<table>-v<variable>", e.g. "1736-v2292" (INPC, 12 months), or with
one classification category, "<table>-v<variable>-c<classification>-<category>",
e.g. "7536-v10841-c1043-49304" (income from work, the median P50).
"""

import json
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from pipeline.http_client import TIMEOUT_SECONDS, make_session

BASE_URL = "https://apisidra.ibge.gov.br/values"
GEO_LEVELS = {"BRA": "n1/all"}
FULL_PERIODS = "all"
RECENT_PERIODS = "last 6"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def read_rows(files: list[Path]) -> list[dict]:
    rows = []
    for file in files:
        records = json.loads(file.read_text(encoding="utf-8"))
        rows.extend(records[1:])
    return rows


def parse(files: list[Path], series_id: str) -> pd.DataFrame:
    table = pd.DataFrame(read_rows(files))
    # "202609" -> "2026-09" (monthly); "2025" stays "2025" (yearly tables).
    code = table["D3C"].astype(str)
    period = code.where(code.str.len() == 4, code.str[:4] + "-" + code.str[4:])
    result = pd.DataFrame(
        {
            "series_id": series_id,
            "period": period,
            "value": pd.to_numeric(table["V"], errors="coerce"),
        }
    )
    result = result.dropna(subset=["value"])
    return result.sort_values("period", ignore_index=True)


def build_url(code: str, geo: str, periods: str) -> str:
    parts = code.split("-")  # "7536-v10841-c1043-49304" -> 4 parts
    table, variable = parts[0], parts[1].removeprefix("v")
    if geo not in GEO_LEVELS:
        raise ValueError(f"SIDRA: unknown geo '{geo}'. Known: {list(GEO_LEVELS)}")
    level = GEO_LEVELS[geo]
    url = f"{BASE_URL}/t/{table}/{level}/v/{variable}/p/{quote(periods)}"
    if len(parts) == 4:  # one category of a classification, e.g. c1043/49304
        url += f"/{parts[2]}/{parts[3]}"
    return url + "?formato=json"


def fetch(code: str, geo: str, periods: str, raw_dir: Path = RAW_DIR) -> list[Path]:
    url = build_url(code, geo, periods)
    session = make_session()
    response = session.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    out = raw_dir / "sidra" / f"{code}__{geo}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(response.content)
    return [out]
