import csv
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, HttpUrl, ValidationError, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LangText(Strict):
    pt: str
    en: str


class SeriesRef(Strict):
    source: Literal["sidra"]
    code: str
    geo: str


class Zones(Strict):
    rule: Literal[
        "band",
        "threshold_plus_trend",
        "distance_from_reference",
        "sahm_rule",
        "trend",
    ]
    target: str
    yellow_margin: float
    basis: Literal["official_target", "imf", "world_bank", "oecd", "brasilfacil_rule"]


class Release(Strict):
    expected_day: int
    stale_after_days: int


class IndicatorSeries(Strict):
    brazil: SeriesRef


class Indicator(Strict):
    id: str
    section: Literal["economia", "dinheiro-publico", "saude", "educacao", "seguranca"]
    group: Literal["leading", "lagging", "coincident"]
    name: LangText
    technical_name: str
    unit: Literal["percent"]
    series: IndicatorSeries
    transform: Literal["none"]
    zones: Zones
    release: Release
    content: str


class IndicatorTargetRow(Strict):
    valid_from: date
    decided_on: date
    target: float
    lower: float | None = None
    upper: float | None = None
    legal_basis: str
    source_url: HttpUrl
    retrieved_at: date

    @model_validator(mode="after")
    def check_band(self) -> "IndicatorTargetRow":
        if (self.lower is None) != (self.upper is None):
            raise ValueError("lower and upper must both be filled or both be empty")
        if self.lower is not None and not (self.lower <= self.target <= self.upper):
            raise ValueError(
                f"target {self.target} is not between lower {self.lower} and upper {self.upper}"
            )
        return self


def load_indicator(file_path: Path) -> Indicator:
    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    indicator = Indicator.model_validate(data)
    if indicator.section != file_path.parent.name:
        raise ValueError(
            f"Indicator section '{indicator.section}' does not match directory name '{file_path.parent.name}'"
        )
    return indicator


def load_indicator_targets(file_path: Path) -> list[IndicatorTargetRow]:
    rows = []
    with open(file_path, "r", encoding="utf-8", newline="") as file:
        for line_number, raw_row in enumerate(csv.DictReader(file), start=2):
            cleaned = {key: (value or None) for key, value in raw_row.items()}
            try:
                rows.append(IndicatorTargetRow.model_validate(cleaned))
            except ValidationError as error:
                raise ValueError(
                    f"{file_path.name} line {line_number}: {error}"
                ) from error
    if not rows:
        raise ValueError(f"{file_path.name} has no rows")
    return rows
