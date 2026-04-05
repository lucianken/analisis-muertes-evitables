"""
Classify death records as evitable or not by joining with the evitable cause table.

Conditions for a death to be evitable:
  1. ICD-10 cause code (3 chars) matches a row in evitable_df.
  2. EDAD_MIN (canonical age group lower bound) is within [edad_min, edad_max].
  3. If sexo_restriccion is set, SEXO must match.

For ischemic heart disease (fraccion=0.5), CUENTA is multiplied by 0.5 before
aggregation, following Nolte & McKee's convention.

The output 'evitables' DataFrame has one row per original death record that
passed all three conditions, with an additional CUENTA_EVITABLE column.
"""

import pandas as pd


def classify(deaths: pd.DataFrame, evitable_df: pd.DataFrame) -> pd.DataFrame:
    """
    Parameters
    ----------
    deaths : output of load.load_all()
    evitable_df : output of causes.get_evitable_df()

    Returns
    -------
    DataFrame of evitable deaths with CUENTA_EVITABLE column.
    """
    merged = deaths.merge(evitable_df, on="CAUSA", how="left")

    # Boolean mask: death matched a cause AND passes age and sex filters
    matched   = merged["edad_max"].notna()
    age_ok    = (merged["EDAD_MIN"] >= merged["edad_min"]) & \
                (merged["EDAD_MIN"] <= merged["edad_max"])
    sex_ok    = merged["sexo_restriccion"].isna() | \
                (merged["SEXO"] == merged["sexo_restriccion"])

    evitables = merged[matched & age_ok & sex_ok].copy()

    # Apply cause fraction (1.0 for all causes except ischemic heart disease = 0.5)
    evitables["CUENTA_EVITABLE"] = evitables["CUENTA"] * evitables["fraccion"]

    return evitables


def aggregate_evitable(evitables: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate evitable deaths to (ANIO, PROVRES, PROV_NOMBRE, SEXO, EDAD_MIN).
    This is the granularity needed for age-standardisation.
    """
    return (
        evitables
        .groupby(["ANIO", "PROVRES", "PROV_NOMBRE", "SEXO", "EDAD_MIN"],
                 as_index=False)["CUENTA_EVITABLE"]
        .sum()
        .rename(columns={"CUENTA_EVITABLE": "DEF_EVITABLES"})
    )
