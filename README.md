# Mortalidad Evitable en Argentina — DEIS

Serie temporal de tasas de mortalidad evitable estandarizadas por edad, desagregadas por provincia y sexo, para todos los años disponibles en los CSV del DEIS (2005–2024).

---

## Pendientes

- [ ] **Corregir población 2005–2010**: los años 2005–2009 usan actualmente el valor de 2010 como aproximación porque la proyección INDEC base 2010 no retrocede. Reemplazar por la proyección base 2001 (o retropolación equivalente) para tener denominadores propios en ese período.

- [ ] **Actualizar lista de causas evitables a OECD/Eurostat 2019**: la lista actual implementa Nolte & McKee 2003. La lista revisada de OECD/Eurostat (2019) amplía el set de causas e incorpora actualizaciones de la evidencia clínica (p. ej. algunos cánceres, VIH, diabetes). Ver: *OECD/Eurostat, "Avoidable mortality: OECD/Eurostat lists of preventable and treatable causes of death", 2019.*

- [ ] **Cuantificar y documentar el sesgo por causas inespecíficas (R-codes)**: el análisis de calidad muestra ~7% de defunciones con código R por año. Cruzar con la literatura que estima el sesgo de subestimación generado por mal-clasificación (p. ej. Joubert et al. 2012, Mathers et al. 2005) para determinar si corresponde aplicar un factor de corrección o simplemente acotar la interpretación de las tasas en jurisdicciones con mayor proporción de R-codes.

---

## Estructura del repositorio

```
├── data/
│   ├── raw/                      # Datos crudos — no modificar
│   │   ├── defweb05.csv … defweb24.csv   # CSVs del DEIS (20 archivos)
│   │   └── descdef1.xlsx                 # Codebook oficial DEIS
│   ├── processed/                # Parquets intermedios generados por el pipeline
│   └── reference/                # Tablas de referencia
│       ├── c2_proyecciones_prov_2010_2040.xls             # Fuente de población 2005–2021
│       ├── proyecciones_jurisdicciones_2022_2040_base.csv # Fuente de población 2022–2024
│       ├── c1_proyecciones_prov_2010_2040.xls             # (no usado — solo total)
│       ├── proyecciones_jurisdicciones_2022_2040_c1.xlsx  # (no usado — solo total)
│       └── poblacion_indec.csv   # Generado automáticamente por build_population.py
├── output/
│   ├── tables/                   # CSVs de resultados
│   └── figures/                  # Gráficos PNG
├── report/
│   ├── generate.py               # Genera el reporte HTML desde las tablas de output
│   ├── mortalidad_evitable_argentina.ipynb  # Notebook ejecutado (GitHub lo previsualiza)
│   └── mortalidad_evitable_argentina.html   # Reporte HTML auto-contenido
└── scripts/
    ├── config.py            # Rutas y constantes (códigos de provincias INDEC)
    ├── causes.py            # Tabla de causas evitables (Nolte & McKee 2003)
    ├── load.py              # Carga y limpieza de los CSVs del DEIS
    ├── classify.py          # Clasificación de defunciones como evitables
    ├── build_population.py  # Construye poblacion_indec.csv desde proyecciones INDEC
    ├── population.py        # Carga poblacion_indec.csv + población estándar OMS
    ├── rates.py             # Tasas crudas, estandarizadas e IC de Byar
    ├── trends.py            # Regresión binomial negativa de tendencia anual
    ├── visualize.py         # Gráficos (temporal, ranking, inequidad)
    ├── export_analysis_tables.py  # Tablas suplementarias para el reporte
    └── main.py              # Orquestador del pipeline completo
```

---

## Dependencias

Python ≥ 3.10

```bash
pip install pandas numpy matplotlib seaborn statsmodels pyarrow nbformat nbconvert ipykernel
```

`pyarrow` es necesario para leer/escribir `.parquet`.
`statsmodels` es necesario para el análisis de tendencias (opcional — el resto del pipeline funciona sin él).
`nbformat`, `nbconvert`, `ipykernel` son necesarios para generar el reporte HTML.

---

## Datos de población — construcción automática

Los datos poblacionales se construyen automáticamente desde los archivos INDEC ya incluidos en `data/reference/`. No se necesita descargar ni procesar nada manualmente.

**Fuentes utilizadas:**

| Archivo | Años cubiertos | Descripción |
|---------|----------------|-------------|
| `c2_proyecciones_prov_2010_2040.xls` | 2005–2021 | Proyecciones base 2010 por provincia × sexo × quinquenio. Los años 2005–2009 usan el valor del año 2010 como aproximación (la proyección no retrocede antes de 2010). |
| `proyecciones_jurisdicciones_2022_2040_base.csv` | 2022–2024 | Proyecciones base 2022, mismo desglose. Formato largo, separador `;`. |

Los quinquenios INDEC (0–4, 5–9, …, 80+) se mapean a los grupos canónicos del análisis:

| Quinquenio INDEC | EDAD_MIN canónico | Tratamiento |
|---|---|---|
| 0–4 | 0 | 1/5 de la población (aproximación <1 año) |
| 0–4 | 1 | 4/5 de la población (parte del grupo 1–9) |
| 5–9 | 1 | Suma completa al grupo 1–9 |
| 10–75 | igual | Mapeo directo |
| ≥80 | 80 | Suma de grupos 80–84, 85–89, 90–94, 95–99, 100+ |

El script `build_population.py` se ejecuta **automáticamente** la primera vez que corres `main.py` si falta `poblacion_indec.csv`. También podés correrlo solo:

```bash
python scripts/build_population.py
```

### NBI provincial (opcional, para el gráfico de inequidad)

Coloca el archivo en: `data/reference/nbi_provincial.csv`

Columnas: `PROVRES` (int), `PCT_NBI` (float — porcentaje de hogares con NBI).

Fuente sugerida: Censo Nacional de Población, Hogares y Viviendas (INDEC) — 2010 o 2022.

---

## Cómo ejecutar

```bash
# Desde la raíz del proyecto:
python scripts/main.py

# Opciones:
python scripts/main.py --skip-trends          # omitir regresión de tendencia
python scripts/main.py --skip-plots           # omitir gráficos
python scripts/main.py --sexo 1               # analizar solo varones (default: 0=ambos)
python scripts/main.py --nbi data/reference/nbi_provincial.csv

# Tablas suplementarias para el reporte:
python scripts/export_analysis_tables.py

# Generar reporte HTML:
python report/generate.py
```

La primera ejecución construye `poblacion_indec.csv` automáticamente si no existe.

---

## Outputs

| Archivo | Descripción |
|---------|-------------|
| `output/tables/quality_report.csv` | Totales por año, % causas R (mal definidas), N provincias |
| `output/tables/tasa_evitable_provincia_anio_sexo.csv` | Tabla maestra: tasa estandarizada + IC 95% por provincia/año/sexo |
| `output/tables/tendencia_anual_provincia.csv` | Cambio % anual por regresión, con p-valor e IC |
| `output/tables/national_series.csv` | Serie temporal nacional por año × sexo |
| `output/tables/evitable_by_cause.csv` | Defunciones evitables por causa × año |
| `output/tables/evitable_by_agegroup.csv` | Defunciones evitables por grupo etario × año |
| `output/tables/cv_by_year.csv` | Coeficiente de variación interprovincial por año |
| `output/tables/trend_by_province.csv` | Tendencia anual por provincia (binomial negativa) |
| `output/figures/serie_temporal_sexo0.png` | Tendencia temporal superpuesta, todas las provincias |
| `output/figures/ranking_provincias_{año}.png` | Barras horizontales con IC, último año disponible |
| `output/figures/tendencia_anual_provincias.png` | Ranking de cambio % anual |
| `output/figures/inequidad_nbi_{año}.png` | Scatter NBI vs. tasa evitable (si se provee NBI) |
| `data/processed/deaths_clean.parquet` | Microdatos limpios (formato parquet) |
| `data/processed/evitable_aggregated.parquet` | Defunciones evitables agregadas por celda |
| `report/mortalidad_evitable_argentina.html` | Reporte completo — abrir en el navegador |
| `report/mortalidad_evitable_argentina.ipynb` | Notebook ejecutado con figuras embebidas |

---

## Descripción del pipeline

### 1. Carga (`load.py`)

Carga todos los `defweb*.csv` detectando automáticamente separador y encoding:

- **2005–2019**: separador coma, encoding `latin1`
- **2020+**: separador punto y coma, encoding `utf-8-sig` (UTF-8 con BOM)

El año se extrae del nombre del archivo con regex.

Los nombres de archivo usan año de 2 dígitos (`defweb05.csv` = 2005, `defweb20_0.csv` = 2020). El cargador extrae el año del patrón `webYY` y lo convierte a 4 dígitos (`2000 + YY`).

**Limpieza aplicada**:
- `PROVRES`: convertir a int; excluir 98 ("Otro país") y 99 ("Lugar no especificado") según `descdef1.xlsx`
- `SEXO`: mantener solo 1 (Varón) y 2 (Mujer); excluir 9 (Sin especificar)
- `CUENTA`: excluir filas con conteo nulo o cero
- `CAUSA`: strip + upper-case

**Armonización de grupos etarios** (`parse_grupedad`):

Los CSVs del DEIS cambiaron el formato de GRUPEDAD en 2024:

| Período | Ejemplo | Descripción |
|---------|---------|-------------|
| 2005–2023 | `02_1 a 9` | Guión bajo; 18 grupos; 1-9 años como un único grupo |
| 2024 | `04.1 año`, `08.5 a 9` | Punto; 25 grupos; años individuales 1-4 separados |

Ambos formatos se mapean a los grupos canónicos. El grupo `1–9` de años anteriores y los grupos individuales 1, 2, 3, 4, 5-9 del 2024 se colapsan al mismo grupo canónico `EDAD_MIN=1`.
Los grupos 80-84 y 85+ del 2024 se colapsan a `EDAD_MIN=80`.
Edades sub-anuales (días, meses) y "Menor de 1 año" → `EDAD_MIN=0`.
"Sin especificar" → `NaN` (excluido del análisis).

### 2. Población canónica (`build_population.py`)

Parsea dos fuentes INDEC y genera `data/reference/poblacion_indec.csv`:

- **`c2_proyecciones_prov_2010_2040.xls`** (años 2010–2021): archivo multi-hoja con bloques verticales de 6 años cada uno. Cada hoja es una provincia; el código de provincia se extrae del nombre (`"06-BUENOS AIRES"` → 6). Se omite la hoja `"01-TOTAL DEL PAÍS"`. Los bloques se detectan buscando filas donde col 0 = `"Edad"`.
- **`proyecciones_jurisdicciones_2022_2040_base.csv`** (años 2022–2024): CSV con separador `;` y columnas con espacios en los nombres. Ya en formato largo.

Los años 2005–2009 no existen en las proyecciones; se usan los valores de 2010 como aproximación.

### 3. Causas evitables (`causes.py`)

Lista de causas basada en: **Nolte E, McKee M. Measuring the health of nations: analysis of mortality amenable to health care. BMJ 2003;327:1129. (PMC261807)**.

Cada causa define:
- Códigos CIE-10 de 3 caracteres (sin punto)
- Rango de edad (edad_min, edad_max)
- Restricción de sexo (si aplica)
- `fraccion`: fracción de defunciones contadas como evitables (= 1.0 para todas excepto cardiopatía isquémica = 0.5)

**Correcciones respecto a versiones anteriores del plan**:

| Causa | Incorrecto | Correcto |
|-------|-----------|---------|
| Ca. piel (no melanoma) | C43 | C44 |
| Úlcera péptica | K25–K28 | K25–K27 (K28 excluido) |
| Nefritis y nefrosis | N00–N29 (continuo) | N00–N07 + N17–N19 + N25–N27 |
| Hipertensión | I10–I13 | I10–I13 + I15 (hipertensión secundaria) |
| Ca. cuerpo uterino | C54 (0–74) | C54+C55 (0–44) |
| Sarampión | 0–74 | 1–14 |
| Secuelas de TBC | ausente | B90 incluido junto con A15–A19 |

**Cardiopatía isquémica (I20–I25)**: incluida al 50% según la convención de Nolte & McKee, que reconoce que parte de la mortalidad isquémica no es evitable con atención médica. En el código, `fraccion=0.5` multiplica el conteo antes de la agregación.

### 4. Clasificación (`classify.py`)

Join entre defunciones y tabla de causas evitables por código CIE-10 (3 chars). Una defunción se clasifica como evitable si:
1. El código CAUSA coincide con alguna causa evitable.
2. `EDAD_MIN` (del registro) está entre `edad_min` y `edad_max` de la causa (ambos inclusive).
3. Si la causa tiene restricción de sexo, `SEXO` del registro debe coincidir.

Las tres condiciones se evalúan simultáneamente como filtro vectorizado (sin bucles).

### 5. Tasas (`rates.py`)

**Tasa cruda**: `DEF_EVITABLES / POBLACION × 100,000`, por celda (provincia × año × sexo × grupo etario).

**Estandarización directa**: suma ponderada de tasas específicas por edad usando pesos de la **Población Mundial Estándar OMS (2000–2025)** (Ahmad et al., GPE Discussion Paper 31, OMS 2001).

Los pesos OMS originales usan quinquenios 0–4, 5–9, etc. Los dos primeros grupos se redistribuyen a los grupos canónicos 0 (<1 año) y 1 (1–9 años):
- `EDAD_MIN=0` recibe 20% del peso 0–4 (~1/5 del quinquenio)
- `EDAD_MIN=1` recibe 80% del peso 0–4 más el peso completo 5–9

**Intervalos de confianza**: aproximación de Byar para conteos Poisson (Breslow & Day 1987), aplicada a los conteos totales observados y escalada a la tasa estandarizada mediante el factor `TASA_STD / TASA_CRUDA_TOTAL`.

### 6. Tendencias (`trends.py`)

Regresión binomial negativa con offset log(población), por provincia:

```
log(E[DEF]) = β₀ + β₁·ANIO + log(POBLACION)
```

- `β₁ < 0` → mortalidad evitable en descenso (señal positiva para el sistema de salud)
- `cambio_pct_anual = (exp(β₁) − 1) × 100`
- Si la binomial negativa no converge, se aplica fallback con regresión de Poisson (indicado en columna `converged=False`)
- Provincias con menos de 5 años de datos son excluidas

### 7. Visualizaciones (`visualize.py`)

Todos los gráficos se guardan en `output/figures/`. Si `matplotlib` no está instalado, los gráficos se saltan con un warning pero el resto del pipeline continúa.

### 8. Reporte (`report/generate.py`)

Construye programáticamente un notebook Jupyter con estructura de short paper (Resumen, Introducción, Métodos, Resultados, Discusión, Limitaciones, Referencias), lo ejecuta con `nbconvert --execute` y exporta a HTML auto-contenido con `--no-input`.

---

## Consideraciones metodológicas

### Incompatibilidad de grupos etarios en 2024

El año 2024 usa un esquema de grupos etarios más fino que todos los años anteriores. Los grupos individuales 1, 2, 3, 4 años y el grupo 5–9 del 2024 se colapsan al grupo canónico 1 (= 1–9 años). Esto implica que para 2024 no es posible distinguir la mortalidad evitable en el subgrupo 1–4 años del subgrupo 5–9 años; ambos aportan al mismo denominador poblacional.

### Años COVID (2020–2021)

La pandemia de COVID-19 distorsiona la mortalidad general y puede afectar la clasificación de causas (especialmente causas cardiovasculares y respiratorias). Se recomienda:
- Calcular la tendencia tanto incluyendo como excluyendo 2020–2021
- Si se incluyen, señalar el quiebre estructural en los gráficos

### Causas mal definidas (R-codes)

El archivo `quality_report.csv` incluye el porcentaje de defunciones con código R (síntomas y signos inespecíficos) por año y provincia. Un `pct_causa_R` alto indica subregistro de causas evitables; las tasas en esas jurisdicciones/años deben interpretarse con cautela.

### Sin ajuste por factores de riesgo

La estandarización es por edad y sexo, no por prevalencia de factores de riesgo (tabaquismo, obesidad, diabetes). La variación residual entre provincias incluye tanto diferencias en la capacidad del sistema de salud como diferencias en prevalencia de factores de riesgo. La eliminación de este componente requeriría datos de la Encuesta Nacional de Factores de Riesgo (ENFR) por provincia.

### Solo mortalidad

La mortalidad evitable captura únicamente los casos más graves (muerte). Condiciones que generan carga de enfermedad sin causar muerte directa (diabetes mal controlada, hipertensión con morbilidad, etc.) no aparecen en este análisis.

---

## Referencias

- Nolte E, McKee M. *Measuring the health of nations: analysis of mortality amenable to health care.* BMJ 2003;327:1129. doi:10.1136/bmj.327.7424.1129
- Ahmad OB, Boschi-Pinto C, Lopez AD, et al. *Age standardization of rates: a new WHO standard.* GPE Discussion Paper Series No. 31. WHO 2001.
- Breslow NE, Day NE. *Statistical Methods in Cancer Research, Vol. II.* IARC 1987. (Byar approximation for Poisson CIs)
- DEIS — Dirección de Estadísticas e Información de Salud, Ministerio de Salud Argentina. Estadísticas vitales: defunciones.
- INDEC — Instituto Nacional de Estadística y Censos. Estimaciones y proyecciones de población 2010–2040.
