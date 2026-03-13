"""
VIX Analytics Platform — Streamlit App
=======================================
App completa con constructor parametrizable de spreads/butterflies,
gráficos estacionales, stacked years, valoración 2D y scanner.

Deploy gratuito en Streamlit Community Cloud.

Uso local:
    pip install streamlit plotly pandas numpy
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="VIX Analytics Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Tema oscuro personalizado
COLORS = {
    "bg": "#0a0e17",
    "panel": "#111827",
    "text": "#e2e8f0",
    "dim": "#94a3b8",
    "accent": "#3b82f6",
    "green": "#10b981",
    "red": "#ef4444",
    "orange": "#f59e0b",
    "purple": "#a855f7",
    "cyan": "#06b6d4",
    "year_colors": [
        "#6366f1", "#ec4899", "#14b8a6", "#f97316", "#8b5cf6",
        "#06b6d4", "#84cc16", "#e11d48", "#0ea5e9", "#d946ef",
        "#fbbf24", "#22d3ee", "#a3e635", "#fb923c", "#c084fc",
    ],
}

PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#111827",
    font=dict(family="JetBrains Mono, Fira Code, monospace", color=COLORS["text"]),
    margin=dict(l=50, r=30, t=50, b=50),
    xaxis=dict(gridcolor="#1e293b", gridwidth=1),
    yaxis=dict(gridcolor="#1e293b", gridwidth=1),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)

# ═══════════════════════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700;800&display=swap');

    .stApp {
        background: #0a0e17;
        font-family: 'JetBrains Mono', monospace;
    }

    section[data-testid="stSidebar"] {
        background: #111827;
        border-right: 1px solid #1e293b;
    }

    h1, h2, h3, h4 { color: #e2e8f0 !important; }

    .metric-card {
        background: #111827;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 16px 20px;
        text-align: center;
    }
    .metric-value {
        font-size: 24px;
        font-weight: 800;
        margin: 4px 0;
    }
    .metric-label {
        font-size: 10px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.12em;
    }

    .signal-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 700;
    }
    .signal-extremo-barato { background: #10b98120; color: #10b981; }
    .signal-barato { background: #10b98110; color: #6ee7b7; }
    .signal-neutral { background: #94a3b810; color: #94a3b8; }
    .signal-caro { background: #f59e0b15; color: #f59e0b; }
    .signal-extremo-caro { background: #ef444420; color: #ef4444; }

    .header-bar {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
        border-bottom: 1px solid #1e293b;
        padding: 16px 24px;
        border-radius: 10px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .header-title {
        font-size: 22px;
        font-weight: 800;
        color: white;
        letter-spacing: 0.05em;
    }
    .header-accent { color: #3b82f6; }
    .header-badge {
        font-size: 10px;
        padding: 2px 8px;
        border-radius: 4px;
        background: rgba(59,130,246,0.15);
        color: #3b82f6;
        font-weight: 600;
        letter-spacing: 0.1em;
    }

    div[data-testid="stExpander"] {
        background: #111827;
        border: 1px solid #1e293b;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600)
def load_data():
    """Carga datos desde el JSON exportado del notebook de Colab."""
    json_path = os.path.join(os.path.dirname(__file__), "vix_spreads_data.json")

    if os.path.exists(json_path):
        with open(json_path, "r") as f:
            raw = json.load(f)

        # Convertir a DataFrames por spread
        data = {}
        for spread_name, spread_data in raw.items():
            all_rows = []
            for year_str, rows in spread_data.get("spreadsByYear", {}).items():
                for r in rows:
                    all_rows.append({
                        "trade_date": r["date"],
                        "monthDay": r["monthDay"],
                        "spread": r["spread"],
                        "vix": r.get("vix"),
                        "dte": r.get("dte"),
                        "year": int(year_str),
                    })
            if all_rows:
                data[spread_name] = pd.DataFrame(all_rows)
        return data, True

    return None, False


@st.cache_data(ttl=3600)
def load_sqlite_data():
    """Carga datos directamente desde SQLite si está disponible."""
    import sqlite3

    db_path = os.path.join(os.path.dirname(__file__), "vix_analytics.db")
    if not os.path.exists(db_path):
        return None

    conn = sqlite3.connect(db_path)

    # Cargar futuros
    df_futures = pd.read_sql("""
        SELECT trade_date, expiry, settle, dte, volume
        FROM vix_futures_eod
        WHERE settle > 0 AND dte > 0
        ORDER BY trade_date, dte
    """, conn)

    # Cargar VIX spot
    df_vix = pd.read_sql("SELECT trade_date, close as vix FROM vix_spot", conn)
    conn.close()

    return df_futures, df_vix


def compute_custom_spread(df_futures, df_vix, legs):
    """
    Calcula un spread/butterfly/combinación personalizada.

    legs: lista de dicts con {month: int, weight: float}
          Ej: M1-M2 = [{month:1, weight:1}, {month:2, weight:-1}]
          Ej: Butterfly = [{month:1, weight:1}, {month:2, weight:-2}, {month:3, weight:1}]
    """
    if df_futures is None or df_futures.empty:
        return None

    # Asignar ranking M1, M2, M3... por fecha
    df = df_futures.copy()
    df["month_rank"] = df.groupby("trade_date")["dte"].rank(method="first").astype(int)

    # Extraer cada pata
    leg_dfs = []
    for i, leg in enumerate(legs):
        m = leg["month"]
        w = leg["weight"]
        leg_df = df[df["month_rank"] == m][["trade_date", "settle", "dte"]].copy()
        leg_df = leg_df.rename(columns={"settle": f"settle_{i}", "dte": f"dte_{i}"})
        leg_dfs.append((leg_df, w, i))

    if not leg_dfs:
        return None

    # Merge todas las patas
    result = leg_dfs[0][0]
    for leg_df, w, i in leg_dfs[1:]:
        result = result.merge(leg_df, on="trade_date", how="inner")

    # Calcular spread
    result["spread"] = sum(
        leg["weight"] * result[f"settle_{i}"]
        for i, leg in enumerate(legs)
    )

    # DTE del front month (la pata más cercana)
    dte_cols = [f"dte_{i}" for i in range(len(legs))]
    result["dte_front"] = result[dte_cols].min(axis=1)

    # Merge con VIX spot
    if df_vix is not None:
        result = result.merge(df_vix, on="trade_date", how="left")

    # Campos extra
    result["trade_date"] = pd.to_datetime(result["trade_date"])
    result["year"] = result["trade_date"].dt.year
    result["monthDay"] = result["trade_date"].dt.strftime("%m-%d")

    return result


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR — CONSTRUCTOR DE SPREADS
# ═══════════════════════════════════════════════════════════════════════════
def render_sidebar():
    """Renderiza el panel lateral con el constructor de spreads."""

    st.sidebar.markdown("""
    <div style='text-align:center; padding: 8px 0 16px 0;'>
        <span style='font-size:20px; font-weight:800; letter-spacing:0.05em;'>
            <span style='color:#3b82f6;'>VIX</span> ANALYTICS
        </span>
        <br>
        <span style='font-size:9px; color:#94a3b8; letter-spacing:0.15em;'>SPREAD BUILDER v1.0</span>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("---")

    # ── Presets rápidos ──
    st.sidebar.markdown("##### ⚡ Presets rápidos")
    preset_col1, preset_col2 = st.sidebar.columns(2)

    presets = {
        "M1−M2": [{"month": 1, "weight": 1.0}, {"month": 2, "weight": -1.0}],
        "M2−M3": [{"month": 2, "weight": 1.0}, {"month": 3, "weight": -1.0}],
        "M1−M3": [{"month": 1, "weight": 1.0}, {"month": 3, "weight": -1.0}],
        "M4−M5": [{"month": 4, "weight": 1.0}, {"month": 5, "weight": -1.0}],
        "Fly 1-2-3": [{"month": 1, "weight": 1.0}, {"month": 2, "weight": -2.0}, {"month": 3, "weight": 1.0}],
        "Fly 2-3-4": [{"month": 2, "weight": 1.0}, {"month": 3, "weight": -2.0}, {"month": 4, "weight": 1.0}],
    }

    for i, (name, legs) in enumerate(presets.items()):
        col = preset_col1 if i % 2 == 0 else preset_col2
        if col.button(name, key=f"preset_{name}", use_container_width=True):
            st.session_state["custom_legs"] = legs
            st.session_state["n_legs"] = len(legs)

    st.sidebar.markdown("---")

    # ── Constructor personalizado ──
    st.sidebar.markdown("##### 🔧 Constructor personalizado")

    n_legs = st.sidebar.radio(
        "Número de patas",
        [2, 3],
        index=0 if st.session_state.get("n_legs", 2) == 2 else 1,
        horizontal=True,
        key="n_legs_radio",
    )

    # Inicializar patas por defecto
    if "custom_legs" not in st.session_state:
        st.session_state["custom_legs"] = [
            {"month": 1, "weight": 1.0},
            {"month": 2, "weight": -1.0},
        ]

    legs = st.session_state["custom_legs"]

    # Ajustar número de patas
    while len(legs) < n_legs:
        legs.append({"month": len(legs) + 1, "weight": 1.0})
    while len(legs) > n_legs:
        legs.pop()

    new_legs = []
    for i in range(n_legs):
        st.sidebar.markdown(f"**Pata {i + 1}**")
        col_m, col_w = st.sidebar.columns([1, 1])

        default_month = legs[i]["month"] if i < len(legs) else i + 1
        default_weight = legs[i]["weight"] if i < len(legs) else (1.0 if i != 1 else -1.0)

        month = col_m.selectbox(
            "Contrato",
            options=list(range(1, 9)),
            format_func=lambda x: f"M{x}",
            index=min(default_month - 1, 7),
            key=f"leg_month_{i}",
        )
        weight = col_w.number_input(
            "Peso",
            value=float(default_weight),
            step=0.5,
            min_value=-5.0,
            max_value=5.0,
            key=f"leg_weight_{i}",
        )
        new_legs.append({"month": month, "weight": weight})

    st.session_state["custom_legs"] = new_legs

    # Mostrar fórmula
    formula_parts = []
    for leg in new_legs:
        w = leg["weight"]
        m = f"M{leg['month']}"
        if w == 1:
            formula_parts.append(f"+{m}")
        elif w == -1:
            formula_parts.append(f"−{m}")
        elif w > 0:
            formula_parts.append(f"+{w}{m}")
        else:
            formula_parts.append(f"{w}{m}")

    formula = " ".join(formula_parts).lstrip("+").strip()
    st.sidebar.markdown(f"""
    <div style='background:#1e293b; border:1px solid #334155; border-radius:8px;
                padding:10px 14px; text-align:center; margin:12px 0;'>
        <span style='color:#94a3b8; font-size:10px; text-transform:uppercase;
                     letter-spacing:0.1em;'>Fórmula</span><br>
        <span style='color:#fff; font-size:16px; font-weight:700;'>{formula}</span>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("---")

    # ── Filtros ──
    st.sidebar.markdown("##### 📅 Período")
    current_year = datetime.now().year
    year_from = st.sidebar.slider(
        "Desde año",
        min_value=2004,
        max_value=current_year,
        value=2015,
        key="year_from",
    )

    stacked_window = st.sidebar.select_slider(
        "Ventana stacked (años)",
        options=[5, 10, 15, 20],
        value=10,
        key="stacked_window",
    )

    return new_legs, formula, year_from, stacked_window


# ═══════════════════════════════════════════════════════════════════════════
# CHARTS
# ═══════════════════════════════════════════════════════════════════════════
def chart_seasonal(df, formula):
    """Gráfico estacional: año actual + medias 5/10/15 años."""
    if df is None or df.empty:
        return None

    current_year = df["year"].max()

    fig = go.Figure()

    # Medias
    for window, color, dash in [(15, COLORS["accent"], "dot"), (10, COLORS["green"], "dash"), (5, COLORS["red"], "dashdot")]:
        years = range(current_year - window, current_year)
        subset = df[df["year"].isin(years)]
        if not subset.empty:
            avg = subset.groupby("monthDay")["spread"].mean().reset_index()
            avg = avg.sort_values("monthDay")
            fig.add_trace(go.Scatter(
                x=avg["monthDay"], y=avg["spread"],
                mode="lines", name=f"Media {window}y",
                line=dict(color=color, width=1.5, dash=dash),
                hovertemplate="%{x}<br>%{y:.3f}<extra></extra>",
            ))

    # Año actual
    current = df[df["year"] == current_year].sort_values("monthDay")
    if not current.empty:
        fig.add_trace(go.Scatter(
            x=current["monthDay"], y=current["spread"],
            mode="lines", name=f"{current_year} (actual)",
            line=dict(color="white", width=2.5),
            hovertemplate="%{x}<br>%{y:.3f}<extra></extra>",
        ))

    fig.add_hline(y=0, line_dash="dash", line_color="#475569", line_width=0.5)
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text=f"Seasonal Builder — {formula}", font=dict(size=14)),
        height=450,
        xaxis_title="Fecha (MM-DD)",
        yaxis_title="Spread",
    )
    return fig


def chart_stacked(df, formula, window=10):
    """Todos los años superpuestos."""
    if df is None or df.empty:
        return None

    current_year = df["year"].max()
    years = sorted(df["year"].unique())
    years = [y for y in years if y >= current_year - window]

    fig = go.Figure()

    for i, y in enumerate(years):
        subset = df[df["year"] == y].sort_values("monthDay")
        is_current = y == current_year
        fig.add_trace(go.Scatter(
            x=subset["monthDay"], y=subset["spread"],
            mode="lines", name=str(y),
            line=dict(
                color="white" if is_current else COLORS["year_colors"][i % len(COLORS["year_colors"])],
                width=2.5 if is_current else 1,
            ),
            opacity=1.0 if is_current else 0.5,
            hovertemplate=f"{y}<br>" + "%{x}: %{y:.3f}<extra></extra>",
        ))

    fig.add_hline(y=0, line_dash="dash", line_color="#475569", line_width=0.5)
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text=f"Stacked Years — {formula} (últimos {window} años)", font=dict(size=14)),
        height=480,
        xaxis_title="Fecha (MM-DD)",
        yaxis_title="Spread",
    )
    return fig


def chart_histogram(df, formula):
    """Histograma de valoración con posición actual."""
    if df is None or df.empty:
        return None

    current_year = df["year"].max()
    latest = df[df["year"] == current_year].iloc[-1] if not df[df["year"] == current_year].empty else None
    if latest is None:
        return None

    # Filtrar observaciones similares en VIX y DTE
    similar = df.copy()
    if latest.get("vix") is not None and pd.notna(latest["vix"]):
        similar = similar[
            (similar["vix"].notna()) &
            (similar["vix"].between(latest["vix"] - 5, latest["vix"] + 5))
        ]
    if latest.get("dte") is not None and pd.notna(latest["dte"]):
        similar = similar[
            (similar["dte_front"].notna() if "dte_front" in similar.columns else True)
        ]

    spreads = similar["spread"].dropna()
    if len(spreads) < 20:
        spreads = df["spread"].dropna()  # Fallback a toda la muestra

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=spreads, nbinsx=40, name="Distribución",
        marker_color="#334155",
        hovertemplate="Rango: %{x:.2f}<br>Frecuencia: %{y}<extra></extra>",
    ))

    # Línea vertical del precio actual
    fig.add_vline(x=latest["spread"], line_color=COLORS["accent"], line_width=2.5)
    fig.add_annotation(
        x=latest["spread"], y=0, yref="paper", yanchor="bottom",
        text=f"ACTUAL: {latest['spread']:.3f}", showarrow=False,
        font=dict(color=COLORS["accent"], size=11, family="JetBrains Mono"),
        bgcolor="rgba(59,130,246,0.15)", borderpad=4,
    )

    pct = (spreads < latest["spread"]).mean() * 100

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text=f"Distribución Histórica — {formula} (percentil: {pct:.0f}%)", font=dict(size=14)),
        height=300,
        showlegend=False,
        xaxis_title="Spread",
        yaxis_title="Frecuencia",
    )
    return fig, pct


def compute_percentile_matrix(df):
    """Calcula la matriz de percentiles 2D (VIX × DTE)."""
    if df is None or df.empty:
        return None

    result_df = df.dropna(subset=["vix"]).copy()
    if "dte_front" in result_df.columns:
        result_df = result_df.dropna(subset=["dte_front"])
        dte_col = "dte_front"
    elif "dte" in result_df.columns:
        result_df = result_df.dropna(subset=["dte"])
        dte_col = "dte"
    else:
        return None

    if result_df.empty:
        return None

    vix_bins = [(0, 15, "<15"), (15, 20, "15-20"), (20, 25, "20-25"), (25, 35, "25-35"), (35, 200, ">35")]
    dte_bins = [(0, 15, "0-15d"), (15, 30, "15-30d"), (30, 60, "30-60d"), (60, 90, "60-90d"), (90, 999, ">90d")]

    matrix = []
    for vmin, vmax, vlabel in vix_bins:
        row = {"vix_bucket": vlabel}
        for dmin, dmax, dlabel in dte_bins:
            mask = (
                (result_df["vix"] >= vmin) & (result_df["vix"] < vmax) &
                (result_df[dte_col] >= dmin) & (result_df[dte_col] < dmax)
            )
            cell_data = result_df.loc[mask, "spread"]
            if len(cell_data) >= 10:
                row[dlabel] = {
                    "p10": cell_data.quantile(0.10),
                    "p50": cell_data.quantile(0.50),
                    "p90": cell_data.quantile(0.90),
                    "n": len(cell_data),
                }
            else:
                row[dlabel] = {"insufficient": True, "n": len(cell_data)}
        matrix.append(row)

    return matrix, dte_bins


# ═══════════════════════════════════════════════════════════════════════════
# SCANNER
# ═══════════════════════════════════════════════════════════════════════════
def compute_scanner(df_futures, df_vix):
    """Calcula valoración para todos los spreads principales."""
    if df_futures is None:
        return None

    spread_configs = [
        ("M1−M2", [{"month": 1, "weight": 1}, {"month": 2, "weight": -1}]),
        ("M2−M3", [{"month": 2, "weight": 1}, {"month": 3, "weight": -1}]),
        ("M3−M4", [{"month": 3, "weight": 1}, {"month": 4, "weight": -1}]),
        ("M4−M5", [{"month": 4, "weight": 1}, {"month": 5, "weight": -1}]),
        ("M1−M3", [{"month": 1, "weight": 1}, {"month": 3, "weight": -1}]),
        ("M2−M4", [{"month": 2, "weight": 1}, {"month": 4, "weight": -1}]),
        ("Fly 1-2-3", [{"month": 1, "weight": 1}, {"month": 2, "weight": -2}, {"month": 3, "weight": 1}]),
        ("Fly 2-3-4", [{"month": 2, "weight": 1}, {"month": 3, "weight": -2}, {"month": 4, "weight": 1}]),
    ]

    results = []
    for name, legs in spread_configs:
        try:
            df = compute_custom_spread(df_futures, df_vix, legs)
            if df is not None and not df.empty:
                current_year = df["year"].max()
                latest = df[df["year"] == current_year].iloc[-1]
                all_spreads = df["spread"].dropna().sort_values()
                pct = (all_spreads < latest["spread"]).mean() * 100

                signal = (
                    "EXTREMO BARATO" if pct < 10 else
                    "BARATO" if pct < 30 else
                    "NEUTRAL" if pct < 70 else
                    "CARO" if pct < 90 else
                    "EXTREMO CARO"
                )

                results.append({
                    "Spread": name,
                    "Precio": round(latest["spread"], 3),
                    "DTE": int(latest.get("dte_front", 0)) if pd.notna(latest.get("dte_front")) else "—",
                    "VIX": round(latest["vix"], 1) if pd.notna(latest.get("vix")) else "—",
                    "Percentil": f"{pct:.0f}%",
                    "Señal": signal,
                    "_pct": pct,
                })
        except Exception:
            pass

    return results


# ═══════════════════════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════════════════════
def main():
    # Header
    st.markdown("""
    <div class="header-bar">
        <span class="header-title"><span class="header-accent">VIX</span> ANALYTICS</span>
        <span class="header-badge">PLATFORM v1.0</span>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    legs, formula, year_from, stacked_window = render_sidebar()

    # ── Load data ──
    # Intentar primero SQLite, luego JSON
    df_futures, df_vix = None, None
    spread_df = None

    sqlite_data = load_sqlite_data()
    json_data, json_loaded = load_data()

    if sqlite_data is not None:
        df_futures, df_vix = sqlite_data
        st.sidebar.success(f"📊 SQLite: {len(df_futures):,} registros")
        # Calcular spread personalizado
        spread_df = compute_custom_spread(df_futures, df_vix, legs)
        if year_from:
            spread_df = spread_df[spread_df["year"] >= year_from] if spread_df is not None else None

    elif json_loaded and json_data:
        # Construir spread desde datos JSON precalculados
        # Mapear legs a nombre de spread en JSON
        st.sidebar.info("📁 Datos JSON cargados")

        # Intentar mapeo directo
        key = f"M{legs[0]['month']}_M{legs[-1]['month']}"
        if key in json_data:
            spread_df = json_data[key]
            if year_from:
                spread_df = spread_df[spread_df["year"] >= year_from]
        else:
            st.sidebar.warning(f"Spread {formula} no precalculado en JSON. Sube el .db para spreads personalizados.")
    else:
        st.warning("⚠️ No se encontraron datos. Coloca `vix_analytics.db` o `vix_spreads_data.json` en el directorio de la app.")
        st.info("""
        **Cómo obtener los datos:**
        1. Ejecuta el notebook de Google Colab para descargar datos de CBOE
        2. Descarga `vix_analytics.db` y/o `vix_spreads_data.json`
        3. Colócalos en el mismo directorio que este archivo `app.py`
        """)
        return

    # ── Tabs ──
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Seasonal Builder",
        "📊 Stacked Years",
        "🎯 Valoración 2D",
        "🔍 Scanner",
        "📋 Datos Históricos",
    ])

    # ── Quick stats ──
    if spread_df is not None and not spread_df.empty:
        current_year = spread_df["year"].max()
        latest = spread_df[spread_df["year"] == current_year]
        if not latest.empty:
            latest_row = latest.iloc[-1]
            cols = st.columns(4)

            spread_val = latest_row["spread"]
            color = COLORS["green"] if spread_val >= 0 else COLORS["red"]
            cols[0].markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Spread Actual</div>
                <div class="metric-value" style="color:{color}">{spread_val:.3f}</div>
            </div>""", unsafe_allow_html=True)

            vix_val = latest_row.get("vix")
            cols[1].markdown(f"""
            <div class="metric-card">
                <div class="metric-label">VIX Spot</div>
                <div class="metric-value" style="color:{COLORS['orange']}">{f'{vix_val:.1f}' if pd.notna(vix_val) else '—'}</div>
            </div>""", unsafe_allow_html=True)

            dte_val = latest_row.get("dte_front", latest_row.get("dte"))
            cols[2].markdown(f"""
            <div class="metric-card">
                <div class="metric-label">DTE Front</div>
                <div class="metric-value" style="color:{COLORS['cyan']}">{f'{int(dte_val)}d' if pd.notna(dte_val) else '—'}</div>
            </div>""", unsafe_allow_html=True)

            cols[3].markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Fórmula</div>
                <div class="metric-value" style="color:{COLORS['accent']}; font-size:16px;">{formula}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

    # ── TAB 1: Seasonal Builder ──
    with tab1:
        fig = chart_seasonal(spread_df, formula)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos suficientes para el gráfico estacional")

    # ── TAB 2: Stacked Years ──
    with tab2:
        fig = chart_stacked(spread_df, formula, stacked_window)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos suficientes para stacked years")

    # ── TAB 3: Valoración 2D ──
    with tab3:
        col_hist, col_pct = st.columns([1, 1])

        with col_hist:
            result = chart_histogram(spread_df, formula)
            if result:
                fig_hist, pct = result
                st.plotly_chart(fig_hist, use_container_width=True)

                # Signal badge
                if pct < 10:
                    cls = "extremo-barato"
                    lbl = "EXTREMO BARATO"
                elif pct < 30:
                    cls = "barato"
                    lbl = "BARATO"
                elif pct < 70:
                    cls = "neutral"
                    lbl = "NEUTRAL"
                elif pct < 90:
                    cls = "caro"
                    lbl = "CARO"
                else:
                    cls = "extremo-caro"
                    lbl = "EXTREMO CARO"

                st.markdown(f"""
                <div style="text-align:center; padding:12px;">
                    <span class="signal-badge signal-{cls}">{lbl}</span>
                    <span style="color:#94a3b8; font-size:12px; margin-left:12px;">
                        Percentil: {pct:.1f}%
                    </span>
                </div>
                """, unsafe_allow_html=True)

        with col_pct:
            st.markdown("**Tabla de Percentiles: VIX × DTE**")
            pct_result = compute_percentile_matrix(spread_df)
            if pct_result:
                matrix, dte_bins = pct_result
                # Renderizar como tabla HTML
                dte_labels = [db[2] for db in dte_bins]
                html = "<table style='width:100%; border-collapse:collapse; font-size:11px;'>"
                html += "<tr><th style='padding:6px; border-bottom:1px solid #1e293b; color:#94a3b8;'>VIX \\ DTE</th>"
                for dl in dte_labels:
                    html += f"<th style='padding:6px; border-bottom:1px solid #1e293b; color:#94a3b8; text-align:center;'>{dl}</th>"
                html += "</tr>"

                for row in matrix:
                    html += f"<tr><td style='padding:6px; border-bottom:1px solid #1e293b08; font-weight:600;'>{row['vix_bucket']}</td>"
                    for dl in dte_labels:
                        cell = row.get(dl, {})
                        if cell.get("insufficient"):
                            html += f"<td style='padding:6px; text-align:center; color:#475569;'>n={cell['n']}</td>"
                        elif "p50" in cell:
                            html += f"""<td style='padding:6px; text-align:center; line-height:1.5;'>
                                <span style='color:#10b981;'>{cell['p10']:.2f}</span> /
                                <span style='color:#fff; font-weight:700;'>{cell['p50']:.2f}</span> /
                                <span style='color:#ef4444;'>{cell['p90']:.2f}</span>
                                <br><span style='color:#475569; font-size:9px;'>n={cell['n']}</span>
                            </td>"""
                        else:
                            html += "<td style='padding:6px; text-align:center; color:#475569;'>—</td>"
                    html += "</tr>"
                html += "</table>"
                html += "<p style='font-size:10px; color:#94a3b8; margin-top:8px;'>Formato: <span style=\"color:#10b981\">p10</span> / <span style=\"color:#fff\">p50</span> / <span style=\"color:#ef4444\">p90</span></p>"
                st.markdown(html, unsafe_allow_html=True)
            else:
                st.info("Datos insuficientes para percentiles 2D (necesita VIX spot y DTE)")

    # ── TAB 4: Scanner ──
    with tab4:
        if df_futures is not None:
            scanner_data = compute_scanner(df_futures, df_vix)
            if scanner_data:
                st.markdown("**Scanner de Oportunidades — Todos los spreads**")

                for row in scanner_data:
                    pct = row["_pct"]
                    if pct < 10:
                        bg, tc = "#10b98118", "#10b981"
                    elif pct < 30:
                        bg, tc = "#10b98110", "#6ee7b7"
                    elif pct < 70:
                        bg, tc = "#94a3b808", "#94a3b8"
                    elif pct < 90:
                        bg, tc = "#f59e0b12", "#f59e0b"
                    else:
                        bg, tc = "#ef444418", "#ef4444"

                    trend = "↑" if pct > 60 else "↓" if pct < 40 else "→"

                    cols = st.columns([2, 1.5, 1, 1, 1.5, 2, 0.5])
                    cols[0].markdown(f"**{row['Spread']}**")
                    price_color = COLORS["green"] if row["Precio"] >= 0 else COLORS["red"]
                    cols[1].markdown(f"<span style='color:{price_color}; font-weight:600;'>{row['Precio']}</span>", unsafe_allow_html=True)
                    cols[2].markdown(f"{row['DTE']}")
                    cols[3].markdown(f"{row['VIX']}")
                    cols[4].markdown(f"{row['Percentil']}")
                    cols[5].markdown(f"<span class='signal-badge signal-{row['Señal'].lower().replace(' ', '-')}'>{row['Señal']}</span>", unsafe_allow_html=True)
                    cols[6].markdown(f"<span style='font-size:18px;'>{trend}</span>", unsafe_allow_html=True)
            else:
                st.info("No se pudo calcular el scanner")
        else:
            st.info("El scanner necesita la base de datos SQLite para calcular todos los spreads")

    # ── TAB 5: Datos Históricos ──
    with tab5:
        if spread_df is not None and not spread_df.empty:
            current_year = spread_df["year"].max()

            target_md = st.selectbox(
                "Seleccionar fecha (MM-DD)",
                options=sorted(spread_df[spread_df["year"] == current_year]["monthDay"].unique(), reverse=True),
                index=0,
            )

            years = sorted(spread_df["year"].unique(), reverse=True)
            table_data = []
            current_spread = None

            for y in years:
                match = spread_df[(spread_df["year"] == y) & (spread_df["monthDay"] == target_md)]
                if not match.empty:
                    row = match.iloc[-1]
                    s = row["spread"]
                    if y == current_year:
                        current_spread = s
                    table_data.append({
                        "Año": f"{'▶ ' if y == current_year else ''}{y}",
                        "Spread": round(s, 3),
                        "VIX": round(row["vix"], 1) if pd.notna(row.get("vix")) else "—",
                        "vs Actual": round(s - current_spread, 3) if current_spread is not None and y != current_year else "—",
                    })

            if table_data:
                st.dataframe(
                    pd.DataFrame(table_data),
                    use_container_width=True,
                    hide_index=True,
                )

                # Botón de exportar
                csv = pd.DataFrame(table_data).to_csv(index=False)
                st.download_button("📥 Exportar a CSV", csv, f"historico_{formula.replace(' ', '_')}.csv", "text/csv")


if __name__ == "__main__":
    main()
