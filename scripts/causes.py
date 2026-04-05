"""
Evitable causes of death — Nolte & McKee (2003), BMJ 327:1129.

Each entry defines:
  descripcion   : label
  codigos       : list of 3-character ICD-10 codes (no dot)
  edad_min      : minimum age (inclusive) for the restriction
  edad_max      : maximum age (inclusive); use 999 for "all ages"
  sexo          : None=both, 1=male only, 2=female only
  fraccion      : fraction of deaths counted as evitable (default 1.0)
                  Ischemic heart disease is counted at 50% per Nolte & McKee.
"""

import pandas as pd

_CAUSES = [

    # ── INFECTIOUS ───────────────────────────────────────────────────────────

    {
        "descripcion": "Infecciones intestinales",
        "codigos": [f"A0{i}" for i in range(10)],           # A00-A09
        "edad_min": 0, "edad_max": 14,
    },
    {
        "descripcion": "Tuberculosis y secuelas",
        "codigos": ["A15","A16","A17","A18","A19","B90"],    # A15-A19 + secuelas
        "edad_min": 0, "edad_max": 74,
    },
    {
        "descripcion": "Difteria",
        "codigos": ["A36"],
        "edad_min": 0, "edad_max": 74,
    },
    {
        "descripcion": "Tétanos",
        "codigos": ["A35"],
        "edad_min": 0, "edad_max": 74,
    },
    {
        "descripcion": "Poliomielitis",
        "codigos": ["A80"],
        "edad_min": 0, "edad_max": 74,
    },
    {
        "descripcion": "Tos convulsa",
        "codigos": ["A37"],
        "edad_min": 0, "edad_max": 14,
    },
    {
        "descripcion": "Septicemia",
        "codigos": ["A40", "A41"],
        "edad_min": 0, "edad_max": 74,
    },
    {
        "descripcion": "Sarampión",
        "codigos": ["B05"],
        "edad_min": 1, "edad_max": 14,
    },

    # ── NEOPLASMS ─────────────────────────────────────────────────────────────

    {
        "descripcion": "Ca. colon y recto",
        "codigos": ["C18","C19","C20","C21"],
        "edad_min": 0, "edad_max": 74,
    },
    {
        "descripcion": "Ca. piel (no melanoma)",
        "codigos": ["C44"],
        "edad_min": 0, "edad_max": 74,
    },
    {
        "descripcion": "Ca. mama",
        "codigos": ["C50"],
        "edad_min": 0, "edad_max": 74, "sexo": 2,
    },
    {
        "descripcion": "Ca. cuello uterino",
        "codigos": ["C53"],
        "edad_min": 0, "edad_max": 74, "sexo": 2,
    },
    {
        # C55 = útero sin especificar; age limit 0-44 per Nolte & McKee
        "descripcion": "Ca. cuerpo uterino",
        "codigos": ["C54", "C55"],
        "edad_min": 0, "edad_max": 44, "sexo": 2,
    },
    {
        "descripcion": "Ca. testículo",
        "codigos": ["C62"],
        "edad_min": 0, "edad_max": 74, "sexo": 1,
    },
    {
        "descripcion": "Enfermedad de Hodgkin",
        "codigos": ["C81"],
        "edad_min": 0, "edad_max": 74,
    },
    {
        "descripcion": "Leucemia",
        "codigos": ["C91","C92","C93","C94","C95"],
        "edad_min": 0, "edad_max": 44,
    },

    # ── ENDOCRINE / METABOLIC ─────────────────────────────────────────────────

    {
        "descripcion": "Enfermedades del tiroides",
        "codigos": ["E00","E01","E02","E03","E04","E05","E06","E07"],
        "edad_min": 0, "edad_max": 74,
    },
    {
        "descripcion": "Diabetes mellitus",
        "codigos": ["E10","E11","E12","E13","E14"],
        "edad_min": 0, "edad_max": 49,
    },

    # ── NEUROLOGICAL ──────────────────────────────────────────────────────────

    {
        "descripcion": "Epilepsia",
        "codigos": ["G40", "G41"],
        "edad_min": 0, "edad_max": 74,
    },

    # ── CARDIOVASCULAR ────────────────────────────────────────────────────────

    {
        "descripcion": "Enf. reumática cardíaca crónica",
        "codigos": ["I05","I06","I07","I08","I09"],
        "edad_min": 0, "edad_max": 74,
    },
    {
        # I14 does not exist in ICD-10; I15 = secondary hypertension
        "descripcion": "Hipertensión arterial",
        "codigos": ["I10","I11","I12","I13","I15"],
        "edad_min": 0, "edad_max": 74,
    },
    {
        # Counted at 50%: Nolte & McKee convention for ischemic heart disease
        "descripcion": "Cardiopatía isquémica (50%)",
        "codigos": ["I20","I21","I22","I23","I24","I25"],
        "edad_min": 0, "edad_max": 74,
        "fraccion": 0.5,
    },
    {
        "descripcion": "Enfermedad cerebrovascular",
        "codigos": ["I60","I61","I62","I63","I64","I65","I66","I67","I68","I69"],
        "edad_min": 0, "edad_max": 74,
    },

    # ── RESPIRATORY ───────────────────────────────────────────────────────────

    {
        # All respiratory except influenza (J10-J11) and pneumonia (J12-J18);
        # restricted to ages 1-14 per Nolte & McKee
        "descripcion": "Enf. respiratorias excl. neumonía e influenza (1-14)",
        "codigos": (
            [f"J0{i}" for i in range(10)] +          # J00-J09
            [f"J{i}"  for i in range(20, 100)]        # J20-J99
        ),
        "edad_min": 1, "edad_max": 14,
    },
    {
        "descripcion": "Influenza",
        "codigos": ["J10", "J11"],
        "edad_min": 0, "edad_max": 74,
    },
    {
        "descripcion": "Neumonía",
        "codigos": ["J12","J13","J14","J15","J16","J17","J18"],
        "edad_min": 0, "edad_max": 74,
    },

    # ── DIGESTIVE ─────────────────────────────────────────────────────────────

    {
        # K28 (gastrojejunal ulcer) excluded per Nolte & McKee
        "descripcion": "Úlcera péptica",
        "codigos": ["K25","K26","K27"],
        "edad_min": 0, "edad_max": 74,
    },
    {
        "descripcion": "Apendicitis",
        "codigos": ["K35","K36","K37","K38"],
        "edad_min": 0, "edad_max": 74,
    },
    {
        "descripcion": "Hernia abdominal",
        "codigos": ["K40","K41","K42","K43","K44","K45","K46"],
        "edad_min": 0, "edad_max": 74,
    },
    {
        "descripcion": "Colelitiasis y colecistitis",
        "codigos": ["K80", "K81"],
        "edad_min": 0, "edad_max": 74,
    },

    # ── UROGENITAL ────────────────────────────────────────────────────────────

    {
        # Non-contiguous ranges: N00-N07 + N17-N19 + N25-N27
        "descripcion": "Nefritis y nefrosis",
        "codigos": (
            ["N00","N01","N02","N03","N04","N05","N06","N07"] +
            ["N17","N18","N19"] +
            ["N25","N26","N27"]
        ),
        "edad_min": 0, "edad_max": 74,
    },
    {
        "descripcion": "Hiperplasia benigna de próstata",
        "codigos": ["N40"],
        "edad_min": 0, "edad_max": 74, "sexo": 1,
    },

    # ── MATERNAL / PERINATAL ──────────────────────────────────────────────────

    {
        "descripcion": "Muerte materna",
        "codigos": [f"O{str(i).zfill(2)}" for i in range(100)],  # O00-O99
        "edad_min": 0, "edad_max": 999, "sexo": 2,
    },
    {
        # A33 = neonatal tetanus; P00-P96 = perinatal conditions
        "descripcion": "Muertes perinatales",
        "codigos": (
            ["A33"] +
            [f"P{str(i).zfill(2)}" for i in range(97)]           # P00-P96
        ),
        "edad_min": 0, "edad_max": 999,
    },

    # ── CONGENITAL ────────────────────────────────────────────────────────────

    {
        "descripcion": "Anomalías cardiovasculares congénitas",
        "codigos": ["Q20","Q21","Q22","Q23","Q24","Q25","Q26","Q27","Q28"],
        "edad_min": 0, "edad_max": 74,
    },

    # ── IATROGENIC ────────────────────────────────────────────────────────────

    {
        # Y60-Y69 = accidentes durante atención médica/quirúrgica
        # Y83-Y84 = reacciones anormales a procedimientos
        "descripcion": "Accidentes durante atención médica",
        "codigos": (
            [f"Y{str(i).zfill(2)}" for i in range(60, 70)] +     # Y60-Y69
            ["Y83", "Y84"]
        ),
        "edad_min": 0, "edad_max": 999,
    },
]


def get_evitable_df() -> pd.DataFrame:
    """
    Returns a DataFrame with one row per ICD-10 3-character code.
    Columns: CAUSA, descripcion, edad_min, edad_max, sexo_restriccion, fraccion
    """
    rows = []
    for cause in _CAUSES:
        fraccion = cause.get("fraccion", 1.0)
        sexo     = cause.get("sexo", None)
        for code in cause["codigos"]:
            rows.append({
                "CAUSA":            code,
                "descripcion":      cause["descripcion"],
                "edad_min":         cause["edad_min"],
                "edad_max":         cause["edad_max"],
                "sexo_restriccion": sexo,
                "fraccion":         fraccion,
            })

    df = pd.DataFrame(rows)

    # Sanity check: warn if any code appears in more than one cause category
    dupes = df[df.duplicated("CAUSA", keep=False)]["CAUSA"].unique()
    if len(dupes):
        import warnings
        warnings.warn(f"Duplicate ICD codes across cause categories: {list(dupes)}")
        df = df.drop_duplicates("CAUSA", keep="first")

    return df
