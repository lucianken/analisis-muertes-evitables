"""
Population data for rate denominators and age-standardisation weights.

────────────────────────────────────────────────────────────────────────────────
WHAT YOU NEED TO PROVIDE
────────────────────────────────────────────────────────────────────────────────
Place a file at:  data/reference/poblacion_indec.csv

Required columns (exact names):
  PROVRES   int   INDEC province code (same values as in DEIS files)
  ANIO      int   Year
  SEXO      int   1=male, 2=female
  EDAD_MIN  int   Lower bound of canonical age group (0, 1, 10, 15, ..., 80)
  POBLACION int   Mid-year population estimate

Where to get the data:
  INDEC — Estimaciones y proyecciones de población 2010-2040:
  https://www.indec.gob.ar/indec/web/Nivel4-Tema-2-24-85
  Download the provincial tables, then reshape to the format above.

Age groups must match the canonical schema in config.CANONICAL_AGES:
  0   = <1 year
  1   = 1-9 years
  10  = 10-14
  15  = 15-19
  ... (5-year bands)
  80  = 80+ years

If INDEC tables use finer age groups, collapse them:
  e.g.  1-4 + 5-9  →  EDAD_MIN=1, POBLACION = sum of both groups

────────────────────────────────────────────────────────────────────────────────
STANDARD POPULATION
────────────────────────────────────────────────────────────────────────────────
The WHO World Standard Population (2000-2025) is used as the reference for
direct age-standardisation. It is hardcoded here so no external file is needed.

The weights are fractions of the total standard population (sums to 1.0).
Source: Ahmad OB et al., GPE Discussion Paper Series No. 31, WHO 2001.

Note: the WHO standard uses 5-year groups from 0-4 onwards. We re-map:
  age  0  (our <1yr)  ←  1/5 of WHO 0-4  weight (rough allocation)
  age  1  (our 1-9yr) ←  4/5 of WHO 0-4  +  WHO 5-9
  age 10  (10-14)     ←  WHO 10-14
  ...
  age 80  (80+)       ←  WHO 80-84 + 85+
"""

import warnings
import numpy as np
import pandas as pd
from pathlib import Path

from config import DATA_REFERENCE, CANONICAL_AGES


# ── WHO World Standard Population weights (per 100,000) ──────────────────────
# Source: Ahmad et al. 2001.  Mapped to our canonical age groups.
# The original 0-4 group (8860/100000) is split ~20% to age-0 and ~80% to age-1.

_WHO_WEIGHTS_RAW = {
    0:  8860 * 0.20,   # <1 year  (approx 1/5 of WHO 0-4 band)
    1:  8860 * 0.80 + 8690,  # 1-9 years  (4/5 of 0-4 + full 5-9)
    10: 8600,
    15: 8470,
    20: 8220,
    25: 7930,
    30: 7610,
    35: 7150,
    40: 6590,
    45: 6040,
    50: 5370,
    55: 4550,
    60: 3720,
    65: 2960,
    70: 2210,
    75: 1520,
    80: 910 + 635,     # 80-84 + 85+
}

_total = sum(_WHO_WEIGHTS_RAW.values())
WHO_STANDARD = pd.DataFrame([
    {"EDAD_MIN": age, "PESO_STD": w / _total}
    for age, w in _WHO_WEIGHTS_RAW.items()
])


# ── Load province/year/sex/age population ─────────────────────────────────────

def load_population(path: Path = None) -> pd.DataFrame:
    """
    Load population data from data/reference/poblacion_indec.csv.

    Returns a DataFrame with columns:
      PROVRES, ANIO, SEXO, EDAD_MIN, POBLACION

    If the file does not exist, raises FileNotFoundError with instructions.
    """
    if path is None:
        path = DATA_REFERENCE / "poblacion_indec.csv"

    if not path.exists():
        raise FileNotFoundError(
            f"Population file not found: {path}\n\n"
            "Download province-level population projections from INDEC:\n"
            "  https://www.indec.gob.ar/indec/web/Nivel4-Tema-2-24-85\n"
            "Then reshape to CSV with columns: PROVRES, ANIO, SEXO, EDAD_MIN, POBLACION\n"
            "See population.py docstring for full instructions."
        )

    pop = pd.read_csv(path)

    required = {"PROVRES", "ANIO", "SEXO", "EDAD_MIN", "POBLACION"}
    missing = required - set(pop.columns)
    if missing:
        raise ValueError(f"poblacion_indec.csv is missing columns: {missing}")

    # Validate age groups
    unexpected_ages = set(pop["EDAD_MIN"].unique()) - set(CANONICAL_AGES)
    if unexpected_ages:
        warnings.warn(
            f"Unexpected EDAD_MIN values in population file: {sorted(unexpected_ages)}. "
            "They will not match death records."
        )

    pop["POBLACION"] = pd.to_numeric(pop["POBLACION"], errors="coerce").fillna(0).astype(int)
    return pop


def get_standard_population() -> pd.DataFrame:
    """Return WHO World Standard Population weights (EDAD_MIN, PESO_STD)."""
    return WHO_STANDARD.copy()
