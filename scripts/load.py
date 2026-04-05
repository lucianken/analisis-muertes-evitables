"""
Load and clean DEIS death microdata CSVs.

Format changes across years (verified against actual files):
  2005-2019  comma separator, latin1 encoding, GRUPEDAD uses underscore  e.g. '02_1 a 9'
  2020+      semicolon separator, UTF-8 BOM encoding, GRUPEDAD uses same underscore style
  2024       semicolon separator, UTF-8 BOM, GRUPEDAD uses dot style with finer groups
             e.g. '04.1 año', '08.5 a 9' — individual years 1-4 are split out

All years are harmonised to the same canonical age groups (see config.CANONICAL_AGES).
"""

import re
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

from config import DATA_RAW, PROVINCIAS, EXCLUDE_PROVRES


# ── Age group parsing ─────────────────────────────────────────────────────────

def parse_grupedad(s: str) -> float:
    """
    Maps any GRUPEDAD string to a canonical EDAD_MIN (int or NaN).

    Canonical groups match the 2005-2023 schema:
      0   = <1 year
      1   = 1-9 years   (2024's individual years 1-4 and 5-9 are collapsed here)
      10  = 10-14
      15  = 15-19
      ... (5-year bands)
      80  = 80+          (2024's separate 80-84 and 85+ are both mapped here)
      NaN = unspecified / unknown
    """
    s = str(s).strip()
    sl = s.lower()

    # Sub-annual (días, meses) and "menor de 1 año" → 0
    if any(x in sl for x in ["día", "dia", "mes", "menor"]):
        return 0

    # "Sin especificar" / codes starting with 99 → NaN
    if "especif" in sl:
        return np.nan

    # Extract the first number that follows a separator (. or _)
    # Covers both '02_1 a 9' and '04.1 año' and '10.15 a 19'
    m = re.search(r"[._]\s*(\d+)", s)
    if not m:
        return np.nan

    age = int(m.group(1))

    # 1-9 → canonical group 1 (handles 2024 individual years 1, 2, 3, 4 and 5-9)
    if 1 <= age <= 9:
        return 1

    # 80+ → canonical group 80 (handles both '80 y más' and '85 y más' in 2024)
    if age >= 80:
        return 80

    return float(age)


# ── Single-file loader ────────────────────────────────────────────────────────

def _load_file(path: Path) -> pd.DataFrame:
    """Load one DEIS CSV and attach the year."""
    # Filenames follow 'defwebYY.csv' or 'defwebYY_0.csv' (2-digit year)
    m = re.search(r"web(\d{2})", path.stem)
    if not m:
        raise ValueError(f"Cannot extract year from filename: {path.name}")
    yy = int(m.group(1))
    year = 2000 + yy

    # Encoding: 2020+ files have a UTF-8 BOM header
    encoding = "utf-8-sig" if year >= 2020 else "latin1"

    df = pd.read_csv(path, sep=None, engine="python", encoding=encoding, dtype=str)

    # Normalise column names (strip spaces, upper-case)
    df.columns = df.columns.str.strip().str.upper()

    # Handle historical column name variants
    df = df.rename(columns={
        "PROV_RES":   "PROVRES",
        "GRUPO_EDAD": "GRUPEDAD",
        "COUNT":      "CUENTA",
    })

    df["ANIO"] = year
    return df


# ── Main loader ───────────────────────────────────────────────────────────────

def load_all(data_dir: Path = DATA_RAW) -> pd.DataFrame:
    """
    Load, clean and return all DEIS CSVs as a single DataFrame.

    Steps applied:
      1. Load each CSV with the correct encoding and auto-detected separator.
      2. Normalise column names.
      3. Parse CUENTA (deaths count) to numeric; drop zero or null rows.
      4. Parse PROVRES to int; exclude foreign/unspecified (98, 99).
      5. Parse SEXO to int; exclude indeterminate (9).
      6. Parse GRUPEDAD to canonical EDAD_MIN; drop unspecified ages.
      7. Strip and upper-case CAUSA codes.
      8. Attach PROV_NOMBRE from the province lookup table.
    """
    csv_files = sorted(data_dir.glob("defweb*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No defweb*.csv files found in {data_dir}")

    parts = []
    for f in csv_files:
        try:
            parts.append(_load_file(f))
        except Exception as exc:
            warnings.warn(f"Skipping {f.name}: {exc}")

    raw = pd.concat(parts, ignore_index=True)

    # ── CUENTA ───────────────────────────────────────────────────────────────
    raw["CUENTA"] = pd.to_numeric(raw["CUENTA"], errors="coerce")
    raw = raw[raw["CUENTA"].fillna(0) > 0].copy()

    # ── PROVRES ──────────────────────────────────────────────────────────────
    raw["PROVRES"] = pd.to_numeric(raw["PROVRES"], errors="coerce")
    raw = raw[raw["PROVRES"].notna()].copy()
    raw["PROVRES"] = raw["PROVRES"].astype(int)
    raw = raw[~raw["PROVRES"].isin(EXCLUDE_PROVRES)]

    # ── SEXO ─────────────────────────────────────────────────────────────────
    raw["SEXO"] = pd.to_numeric(raw["SEXO"], errors="coerce").astype("Int64")
    raw = raw[raw["SEXO"].isin([1, 2])]

    # ── CAUSA ─────────────────────────────────────────────────────────────────
    raw["CAUSA"] = raw["CAUSA"].astype(str).str.strip().str.upper()

    # ── GRUPEDAD → EDAD_MIN ──────────────────────────────────────────────────
    raw["EDAD_MIN"] = raw["GRUPEDAD"].apply(parse_grupedad)
    raw = raw[raw["EDAD_MIN"].notna()].copy()
    raw["EDAD_MIN"] = raw["EDAD_MIN"].astype(int)

    # ── Province label ────────────────────────────────────────────────────────
    raw["PROV_NOMBRE"] = raw["PROVRES"].map(PROVINCIAS)

    # Keep only columns used downstream
    cols = ["ANIO", "PROVRES", "PROV_NOMBRE", "SEXO", "CAUSA", "EDAD_MIN", "CUENTA"]
    raw = raw[cols].copy()

    raw["CUENTA"] = raw["CUENTA"].astype(int)
    raw["SEXO"]   = raw["SEXO"].astype(int)

    return raw


# ── Validation helper ─────────────────────────────────────────────────────────

def quality_report(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a per-year quality summary useful for the validation checklist.
    Columns: ANIO, total_muertes, pct_causa_R (ill-defined), n_provincias
    """
    total = df.groupby("ANIO")["CUENTA"].sum().rename("total_muertes")

    r_codes = (
        df[df["CAUSA"].str.startswith("R")]
        .groupby("ANIO")["CUENTA"].sum()
        .rename("muertes_R")
    )

    n_prov = df.groupby("ANIO")["PROVRES"].nunique().rename("n_provincias")

    report = pd.concat([total, r_codes, n_prov], axis=1).fillna(0)
    report["pct_causa_R"] = (report["muertes_R"] / report["total_muertes"] * 100).round(2)
    return report.reset_index()
