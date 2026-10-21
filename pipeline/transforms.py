"""Numbers computed from stored series. Never stored: recomputed on every run,
so a revision upstream flows through by itself (design: "Derive")."""

import pandas as pd


def real_rate(selic: pd.DataFrame, expected_inflation: pd.DataFrame) -> pd.DataFrame:
    """Ex-ante real interest rate, in % a year.

    (1 + Selic) / (1 + inflation expected for the next 12 months) - 1.
    Only months present in both series are kept.
    """
    both = selic.merge(expected_inflation, on="period", suffixes=("_selic", "_exp"))
    value = ((1 + both["value_selic"] / 100) / (1 + both["value_exp"] / 100) - 1) * 100
    return pd.DataFrame({"period": both["period"], "value": value.round(2)})
