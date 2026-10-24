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
    source: Literal["sidra", "sgs", "focus", "imf", "oecd", "bis", "worldbank"]
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
        "vs_peer_average",
        "trend",
    ]
    basis: Literal["official_target", "imf", "world_bank", "oecd", "brasilfacil_rule"]
    # band: an official target file plus Brasil Fácil's yellow margin
    target: str | None = None
    yellow_margin: float | None = None
    # change_from_year_before: thresholds in points of the rate
    green_below: float | None = None
    red_from: float | None = None
    # vs_peer_average: the countries whose average Brazil is compared with.
    # Fixed here, so the colour does not change when readers switch lines on/off.
    peers: list[str] | None = None
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
            "vs_peer_average": ["peers", "checked_on"],
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


class PeerGroup(Strict):
    """Comparison countries that come from one source, e.g. IMF inflation."""

    source: Literal["imf", "oecd", "bis", "worldbank"]
    code: str
    geo: list[str]  # country codes from config/countries.yaml
    source_name: str  # shown under the chart, e.g. "FMI"

    def refs(self) -> list[SeriesRef]:
        return [SeriesRef(source=self.source, code=self.code, geo=g) for g in self.geo]


class IndicatorSeries(Strict):
    # brazil: the series shown as it is published.
    # inputs: named series a transform combines (e.g. selic + expected inflation).
    # peers: the comparison countries, drawn as thin grey lines.
    brazil: SeriesRef | None = None
    inputs: dict[str, SeriesRef] | None = None
    peers: list[PeerGroup] = []
    # forecast: an official forecast of the next years (e.g. the IMF's), drawn
    # apart from the results and never coloured.
    forecast: SeriesRef | None = None
    # expected: what was expected for each period before it happened (e.g. the
    # Focus survey in January), shown next to the result, never coloured.
    expected: SeriesRef | None = None
    # band: two series drawn as a shaded band around the main line (a fan
    # chart), e.g. the income of the poorest and richest 10%. Same transform.
    band: dict[Literal["lower", "upper"], SeriesRef] | None = None

    @model_validator(mode="after")
    def check_one_kind(self) -> "IndicatorSeries":
        if (self.brazil is None) == (self.inputs is None):
            raise ValueError("series needs either 'brazil' or 'inputs', not both")
        if self.band is not None and set(self.band) != {"lower", "upper"}:
            raise ValueError("band needs both 'lower' and 'upper'")
        return self

    def all_refs(self) -> list[SeriesRef]:
        own = [self.brazil] if self.brazil else list(self.inputs.values())
        band = list(self.band.values()) if self.band else []
        extra = [
            ref for ref in (self.forecast, self.expected) if ref is not None
        ] + band
        return own + extra + [ref for group in self.peers for ref in group.refs()]


class Country(Strict):
    name: LangText
    # A shorter name for the chart's end labels on a phone; defaults to name.
    short: LangText | None = None
    role: Literal["reference", "peer"]
    default_on: bool = False


def load_countries(file_path: Path) -> dict[str, Country]:
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    return {code: Country.model_validate(value) for code, value in data.items()}


class SourceInfo(Strict):
    name: str
    table: str
    url: HttpUrl


class CompareWith(Strict):
    indicator: str  # the id of another indicator, drawn as a thin grey line
    label: LangText  # its short name at the end of the line, e.g. "IPCA"


class ReferenceLine(Strict):
    """A dashed horizontal line with a name, e.g. "EUA = 100" on the price level."""

    value: float
    label: LangText


class ChartSettings(Strict):
    show_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    compare_with: CompareWith | None = None
    # Show the grey "Sem meta" pill when there is no zone. Turn off where
    # "no target" would mislead (the Selic is itself a decision).
    no_target_pill: bool = True
    # "bar": one bar per period, coloured by its zone (yearly growth rates).
    # "fan": the main line inside a shaded band (series.band), e.g. income.
    kind: Literal["line", "bar", "fan"] = "line"
    # Only where a rise is clearly good for people (the real minimum wage,
    # income, GDP per person): the section page then says "Melhorando" or
    # "Piorando". Everywhere else it only says which way the number moved.
    higher_is_better: bool = False
    reference_line: ReferenceLine | None = None


class Indicator(Strict):
    id: str
    section: Literal["economia", "dinheiro-publico", "saude", "educacao", "seguranca"]
    group: Literal["leading", "lagging", "coincident"]
    name: LangText
    slug: LangText
    technical_name: str
    unit: Literal["percent", "usd_ppp", "brl", "usd"]
    # "rolling_quarter": each value covers 3 months ending in its period (PNAD)
    period_kind: Literal["month", "rolling_quarter", "year"] = "month"
    series: IndicatorSeries
    source: SourceInfo
    transform: Literal["none", "real_rate", "real_value"]
    zones: Zones | None = None  # None: no official target, so no colour
    chart: ChartSettings = ChartSettings()
    # id of an indicator mentioned, with a link, under the number
    related: str | None = None
    release: Release
    content: str

    @model_validator(mode="after")
    def check_series_for_transform(self) -> "Indicator":
        needed = {
            "real_rate": {"selic", "expected_inflation"},
            "real_value": {"nominal", "price_index"},
        }.get(self.transform)
        if needed is None and self.series.brazil is None:
            raise ValueError("transform 'none' needs series.brazil")
        if needed is not None and set(self.series.inputs or {}) != needed:
            raise ValueError(
                f"transform '{self.transform}' needs inputs: {sorted(needed)}"
            )
        return self


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


class SectionGroup(Strict):
    """One glass box on a section page, e.g. "Trabalho", with its indicators."""

    id: str  # its texts are in content/<lang>/<section>/index.md, under groups
    indicators: list[str]


class Section(Strict):
    groups: list[SectionGroup]


def load_sections(file_path: Path) -> dict[str, Section]:
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    return {name: Section.model_validate(value) for name, value in data.items()}
