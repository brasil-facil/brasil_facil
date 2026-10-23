import json
import shutil
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup

from pipeline.export import (
    COUNTRIES_FILE,
    UNITS,
    chart_data,
    current_table,
    tile_data,
)
from pipeline.models import Indicator, load_countries, load_indicator, load_sections

ROOT = Path(__file__).parent
TEMPLATES = ROOT / "site_src" / "templates"
STATIC = ROOT / "site_src" / "static"
CONTENT = ROOT / "content"
CONFIG = ROOT / "config"
DIST = ROOT / "dist"
LANGS = ["pt", "en"]

SECTIONS_FILE = CONFIG / "sections.yaml"
# Each section's address per language (its folder in config/ and content/ is the key).
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
def number(value: float, lang: str, whole: bool = False) -> str:
    # Big amounts (US$ 19.968) without decimals; rates (4,58%) with up to two.
    # whole=True: no decimals at all (money: R$ 845, not R$ 845,12).
    # Round half up (1234.5 -> 1235): Python's own rounding sends .5 to the
    # even neighbour (1234), which readers would not expect.
    step = Decimal(1) if whole or abs(value) >= 1000 else Decimal("0.01")
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
    """A number with its unit, on the right side: "4,58%" or "US$ 19.968".

    Money (a unit before the number) has no decimals, like the chart's labels.
    """
    money = bool(data["unit_prefix"])
    return data["unit_prefix"] + number(value, lang, whole=money) + data["unit"]


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
    # "{yellow_margin}" in the text becomes "1,5", read from the indicator's
    # YAML, so the colour rules on the page never drift from the real ones.
    text["body_html"] = markdown.markdown(
        body.format_map(zone_numbers(indicator, lang))
    )
    return text


def zone_numbers(indicator: Indicator, lang: str) -> dict[str, str]:
    """The colour limits of an indicator, written for readers: {"red_from": "0,5"}."""
    if indicator.zones is None:
        return {}
    limits = {
        "yellow_margin": indicator.zones.yellow_margin,
        "green_below": indicator.zones.green_below,
        "red_from": indicator.zones.red_from,
    }
    numbers = {
        name: number(value, lang) for name, value in limits.items() if value is not None
    }
    if indicator.zones.peers:
        numbers["peers"] = country_names(indicator.zones.peers, lang)
    return numbers


def country_names(geos: list[str], lang: str) -> str:
    """["MEX", "COL", "ZAF"] -> "México, Colômbia e África do Sul"."""
    countries = load_countries(COUNTRIES_FILE)
    names = [getattr(countries[geo].name, lang) for geo in geos]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + (" e " if lang == "pt" else " and ") + names[-1]


def peer_average_text(
    indicator: Indicator, data: dict, s: dict[str, str], lang: str
) -> str | None:
    """'Média de México, Colômbia e África do Sul no mesmo ano: 1,4%'."""
    reference = data["latest"]["reference"]
    if reference is None:
        return None
    names = country_names(indicator.zones.peers, lang)
    return s["peer_average"].format(names=names, value=amount(reference, lang, data))


def forecast_text(data: dict, s: dict[str, str], lang: str) -> str | None:
    """'Previsão do FMI: 2,18% em 2026 e 1,86% em 2027'."""
    if not data["forecast"]:
        return None
    link = " em " if lang == "pt" else " in "
    items = [
        amount(value, lang, data) + link + period for period, value in data["forecast"]
    ]
    joined = ", ".join(items[:-1]) + (" e " if lang == "pt" else " and ") + items[-1]
    return s["forecast"].format(items=joined if len(items) > 1 else items[0])


def expected_text(data: dict, s: dict[str, str], lang: str) -> str | None:
    """'Em janeiro de 2025, os economistas esperavam 2,02% para o ano...'."""
    year = data["latest"]["period"]
    expected = dict(data["expected"] or [])
    if year not in expected:
        return None
    return s["expected"].format(year=year, value=amount(expected[year], lang, data))


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


def section_url(section: str, lang: str) -> str:
    return f"/{lang}/{SECTION_SLUGS[section][lang]}/"


def load_section_text(section: str, lang: str) -> dict:
    """The section page's texts: title, question, intro and each group's name."""
    path = CONTENT / lang / section / "index.md"
    if not path.exists():
        raise FileNotFoundError(f"missing translation: {path.relative_to(ROOT)}")
    _, front, _ = path.read_text(encoding="utf-8").split("---", 2)
    return yaml.safe_load(front)


def date_long(day: date, lang: str) -> str:
    """date(2026, 10, 23) -> "23 de outubro de 2026" or "23 October 2026"."""
    month = MONTHS_LONG[lang][day.month - 1]
    if lang == "pt":
        return f"{day.day} de {month} de {day.year}"
    return f"{day.day} {month} {day.year}"


# Zones are stored as green / yellow / red; the CSS classes say what they mean.
ZONE_CLASS = {"green": "good", "yellow": "watch", "red": "bad"}


def tile_svg(tile: dict, colour: str) -> Markup:
    """The small chart on a tile: one point per year, and under it one small
    square per year in that year's colour (only for indicators with colours).

    Colours are CSS classes (good, watch, bad, brand), so the light and dark
    looks both work. Drawn here, as plain SVG: no JavaScript needed.
    """
    values = tile["values"]
    if len(values) < 2:
        return Markup("")
    width, height, pad = 300, 44, 4
    has_strip = any(zone is not None for zone in tile["zones"])
    strip_top, strip_height = height + 6, 7
    labels_y = (strip_top + strip_height if has_strip else height) + 11
    low, high = min(values), max(values)
    step = width / len(values)

    def x(i: int) -> float:
        return step * (i + 0.5)

    def y(value: float) -> float:
        return pad + (1 - (value - low) / ((high - low) or 1)) * (height - 2 * pad)

    coords = [f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values)]
    last = len(values) - 1
    area = "M" + " L".join(coords) + f" L{x(last):.1f},{height} L{x(0):.1f},{height} Z"
    parts = [
        f'<svg viewBox="0 0 {width} {labels_y + 2}" aria-hidden="true" class="spark">',
        f'<path class="spark-area {colour}" d="{area}"/>',
        f'<polyline class="spark-line {colour}" points="{" ".join(coords)}"/>',
        (
            f'<circle class="spark-dot {colour}" cx="{x(last):.1f}" '
            f'cy="{y(values[-1]):.1f}" r="3"/>'
        ),
    ]
    if has_strip:
        for i, zone in enumerate(tile["zones"]):
            if zone is not None:
                parts.append(
                    f'<rect class="spark-year {ZONE_CLASS[zone]}" x="{step * i + 0.7:.1f}" '
                    f'y="{strip_top}" width="{step - 1.4:.1f}" '
                    f'height="{strip_height}" rx="1.5"/>'
                )
    parts.append(f'<text x="0" y="{labels_y}">{tile["years"][0]}</text>')
    parts.append(
        f'<text x="{width}" y="{labels_y}" text-anchor="end">{tile["years"][-1]}</text>'
    )
    parts.append("</svg>")
    return Markup("".join(parts))


def tile_view(indicator: Indicator, data: dict, text: dict, s: dict, lang: str) -> dict:
    """Everything one tile on a section page shows.

    Three kinds: with colours (Bom / Atenção / Preocupante and since when);
    higher_is_better (Melhorando / Piorando and in how many years it improved);
    neutral (only which way it moved against a year earlier).
    """
    tile = tile_data(data, indicator.chart.higher_is_better)
    latest = data["latest"]
    kind = indicator.period_kind
    zone = latest["zone"]
    pill = None
    if zone is not None:
        word = s[f"zone_{zone}"]
        pill = {"class": ZONE_CLASS[zone], "text": word}
        since = period_short(latest["zone_since"], lang, kind)
        line = {"class": ZONE_CLASS[zone], "text": f"{word} {s['since']} {since}"}
        colour = ZONE_CLASS[zone]
    elif indicator.chart.higher_is_better:
        if tile["direction"] in ("up", "down"):
            pill = {
                "class": "trend",
                "text": s[f"trend_{tile['direction']}"],
                "improving": tile["direction"] == "up",
            }
        line = {
            "class": "trend",
            "text": s["better_years"].format(
                better=tile["better_years"], years=tile["compared_years"]
            ),
        }
        colour = "brand"
    else:
        moved = tile["direction"] or "same"
        line = {"class": "neutral", "text": s[f"moved_{moved}"]}
        colour = "brand"
    return {
        "url": page_url(indicator, lang),
        "name": data["title"],
        "question": text["question"],
        "value": amount(latest["value"], lang, data),
        "period": period_short(latest["period"], lang, kind),
        "zone": zone,  # for the zone_pill macro (icon and word)
        "pill": pill,
        "line": line,
        "svg": tile_svg(tile, colour),
    }


def nav_links(lang: str, current: str, section_texts: dict) -> list[dict]:
    """The tabs in the header: Início, then one per section."""
    links = [{"url": f"/{lang}/", "key": "home", "current": current == "home"}]
    for section in SECTION_SLUGS:
        links.append(
            {
                "url": section_url(section, lang),
                "key": section,
                "name": section_texts[section]["title"],
                "current": current == section,
            }
        )
    return links


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
    sections = load_sections(SECTIONS_FILE)
    for name, section in sections.items():
        listed = [i for group in section.groups for i in group.indicators]
        unknown = [i for i in listed if i not in by_id]
        if unknown:
            raise ValueError(f"sections.yaml, {name}: unknown indicators {unknown}")

    for lang in LANGS:
        other = "en" if lang == "pt" else "pt"
        s = strings[lang]
        metric_pages = []
        tiles = {}
        section_texts = {name: load_section_text(name, lang) for name in sections}

        for indicator in indicators:
            data = chart_data(indicator, lang, others=by_id)
            text = load_text(indicator, lang)
            # A fan chart's line labels are text for readers: they live in the
            # page's front matter and travel to the chart inside its JSON.
            for key in ("fan_labels", "fan_short"):
                if key in text:
                    data[key] = text[key]
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
                peer_average=peer_average_text(indicator, data, s, lang),
                forecast=forecast_text(data, s, lang),
                expected=expected_text(data, s, lang),
                related=related_link(indicator, by_id, text, lang),
                compare_url=compare_url(indicator, by_id, lang),
                json_url=json_url,
                other_url=page_url(indicator, other),
                nav=nav_links(lang, indicator.section, section_texts),
                back={
                    "url": section_url(indicator.section, lang),
                    "name": section_texts[indicator.section]["title"],
                },
            )
            write(dist / url.strip("/") / "index.html", html, dist)
            metric_pages.append({"url": url, "title": data["title"]})
            tiles[indicator.id] = tile_view(indicator, data, text, s, lang)

        for name, section in sections.items():
            texts = section_texts[name]
            groups = [
                {
                    "id": group.id,
                    "name": texts["groups"][group.id]["name"],
                    "intro": texts["groups"][group.id]["intro"],
                    "tiles": [tiles[i] for i in group.indicators],
                }
                for group in section.groups
            ]
            listed = [tile for group in groups for tile in group["tiles"]]
            counts = {
                key: sum(1 for t in listed if (t["pill"] or {}).get("class") == key)
                for key in ("good", "watch", "bad")
            }
            # "melhorando" counts only the tiles that improved, not "Piorando".
            counts["trend"] = sum(
                1 for t in listed if (t["pill"] or {}).get("improving")
            )
            page = env.get_template("section.html").render(
                lang=lang,
                s=s,
                text=texts,
                groups=groups,
                counts=counts,
                updated=date_long(date.today(), lang),
                other_url=section_url(name, other),
                nav=nav_links(lang, name, section_texts),
            )
            write(dist / section_url(name, lang).strip("/") / "index.html", page, dist)

        home = env.get_template("home.html").render(
            lang=lang,
            s=s,
            metric_pages=metric_pages,
            other_url=f"/{other}/",
            nav=nav_links(lang, "home", section_texts),
        )
        write(dist / lang / "index.html", home, dist)

    shutil.copytree(STATIC, dist / "static", dirs_exist_ok=True)
    (dist / "_redirects").write_text("/  /pt/  302\n", encoding="utf-8")


if __name__ == "__main__":
    main()
