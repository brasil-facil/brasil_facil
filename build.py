import json
import shutil
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from pipeline.export import chart_data
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
    text = f"{value:,.2f}".rstrip("0").rstrip(".")
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
    env.filters.update(number=number, month_short=month_short, month_long=month_long)
    strings = load_strings()
    indicators = [load_indicator(p) for p in sorted(CONFIG.glob("*/*.yaml"))]

    for lang in LANGS:
        other = "en" if lang == "pt" else "pt"
        s = strings[lang]
        metric_pages = []

        for indicator in indicators:
            data = chart_data(indicator, lang)
            text = load_text(indicator, lang)
            json_url = f"/data/{lang}/{indicator.id}.json"
            write(
                dist / json_url.lstrip("/"), json.dumps(data, ensure_ascii=False), dist
            )

            url = page_url(indicator, lang)
            summary = text["summary"].format(
                month=month_long(data["latest"]["period"], lang),
                value=number(data["latest"]["value"], lang) + data["unit"],
            )
            html = env.get_template("metric.html").render(
                lang=lang,
                s=s,
                data=data,
                text=text,
                summary=summary,
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
