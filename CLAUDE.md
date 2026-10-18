# Brasil Fácil

A free, public website that explains how Brazil is doing (economy, public money,
health, education, public safety) in plain language, using official data
(IBGE, Banco Central, Tesouro, OECD, IMF, World Bank) and comparing Brazil with
other countries. The site is in Portuguese first, with an English translation.

## How to work with me

- I am building this myself to learn. Start with an explanation or a hint and
  let me try first.
- When I ask for help writing code, write it in small pieces and explain every
  line, so I understand everything I commit. Never write whole features or many
  files at once.
- When you review, tell me what is wrong and why, then let me fix it.
- Keep explanations short and concrete. I know Python and Java, and I have an
  econometrics and quantitative finance background.
- I work on Windows with PowerShell. Give commands that work there.

## Reference documents

Read these before suggesting a design. If they disagree, the technical design wins.

- `docs/technical-design.md`: stack, folder layout, data model, pipeline,
  zones, site build, automation, hosting, and the build roadmap (phases 1 to 8).
- `docs/data-sources-economy.md`: economic sources (IBGE, BCB, OECD, BIS, IMF,
  World Bank), series codes and example queries.
- `docs/data-sources-public-services.md`: public spending, schools, health,
  public safety, and how to fetch each source efficiently.
- `docs/design/`: the visual identity guide and the Resumo page mockup (HTML).
  Read `docs/design/README.md` first; it says which colors are final.

`docs/` is not committed (it's in `.gitignore`), so it only exists on my laptop.

## Tools and commands

- Python 3.12, managed with **uv**. Never use pip, venv or requirements.txt.
  - Add a package: `uv add <name>` (dev tools: `uv add --dev <name>`)
  - Run anything: `uv run ...`, e.g. `uv run python build.py`, `uv run pytest`
  - Lint and format: `uv run ruff check .` and `uv run ruff format .`
- Build the site: `uv run python build.py` writes the finished site to `dist/`.
- Preview locally: `uv run python -m http.server -d dist 8000`, then open
  http://localhost:8000/pt/

## Stack

Python ETL (requests, pandas) -> CSV files in `data/` -> Jinja2 templates ->
static HTML in `dist/` with Apache ECharts charts. Hosted on Cloudflare Pages;
data refreshed monthly by GitHub Actions. No database, no server, no secrets
in the repository.

## Folder layout

- `config/` one YAML file per indicator, grouped by section
- `pipeline/` everything that downloads and processes data
- `data/` processed data, committed (`data/raw/` is not committed)
- `content/pt/`, `content/en/` page texts
- `site_src/templates/`, `site_src/static/` HTML templates, CSS, JS
- `build.py` renders everything into `dist/` (`dist/` is not committed)
- `tests/` pytest tests

Rules: only `pipeline/` writes to `data/`; only `build.py` writes to `dist/`.

## Writing for readers

- The reader finished primary school. Use everyday words.
- Never use jargon or acronyms alone: say "inflação (preços subindo)", not
  just "IPCA".
- Stay politically neutral: describe what the data shows, never call a
  government or policy good or bad.

## Git

- Work on a branch, open a pull request, merge after review. Never push
  directly to `main`.
- Commit messages in Portuguese or English, short and descriptive.
