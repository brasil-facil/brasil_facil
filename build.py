import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).parent
TEMPLATES = ROOT / "site_src" / "templates"
DIST = ROOT / "dist"

PAGES = {
    "pt": {
        "lang": "pt-BR",
        "coming_soon": "Em breve.",
        "description": "Aqui você vai ver como o Brasil está: economia, dinheiro público, saúde, educação e segurança. Tudo com dados oficiais e em palavras simples.",
        "other_url": "/en/",
        "other_lang": "en",
        "other_name": "English",
    },
    "en": {
        "lang": "en",
        "coming_soon": "Coming soon.",
        "description": "Here you will see how Brazil is doing: economy, public money, health, education and safety. All with official data, in simple words.",
        "other_url": "/pt/",
        "other_lang": "pt-BR",
        "other_name": "Português",
    },
}


def main() -> None:

    shutil.rmtree(DIST, ignore_errors=True)

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=True,
        undefined=StrictUndefined,
    )
    template = env.get_template("base.html")

    for folder, values in PAGES.items():
        html = template.render(**values)
        out = DIST / folder / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}")

    # Copy static files
    shutil.copytree(ROOT / "site_src" / "static", DIST / "static", dirs_exist_ok=True)

    (DIST / "_redirects").write_text("/  /pt/  302\n", encoding="utf-8")


if __name__ == "__main__":
    main()
