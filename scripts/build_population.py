"""
build_population.py — Construye data/reference/poblacion_indec.csv

Fuentes:
  2005–2021  →  c2_proyecciones_prov_2010_2040.xls
                (INDEC, Cuadro 2: población por provincia × sexo × quinquenio × año)
  2022–2024  →  proyecciones_jurisdicciones_2022_2040_base.csv
                (INDEC, base 2022: mismas dimensiones, formato largo)

Mapeo de quinquenios INDEC → grupos canónicos del análisis:
  INDEC 0–4   →  EDAD_MIN 0  (<1 año):   1/5  de la población 0–4
              →  EDAD_MIN 1  (1–9 años): 4/5  de la población 0–4
  INDEC 5–9   →  EDAD_MIN 1  (suma al grupo 1–9)
  INDEC 10–75 →  EDAD_MIN igual al límite inferior (10, 15, ..., 75)
  INDEC ≥ 80  →  EDAD_MIN 80 (80+, todos los grupos se suman)

Nota años 2005–2009: la proyección 2010 no retrocede antes de 2010.
Se usan los valores de 2010 como aproximación para 2005–2009.

Ejecución:
    python scripts/build_population.py
"""

import re
import sys
import warnings
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_REFERENCE, PROVINCIAS

_VALID_PROVRES = set(PROVINCIAS.keys())


# ── Age label parser ──────────────────────────────────────────────────────────

def _parse_age_label(s: str) -> int | None:
    """
    Parse an age group label from the c2 XLS file to its lower-bound integer.

    Examples:
      "0-4"     → 0
      "5-9"     → 5
      "10-14"   → 10
      "80-84"   → 80
      "100 y más" → 100
    Returns None if the string cannot be parsed (e.g., blank, "Total", "Fuente").
    """
    s = str(s).strip()
    if not s or s.lower() in ("nan", "total", "."):
        return None
    if s.lower().startswith("fuente"):
        return None

    # "100 y más" style
    m = re.match(r"^(\d+)\s+y\s+m", s, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # "0-4", "5 - 9", "10–14" etc. (hyphen or en-dash)
    m = re.match(r"^(\d+)\s*[-–]", s)
    if m:
        return int(m.group(1))

    return None


# ── c2 XLS parser (2005–2021) ─────────────────────────────────────────────────

def parse_c2_xls(path: Path, years_wanted: list[int]) -> pd.DataFrame:
    """
    Parse c2_proyecciones_prov_2010_2040.xls into a long DataFrame.

    The workbook has one sheet per province plus a GraphData sheet.
    Each provincial sheet contains vertically stacked 6-year blocks.
    Each block has:
      Row 0: "Edad | year1 | NaN | NaN | NaN | year2 | ..."  (year headers)
      Row 1: "NaN  | Ambos | Var | Muj | NaN | Ambos | ..."  (sex sub-headers)
      Row 2: blank
      Row 3: "Total | ..."  (skip)
      Row 4: blank
      Rows 5–25: age groups (0-4, 5-9, ..., 100+)
      Row 26–27: blank / source note

    Within each block the column pattern per year is:
      col c   = year value (in year-header row) / Ambos sexos values
      col c+1 = NaN / Varones values
      col c+2 = NaN / Mujeres values
      col c+3 = NaN separator

    Returns columns: PROVRES, ANIO, SEXO, EDAD_INDEC, POBLACION
    """
    years_set = set(years_wanted)
    xl = pd.ExcelFile(path)

    rows = []
    for sheet in xl.sheet_names:
        # Only provincial sheets (start with a digit), skip "01-TOTAL DEL PAÍS"
        if not sheet[0].isdigit():
            continue
        prov_code = int(sheet.split("-")[0])
        if prov_code not in _VALID_PROVRES:
            continue

        df = xl.parse(sheet, header=None)
        n_cols = len(df.columns)

        # Find block start rows: rows where col 0 stripped == "edad"
        block_starts = df.index[
            df[0].astype(str).str.strip().str.lower() == "edad"
        ].tolist()

        for b_idx, b_start in enumerate(block_starts):
            year_row = df.iloc[b_start]      # "Edad | 2010 | NaN | NaN | NaN | 2011 ..."
            # sex_row  = df.iloc[b_start + 1]  # not needed — we map by position

            # Build col_index → (year, sexo) for Varones and Mujeres
            col_map: dict[int, tuple[int, int]] = {}
            for c in range(1, n_cols):
                val = year_row.iloc[c]
                if pd.isna(val):
                    continue
                try:
                    yr = int(float(val))
                except (ValueError, TypeError):
                    continue
                if yr not in years_set:
                    continue
                # Varones = c+1, Mujeres = c+2 (relative to the year column)
                if c + 1 < n_cols:
                    col_map[c + 1] = (yr, 1)
                if c + 2 < n_cols:
                    col_map[c + 2] = (yr, 2)

            if not col_map:
                continue

            # Data rows: from b_start+2 until next block start (or end of sheet)
            b_end = block_starts[b_idx + 1] if b_idx + 1 < len(block_starts) else len(df)

            for r in range(b_start + 2, b_end):
                age_raw = df.iloc[r, 0]
                edad = _parse_age_label(str(age_raw))
                if edad is None:
                    continue

                for col_idx, (yr, sexo) in col_map.items():
                    pop_val = df.iloc[r, col_idx]
                    if pd.isna(pop_val):
                        continue
                    try:
                        pop = int(float(str(pop_val).replace(",", "")))
                    except ValueError:
                        continue
                    if pop <= 0:
                        continue
                    rows.append({
                        "PROVRES":    prov_code,
                        "ANIO":       yr,
                        "SEXO":       sexo,
                        "EDAD_INDEC": edad,
                        "POBLACION":  pop,
                    })

    return pd.DataFrame(rows)


# ── 2022 CSV parser ───────────────────────────────────────────────────────────

def parse_2022_csv(path: Path, years_wanted: list[int]) -> pd.DataFrame:
    """
    Parse proyecciones_jurisdicciones_2022_2040_base.csv into the same
    long format as parse_c2_xls.

    CSV columns (semicolon-separated, leading/trailing spaces in names):
      Jurisdiccion ; Sexo ; Edad(q) ; Poblacion ; Fecha

    Returns columns: PROVRES, ANIO, SEXO, EDAD_INDEC, POBLACION
    """
    df = pd.read_csv(path, sep=";")
    df.columns = df.columns.str.strip()

    df = df.rename(columns={
        "Jurisdiccion": "PROVRES",
        "Sexo":         "SEXO",
        "Edad(q)":      "EDAD_INDEC",
        "Poblacion":    "POBLACION",
        "Fecha":        "ANIO",
    })

    df = df[df["ANIO"].isin(years_wanted)].copy()
    df["PROVRES"]    = df["PROVRES"].astype(int)
    df["SEXO"]       = df["SEXO"].astype(int)
    df["EDAD_INDEC"] = df["EDAD_INDEC"].astype(int)
    df["POBLACION"]  = pd.to_numeric(df["POBLACION"], errors="coerce").fillna(0).astype(int)
    df["ANIO"]       = df["ANIO"].astype(int)

    return df[["PROVRES", "ANIO", "SEXO", "EDAD_INDEC", "POBLACION"]]


# ── Age harmonisation ─────────────────────────────────────────────────────────

def harmonize_ages(df: pd.DataFrame) -> pd.DataFrame:
    """
    Map INDEC quinquennial age groups to canonical EDAD_MIN values.

    INDEC group → Canonical EDAD_MIN
      0  (0–4)   →  0  (<1 yr):   population × 1/5
                 →  1  (1–9 yr):  population × 4/5
      5  (5–9)   →  1  (1–9 yr):  full population (added to the 1–9 group)
      10–75      →  same value (direct mapping)
      ≥ 80       →  80  (80+):    all groups summed
    """
    parts = []

    # ── Group 0–4 split into age-0 and age-1 ────────────────────────────────
    g04 = df[df["EDAD_INDEC"] == 0].copy()

    age0 = g04.copy()
    age0["EDAD_MIN"]  = 0
    age0["POBLACION"] = (age0["POBLACION"] / 5).round().astype(int)

    age1_from04 = g04.copy()
    age1_from04["EDAD_MIN"]  = 1
    age1_from04["POBLACION"] = (age1_from04["POBLACION"] * 4 / 5).round().astype(int)

    parts.extend([age0, age1_from04])

    # ── Group 5–9 → age-1 ───────────────────────────────────────────────────
    g59 = df[df["EDAD_INDEC"] == 5].copy()
    g59["EDAD_MIN"] = 1
    parts.append(g59)

    # ── Groups 10–75 → direct mapping ───────────────────────────────────────
    gmid = df[df["EDAD_INDEC"].between(10, 75)].copy()
    gmid["EDAD_MIN"] = gmid["EDAD_INDEC"]
    parts.append(gmid)

    # ── Groups 80+ → collapse to 80 ─────────────────────────────────────────
    g80p = df[df["EDAD_INDEC"] >= 80].copy()
    g80p["EDAD_MIN"] = 80
    parts.append(g80p)

    canonical = pd.concat(parts, ignore_index=True)
    canonical = (
        canonical
        .groupby(["PROVRES", "ANIO", "SEXO", "EDAD_MIN"], as_index=False)["POBLACION"]
        .sum()
    )
    canonical = canonical.sort_values(["PROVRES", "ANIO", "SEXO", "EDAD_MIN"]).reset_index(drop=True)
    return canonical


# ── Main build function ───────────────────────────────────────────────────────

def build(out_path: Path = None) -> pd.DataFrame:
    """
    Build and save data/reference/poblacion_indec.csv.

    Returns the canonical population DataFrame.
    """
    if out_path is None:
        out_path = DATA_REFERENCE / "poblacion_indec.csv"

    c2_path  = DATA_REFERENCE / "c2_proyecciones_prov_2010_2040.xls"
    csv_path = DATA_REFERENCE / "proyecciones_jurisdicciones_2022_2040_base.csv"

    if not c2_path.exists():
        raise FileNotFoundError(f"Missing: {c2_path}")
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing: {csv_path}")

    # ── Parse 2010-based projections for years 2010–2021 ────────────────────
    print("Parsing c2 XLS (2010–2021)...")
    df_2010_raw = parse_c2_xls(c2_path, years_wanted=list(range(2010, 2022)))

    if df_2010_raw.empty:
        raise RuntimeError("c2 XLS parsing returned no rows — check file structure.")

    # ── Extend back to 2005–2009 using 2010 values as approximation ─────────
    base_2010 = df_2010_raw[df_2010_raw["ANIO"] == 2010].copy()
    if base_2010.empty:
        warnings.warn("Year 2010 not found in c2 XLS; 2005–2009 will be missing.")
    else:
        extras = []
        for yr in range(2005, 2010):
            yr_df = base_2010.copy()
            yr_df["ANIO"] = yr
            extras.append(yr_df)
        df_2010_raw = pd.concat([df_2010_raw] + extras, ignore_index=True)

    # ── Parse 2022-based projections for years 2022–2024 ────────────────────
    print("Parsing 2022 CSV (2022–2024)...")
    df_2022_raw = parse_2022_csv(csv_path, years_wanted=list(range(2022, 2025)))

    if df_2022_raw.empty:
        raise RuntimeError("2022 CSV parsing returned no rows — check file content.")

    # ── Combine and harmonise age groups ────────────────────────────────────
    print("Harmonising age groups...")
    combined  = pd.concat([df_2010_raw, df_2022_raw], ignore_index=True)
    canonical = harmonize_ages(combined)

    n_years   = canonical["ANIO"].nunique()
    n_provs   = canonical["PROVRES"].nunique()
    n_rows    = len(canonical)
    print(f"  {n_rows:,} rows | {n_provs} provinces | {n_years} years "
          f"({canonical['ANIO'].min()}–{canonical['ANIO'].max()})")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canonical.to_csv(out_path, index=False)
    print(f"Saved: {out_path}")

    return canonical


if __name__ == "__main__":
    build()
