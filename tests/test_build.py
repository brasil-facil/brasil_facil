import json

import build


def test_number_format_per_language():
    assert build.number(4.58, "pt") == "4,58"
    assert build.number(4.58, "en") == "4.58"
    assert build.number(1234.5, "pt") == "1.235"  # big amounts: no decimals
    assert build.number(19967.59, "en") == "19,968"
    assert build.number(4.5, "pt") == "4,5"
    assert build.number(10.0, "en") == "10"


def test_month_format_per_language():
    assert build.month_short("2026-09", "pt") == "set/2026"
    assert build.month_long("2026-09", "pt") == "setembro de 2026"
    assert build.month_long("2026-09", "en") == "September 2026"


def test_build_writes_both_languages(tmp_path):
    build.main(tmp_path)
    pt = (tmp_path / "pt" / "economia" / "inflacao" / "index.html").read_text(
        encoding="utf-8"
    )
    en = (tmp_path / "en" / "economy" / "inflation" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'lang="pt-BR"' in pt and 'href="/en/economy/inflation/"' in pt
    assert 'lang="en"' in en and 'href="/pt/economia/inflacao/"' in en
    assert "Atenção" in pt and "Watch" in en
    data = json.loads(
        (tmp_path / "data" / "en" / "inflacao.json").read_text(encoding="utf-8")
    )
    assert data["lang"] == "en"
    assert (tmp_path / "static" / "echarts.min.js").exists()
    assert (tmp_path / "_redirects").read_text(encoding="utf-8") == "/  /pt/  302\n"


def test_build_writes_the_inpc_page_with_ipca_next_to_it(tmp_path):
    build.main(tmp_path)
    pt = (tmp_path / "pt" / "economia" / "inpc" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "Sem meta" in pt
    assert "IPCA no mesmo mês" in pt
    home = (tmp_path / "pt" / "index.html").read_text(encoding="utf-8")
    assert "/pt/economia/inpc/" in home and "/pt/economia/inflacao/" in home


def test_ipca_page_links_to_inpc_with_its_value(tmp_path):
    build.main(tmp_path)
    pt = (tmp_path / "pt" / "economia" / "inflacao" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'href="/pt/economia/inpc/"' in pt
    assert "usado no reajuste do salário mínimo" in pt


def test_rolling_quarter_periods():
    assert build.period_short("2026-08", "pt", "rolling_quarter") == "jun–ago/2026"
    assert build.period_long("2026-08", "pt", "rolling_quarter") == (
        "junho a agosto de 2026"
    )
    assert build.period_long("2026-01", "en", "rolling_quarter") == (
        "November 2025 to January 2026"
    )
    assert build.period_short("2026-09", "pt") == "set/2026"


def test_change_text():
    s = build.load_strings()["pt"]
    assert build.change_text(-0.3, s, "pt") == "0,3 ponto menor do que um ano antes"
    assert build.change_text(2.4, s, "pt") == "2,4 pontos maior do que um ano antes"
    assert build.change_text(None, s, "pt") is None


def test_selic_pages_link_both_ways_without_no_target_pill(tmp_path):
    build.main(tmp_path)
    selic = (tmp_path / "pt" / "economia" / "selic" / "index.html").read_text(
        encoding="utf-8"
    )
    real = (tmp_path / "pt" / "economia" / "juro-real" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "Sem meta" not in selic and "Sem meta" not in real
    assert 'href="/pt/economia/juro-real/"' in selic
    assert 'href="/pt/economia/selic/"' in real


def test_inflation_page_has_country_buttons(tmp_path):
    build.main(tmp_path)
    pt = (tmp_path / "pt" / "economia" / "inflacao" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "Comparar com" in pt
    assert 'data-geo="MEX" aria-pressed="true"' in pt
    assert 'data-geo="USA" aria-pressed="false"' in pt
    assert "FMI:" in pt and "OCDE:" in pt
