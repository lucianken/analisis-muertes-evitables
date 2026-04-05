"""
Visualisation: temporal trends, provincial comparisons, inequity scatter.
"""

import warnings
import numpy as np
import pandas as pd
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mtick
    import seaborn as sns
    _HAS_MPL = True
except ImportError:
    _HAS_MPL = False
    warnings.warn("matplotlib/seaborn not installed. Plots will be skipped.")

from config import OUTPUT_FIGURES


def _require_mpl(fn):
    def wrapper(*args, **kwargs):
        if not _HAS_MPL:
            warnings.warn(f"Skipping {fn.__name__}: matplotlib not available.")
            return
        return fn(*args, **kwargs)
    return wrapper


@_require_mpl
def plot_temporal_series(
    std_rates: pd.DataFrame,
    sexo: int = 0,
    highlight: list[str] | None = None,
    save: bool = True,
):
    """
    Line chart: standardised evitable mortality rate over time, all provinces.
    `highlight` is an optional list of PROV_NOMBRE to draw thicker/labelled.
    """
    data = std_rates[std_rates["SEXO"] == sexo].copy()

    fig, ax = plt.subplots(figsize=(14, 7))
    sns.set_style("whitegrid")

    highlight = set(highlight or [])

    for prov, grp in data.groupby("PROV_NOMBRE"):
        grp = grp.sort_values("ANIO")
        lw = 2.5 if prov in highlight else 0.9
        alpha = 1.0 if prov in highlight else 0.45
        ax.plot(grp["ANIO"], grp["TASA_STD"], label=prov, linewidth=lw, alpha=alpha)
        if prov in highlight:
            last = grp.iloc[-1]
            ax.annotate(prov, (last["ANIO"], last["TASA_STD"]),
                        fontsize=8, ha="left", va="center")

    sexo_label = {0: "ambos sexos", 1: "varones", 2: "mujeres"}.get(sexo, str(sexo))
    ax.set_title(f"Tasa de mortalidad evitable estandarizada por provincia — {sexo_label}",
                 fontsize=13)
    ax.set_xlabel("Año")
    ax.set_ylabel("Defunciones por 100,000 hab.")
    ax.xaxis.set_major_locator(mtick.MaxNLocator(integer=True))

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, fontsize=6.5, ncol=3, loc="upper right",
              framealpha=0.7, title="Provincia")

    plt.tight_layout()
    if save:
        out = OUTPUT_FIGURES / f"serie_temporal_sexo{sexo}.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"Saved: {out}")
    plt.close(fig)


@_require_mpl
def plot_trend_ranking(trends: pd.DataFrame, save: bool = True):
    """
    Horizontal bar chart of % annual change per province, sorted by change.
    """
    if trends.empty:
        warnings.warn("No trend results to plot.")
        return

    fig, ax = plt.subplots(figsize=(9, max(5, len(trends) * 0.4)))
    colors = ["#d73027" if x > 0 else "#1a9850" for x in trends["cambio_pct_anual"]]
    ax.barh(trends["PROV_NOMBRE"], trends["cambio_pct_anual"], color=colors)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Cambio % anual en mortalidad evitable (binomial negativa)")
    ax.set_title("Tendencia temporal de mortalidad evitable por provincia")

    for i, row in trends.iterrows():
        sig = "(*)" if row["p_valor"] < 0.05 else ""
        ax.text(
            row["cambio_pct_anual"] + (0.05 if row["cambio_pct_anual"] >= 0 else -0.05),
            i,
            f"{row['cambio_pct_anual']:.1f}%{sig}",
            va="center",
            ha="left" if row["cambio_pct_anual"] >= 0 else "right",
            fontsize=7.5,
        )

    plt.tight_layout()
    if save:
        out = OUTPUT_FIGURES / "tendencia_anual_provincias.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"Saved: {out}")
    plt.close(fig)


@_require_mpl
def plot_inequity_scatter(
    std_rates: pd.DataFrame,
    nbi: pd.DataFrame,
    anio: int | None = None,
    sexo: int = 0,
    save: bool = True,
):
    """
    Scatter: % households with NBI vs. standardised evitable mortality rate.

    Parameters
    ----------
    nbi   : DataFrame with columns PROVRES, PCT_NBI (and optionally ANIO)
    anio  : year to plot (defaults to most recent year in std_rates)
    """
    if anio is None:
        anio = std_rates["ANIO"].max()

    data = (
        std_rates[(std_rates["ANIO"] == anio) & (std_rates["SEXO"] == sexo)]
        .merge(nbi, on="PROVRES", how="inner")
    )

    if data.empty:
        warnings.warn(f"No data for ANIO={anio}, SEXO={sexo} after joining with NBI.")
        return

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.scatter(data["PCT_NBI"], data["TASA_STD"], s=70, color="#2166ac", zorder=3)

    for _, row in data.iterrows():
        ax.annotate(row["PROV_NOMBRE"], (row["PCT_NBI"], row["TASA_STD"]),
                    fontsize=7.5, xytext=(3, 2), textcoords="offset points")

    m, b = np.polyfit(data["PCT_NBI"], data["TASA_STD"], 1)
    x_range = np.linspace(data["PCT_NBI"].min(), data["PCT_NBI"].max(), 100)
    ax.plot(x_range, m * x_range + b, "r--", linewidth=1.2, label=f"Tendencia lineal")

    ax.set_xlabel("% hogares con NBI")
    ax.set_ylabel("Tasa mortalidad evitable estandarizada (por 100,000)")
    ax.set_title(f"Inequidad: NBI vs. mortalidad evitable — {anio}")
    ax.legend(fontsize=8)

    plt.tight_layout()
    if save:
        out = OUTPUT_FIGURES / f"inequidad_nbi_{anio}.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"Saved: {out}")
    plt.close(fig)


@_require_mpl
def plot_latest_year_bars(
    std_rates: pd.DataFrame,
    anio: int | None = None,
    sexo: int = 0,
    save: bool = True,
):
    """
    Horizontal bar chart of standardised rate by province for the latest year,
    with 95% CI error bars.
    """
    if anio is None:
        anio = std_rates["ANIO"].max()

    data = (
        std_rates[(std_rates["ANIO"] == anio) & (std_rates["SEXO"] == sexo)]
        .sort_values("TASA_STD")
    )

    fig, ax = plt.subplots(figsize=(9, max(5, len(data) * 0.4)))
    ax.barh(data["PROV_NOMBRE"], data["TASA_STD"], color="#4393c3", alpha=0.85)

    xerr_lower = data["TASA_STD"] - data["IC_INF"]
    xerr_upper = data["IC_SUP"] - data["TASA_STD"]
    ax.errorbar(
        data["TASA_STD"],
        range(len(data)),
        xerr=[xerr_lower.clip(lower=0), xerr_upper.clip(lower=0)],
        fmt="none",
        color="black",
        linewidth=1,
        capsize=3,
    )

    ax.set_xlabel("Tasa estandarizada por 100,000 hab.")
    ax.set_title(f"Mortalidad evitable por provincia — {anio}")

    plt.tight_layout()
    if save:
        out = OUTPUT_FIGURES / f"ranking_provincias_{anio}.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"Saved: {out}")
    plt.close(fig)
