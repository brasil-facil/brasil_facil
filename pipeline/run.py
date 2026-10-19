import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from pipeline import store
from pipeline.models import (
    Indicator,
    SeriesRef,
    load_indicator,
    load_indicator_targets,
)
from pipeline.sources import sidra
from pipeline.zones import compute_zones

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
TARGETS_DIR = ROOT / "data" / "targets"
SOURCES = {"sidra": sidra}


def series_id(ref: SeriesRef) -> str:
    return f"{ref.source}.{ref.code}.{ref.geo}"


def load_all_indicators(config_dir: Path = CONFIG_DIR) -> list[Indicator]:
    return [load_indicator(path) for path in sorted(config_dir.glob("*/*.yaml"))]


def update_indicator(
    indicator: Indicator,
    full: bool,
    today: str,
    series_dir: Path = store.SERIES_DIR,
) -> tuple[int, int]:
    ref = indicator.series.brazil
    sid = series_id(ref)
    source = SOURCES[ref.source]
    first_time = not store.series_path(sid, series_dir).exists()
    periods = source.FULL_PERIODS if full or first_time else source.RECENT_PERIODS
    files = source.fetch(ref.code, ref.geo, periods)
    try:
        parsed = source.parse(files, sid)
    finally:
        for file in files:
            file.unlink(missing_ok=True)
    return store.update_series(sid, parsed, today, series_dir)


def latest_zone(
    indicator: Indicator,
    series_dir: Path = store.SERIES_DIR,
    targets_dir: Path = TARGETS_DIR,
) -> pd.Series:
    sid = series_id(indicator.series.brazil)
    current = store.current_values(
        store.read_history(store.series_path(sid, series_dir))
    )
    values = current.reset_index()
    targets = load_indicator_targets(targets_dir / f"{indicator.zones.target}.csv")
    return compute_zones(values, targets, indicator.zones).iloc[-1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update Brasil Fácil data.")
    parser.add_argument(
        "--full", action="store_true", help="download the full history again"
    )
    args = parser.parse_args(argv)
    today = date.today().isoformat()

    indicators = load_all_indicators()
    failures = 0
    print(f"{'indicator':<14}{'new':>6}{'revised':>9}  latest")
    for indicator in indicators:
        try:
            new, revised = update_indicator(indicator, args.full, today)
            latest = latest_zone(indicator)
            print(
                f"{indicator.id:<14}{new:>6}{revised:>9}  "
                f"{latest['period']} {latest['value']} ({latest['zone']})"
            )
        except Exception as error:  # noqa: BLE001 (fail soft: one source must not stop the others)
            failures += 1
            print(f"{indicator.id:<14}FAILED: {error}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
