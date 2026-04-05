"""
export_analysis_tables.py — genera tablas adicionales para el reporte.

Ejecutar desde la raíz del proyecto:
    python scripts/export_analysis_tables.py

Genera en output/tables/:
  national_series.csv        — tasa estandarizada nacional por año × sexo
  evitable_by_cause.csv      — defunciones evitables por grupo de causa × año
  evitable_by_agegroup.csv   — defunciones evitables por grupo etario × año (nacional)
  trend_by_province.csv      — cambio % anual por provincia (binomial negativa)
  cv_by_year.csv             — coeficiente de variación interprovincial por año
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from config      import DATA_PROCESSED, DATA_REFERENCE, OUTPUT_TABLES
from load        import load_all
from causes      import get_evitable_df
from classify    import classify
from population  import load_population, get_standard_population
from rates       import compute_crude_rates, standardise, add_ambos_sexos
from trends      import fit_trends


SCALE = 100_000


# ── Helpers ───────────────────────────────────────────────────────────────────

def _byar_ci(d, n):
    d = np.maximum(np.asarray(d, float), 0.5)
    lo = d * (1 - 1/(9*d) - 1.96/np.sqrt(9*d))**3 / n * SCALE
    hi = (d+1) * (1 - 1/(9*(d+1)) + 1.96/np.sqrt(9*(d+1)))**3 / n * SCALE
    return lo, hi


# ── 1. National series ────────────────────────────────────────────────────────

def build_national_series(evitable_agg, pop):
    """
    Directly standardised national rate by year × sex (0=both, 1=M, 2=F).
    Pooled across all provinces, then standardised with WHO weights.
    """
    std_pop = get_standard_population()

    # Male + Female by age group (national total)
    nat = (
        evitable_agg
        .groupby(["ANIO", "SEXO", "EDAD_MIN"], as_index=False)["DEF_EVITABLES"]
        .sum()
    )
    nat_pop = (
        pop
        .groupby(["ANIO", "SEXO", "EDAD_MIN"], as_index=False)["POBLACION"]
        .sum()
    )
    merged = nat.merge(nat_pop, on=["ANIO", "SEXO", "EDAD_MIN"], how="left")
    merged["TASA_CRUDA"] = merged["DEF_EVITABLES"] / merged["POBLACION"] * SCALE

    data = merged.merge(std_pop, on="EDAD_MIN", how="left")
    data["CONTRIB"] = data["TASA_CRUDA"] * data["PESO_STD"]

    by_sex = (
        data
        .groupby(["ANIO", "SEXO"], as_index=False)
        .agg(TASA_STD=("CONTRIB", "sum"),
             DEF_EVITABLES=("DEF_EVITABLES", "sum"),
             POB_TOTAL=("POBLACION", "sum"))
    )
    by_sex["TASA_CRUDA_TOTAL"] = by_sex["DEF_EVITABLES"] / by_sex["POB_TOTAL"] * SCALE

    # Both sexes combined
    both_nat = (
        evitable_agg
        .groupby(["ANIO", "EDAD_MIN"], as_index=False)["DEF_EVITABLES"]
        .sum()
        .assign(SEXO=0)
    )
    both_pop = (
        pop
        .groupby(["ANIO", "EDAD_MIN"], as_index=False)["POBLACION"]
        .sum()
        .assign(SEXO=0)
    )
    bm = both_nat.merge(both_pop, on=["ANIO", "EDAD_MIN", "SEXO"], how="left")
    bm["TASA_CRUDA"] = bm["DEF_EVITABLES"] / bm["POBLACION"] * SCALE
    bd = bm.merge(std_pop, on="EDAD_MIN", how="left")
    bd["CONTRIB"] = bd["TASA_CRUDA"] * bd["PESO_STD"]
    both = (
        bd
        .groupby(["ANIO", "SEXO"], as_index=False)
        .agg(TASA_STD=("CONTRIB", "sum"),
             DEF_EVITABLES=("DEF_EVITABLES", "sum"),
             POB_TOTAL=("POBLACION", "sum"))
    )
    both["TASA_CRUDA_TOTAL"] = both["DEF_EVITABLES"] / both["POB_TOTAL"] * SCALE

    result = pd.concat([by_sex, both], ignore_index=True)

    lo, hi = _byar_ci(result["DEF_EVITABLES"].values, result["POB_TOTAL"].values)
    sf = np.where(result["TASA_CRUDA_TOTAL"] > 0,
                  result["TASA_STD"] / result["TASA_CRUDA_TOTAL"], 1.0)
    result["IC_INF"] = lo * sf
    result["IC_SUP"] = hi * sf

    return result.sort_values(["ANIO", "SEXO"]).reset_index(drop=True)


# ── 2. By cause group ────────────────────────────────────────────────────────

# Broad grouping of the 36 Nolte & McKee cause categories
_CAUSE_GROUP = {
    "Infecciones intestinales":                     "Infecciosas",
    "Tuberculosis y secuelas":                      "Infecciosas",
    "Difteria":                                     "Infecciosas",
    "Tétanos":                                      "Infecciosas",
    "Poliomielitis":                                "Infecciosas",
    "Tos convulsa":                                 "Infecciosas",
    "Septicemia":                                   "Infecciosas",
    "Sarampión":                                    "Infecciosas",
    "Ca. colon y recto":                            "Neoplasias",
    "Ca. piel (no melanoma)":                       "Neoplasias",
    "Ca. mama":                                     "Neoplasias",
    "Ca. cuello uterino":                           "Neoplasias",
    "Ca. cuerpo uterino":                           "Neoplasias",
    "Ca. testículo":                                "Neoplasias",
    "Enfermedad de Hodgkin":                        "Neoplasias",
    "Leucemia":                                     "Neoplasias",
    "Enfermedades del tiroides":                    "Endócrino/Metabólico",
    "Diabetes mellitus":                            "Endócrino/Metabólico",
    "Epilepsia":                                    "Neurológico",
    "Enf. reumática cardíaca crónica":              "Cardiovascular",
    "Hipertensión arterial":                        "Cardiovascular",
    "Cardiopatía isquémica (50%)":                  "Cardiovascular",
    "Enfermedad cerebrovascular":                   "Cardiovascular",
    "Enf. respiratorias excl. neumonía e influenza (1-14)": "Respiratorio",
    "Influenza":                                    "Respiratorio",
    "Neumonía":                                     "Respiratorio",
    "Úlcera péptica":                               "Digestivo",
    "Apendicitis":                                  "Digestivo",
    "Hernia abdominal":                             "Digestivo",
    "Colelitiasis y colecistitis":                  "Digestivo",
    "Nefritis y nefrosis":                          "Urogenital",
    "Hiperplasia benigna de próstata":              "Urogenital",
    "Muerte materna":                               "Materno-Perinatal",
    "Muertes perinatales":                          "Materno-Perinatal",
    "Anomalías cardiovasculares congénitas":        "Congénito",
    "Accidentes durante atención médica":           "Iatrogénico",
}


def build_by_cause(evitables_full):
    """
    Defunciones evitables por descripción de causa × año (nacional, ambos sexos).
    """
    df = (
        evitables_full
        .groupby(["ANIO", "descripcion"], as_index=False)["CUENTA_EVITABLE"]
        .sum()
        .rename(columns={"CUENTA_EVITABLE": "DEF_EVITABLES"})
    )
    df["GRUPO"] = df["descripcion"].map(_CAUSE_GROUP).fillna("Otro")
    return df.sort_values(["ANIO", "GRUPO", "DEF_EVITABLES"],
                          ascending=[True, True, False]).reset_index(drop=True)


# ── 3. By age group ──────────────────────────────────────────────────────────

_AGE_LABELS = {
    0:  "<1",
    1:  "1-9",
    10: "10-14",
    15: "15-19",
    20: "20-24",
    25: "25-29",
    30: "30-34",
    35: "35-39",
    40: "40-44",
    45: "45-49",
    50: "50-54",
    55: "55-59",
    60: "60-64",
    65: "65-69",
    70: "70-74",
    75: "75-79",
    80: "80+",
}


def build_by_agegroup(evitable_agg):
    """
    Defunciones evitables por grupo etario × año (nacional, ambos sexos).
    """
    df = (
        evitable_agg
        .groupby(["ANIO", "EDAD_MIN"], as_index=False)["DEF_EVITABLES"]
        .sum()
    )
    df["EDAD_LABEL"] = df["EDAD_MIN"].map(_AGE_LABELS)
    return df.sort_values(["ANIO", "EDAD_MIN"]).reset_index(drop=True)


# ── 4. CV interprovincial ────────────────────────────────────────────────────

def build_cv(std_rates):
    """
    Coeficiente de variación (%) de la tasa estandarizada entre las 24 provincias,
    por año × sexo. Indicador de inequidad interprovincial.
    """
    rows = []
    for (anio, sexo), grp in std_rates.groupby(["ANIO", "SEXO"]):
        mu = grp["TASA_STD"].mean()
        if mu > 0:
            cv = grp["TASA_STD"].std() / mu * 100
        else:
            cv = np.nan
        rows.append({"ANIO": anio, "SEXO": sexo,
                     "CV_PCT": round(cv, 2),
                     "TASA_MEDIA": round(mu, 2),
                     "TASA_MIN": round(grp["TASA_STD"].min(), 2),
                     "TASA_MAX": round(grp["TASA_STD"].max(), 2)})
    return pd.DataFrame(rows).sort_values(["ANIO", "SEXO"]).reset_index(drop=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    OUTPUT_TABLES.mkdir(parents=True, exist_ok=True)

    print("Loading deaths...")
    deaths = load_all()

    print("Classifying evitable deaths (with cause labels)...")
    evitable_df = get_evitable_df()
    evitables_full = classify(deaths, evitable_df)  # keeps 'descripcion' column

    # Aggregated by (ANIO, PROVRES, SEXO, EDAD_MIN)
    from classify import aggregate_evitable
    evitable_agg = aggregate_evitable(evitables_full)

    print("Loading population...")
    pop = load_population()

    print("Building national series...")
    national = build_national_series(evitable_agg, pop)
    national.to_csv(OUTPUT_TABLES / "national_series.csv", index=False, float_format="%.4f")
    print(f"  national_series.csv ({len(national)} rows)")

    print("Building by-cause table...")
    cause_df = build_by_cause(evitables_full)
    cause_df.to_csv(OUTPUT_TABLES / "evitable_by_cause.csv", index=False, float_format="%.2f")
    print(f"  evitable_by_cause.csv ({len(cause_df)} rows)")

    print("Building by-age-group table...")
    age_df = build_by_agegroup(evitable_agg)
    age_df.to_csv(OUTPUT_TABLES / "evitable_by_agegroup.csv", index=False, float_format="%.2f")
    print(f"  evitable_by_agegroup.csv ({len(age_df)} rows)")

    print("Building CV table...")
    std_rates = pd.read_csv(OUTPUT_TABLES / "tasa_evitable_provincia_anio_sexo.csv")
    cv_df = build_cv(std_rates[std_rates["SEXO"] != 0])
    cv_df.to_csv(OUTPUT_TABLES / "cv_by_year.csv", index=False)
    print(f"  cv_by_year.csv ({len(cv_df)} rows)")

    print("Fitting trend models...")
    from trends import fit_trends
    both = std_rates.copy()
    trend_df = fit_trends(both, sexo=0)
    if not trend_df.empty:
        trend_df.to_csv(OUTPUT_TABLES / "trend_by_province.csv", index=False, float_format="%.6f")
        print(f"  trend_by_province.csv ({len(trend_df)} rows)")
    else:
        print("  Trend models skipped (statsmodels unavailable).")

    print("\nAll tables written to output/tables/")


if __name__ == "__main__":
    main()
