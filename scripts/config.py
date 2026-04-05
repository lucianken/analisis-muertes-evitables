from pathlib import Path

ROOT = Path(__file__).parent.parent

DATA_RAW       = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_REFERENCE = ROOT / "data" / "reference"
OUTPUT_TABLES  = ROOT / "output" / "tables"
OUTPUT_FIGURES = ROOT / "output" / "figures"

# From descdef1.xlsx sheet PROVRES
PROVINCIAS = {
    2:  "CABA",
    6:  "Buenos Aires",
    10: "Catamarca",
    14: "Córdoba",
    18: "Corrientes",
    22: "Chaco",
    26: "Chubut",
    30: "Entre Ríos",
    34: "Formosa",
    38: "Jujuy",
    42: "La Pampa",
    46: "La Rioja",
    50: "Mendoza",
    54: "Misiones",
    58: "Neuquén",
    62: "Río Negro",
    66: "Salta",
    70: "San Juan",
    74: "San Luis",
    78: "Santa Cruz",
    82: "Santa Fe",
    86: "Santiago del Estero",
    90: "Tucumán",
    94: "Tierra del Fuego",
}

# Codes to exclude: 98=Otro país, 99=Lugar no especificado
EXCLUDE_PROVRES = {98, 99}

# Canonical age group lower bounds used throughout the analysis.
# Group 0  = <1 year
# Group 1  = 1-9 years  (coarse group from 2005-2023 schema, 2024 is collapsed into it)
# Groups 10-75 = standard 5-year bands
# Group 80 = 80+ years
CANONICAL_AGES = [0, 1, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]
