import csv
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    model_validator,
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LangText(Strict):
    pt: str
    en: str


class SeriesRef(Strict):
    source: Literal["sidra"]
    code: str
    geo: str

    @property
    def series_id(self) -> str:
        return f"{self.source}.{self.code}.{self.geo}"


class Zones(Strict):
    rule: Literal[
        "band",
        "threshold_plus_trend",
        "distance_from_reference",
        "change_from_year_before",
        "trend",
    ]
    basis: Literal["official_target", "imf", "world_bank", "oecd", "brasilfacil_rule"]
    # band: an official target file plus Brasil Fácil's yellow margin
    target: str | None = None
    yellow_margin: float | None = None
    # change_from_year_before: thresholds in points of the rate
    green_below: float | None = None
    red_from: float | None = None
    # where a Brasil Fácil rule comes from, and when it was last checked
    citation: str | None = None
    checked_on: date | None = None

    @model_validator(mode="after")
    def check_fields_for_rule(self) -> "Zones":
        needed = {
            "band": ["target", "yellow_margin"],
            "change_from_year_before": [
                "green_below",
                "red_from",
                "citation",
                "checked_on",
            ],
        }.get(self.rule, [])
        missing = [name for name in needed if getattr(self, name) is None]
        if missing:
            raise ValueError(f"rule '{self.rule}' needs: {', '.join(missing)}")
        if self.rule == "change_from_year_before" and self.green_below > self.red_from:
            raise ValueError("green_below must not be larger than red_from")
        return self


class Release(Strict):
    expected_day: int
    stale_after_days: int


class IndicatorSeries(Strict):
    brazil: SeriesRef


class SourceInfo(Strict):
    name: str
    table: str
    url: HttpUrl


class CompareWith(Strict):
    indicator: str  # the id of another indicator, drawn as a thin grey line
    label: LangText  # its short name at the end of the line, e.g. "IPCA"


class ChartSettings(Strict):
    show_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    compare_with: CompareWith | None = None


class Indicator(Strict):
    id: str
    section: Literal["economia", "dinheiro-publico", "saude", "educacao", "seguranca"]
    group: Literal["leading", "lagging", "coincident"]
    name: LangText
    slug: LangText
    technical_name: str
    unit: Literal["percent"]
    # "rolling_quarter": each value covers 3 months ending in its period (PNAD)
    period_kind: Literal["month", "rolling_quarter"] = "month"
    series: IndicatorSeries
    source: SourceInfo
    transform: Literal["none"]
    zones: Zones | None = None  # None: no official target, so no colour
    chart: ChartSettings = ChartSettings()
    # id of an indicator mentioned, with a link, under the number
    related: str | None = None
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
