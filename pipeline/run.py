import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from pipeline import store
from pipeline.export import TARGETS_DIR, zone_table
from pipeline.models import Indicator, load_indicator
from pipeline.sources import sidra

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
SOURCES = {"sidra": sidra}


def load_all_indicators(config_dir: Path = CONFIG_DIR) -> list[Indicator]:
    return [load_indicator(path) for path in sorted(config_dir.glob("*/*.yaml"))]


def update_indicator(
    indicator: Indicator,
    full: bool,
    today: str,
    series_dir: Path = store.SERIES_DIR,
) -> tuple[int, int]:
    ref = indicator.series.brazil
    sid = ref.series_id
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
    return zone_table(indicator, series_dir, targets_dir).iloc[-1]


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
                f"{latest['period']} {latest['value']} ({latest['zone'] or 'no zone'})"
            )
        except Exception as error:  # noqa: BLE001 (fail soft: one source must not stop the others)
            failures += 1
            print(f"{indicator.id:<14}FAILED: {error}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
