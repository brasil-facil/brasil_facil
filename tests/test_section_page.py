import build
from pipeline.export import tile_data
from pipeline.models import load_sections


def chart(points, zones=None):
    return {"points": points, "point_zones": zones or [None] * len(points)}


def test_tiles_use_the_last_period_of_each_year():
    data = chart(
        [["2024-06", 4.0], ["2024-12", 4.8], ["2025-06", 5.0], ["2025-12", 4.2]],
        ["green", "yellow", "yellow", "green"],
    )
    tile = tile_data(data)
    assert tile["years"] == ["2024", "2025"]
    assert tile["values"] == [4.8, 4.2]  # December of each year
    assert tile["zones"] == ["yellow", "green"]
    assert tile["direction"] == "down"  # 4.2 against 4.8 a year earlier


def test_improving_years_count_rises_only_when_higher_is_better():
    data = chart([["2023", 10.0], ["2024", 12.0], ["2025", 11.0]])
    assert tile_data(data, higher_is_better=True)["better_years"] == 1
    assert tile_data(data, higher_is_better=False)["better_years"] == 1  # 12 -> 11
    assert tile_data(data)["compared_years"] == 2


def test_every_indicator_is_in_one_group_of_the_section_page():
    sections = load_sections(build.SECTIONS_FILE)
    listed = [i for group in sections["economia"].groups for i in group.indicators]
    files = sorted(p.stem for p in (build.CONFIG / "economia").glob("*.yaml"))
    assert sorted(listed) == files and len(listed) == len(set(listed))


def test_section_page(tmp_path):
    build.main(tmp_path)
    page = (tmp_path / "pt" / "economia" / "index.html").read_text("utf-8")
    assert 'Como está a <span class="accent">economia</span> do Brasil?' in page
    for name in ("Trabalho", "Preços e juros", "Produção"):
        assert f">{name}</h2>" in page
    assert 'href="/pt/economia/inflacao/"' in page  # a tile opens its own page
    assert (
        '<h3 class="tile-name">Aumento dos preços</h3>' in page
    )  # the short tile name
    assert '<h3 class="tile-name">Economic growth</h3>' in (
        tmp_path / "en" / "economy" / "index.html"
    ).read_text("utf-8")
    assert "Melhorando" in page and "Piorando" in page  # higher_is_better tiles
    assert "</b> piorando</span>" in page  # a worsening tile is counted too
    # Preços e juros has 5 tiles: one empty "coming next" box completes row 2.
    assert page.count('class="tile tile-soon"') == 1
    assert "Subiu em relação a um ano antes" in page or "Caiu em relação" in page
    assert '<a href="/pt/economia/" aria-current="page">Economia</a>' in page
    en = (tmp_path / "en" / "economy" / "index.html").read_text("utf-8")
    assert (
        'How is Brazil&#39;s <span class="accent">economy</span> doing?' in en
        and ">Work</h2>" in en
    )
    indicator = (tmp_path / "pt" / "economia" / "inflacao" / "index.html").read_text(
        "utf-8"
    )
    assert "Voltar para Economia" in indicator and 'class="metric-main"' in indicator


def test_dates_in_both_languages():
    from datetime import date

    assert build.date_long(date(2026, 10, 23), "pt") == "23 de outubro de 2026"
    assert build.date_long(date(2026, 10, 23), "en") == "23 October 2026"


def test_explanation_is_split_by_heading_not_order():
    body = "\n## Why does it matter?\nBecause.\n\n## What is it?\nA thing.\n" + "".join(
        f"\n## {h}\nText.\n"
        for h in (
            "How is it calculated?",
            "How to read the chart?",
            "Where does it come from?",
        )
    )
    sections = build.split_sections(body, "en", build.CONTENT / "x.md")
    assert sections["what"]["html"] == "<p>A thing.</p>"
    assert sections["why"]["heading"] == "Why does it matter?"


def test_unknown_heading_stops_the_build():
    import pytest

    with pytest.raises(ValueError, match="unknown heading"):
        build.split_sections(
            "\n## O que é isso?\nTexto.\n", "pt", build.CONTENT / "x.md"
        )


def test_home_page_shows_the_sections_and_how_we_work(tmp_path):
    build.main(tmp_path)
    home = (tmp_path / "pt" / "index.html").read_text("utf-8")
    assert 'href="/pt/economia/"' in home and "11 números" in home  # live section
    assert home.count('<span class="pill soon">Em breve</span>') == 4
    assert "Como trabalhamos" in home and "Sem opinião" in home
    assert build.REPO_URL in home
    assert '<a href="/pt/" aria-current="page">Início</a>' in home
    en = (tmp_path / "en" / "index.html").read_text("utf-8")
    assert "How we work" in en and "Coming soon" in en


def test_economia_tab_has_a_dropdown_with_every_indicator(tmp_path):
    build.main(tmp_path)
    page = (tmp_path / "pt" / "index.html").read_text("utf-8")
    menu = page.split('<div class="nav-menu">', 1)[1].split("</nav>", 1)[0]
    assert menu.count('<div class="nav-menu-group">') == 3  # the three groups
    assert '<a href="/pt/economia/desemprego/">Desemprego</a>' in menu
    assert menu.count("<a href=") == 11  # every indicator, by its tile name


def test_accent_marks_one_word_and_still_escapes():
    assert str(build.accent("a *b* c")) == 'a <span class="accent">b</span> c'
    assert str(build.accent("<i>")) == "&lt;i&gt;"


def test_home_and_section_pages_say_the_picture_is_not_complete(tmp_path):
    build.main(tmp_path)
    for page in ("pt/index.html", "pt/economia/index.html", "en/economy/index.html"):
        assert 'class="note-wip"' in (tmp_path / page).read_text("utf-8"), page
