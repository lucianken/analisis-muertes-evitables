"""
Crude rates, age-standardised rates, and Poisson confidence intervals.

All rates are expressed per 100,000 person-years.

Age-standardisation method: direct standardisation using WHO World Standard
Population weights (see population.py).

Confidence intervals: Byar's approximation for Poisson counts (Breslow & Day 1987).
Applied to the observed total evitable deaths, then scaled to the standardised rate.
"""

import numpy as np
import pandas as pd

from population import get_standard_population


SCALE = 100_000   # rates per 100,000


# ── Byar confidence interval ─────────────────────────────────────────────────

def _byar_ci(d: np.ndarray, n: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Byar's approximation for 95% CI on a crude Poisson rate d/n.

    Parameters
    ----------
    d : observed event count (may be fractional due to the 0.5 fraction on IHD)
    n : population at risk

    Returns
    -------
    (lower, upper) — both on the same scale as d/n * SCALE
    """
    d = np.maximum(d, 0.5)   # continuity correction for zero counts
    lower = d * (1 - 1 / (9 * d) - 1.96 / np.sqrt(9 * d)) ** 3 / n * SCALE
    upper = (d + 1) * (1 - 1 / (9 * (d + 1)) + 1.96 / np.sqrt(9 * (d + 1))) ** 3 / n * SCALE
    return lower, upper


# ── Crude rates ───────────────────────────────────────────────────────────────

def compute_crude_rates(
    evitable_agg: pd.DataFrame,
    population: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute age-specific crude rates.

    Parameters
    ----------
    evitable_agg : output of classify.aggregate_evitable()
                   columns: ANIO, PROVRES, PROV_NOMBRE, SEXO, EDAD_MIN, DEF_EVITABLES
    population   : output of population.load_population()
                   columns: PROVRES, ANIO, SEXO, EDAD_MIN, POBLACION

    Returns
    -------
    DataFrame with TASA_CRUDA added (per 100,000).
    """
    merged = evitable_agg.merge(
        population,
        on=["PROVRES", "ANIO", "SEXO", "EDAD_MIN"],
        how="left",
    )

    missing_pop = merged["POBLACION"].isna().sum()
    if missing_pop > 0:
        import warnings
        warnings.warn(
            f"{missing_pop} age-group/year/province/sex cells have no population data. "
            "Rates for those cells will be NaN."
        )

    merged["TASA_CRUDA"] = merged["DEF_EVITABLES"] / merged["POBLACION"] * SCALE
    return merged


# ── Age-standardised rates ────────────────────────────────────────────────────

def standardise(crude: pd.DataFrame) -> pd.DataFrame:
    """
    Directly age-standardise crude rates using WHO World Standard Population.

    The function produces one row per (ANIO, PROVRES, PROV_NOMBRE, SEXO) with:
      TASA_STD         — directly standardised rate per 100,000
      DEF_EVITABLES    — total observed evitable deaths
      POB_TOTAL        — total observed population
      TASA_CRUDA_TOTAL — overall crude rate (DEF_EVITABLES / POB_TOTAL * 100k)
      IC_INF, IC_SUP   — Byar 95% CI on TASA_STD (scaled from total observed counts)

    The CI is computed on the total observed counts and then scaled to approximate
    the uncertainty of the standardised rate — appropriate when all age cells are
    from the same geographic/demographic unit.
    """
    std_pop = get_standard_population()

    data = crude.merge(std_pop, on="EDAD_MIN", how="left")

    missing_weights = data["PESO_STD"].isna().sum()
    if missing_weights > 0:
        import warnings
        warnings.warn(f"{missing_weights} rows have no standard population weight.")

    data["CONTRIBUCION"] = data["TASA_CRUDA"] * data["PESO_STD"]

    grp_cols = ["ANIO", "PROVRES", "PROV_NOMBRE", "SEXO"]
    result = (
        data
        .groupby(grp_cols, as_index=False)
        .agg(
            TASA_STD=("CONTRIBUCION",   "sum"),
            DEF_EVITABLES=("DEF_EVITABLES", "sum"),
            POB_TOTAL=("POBLACION",     "sum"),
        )
    )

    result["TASA_CRUDA_TOTAL"] = result["DEF_EVITABLES"] / result["POB_TOTAL"] * SCALE

    lower, upper = _byar_ci(result["DEF_EVITABLES"].values,
                            result["POB_TOTAL"].values)

    # Scale CI from crude rate to standardised rate
    scale_factor = np.where(
        result["TASA_CRUDA_TOTAL"] > 0,
        result["TASA_STD"] / result["TASA_CRUDA_TOTAL"],
        1.0,
    )
    result["IC_INF"] = lower * scale_factor
    result["IC_SUP"] = upper * scale_factor

    return result


# ── Both-sexes combined ───────────────────────────────────────────────────────

def add_ambos_sexos(std_rates: pd.DataFrame, crude: pd.DataFrame) -> pd.DataFrame:
    """
    Append rows with SEXO=0 (both sexes combined) to the standardised rate table.
    """
    both_crude = (
        crude
        .groupby(["ANIO", "PROVRES", "PROV_NOMBRE", "EDAD_MIN"], as_index=False)
        .agg(DEF_EVITABLES=("DEF_EVITABLES", "sum"),
             POBLACION=("POBLACION", "sum"))
    )
    both_crude["SEXO"] = 0
    both_crude["TASA_CRUDA"] = both_crude["DEF_EVITABLES"] / both_crude["POBLACION"] * SCALE

    both_std = standardise(both_crude)

    return pd.concat([std_rates, both_std], ignore_index=True)
