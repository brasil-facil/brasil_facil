import json
import shutil
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from pipeline.export import UNITS, chart_data, current_table
from pipeline.models import Indicator, load_indicator

ROOT = Path(__file__).parent
TEMPLATES = ROOT / "site_src" / "templates"
STATIC = ROOT / "site_src" / "static"
CONTENT = ROOT / "content"
CONFIG = ROOT / "config"
DIST = ROOT / "dist"
LANGS = ["pt", "en"]

# Until config/sections.yaml exists (phase 5): each section's address per language.
SECTION_SLUGS = {"economia": {"pt": "economia", "en": "economy"}}

MONTHS_SHORT = {
    "pt": [
        "jan",
        "fev",
        "mar",
        "abr",
        "mai",
        "jun",
        "jul",
        "ago",
        "set",
        "out",
        "nov",
        "dez",
    ],
    "en": [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ],
}
MONTHS_LONG = {
    "pt": [
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ],
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
}


# Formatting helpers, used in templates as filters: {{ 4.58 | number(lang) }}.
def number(value: float, lang: str) -> str:
    # Big amounts (US$ 19.968) without decimals; rates (4,58%) with up to two.
    # Round half up (1234.5 -> 1235): Python's own rounding sends .5 to the
    # even neighbour (1234), which readers would not expect.
    step = Decimal(1) if abs(value) >= 1000 else Decimal("0.01")
    rounded = Decimal(str(value)).quantize(step, rounding=ROUND_HALF_UP)
    text = f"{rounded:,}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if lang == "pt":
        text = text.replace(",", "_").replace(".", ",").replace("_", ".")
    return text


def month_short(period: str, lang: str) -> str:
    year, month = period.split("-")
    return f"{MONTHS_SHORT[lang][int(month) - 1]}/{year}"


def month_long(period: str, lang: str) -> str:
    year, month = period.split("-")
    name = MONTHS_LONG[lang][int(month) - 1]
    return f"{name} de {year}" if lang == "pt" else f"{name} {year}"


def months_back(period: str, n: int) -> str:
    year, month = (int(part) for part in period.split("-"))
    index = year * 12 + (month - 1) - n
    return f"{index // 12}-{index % 12 + 1:02d}"


# A rolling quarter (PNAD) ending in 2026-08 covers June to August 2026.
def amount(value: float, lang: str, data: dict) -> str:
    """A number with its unit, on the right side: "4,58%" or "US$ 19.968"."""
    return data["unit_prefix"] + number(value, lang) + data["unit"]


def period_short(period: str, lang: str, kind: str = "month") -> str:
    if kind == "year":
        return period
    if kind == "month":
        return month_short(period, lang)
    start = months_back(period, 2)
    if start[:4] == period[:4]:
        first = month_short(start, lang).split("/")[0]
        return f"{first}–{month_short(period, lang)}"
    return f"{month_short(start, lang)}–{month_short(period, lang)}"


def period_long(period: str, lang: str, kind: str = "month") -> str:
    if kind == "year":
        return period
    if kind == "month":
        return month_long(period, lang)
    start = months_back(period, 2)
    link = " a " if lang == "pt" else " to "
    if start[:4] == period[:4]:
        first = MONTHS_LONG[lang][int(start[5:]) - 1]
        return first + link + month_long(period, lang)
    return month_long(start, lang) + link + month_long(period, lang)


def change_text(change: float | None, s: dict[str, str], lang: str) -> str | None:
    """'0,3 ponto menor do que um ano antes' for the year-on-year rule."""
    if change is None:
        return None
    if change == 0:
        return s["change_same"]
    size = abs(change)
    unit = s["point"] if size < 2 else s["points"]
    key = "change_higher" if change > 0 else "change_lower"
    return s[key].format(value=f"{number(size, lang)} {unit}")


def load_strings() -> dict[str, dict[str, str]]:
    strings = yaml.safe_load((CONTENT / "strings.yaml").read_text(encoding="utf-8"))
    missing = set(strings["pt"]) ^ set(strings["en"])
    if missing:
        raise ValueError(
            f"strings.yaml: keys missing in one language: {sorted(missing)}"
        )
    return strings


def load_text(indicator: Indicator, lang: str) -> dict[str, str]:
    path = CONTENT / lang / indicator.section / f"{indicator.content}.md"
    if not path.exists():
        raise FileNotFoundError(f"missing translation: {path.relative_to(ROOT)}")
    _, front, body = path.read_text(encoding="utf-8").split("---", 2)
    text = yaml.safe_load(front)
    text["body_html"] = markdown.markdown(body)
    return text


def page_url(indicator: Indicator, lang: str) -> str:
    section = SECTION_SLUGS[indicator.section][lang]
    return f"/{lang}/{section}/{getattr(indicator.slug, lang)}/"


def related_link(
    indicator: Indicator,
    by_id: dict[str, Indicator],
    text: dict[str, str],
    lang: str,
) -> dict[str, str] | None:
    """The "see also" line under the number, e.g. the INPC on the IPCA page."""
    if indicator.related is None:
        return None
    if indicator.related not in by_id:
        raise ValueError(f"{indicator.id}: related names unknown '{indicator.related}'")
    if "related_note" not in text:
        raise ValueError(f"{indicator.id}: content needs a related_note ({lang})")
    other = by_id[indicator.related]
    value = current_table(other)["value"].iloc[-1]
    prefix, unit = UNITS[other.unit]
    return {
        "text": text["related_note"].format(value=prefix + number(value, lang) + unit),
        "url": page_url(other, lang),
    }


def compare_url(
    indicator: Indicator, by_id: dict[str, Indicator], lang: str
) -> str | None:
    """The page of the indicator drawn as the grey comparison line."""
    compare = indicator.chart.compare_with
    return None if compare is None else page_url(by_id[compare.indicator], lang)


def write(path: Path, text: str, dist: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path.relative_to(dist).as_posix()}")


def main(dist: Path = DIST) -> None:
    shutil.rmtree(dist, ignore_errors=True)
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=True,
        undefined=StrictUndefined,
    )
    env.filters.update(
        number=number,
        amount=amount,
        month_short=month_short,
        month_long=month_long,
        period_short=period_short,
    )
    strings = load_strings()
    indicators = [load_indicator(p) for p in sorted(CONFIG.glob("*/*.yaml"))]
    by_id = {indicator.id: indicator for indicator in indicators}

    for lang in LANGS:
        other = "en" if lang == "pt" else "pt"
        s = strings[lang]
        metric_pages = []

        for indicator in indicators:
            data = chart_data(indicator, lang, others=by_id)
            text = load_text(indicator, lang)
            json_url = f"/data/{lang}/{indicator.id}.json"
            write(
                dist / json_url.lstrip("/"), json.dumps(data, ensure_ascii=False), dist
            )

            url = page_url(indicator, lang)
            kind = indicator.period_kind
            summary = text["summary"].format(
                month=period_long(data["latest"]["period"], lang, kind),
                value=amount(data["latest"]["value"], lang, data),
            )
            html = env.get_template("metric.html").render(
                lang=lang,
                s=s,
                data=data,
                text=text,
                summary=summary,
                latest_period=period_short(data["latest"]["period"], lang, kind),
                latest_period_long=period_long(data["latest"]["period"], lang, kind),
                change=change_text(data["latest"]["change"], s, lang),
                related=related_link(indicator, by_id, text, lang),
                compare_url=compare_url(indicator, by_id, lang),
                json_url=json_url,
                other_url=page_url(indicator, other),
            )
            write(dist / url.strip("/") / "index.html", html, dist)
            metric_pages.append({"url": url, "title": data["title"]})

        home = env.get_template("home.html").render(
            lang=lang, s=s, metric_pages=metric_pages, other_url=f"/{other}/"
        )
        write(dist / lang / "index.html", home, dist)

    shutil.copytree(STATIC, dist / "static", dirs_exist_ok=True)
    (dist / "_redirects").write_text("/  /pt/  302\n", encoding="utf-8")


if __name__ == "__main__":
    main()
