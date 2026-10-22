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


def real_value(nominal: pd.DataFrame, price_index: pd.DataFrame) -> pd.DataFrame:
    """An amount in money of the latest month: today's purchasing power.

    value x (price index of the latest month / price index of that month).
    Monthly amounts: only months present in both series are kept; the latest
    of them is the base, so the newest value is the same as the official one.
    Yearly amounts ("a preços médios do ano", e.g. income from IBGE's yearly
    survey) use the year's average index, and the latest month as the base,
    so they are in the same money as monthly pages.
    """
    yearly = nominal["period"].str.len().eq(4).all()
    if yearly:
        months = price_index.assign(period=price_index["period"].str[:4])
        complete = months.groupby("period")["value"].count() == 12
        averages = months.groupby("period")["value"].mean()[complete].reset_index()
        both = nominal.merge(averages, on="period", suffixes=("_nominal", "_index"))
        base = price_index.sort_values("period")["value"].iloc[-1]
        value = both["value_nominal"] * base / both["value_index"]
        return pd.DataFrame({"period": both["period"], "value": value.round(2)})
    both = nominal.merge(price_index, on="period", suffixes=("_nominal", "_index"))
    base = both["value_index"].iloc[-1]
    value = both["value_nominal"] * base / both["value_index"]
    return pd.DataFrame({"period": both["period"], "value": value.round(2)})
