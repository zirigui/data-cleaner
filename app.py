import pandas as pd
import streamlit as st

import charts as ch
import cleaner as cl

st.set_page_config(page_title="Limpador de Dados", page_icon=":material/cleaning_services:", layout="wide")

STEPS = ["Carregar", "Diagnóstico", "Limpeza", "Resultado"]
SEPARATORS = {"Automático": None, "Vírgula (,)": ",", "Ponto e vírgula (;)": ";", "Tab": "\t", "Barra vertical (|)": "|"}
TYPE_TARGETS = ["número", "inteiro", "data", "texto", "categoria", "booleano"]
IMPUTE_METHODS = ["automática (Pearson)", "média", "mediana", "moda", "valor fixo",
                  "forward fill", "backward fill", "interpolação linear"]
FEATURES = [
    ("Nulos e duplicatas", "Remove linhas repetidas, linhas com valores ausentes e colunas vazias demais."),
    ("Texto", "Tira espaços extras, padroniza maiúsculas e minúsculas, remove acentos e símbolos."),
    ("Tipos e colunas", "Converte números no formato brasileiro, datas e booleanos; renomeia e exclui colunas."),
    ("Imputação", "Preenche nulos com média, mediana, moda, valor fixo, forward/backward fill ou interpolação."),
    ("Assimetria de Pearson", "No modo automático, escolhe entre média e mediana conforme a assimetria de cada coluna."),
    ("Outliers e filtros", "Detecta valores extremos por IQR ou Z-score e mantém só as linhas que interessam."),
]
PREVIEW_ROWS = 1000

st.markdown(
    """
    <style>
    /* Sem barra de ferramentas (links para GitHub, fork, menu) */
    [data-testid="stToolbar"], [data-testid="stToolbarActions"], .stAppDeployButton,
    [data-testid="stMainMenu"], #MainMenu { display: none !important; }
    header[data-testid="stHeader"] { background: transparent; }
    .block-container { max-width: 1100px; padding-top: 2.5rem; }

    .stepper { display: flex; margin: .25rem 0 2rem; border-bottom: 1px solid rgba(128,128,128,.25); }
    .stepper .step { flex: 1; padding: .6rem 0; font-size: .9rem; opacity: .45;
                     border-bottom: 2px solid transparent; margin-bottom: -1px; }
    .stepper .step b { font-weight: 600; margin-right: .5rem; }
    .stepper .step.done { opacity: .75; }
    .stepper .step.current { opacity: 1; border-bottom-color: currentColor; font-weight: 600; }
    .feature h4 { font-size: 1rem; font-weight: 600; margin: 0 0 .25rem; padding: 0; }
    .feature p { font-size: .9rem; opacity: .7; margin: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Streamlit descarta o estado de widgets que não aparecem na tela; reatribuir as
# chaves mantém as opções da limpeza ao navegar entre as etapas.
for _key in list(st.session_state.keys()):
    if _key.startswith("opt_"):
        st.session_state[_key] = st.session_state[_key]

state = st.session_state
state.setdefault("step", 1)


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Lendo arquivo...")
def load(data: bytes, name: str, sep: str | None, sheet: str | None):
    return cl.read_file(data, name, sep, sheet)


@st.cache_data
def sheets(data: bytes):
    return cl.excel_sheets(data)


def go(step: int):
    state.step = step
    st.rerun()


def fmt_int(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def fmt_delta(n: int) -> str:
    return f"{n:+d}" if n else "0"


def reset_options():
    for key in list(state.keys()):
        if key.startswith("opt_") or key in ("cleaned", "log", "config"):
            del state[key]


def stepper(current: int):
    items = []
    for i, name in enumerate(STEPS, start=1):
        cls = "current" if i == current else ("done" if i < current else "")
        items.append(f'<div class="step {cls}"><b>{i}</b>{name}</div>')
    st.markdown(f'<div class="stepper">{"".join(items)}</div>', unsafe_allow_html=True)


def show_chart(chart, table: pd.DataFrame, empty_msg: str = "Nada a mostrar."):
    if chart is None:
        st.caption(empty_msg)
        return
    st.altair_chart(chart, width="stretch")
    with st.expander("Ver dados do gráfico"):
        st.dataframe(table, hide_index=True, width="stretch")


def show_table(df: pd.DataFrame):
    if len(df) > PREVIEW_ROWS:
        st.caption(f"Primeiras {fmt_int(PREVIEW_ROWS)} de {fmt_int(len(df))} linhas")
    try:
        st.dataframe(df.head(PREVIEW_ROWS), width="stretch")
    except Exception:
        st.dataframe(df.head(PREVIEW_ROWS).astype(str), width="stretch")


def metrics(df: pd.DataFrame):
    return len(df), df.shape[1], int(df.isna().sum().sum()), int(df.duplicated().sum())


def nav(back: int | None = None, forward: tuple[str, int] | None = None, forward_disabled=False):
    st.write("")
    left, _, right = st.columns([1, 3, 1])
    if back and left.button("Voltar", icon=":material/arrow_back:", width="stretch"):
        go(back)
    if forward and right.button(forward[0], type="primary", width="stretch", disabled=forward_disabled):
        go(forward[1])


def current_data():
    """DataFrame original do arquivo em memória (ou None)."""
    if "file_data" not in state:
        return None
    try:
        df, used_sep = load(state.file_data, state.file_name, state.get("sep_value"), state.get("opt_sheet"))
        state.used_sep = used_sep
        return df
    except Exception as e:
        st.error(f"Não foi possível ler o arquivo: {e}")
        return None


def structured(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Aplica só as etapas de colunas e tipos (base para pré-visualizações e para o 'antes')."""
    out, _ = cl.columns_step(df.copy(), config.get("drop_columns"), config.get("rename"),
                             config.get("snake_case", False))
    conv = {k: v for k, v in config.get("conversions", {}).items() if k in out.columns}
    out, _ = cl.types_step(out, conv, config.get("decimal_comma", False), config.get("dayfirst", True))
    return out


# --------------------------------------------------------------------------- #
# Etapa 1 — Carregar
# --------------------------------------------------------------------------- #
def step_upload():
    st.markdown("Limpe e prepare seus dados em poucos passos.")
    uploaded = st.file_uploader("Arquivo", type=["csv", "txt", "xlsx", "xls", "json", "parquet"],
                                label_visibility="collapsed")
    if uploaded is not None:
        file_id = f"{uploaded.name}-{uploaded.size}"
        if state.get("file_id") != file_id:
            reset_options()
            state.file_id, state.file_name, state.file_data = file_id, uploaded.name, uploaded.getvalue()

    df = None
    if "file_data" in state:
        ext = state.file_name.rsplit(".", 1)[-1].lower()
        c1, _ = st.columns([1, 2])
        if ext in ("csv", "txt"):
            label = c1.selectbox("Separador", list(SEPARATORS), key="opt_sep")
            state.sep_value = SEPARATORS[label]
        elif ext in ("xlsx", "xls"):
            c1.selectbox("Planilha", sheets(state.file_data), key="opt_sheet")
        df = current_data()
        if df is not None:
            detail = f"{fmt_int(len(df))} linhas · {df.shape[1]} colunas"
            if state.get("used_sep") and ext in ("csv", "txt"):
                detail += f" · separador {repr(state.used_sep)}"
            st.caption(f"**{state.file_name}** — {detail}")
            st.dataframe(df.head(5), width="stretch", hide_index=True)

    st.write("")
    st.subheader("O que o limpador faz")
    for row in (FEATURES[:3], FEATURES[3:]):
        cols = st.columns(3, gap="large")
        for col, (title, text) in zip(cols, row):
            col.markdown(f'<div class="feature"><h4>{title}</h4><p>{text}</p></div>', unsafe_allow_html=True)
        st.write("")

    nav(forward=("Avançar", 2), forward_disabled=df is None)


# --------------------------------------------------------------------------- #
# Etapa 2 — Diagnóstico
# --------------------------------------------------------------------------- #
def step_diagnosis(df: pd.DataFrame):
    rows, cols, nulls, dups = metrics(df)
    m = st.columns(4)
    m[0].metric("Linhas", fmt_int(rows))
    m[1].metric("Colunas", cols)
    m[2].metric("Células nulas", fmt_int(nulls), f"{nulls / max(df.size, 1):.1%} do total", delta_color="off")
    m[3].metric("Linhas duplicadas", fmt_int(dups))

    num_cols, txt_cols = cl.numeric_columns(df), cl.text_columns(df)
    t_nulls, t_dist, t_cat, t_corr, t_cols = st.tabs(["Nulos", "Distribuição", "Categorias", "Correlação", "Colunas"])

    with t_nulls:
        st.markdown("**Percentual de nulos por coluna**")
        show_chart(*ch.nulls_bar(df), empty_msg="Nenhuma coluna tem valores nulos.")

    with t_dist:
        if not num_cols:
            st.caption("Nenhuma coluna numérica. Converta colunas na etapa de Limpeza (Tipos e colunas).")
        else:
            c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
            col = c1.selectbox("Coluna", num_cols, key="diag_dist_col")
            with_out = c2.toggle("Incluir outliers no eixo", key="diag_dist_out")
            sk = cl.pearson_skewness(df[col])
            st.markdown(f"**Distribuição de {col}** — assimetria de Pearson {sk:+.2f} ({cl.interpret_skewness(sk)})")
            show_chart(*ch.distribution(df[col], include_outliers=with_out))

    with t_cat:
        if not txt_cols:
            st.caption("Nenhuma coluna de texto.")
        else:
            col = st.selectbox("Coluna", txt_cols, key="diag_cat_col")
            st.markdown(f"**Valores mais frequentes em {col}** — {fmt_int(df[col].nunique())} valores distintos")
            show_chart(*ch.top_values(df[col]))

    with t_corr:
        st.markdown("**Correlação entre colunas numéricas** — o tom indica a força; o sinal, a direção")
        show_chart(*ch.correlation(df), empty_msg="São necessárias ao menos duas colunas numéricas.")

    with t_cols:
        st.dataframe(cl.diagnose(df), hide_index=True, width="stretch")

    nav(back=1, forward=("Avançar", 3))


# --------------------------------------------------------------------------- #
# Etapa 3 — Limpeza
# --------------------------------------------------------------------------- #
def default(key: str, value):
    """Define o valor inicial de um widget pelo Session State e devolve a chave."""
    state.setdefault(key, value)
    return key


CLEANING_DEFAULTS = {"opt_decimal": True, "opt_dayfirst": True, "opt_strip": True, "opt_collapse": True,
                     "opt_empty": True, "opt_threshold": 50, "opt_skew": 0.5, "opt_n_filters": 0}


def step_cleaning(df: pd.DataFrame):
    for key, value in CLEANING_DEFAULTS.items():
        state.setdefault(key, value)
    st.caption("As operações são aplicadas nesta ordem: colunas → tipos → texto → "
               "nulos e duplicatas → imputação → outliers → filtros.")
    t_types, t_text, t_dup, t_imp, t_out, t_filt = st.tabs(
        ["Tipos e colunas", "Texto", "Nulos e duplicatas", "Imputação", "Outliers", "Filtros"])
    all_cols = df.columns.tolist()

    with t_types:
        c1, c2 = st.columns(2, gap="large")
        drop_cols = c1.multiselect("Excluir colunas", all_cols, key="opt_drop")
        remaining = [c for c in all_cols if c not in drop_cols]
        to_rename = c1.multiselect("Renomear colunas", remaining, key="opt_rename_cols")
        rename = {c: c1.text_input(f"Novo nome para {c}", key=default(f"opt_rename_{c}", str(c))) for c in to_rename}
        snake = c1.checkbox("Padronizar nomes (snake_case)", key="opt_snake")

        renamed, _ = cl.columns_step(df.head(0).copy(), drop_cols, rename, snake)
        to_convert = c2.multiselect("Converter tipo de", renamed.columns.tolist(), key="opt_convert")
        conversions = {c: c2.selectbox(f"{c} para", TYPE_TARGETS, key=f"opt_type_{c}") for c in to_convert}
        decimal_comma = c2.checkbox("Números no formato brasileiro (1.234,56)", key="opt_decimal")
        dayfirst = c2.checkbox("Datas com dia primeiro (dd/mm/aaaa)", key="opt_dayfirst")

    schema = structured(df, {"drop_columns": drop_cols, "rename": rename, "snake_case": snake,
                             "conversions": conversions, "decimal_comma": decimal_comma, "dayfirst": dayfirst})
    cols = schema.columns.tolist()
    num_cols, txt_cols = cl.numeric_columns(schema), cl.text_columns(schema)

    with t_text:
        text_cols = st.multiselect("Colunas de texto", txt_cols,
                                   key=default(f"opt_text_cols_{hash(tuple(txt_cols))}", txt_cols))
        c1, c2 = st.columns(2, gap="large")
        text_options = {
            "strip": c1.checkbox("Remover espaços nas pontas", key="opt_strip"),
            "collapse_spaces": c1.checkbox("Remover espaços duplicados", key="opt_collapse"),
            "accents": c1.checkbox("Remover acentos", key="opt_accents"),
            "special": c1.checkbox("Remover caracteres especiais", key="opt_special"),
            "empty_as_null": c1.checkbox("Tratar vazios, NA, null e - como nulos", key="opt_empty"),
            "case": c2.radio("Maiúsculas e minúsculas", ["manter", "minúsculas", "MAIÚSCULAS", "Título"],
                             key="opt_case"),
        }

    with t_dup:
        c1, c2 = st.columns(2, gap="large")
        drop_dup = c1.checkbox("Remover linhas duplicadas", key="opt_dup")
        dup_subset, keep = None, "first"
        if drop_dup:
            dup_subset = c1.multiselect("Comparar apenas as colunas (vazio = todas)", cols, key="opt_dup_subset")
            keep = {"primeira": "first", "última": "last", "nenhuma": False}[
                c1.radio("Manter ocorrência", ["primeira", "última", "nenhuma"], horizontal=True, key="opt_keep")]
        null_rows = c2.multiselect("Remover linhas com nulos nas colunas", cols, key="opt_null_rows")
        threshold = None
        if c2.checkbox("Excluir colunas com muitos nulos", key="opt_null_cols"):
            threshold = c2.slider("% máximo de nulos por coluna", 0, 100, key="opt_threshold")

    with t_imp:
        c1, c2 = st.columns(2, gap="large")
        impute_cols = c1.multiselect("Colunas para preencher nulos", cols, key="opt_impute_cols")
        impute_method = c1.selectbox("Método", IMPUTE_METHODS, key="opt_impute_method")
        fixed_value, skew_limit = None, 0.5
        if impute_method == "valor fixo":
            fixed_value = c1.text_input("Valor", key="opt_fixed")
        elif impute_method == "automática (Pearson)":
            skew_limit = c1.number_input("Limite de |assimetria| para usar a média", 0.0, 5.0, step=0.1,
                                         key="opt_skew")
            c2.caption("Assimetria de Pearson = 3 × (média − mediana) / desvio padrão. Abaixo do limite, "
                       "usa a média; acima, a mediana. Colunas de texto usam a moda.")
            numeric_sel = [c for c in impute_cols if c in num_cols]
            if numeric_sel:
                skews = [cl.pearson_skewness(schema[c]) for c in numeric_sel]
                c2.dataframe(pd.DataFrame({
                    "coluna": numeric_sel,
                    "assimetria": [round(s, 2) for s in skews],
                    "vai usar": ["média" if abs(s) < skew_limit else "mediana" for s in skews],
                }), hide_index=True, width="stretch")
        elif impute_method in ("forward fill", "backward fill"):
            c2.caption("Preenche com o valor anterior (forward) ou seguinte (backward) na ordem das linhas.")

    with t_out:
        c1, c2 = st.columns(2, gap="large")
        out_cols = c1.multiselect("Colunas numéricas", num_cols, key="opt_out_cols")
        out_method = c1.radio("Método", ["IQR", "Z-score"], horizontal=True, key="opt_out_method")
        out_factor = c1.number_input("Fator (IQR) ou nº de desvios (Z-score)", 0.5, 10.0, step=0.5,
                                     key=default(f"opt_factor_{out_method}", 1.5 if out_method == "IQR" else 3.0))
        out_action = c1.selectbox("Ação", ["remover linhas", "limitar (winsorizar)", "substituir por nulo"],
                                  key="opt_out_action")
        if out_cols:
            preview_col = c2.selectbox("Visualizar", out_cols, key="opt_out_preview")
            if out_method == "IQR":
                chart, _ = ch.distribution(schema[preview_col], out_factor, include_outliers=True)
                with c2:
                    st.altair_chart(chart, width="stretch")
            else:
                c2.caption("A visualização com boxplot usa o método IQR.")

    with t_filt:
        n_filters = st.number_input("Quantidade de filtros", 0, 10, key="opt_n_filters")
        filters = []
        for i in range(int(n_filters)):
            c1, c2, c3 = st.columns([2, 1, 2])
            f_col = c1.selectbox("Coluna", cols, key=f"opt_fcol_{i}")
            f_op = c2.selectbox("Operador", cl.OPERATORS, key=f"opt_fop_{i}")
            f_val = "" if f_op in ("é nulo", "não é nulo") else c3.text_input("Valor", key=f"opt_fval_{i}")
            filters.append({"column": f_col, "operator": f_op, "value": f_val})
        if n_filters:
            st.caption("Linhas que não atendem aos filtros são removidas.")

    config = {
        "drop_columns": drop_cols, "rename": rename, "snake_case": snake,
        "conversions": conversions, "decimal_comma": decimal_comma, "dayfirst": dayfirst,
        "text_columns": text_cols, "text_options": text_options,
        "dup_null": {"drop_duplicates": drop_dup, "dup_subset": dup_subset, "keep": keep,
                     "drop_null_rows_in": null_rows, "drop_cols_threshold": threshold},
        "impute_columns": impute_cols, "impute_method": impute_method,
        "fixed_value": fixed_value, "skew_limit": skew_limit,
        "outlier_columns": out_cols, "outlier_method": out_method,
        "outlier_factor": out_factor, "outlier_action": out_action,
        "filters": filters,
    }

    st.write("")
    left, _, right = st.columns([1, 3, 1])
    if left.button("Voltar", icon=":material/arrow_back:", width="stretch"):
        go(2)
    if right.button("Aplicar limpeza", type="primary", width="stretch"):
        try:
            state.cleaned, state.log = cl.run_pipeline(df, config)
            state.config = config
        except Exception as e:
            st.error(f"Erro ao aplicar a limpeza: {e}")
        else:
            go(4)


# --------------------------------------------------------------------------- #
# Etapa 4 — Resultado
# --------------------------------------------------------------------------- #
def step_result(df: pd.DataFrame):
    cleaned, config = state.get("cleaned"), state.get("config", {})
    if cleaned is None:
        st.caption("Nenhuma limpeza aplicada ainda.")
        nav(back=3)
        return

    o, c = metrics(df), metrics(cleaned)
    m = st.columns(4)
    m[0].metric("Linhas", fmt_int(c[0]), fmt_delta(c[0] - o[0]), delta_color="off")
    m[1].metric("Colunas", c[1], fmt_delta(c[1] - o[1]), delta_color="off")
    m[2].metric("Células nulas", fmt_int(c[2]), fmt_delta(c[2] - o[2]), delta_color="inverse")
    m[3].metric("Linhas duplicadas", fmt_int(c[3]), fmt_delta(c[3] - o[3]), delta_color="inverse")

    # "Antes" = original com colunas e tipos ajustados, para comparar pelos mesmos nomes
    baseline = structured(df, config)

    t_nulls, t_dist, t_data, t_log = st.tabs(["Nulos", "Distribuição", "Dados", "Registro"])
    with t_nulls:
        st.markdown("**Nulos por coluna, antes e depois**")
        show_chart(*ch.nulls_compare(baseline, cleaned), empty_msg="Não havia nulos no arquivo.")
    with t_dist:
        shared = [col for col in cl.numeric_columns(cleaned) if col in baseline.columns]
        if not shared:
            st.caption("Nenhuma coluna numérica para comparar.")
        else:
            col = st.selectbox("Coluna", shared, key="res_dist_col")
            st.markdown(f"**Distribuição de {col}, antes e depois**")
            show_chart(*ch.distribution_compare(baseline[col], cleaned[col]))
            st.caption("Antes = dados originais com as conversões de tipo aplicadas.")
    with t_data:
        view = st.segmented_control("Visualizar", ["Depois", "Antes"], default="Depois", key="res_view",
                                    label_visibility="collapsed")
        show_table(df if view == "Antes" else cleaned)
    with t_log:
        log = state.get("log") or ["Nenhuma alteração aplicada."]
        st.markdown("\n".join(f"- {line}" for line in log))

    st.write("")
    st.subheader("Baixar")
    base = state.file_name.rsplit(".", 1)[0] + "_limpo"
    d1, d2, d3 = st.columns([1, 1, 2])
    csv_sep = d3.radio("Separador do CSV", [",", ";"], horizontal=True, key="res_csv_sep")
    d1.download_button("CSV", cl.to_csv_bytes(cleaned, csv_sep), f"{base}.csv", "text/csv",
                       icon=":material/download:", width="stretch")
    try:
        d2.download_button("Excel", cl.to_excel_bytes(cleaned), f"{base}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           icon=":material/download:", width="stretch")
    except Exception as e:
        d2.caption(f"Excel indisponível: {e}")

    st.write("")
    left, _, right = st.columns([1, 3, 1])
    if left.button("Ajustar limpeza", icon=":material/arrow_back:", width="stretch"):
        go(3)
    if right.button("Novo arquivo", width="stretch"):
        reset_options()
        for key in ("file_id", "file_name", "file_data", "sep_value", "used_sep"):
            state.pop(key, None)
        go(1)


# --------------------------------------------------------------------------- #
# Página
# --------------------------------------------------------------------------- #
st.title("Limpador de Dados")
data = current_data() if state.step > 1 else None
if state.step > 1 and data is None:
    state.step = 1
stepper(state.step)

if state.step == 1:
    step_upload()
elif state.step == 2:
    step_diagnosis(data)
elif state.step == 3:
    step_cleaning(data)
else:
    step_result(data)
