import shutil
from pathlib import Path

from pipeline import run
from pipeline.sources import sidra

FIXTURE = Path(__file__).parent / "fixtures" / "sidra_1737-v2265.json"
CONFIG = Path(__file__).parents[1] / "config"


def by_id(indicators):
    return {indicator.id: indicator for indicator in indicators}


def fake_fetch(tmp_path: Path, asked: list[str]):
    def fetch(code: str, geo: str, periods: str) -> list[Path]:
        asked.append(periods)
        copy = tmp_path / "raw.json"
        shutil.copy(FIXTURE, copy)
        return [copy]

    return fetch


def test_update_indicator_full_first_then_recent(tmp_path, monkeypatch):
    asked: list[str] = []
    monkeypatch.setattr(sidra, "fetch", fake_fetch(tmp_path, asked))
    indicator = by_id(run.load_all_indicators(CONFIG))["inflacao"]
    series_dir = tmp_path / "series"

    assert run.update_indicator(indicator, False, "2026-10-19", series_dir) == (550, 0)
    assert run.update_indicator(indicator, False, "2026-10-26", series_dir) == (0, 0)
    assert asked == ["all", "last 6"]
    assert not (tmp_path / "raw.json").exists()


def test_latest_zone_is_september_2026_yellow(tmp_path, monkeypatch):
    monkeypatch.setattr(sidra, "fetch", fake_fetch(tmp_path, []))
    indicator = by_id(run.load_all_indicators(CONFIG))["inflacao"]
    series_dir = tmp_path / "series"
    run.update_indicator(indicator, False, "2026-10-19", series_dir)

    latest = run.latest_zone(indicator, series_dir)
    assert (latest["period"], latest["value"], latest["zone"]) == (
        "2026-09",
        4.58,
        "yellow",
    )
