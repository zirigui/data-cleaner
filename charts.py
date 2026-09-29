"""Gráficos Altair monocromáticos. Cada função retorna (gráfico, tabela equivalente)."""

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import cleaner as cl

# Tons validados por contraste (marca ≥ 3:1 contra o fundo) em cada modo
PALETTES = {
    "light": {"ink": "#1a1a1a", "muted": "#949494", "text": "#525252", "surface": "#ffffff", "wash": "#f0f0f0"},
    "dark": {"ink": "#ececec", "muted": "#6b6b6b", "text": "#a3a3a3", "surface": "#0e1117", "wash": "#24262c"},
}
BAR = 18  # espessura das barras (≤ 24px)
# Números no padrão brasileiro nos eixos e tooltips
LOCALE = {"number": {"decimal": ",", "thousands": ".", "grouping": [3], "currency": ["R$ ", ""]}}
BEFORE, AFTER = "Antes", "Depois"


def palette() -> dict:
    try:
        mode = st.context.theme.type or "light"
    except Exception:
        mode = "light"
    return PALETTES.get(mode, PALETTES["light"])


def _pair_scale(p):
    return alt.Scale(domain=[BEFORE, AFTER], range=[p["muted"], p["ink"]])


def _legend():
    return alt.Legend(title=None, orient="top", direction="horizontal", symbolType="square")


def _finish(chart):
    return chart.configure(locale=LOCALE)


def _fmt(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------------------- #
# Nulos
# --------------------------------------------------------------------------- #
def null_table(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "coluna": df.columns.astype(str),
        "nulos": df.isna().sum().values,
        "% nulos": (df.isna().mean() * 100).round(2).values,
    })


def nulls_bar(df: pd.DataFrame):
    p = palette()
    data = null_table(df).query("nulos > 0").sort_values("% nulos", ascending=False)
    if data.empty:
        return None, data
    base = alt.Chart(data).encode(
        y=alt.Y("coluna:N", sort="-x", title=None),
        x=alt.X("% nulos:Q", title="% de nulos", scale=alt.Scale(domain=[0, max(100, data["% nulos"].max())])),
        tooltip=["coluna", "nulos", alt.Tooltip("% nulos:Q", format=".2f")],
    )
    bars = base.mark_bar(color=p["ink"], size=BAR, cornerRadiusEnd=4)
    labels = base.mark_text(align="left", dx=6, color=p["text"]).encode(text=alt.Text("% nulos:Q", format=".1f"))
    return _finish((bars + labels).properties(height=max(90, 30 * len(data)))), data


def nulls_compare(before: pd.DataFrame, after: pd.DataFrame):
    p = palette()
    b = null_table(before).assign(momento=BEFORE)
    a = null_table(after).assign(momento=AFTER)
    data = pd.concat([b, a])
    keep = data.groupby("coluna")["nulos"].transform("max") > 0
    data = data[keep]
    if data.empty:
        return None, data
    chart = alt.Chart(data).mark_bar(size=BAR // 2 + 2, cornerRadiusEnd=4).encode(
        y=alt.Y("coluna:N", title=None, sort=alt.EncodingSortField("% nulos", op="max", order="descending")),
        yOffset=alt.YOffset("momento:N", sort=[BEFORE, AFTER]),
        x=alt.X("% nulos:Q", title="% de nulos"),
        color=alt.Color("momento:N", scale=_pair_scale(p), legend=_legend()),
        tooltip=["coluna", "momento", "nulos", alt.Tooltip("% nulos:Q", format=".2f")],
    ).properties(height=max(110, 40 * data["coluna"].nunique()))
    table = data.pivot(index="coluna", columns="momento", values="nulos").reindex(columns=[BEFORE, AFTER]).reset_index()
    return _finish(chart), table


# --------------------------------------------------------------------------- #
# Distribuição numérica
# --------------------------------------------------------------------------- #
MAX_OUTLIER_POINTS = 500


def _histogram(s: pd.Series, bins: int = 30) -> pd.DataFrame:
    counts, edges = np.histogram(s, bins=bins)
    return pd.DataFrame({"inicio": edges[:-1], "fim": edges[1:], "linhas": counts})


def _kde(s: pd.Series, grid: np.ndarray, max_points: int = 5000) -> np.ndarray:
    """Densidade gaussiana (largura de banda de Silverman), calculada em Python."""
    x = s.sample(max_points, random_state=0).to_numpy() if len(s) > max_points else s.to_numpy()
    std = x.std(ddof=1) if len(x) > 1 else 0
    iqr = np.subtract(*np.percentile(x, [75, 25])) if len(x) > 1 else 0
    spread = min(std, iqr / 1.34) if iqr > 0 else std
    if not spread:
        return np.zeros_like(grid)
    bw = 0.9 * spread * len(x) ** (-1 / 5)
    z = (grid[:, None] - x[None, :]) / bw
    return np.exp(-0.5 * z ** 2).sum(axis=1) / (len(x) * bw * np.sqrt(2 * np.pi))


def distribution(series: pd.Series, iqr_factor: float = 1.5, include_outliers: bool = False):
    """Histograma com linhas de média e mediana + boxplot com outliers (IQR).

    Tudo é agregado em Python: o gráfico recebe só as barras, os quartis e uma
    amostra dos outliers, qualquer que seja o tamanho do arquivo.
    """
    p = palette()
    s = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    mean, median = float(s.mean()), float(s.median())
    q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
    low, high = cl.outlier_bounds(s, "IQR", iqr_factor)
    inside = s[(s >= low) & (s <= high)]
    outliers = s[(s < low) | (s > high)]
    # Sem outliers no eixo, o histograma mostra a faixa típica em vez de ser esmagado por extremos
    shown = s if include_outliers or inside.empty else inside
    x_title = str(series.name)
    if len(outliers) and not include_outliers:
        x_title += f" — {len(outliers)} outlier(s) fora do eixo"

    bins = _histogram(shown)
    hist = alt.Chart(bins).mark_bar(
        color=p["muted"], binSpacing=2,  # cantos arredondados somem com bin="binned"
    ).encode(
        x=alt.X("inicio:Q", bin="binned", title=None, scale=alt.Scale(zero=False, nice=False)),
        x2="fim:Q",
        # Folga no topo para os rótulos de média e mediana
        y=alt.Y("linhas:Q", title="Linhas", scale=alt.Scale(domain=[0, max(1, int(bins["linhas"].max() * 1.15))])),
        tooltip=[alt.Tooltip("inicio:Q", format=",.2f", title="de"),
                 alt.Tooltip("fim:Q", format=",.2f", title="até"), "linhas:Q"],
    )
    refs = pd.DataFrame({"medida": ["média", "mediana"], "valor": [mean, median]})
    refs = refs[refs["valor"].between(shown.min(), shown.max())]
    refs["rotulo"] = refs["medida"] + " " + refs["valor"].map(_fmt)
    rules = alt.Chart(refs).mark_rule(color=p["ink"], strokeWidth=2).encode(
        x=alt.X("valor:Q", title=None), tooltip=["medida", alt.Tooltip("valor:Q", format=",.2f")])
    # Rótulos no topo; o da direita alinha à esquerda e vice-versa para não colidirem
    right = "média" if mean >= median else "mediana"

    def label(side_right: bool):
        cond = alt.datum.medida == right if side_right else alt.datum.medida != right
        return alt.Chart(refs).transform_filter(cond).mark_text(
            baseline="top", dy=2, color=p["text"],
            align="left" if side_right else "right", dx=6 if side_right else -6,
        ).encode(x=alt.X("valor:Q", title=None), y=alt.value(0), text="rotulo:N")

    top = (hist + rules + label(True) + label(False)).properties(height=220)

    stats = pd.DataFrame([{"q1": q1, "q3": q3, "mediana": median,
                           "min": float(inside.min()) if len(inside) else q1,
                           "max": float(inside.max()) if len(inside) else q3}])
    box_tip = [alt.Tooltip(c, format=",.2f") for c in ("min:Q", "q1:Q", "mediana:Q", "q3:Q", "max:Q")]
    whisker = alt.Chart(stats).mark_rule(color=p["muted"]).encode(x=alt.X("min:Q", title=x_title), x2="max:Q", tooltip=box_tip)
    box = alt.Chart(stats).mark_bar(color=p["muted"], size=BAR, cornerRadius=4).encode(
        x=alt.X("q1:Q", title=x_title), x2="q3:Q", tooltip=box_tip)
    mid = alt.Chart(stats).mark_tick(color=p["ink"], thickness=2, size=BAR).encode(x=alt.X("mediana:Q", title=x_title), tooltip=box_tip)
    dots_data = outliers if include_outliers else outliers.iloc[0:0]
    if len(dots_data) > MAX_OUTLIER_POINTS:
        dots_data = dots_data.sample(MAX_OUTLIER_POINTS, random_state=0)
    dots = alt.Chart(pd.DataFrame({"valor": dots_data.to_numpy()})).mark_circle(
        color=p["ink"], size=64, opacity=1, stroke=p["surface"], strokeWidth=2,
    ).encode(x=alt.X("valor:Q", title=x_title), tooltip=[alt.Tooltip("valor:Q", format=",.2f", title="outlier")])
    bottom = (whisker + box + mid + dots).properties(height=50)

    table = pd.DataFrame({
        "medida": ["linhas", "média", "mediana", "desvio padrão", "mínimo", "máximo",
                   "assimetria (Pearson)", f"outliers (IQR × {iqr_factor})"],
        "valor": [len(s), mean, median, s.std(), s.min(), s.max(), cl.pearson_skewness(s), len(outliers)],
    })
    return _finish(alt.vconcat(top, bottom, spacing=4).resolve_scale(x="shared")), table


def distribution_compare(before: pd.Series, after: pd.Series):
    """Curvas de densidade sobrepostas (antes em cinza, depois em tinta)."""
    p = palette()
    b = pd.to_numeric(before, errors="coerce").dropna().astype(float)
    a = pd.to_numeric(after, errors="coerce").dropna().astype(float)
    lo, hi = min(b.min(), a.min()), max(b.max(), a.max())
    grid = np.linspace(lo, hi, 200) if hi > lo else np.array([lo])
    data = pd.concat([pd.DataFrame({"valor": grid, "densidade": _kde(b, grid), "momento": BEFORE}),
                      pd.DataFrame({"valor": grid, "densidade": _kde(a, grid), "momento": AFTER})])
    chart = alt.Chart(data).mark_line(strokeWidth=2, strokeJoin="round", strokeCap="round").encode(
        x=alt.X("valor:Q", title=str(after.name), scale=alt.Scale(zero=False, nice=False)),
        y=alt.Y("densidade:Q", title="Densidade", axis=alt.Axis(format=".2~g")),
        color=alt.Color("momento:N", scale=_pair_scale(p), legend=_legend()),
        tooltip=["momento", alt.Tooltip("valor:Q", format=",.2f"), alt.Tooltip("densidade:Q", format=".3~g")],
    ).properties(height=240)
    chart = _finish(chart)

    def stats(s):
        return [len(s), s.mean(), s.median(), s.std(), cl.pearson_skewness(s)]
    table = pd.DataFrame({"medida": ["linhas", "média", "mediana", "desvio padrão", "assimetria (Pearson)"],
                          BEFORE: stats(b), AFTER: stats(a)})
    return chart, table


# --------------------------------------------------------------------------- #
# Categorias e correlação
# --------------------------------------------------------------------------- #
def top_values(series: pd.Series, n: int = 10):
    p = palette()
    counts = series.astype("string").fillna("(nulo)").value_counts()
    data = counts.head(n).rename_axis("valor").reset_index(name="linhas")
    if len(counts) > n:
        data = pd.concat([data, pd.DataFrame({"valor": [f"Outros ({len(counts) - n})"],
                                              "linhas": [int(counts.iloc[n:].sum())]})])
    data["%"] = (data["linhas"] / len(series) * 100).round(1)
    order = data["valor"].tolist()
    data["outros"] = data["valor"].str.startswith("Outros (") & (len(counts) > n)
    base = alt.Chart(data).encode(
        y=alt.Y("valor:N", sort=order, title=None),
        x=alt.X("linhas:Q", title="Linhas"),
        tooltip=["valor", "linhas", alt.Tooltip("%:Q", format=".1f")],
    )
    # O grupo "Outros" fica em cinza para não ser lido como mais uma categoria
    bars = base.mark_bar(size=BAR, cornerRadiusEnd=4).encode(
        color=alt.condition(alt.datum.outros, alt.value(p["muted"]), alt.value(p["ink"])))
    labels = base.mark_text(align="left", dx=6, color=p["text"]).encode(text="linhas:Q")
    return _finish((bars + labels).properties(height=max(90, 30 * len(data)))), data


def correlation(df: pd.DataFrame, max_cols: int = 12):
    """Mapa de calor: tom (cinza) = intensidade |r|; o sinal aparece no número de cada célula."""
    p = palette()
    num = df[cl.numeric_columns(df)].iloc[:, :max_cols]
    if num.shape[1] < 2:
        return None, pd.DataFrame()
    corr = num.corr()
    data = corr.rename_axis("x").reset_index().melt(id_vars="x", var_name="y", value_name="r").dropna()
    data["r"] = data["r"].round(2) + 0.0  # evita "-0,00"
    data["|r|"] = data["r"].abs()
    base = alt.Chart(data).encode(
        x=alt.X("x:N", title=None, sort=list(corr.columns), axis=alt.Axis(labelAngle=-40)),
        y=alt.Y("y:N", title=None, sort=list(corr.columns)),
    )
    cells = base.mark_rect(stroke=p["surface"], strokeWidth=2, cornerRadius=2).encode(
        color=alt.Color("|r|:Q", scale=alt.Scale(domain=[0, 1], range=[p["wash"], p["ink"]]),
                        legend=alt.Legend(title="|r|", orient="right", gradientLength=120)),
        tooltip=["x", "y", alt.Tooltip("r:Q", format="+.2f")],
    )
    # Texto claro sobre célula escura e vice-versa
    text = base.mark_text(fontSize=11).encode(
        text=alt.Text("r:Q", format="+.2f"),
        color=alt.condition(alt.datum["|r|"] > 0.55, alt.value(p["surface"]), alt.value(p["text"])),
    )
    size = max(220, 46 * len(corr))
    return _finish((cells + text).properties(height=size)), corr.round(3).reset_index(names="coluna")
