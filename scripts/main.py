"""
main.py — Mortalidad evitable en Argentina (DEIS)

Run from the project root:
    python scripts/main.py

Optional flags:
    --skip-trends       skip negative binomial regression
    --skip-plots        skip all plots
    --sexo {0,1,2}      sexo for trend/plots (default 0 = ambos sexos)
    --nbi PATH          path to NBI CSV for inequity scatter

Outputs are written to output/tables/ and output/figures/.
"""

import argparse
import sys
from pathlib import Path

# Allow imports from the scripts directory when run directly
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    DATA_PROCESSED, DATA_REFERENCE,
    OUTPUT_TABLES, OUTPUT_FIGURES,
)
from causes     import get_evitable_df
from load       import load_all, quality_report
from classify   import classify, aggregate_evitable
from population       import load_population, get_standard_population
from build_population import build as build_population
from rates      import compute_crude_rates, standardise, add_ambos_sexos
from trends     import fit_trends
from visualize  import (
    plot_temporal_series,
    plot_trend_ranking,
    plot_inequity_scatter,
    plot_latest_year_bars,
)


def parse_args():
    p = argparse.ArgumentParser(description="Mortalidad evitable Argentina — DEIS")
    p.add_argument("--skip-trends", action="store_true")
    p.add_argument("--skip-plots",  action="store_true")
    p.add_argument("--sexo",        type=int, default=0, choices=[0, 1, 2])
    p.add_argument("--nbi",         type=str, default=None,
                   help="Path to NBI CSV (columns: PROVRES, PCT_NBI)")
    return p.parse_args()


def main():
    args = parse_args()

    # Ensure output directories exist
    for d in [DATA_PROCESSED, OUTPUT_TABLES, OUTPUT_FIGURES]:
        d.mkdir(parents=True, exist_ok=True)

    # Auto-build population file if missing
    pop_path = DATA_REFERENCE / "poblacion_indec.csv"
    if not pop_path.exists():
        print("Population file not found. Building from INDEC projections...")
        build_population(pop_path)

    # ── 1. Load DEIS data ─────────────────────────────────────────────────────
    print("Loading DEIS CSVs...")
    deaths = load_all()
    print(f"  {len(deaths):,} records, years {deaths['ANIO'].min()}–{deaths['ANIO'].max()}")

    qr = quality_report(deaths)
    qr.to_csv(OUTPUT_TABLES / "quality_report.csv", index=False)
    print(f"  Quality report saved. R-code % range: "
          f"{qr['pct_causa_R'].min():.1f}–{qr['pct_causa_R'].max():.1f}%")

    deaths.to_parquet(DATA_PROCESSED / "deaths_clean.parquet", index=False)

    # ── 2. Classify evitable deaths ───────────────────────────────────────────
    print("Classifying evitable deaths...")
    evitable_df = get_evitable_df()
    evitables   = classify(deaths, evitable_df)
    agg         = aggregate_evitable(evitables)
    print(f"  {agg['DEF_EVITABLES'].sum():,.0f} total evitable death-years")

    agg.to_parquet(DATA_PROCESSED / "evitable_aggregated.parquet", index=False)

    # ── 3. Load population ────────────────────────────────────────────────────
    print("Loading population data...")
    try:
        pop = load_population()
    except FileNotFoundError as e:
        print(f"\n{'='*60}\nERROR: {e}\n{'='*60}\n")
        print("Saving evitable death counts without rates. "
              "Add population data and rerun to get standardised rates.")
        agg.to_csv(OUTPUT_TABLES / "evitable_counts_only.csv", index=False)
        return

    # ── 4. Crude rates ────────────────────────────────────────────────────────
    print("Computing crude rates...")
    crude = compute_crude_rates(agg, pop)

    # ── 5. Standardised rates ─────────────────────────────────────────────────
    print("Age-standardising rates...")
    std_by_sex = standardise(crude)
    std_all    = add_ambos_sexos(std_by_sex, crude)

    std_all.to_csv(
        OUTPUT_TABLES / "tasa_evitable_provincia_anio_sexo.csv",
        index=False, float_format="%.4f",
    )
    print(f"  Saved tasa_evitable_provincia_anio_sexo.csv "
          f"({len(std_all):,} rows)")

    # ── 6. Trend analysis ─────────────────────────────────────────────────────
    trends_df = None
    if not args.skip_trends:
        print("Fitting trend models...")
        trends_df = fit_trends(std_all, sexo=args.sexo)
        if not trends_df.empty:
            trends_df.to_csv(
                OUTPUT_TABLES / "tendencia_anual_provincia.csv",
                index=False, float_format="%.6f",
            )
            sig = (trends_df["p_valor"] < 0.05).sum()
            print(f"  {len(trends_df)} provinces fitted, {sig} with p<0.05")
        else:
            print("  No trend results (statsmodels missing or insufficient data).")

    # ── 7. Plots ──────────────────────────────────────────────────────────────
    if not args.skip_plots:
        print("Generating plots...")

        plot_temporal_series(std_all, sexo=args.sexo)
        plot_latest_year_bars(std_all, sexo=args.sexo)

        if trends_df is not None and not trends_df.empty:
            plot_trend_ranking(trends_df)

        if args.nbi:
            import pandas as pd
            nbi_path = Path(args.nbi)
            if nbi_path.exists():
                nbi = pd.read_csv(nbi_path)
                plot_inequity_scatter(std_all, nbi, sexo=args.sexo)
            else:
                print(f"  NBI file not found: {args.nbi} — skipping inequity plot.")

    print("\nDone.")


if __name__ == "__main__":
    main()
