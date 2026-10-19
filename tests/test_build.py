import json

import build


def test_number_format_per_language():
    assert build.number(4.58, "pt") == "4,58"
    assert build.number(4.58, "en") == "4.58"
    assert build.number(1234.5, "pt") == "1.234,5"
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
