"""
Trend analysis: annual change in evitable mortality by province.

Method: negative binomial regression with log(population) as offset.
This accounts for overdispersion commonly seen in mortality count data.

The model is: log(E[deaths]) = β₀ + β₁·ANIO + log(population)

Coefficient β₁ (coef_anio) represents the log rate ratio per year.
cambio_pct_anual = (exp(β₁) - 1) × 100 gives the percentage change per year.
Negative values mean evitable mortality is declining.

Requires: statsmodels >= 0.13
"""

import warnings
import numpy as np
import pandas as pd

try:
    import statsmodels.formula.api as smf
    _HAS_STATSMODELS = True
except ImportError:
    _HAS_STATSMODELS = False
    warnings.warn(
        "statsmodels not installed. Trend analysis will be skipped.\n"
        "Install with: pip install statsmodels"
    )


def fit_trends(
    std_rates: pd.DataFrame,
    sexo: int = 0,
    min_years: int = 5,
) -> pd.DataFrame:
    """
    Fit a negative binomial trend model for each province.

    Parameters
    ----------
    std_rates  : output of rates.add_ambos_sexos() or rates.standardise()
    sexo       : 0=both, 1=male, 2=female
    min_years  : minimum number of data points required to fit (default 5)

    Returns
    -------
    DataFrame with one row per province:
      PROVRES, PROV_NOMBRE, n_anios, coef_anio,
      cambio_pct_anual, p_valor, ic_inf_log, ic_sup_log, converged
    """
    if not _HAS_STATSMODELS:
        return pd.DataFrame()

    subset = std_rates[std_rates["SEXO"] == sexo].copy()
    subset = subset.sort_values("ANIO")

    results = []
    for (provres, prov_nombre), grp in subset.groupby(["PROVRES", "PROV_NOMBRE"]):
        grp = grp.dropna(subset=["DEF_EVITABLES", "POB_TOTAL"])

        if len(grp) < min_years:
            warnings.warn(f"{prov_nombre}: only {len(grp)} years, skipping trend.")
            continue
        if grp["DEF_EVITABLES"].sum() == 0:
            warnings.warn(f"{prov_nombre}: zero evitable deaths, skipping trend.")
            continue

        # Round counts for count model (fractional due to IHD 0.5 weight)
        grp = grp.copy()
        grp["DEF_INT"] = grp["DEF_EVITABLES"].round().astype(int)

        converged = True
        try:
            model = smf.negativebinomial(
                "DEF_INT ~ ANIO",
                data=grp,
                exposure=grp["POB_TOTAL"],
            ).fit(disp=False, maxiter=200)
        except Exception as exc:
            warnings.warn(f"{prov_nombre}: model failed ({exc}). Trying Poisson fallback.")
            try:
                model = smf.poisson(
                    "DEF_INT ~ ANIO",
                    data=grp,
                    exposure=grp["POB_TOTAL"],
                ).fit(disp=False)
            except Exception as exc2:
                warnings.warn(f"{prov_nombre}: Poisson fallback also failed ({exc2}). Skipping.")
                continue
            converged = False

        ci = model.conf_int()
        results.append({
            "PROVRES":          provres,
            "PROV_NOMBRE":      prov_nombre,
            "n_anios":          len(grp),
            "coef_anio":        model.params["ANIO"],
            "cambio_pct_anual": (np.exp(model.params["ANIO"]) - 1) * 100,
            "p_valor":          model.pvalues["ANIO"],
            "ic_inf_log":       ci.loc["ANIO", 0],
            "ic_sup_log":       ci.loc["ANIO", 1],
            "converged":        converged,
        })

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values("cambio_pct_anual").reset_index(drop=True)
    return df
