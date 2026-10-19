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
    result = pd.DataFrame(
        {
            "series_id": series_id,
            "period": table["D3C"].str[:4] + "-" + table["D3C"].str[4:],
            "value": pd.to_numeric(table["V"], errors="coerce"),
        }
    )
    result = result.dropna(subset=["value"])
    return result.sort_values("period", ignore_index=True)


def build_url(code: str, geo: str, periods: str) -> str:
    table, variable = code.split("-v")
    if geo not in GEO_LEVELS:
        raise ValueError(f"SIDRA: unknown geo '{geo}'. Known: {list(GEO_LEVELS)}")
    level = GEO_LEVELS[geo]
    return f"{BASE_URL}/t/{table}/{level}/v/{variable}/p/{quote(periods)}?formato=json"


def fetch(code: str, geo: str, periods: str, raw_dir: Path = RAW_DIR) -> list[Path]:
    url = build_url(code, geo, periods)
    session = make_session()
    response = session.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    out = raw_dir / "sidra" / f"{code}__{geo}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(response.content)
    return [out]
