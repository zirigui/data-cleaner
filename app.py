import pandas as pd
import streamlit as st

import cleaner as cl

st.set_page_config(page_title="Limpador de Dados", page_icon="🧹", layout="wide")

SEPARATORS = {"Automático": None, "Vírgula (,)": ",", "Ponto e vírgula (;)": ";", "Tab": "\t", "Barra vertical (|)": "|"}
TYPE_TARGETS = ["número", "inteiro", "data", "texto", "categoria", "booleano"]
IMPUTE_METHODS = ["automática (Pearson)", "média", "mediana", "moda", "valor fixo",
                  "forward fill", "backward fill", "interpolação linear"]
PREVIEW_ROWS = 1000


@st.cache_data(show_spinner="Lendo arquivo...")
def load(data: bytes, name: str, sep: str | None, sheet: str | None):
    return cl.read_file(data, name, sep, sheet)


@st.cache_data
def sheets(data: bytes):
    return cl.excel_sheets(data)


def show_table(df: pd.DataFrame):
    if len(df) > PREVIEW_ROWS:
        st.caption(f"Mostrando as primeiras {PREVIEW_ROWS} de {len(df):,} linhas".replace(",", "."))
    try:
        st.dataframe(df.head(PREVIEW_ROWS), width="stretch")
    except Exception:
        st.dataframe(df.head(PREVIEW_ROWS).astype(str), width="stretch")


def reset_options():
    for key in list(st.session_state.keys()):
        if key.startswith("opt_") or key in ("cleaned", "log"):
            del st.session_state[key]


# --------------------------------------------------------------------------- #
# Sidebar: upload
# --------------------------------------------------------------------------- #
sb = st.sidebar
sb.title("🧹 Limpador de Dados")
sb.subheader("📁 Upload")
uploaded = sb.file_uploader("Arraste o arquivo", type=["csv", "txt", "xlsx", "xls", "json", "parquet"])

if uploaded is None:
    st.title("🧹 Limpador de Dados")
    st.info("Envie um arquivo **CSV, TXT, Excel, JSON ou Parquet** na barra lateral para começar.")
    st.markdown(
        """
        **O que dá para fazer:**
        - Remover duplicatas e linhas/colunas com nulos
        - Padronizar textos (espaços, maiúsculas/minúsculas, acentos, caracteres especiais)
        - Converter tipos, renomear e excluir colunas
        - Imputar nulos (média, mediana, moda, valor fixo, forward/backward fill, interpolação)
          ou escolher automaticamente entre média e mediana pela **assimetria de Pearson**
        - Detectar e tratar outliers (IQR ou Z-score) e filtrar linhas
        - Baixar o resultado em CSV ou Excel
        """
    )
    st.stop()

# Troca de arquivo → descarta opções e resultado anterior
file_id = f"{uploaded.name}-{uploaded.size}"
if st.session_state.get("file_id") != file_id:
    reset_options()
    st.session_state.file_id = file_id

data = uploaded.getvalue()
ext = uploaded.name.rsplit(".", 1)[-1].lower()
sep_choice, sheet = None, None
if ext in ("csv", "txt"):
    sep_label = sb.selectbox("Separador", list(SEPARATORS), key="opt_sep")
    sep_choice = SEPARATORS[sep_label]
elif ext in ("xlsx", "xls"):
    sheet = sb.selectbox("Planilha", sheets(data), key="opt_sheet")

try:
    original, used_sep = load(data, uploaded.name, sep_choice, sheet)
except Exception as e:
    st.error(f"Não foi possível ler o arquivo: {e}")
    st.stop()

if used_sep and sep_choice is None:
    sb.caption(f"Separador detectado: `{repr(used_sep)}`")

# --------------------------------------------------------------------------- #
# Sidebar: seções (criadas na ordem de exibição, preenchidas na ordem de dependência)
# --------------------------------------------------------------------------- #
exp_dup = sb.expander("Duplicatas e nulos")
exp_text = sb.expander("Texto")
exp_types = sb.expander("Tipos e colunas")
exp_impute = sb.expander("Imputação")
exp_out = sb.expander("Outliers e filtros")

all_cols = original.columns.tolist()

# ---- Tipos e colunas (define os nomes/tipos usados pelas demais seções)
with exp_types:
    drop_cols = st.multiselect("Excluir colunas", all_cols, key="opt_drop")
    remaining = [c for c in all_cols if c not in drop_cols]
    to_rename = st.multiselect("Renomear colunas", remaining, key="opt_rename_cols")
    rename = {c: st.text_input(f"Novo nome para '{c}'", value=str(c), key=f"opt_rename_{c}") for c in to_rename}
    snake = st.checkbox("Padronizar nomes (snake_case)", key="opt_snake")

    schema, _ = cl.columns_step(original.head(500).copy(), drop_cols, rename, snake)
    st.divider()
    to_convert = st.multiselect("Converter tipo de", schema.columns.tolist(), key="opt_convert")
    conversions = {c: st.selectbox(f"'{c}' para", TYPE_TARGETS, key=f"opt_type_{c}") for c in to_convert}
    decimal_comma = st.checkbox("Números no formato brasileiro (1.234,56)", value=True, key="opt_decimal")
    dayfirst = st.checkbox("Datas com dia primeiro (dd/mm/aaaa)", value=True, key="opt_dayfirst")

    schema, _ = cl.types_step(schema, conversions, decimal_comma, dayfirst)

cols = schema.columns.tolist()
num_cols = cl.numeric_columns(schema)
txt_cols = cl.text_columns(schema)

# ---- Texto
with exp_text:
    text_cols = st.multiselect("Colunas de texto", txt_cols, default=txt_cols, key=f"opt_text_cols_{len(txt_cols)}_{hash(tuple(txt_cols))}")
    text_options = {
        "strip": st.checkbox("Remover espaços nas pontas", value=True, key="opt_strip"),
        "collapse_spaces": st.checkbox("Remover espaços duplicados", value=True, key="opt_collapse"),
        "case": st.radio("Maiúsculas/minúsculas", ["manter", "minúsculas", "MAIÚSCULAS", "Título"],
                         horizontal=True, key="opt_case"),
        "accents": st.checkbox("Remover acentos", key="opt_accents"),
        "special": st.checkbox("Remover caracteres especiais", key="opt_special"),
        "empty_as_null": st.checkbox("Tratar vazios e 'NA', 'null', '-' como nulos", value=True, key="opt_empty"),
    }

# ---- Duplicatas e nulos
with exp_dup:
    drop_dup = st.checkbox("Remover linhas duplicadas", key="opt_dup")
    dup_subset, keep = None, "first"
    if drop_dup:
        dup_subset = st.multiselect("Considerar apenas as colunas (vazio = todas)", cols, key="opt_dup_subset")
        keep = {"primeira": "first", "última": "last", "nenhuma": False}[
            st.radio("Manter ocorrência", ["primeira", "última", "nenhuma"], horizontal=True, key="opt_keep")]
    null_rows = st.multiselect("Remover linhas com nulos nas colunas", cols, key="opt_null_rows")
    threshold = None
    if st.checkbox("Excluir colunas com muitos nulos", key="opt_null_cols"):
        threshold = st.slider("% máximo de nulos por coluna", 0, 100, 50, key="opt_threshold")

# ---- Imputação
with exp_impute:
    impute_cols = st.multiselect("Colunas para preencher nulos", cols, key="opt_impute_cols")
    impute_method = st.selectbox("Método", IMPUTE_METHODS, key="opt_impute_method")
    fixed_value, skew_limit = None, 0.5
    if impute_method == "valor fixo":
        fixed_value = st.text_input("Valor", key="opt_fixed")
    elif impute_method == "automática (Pearson)":
        skew_limit = st.number_input("Limite de |assimetria| para usar a média", 0.0, 5.0, 0.5, 0.1, key="opt_skew")
        st.caption("Assimetria de Pearson = 3·(média − mediana) / desvio padrão. "
                   "Abaixo do limite usa a **média**, acima usa a **mediana**. Colunas de texto usam a **moda**.")
    elif impute_method in ("forward fill", "backward fill"):
        st.caption("Preenche com o valor anterior (forward) ou seguinte (backward) na ordem das linhas.")

# ---- Outliers e filtros
with exp_out:
    out_cols = st.multiselect("Colunas numéricas para outliers", num_cols, key="opt_out_cols")
    out_method = st.radio("Método", ["IQR", "Z-score"], horizontal=True, key="opt_out_method")
    default_factor = 1.5 if out_method == "IQR" else 3.0
    out_factor = st.number_input("Fator (IQR) / nº de desvios (Z-score)", 0.5, 10.0, default_factor, 0.5,
                                 key=f"opt_factor_{out_method}")
    out_action = st.selectbox("Ação", ["remover linhas", "limitar (winsorizar)", "substituir por nulo"],
                              key="opt_out_action")
    st.divider()
    n_filters = st.number_input("Quantidade de filtros", 0, 10, 0, key="opt_n_filters")
    filters = []
    for i in range(int(n_filters)):
        c1, c2 = st.columns(2)
        f_col = c1.selectbox("Coluna", cols, key=f"opt_fcol_{i}")
        f_op = c2.selectbox("Operador", cl.OPERATORS, key=f"opt_fop_{i}")
        f_val = "" if f_op in ("é nulo", "não é nulo") else st.text_input("Valor", key=f"opt_fval_{i}")
        filters.append({"column": f_col, "operator": f_op, "value": f_val})
        st.caption("Linhas que **não** atendem ao filtro são removidas.")

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

sb.write("")
if sb.button("▶ Aplicar limpeza", type="primary", width="stretch"):
    try:
        st.session_state.cleaned, st.session_state.log = cl.run_pipeline(original, config)
    except Exception as e:
        st.session_state.pop("cleaned", None)
        st.session_state.log = []
        sb.error(f"Erro ao aplicar limpeza: {e}")
if sb.button("↺ Resetar", width="stretch"):
    reset_options()
    st.rerun()

# --------------------------------------------------------------------------- #
# Área principal
# --------------------------------------------------------------------------- #
cleaned = st.session_state.get("cleaned")
current = cleaned if cleaned is not None else original

st.title("📊 Diagnóstico")
st.caption(f"Arquivo: **{uploaded.name}**" + (" — resultado após a limpeza" if cleaned is not None else ""))


def metrics(df):
    return len(df), df.shape[1], int(df.isna().sum().sum()), int(df.duplicated().sum())


o_rows, o_cols, o_nulls, o_dups = metrics(original)
m1, m2, m3, m4 = st.columns(4)
if cleaned is not None:
    c_rows, c_cols, c_nulls, c_dups = metrics(cleaned)
    m1.metric("Linhas", f"{c_rows:,}".replace(",", "."), c_rows - o_rows, delta_color="off")
    m2.metric("Colunas", c_cols, c_cols - o_cols, delta_color="off")
    m3.metric("Nulos", f"{c_nulls:,}".replace(",", "."), c_nulls - o_nulls, delta_color="inverse")
    m4.metric("Duplicatas", c_dups, c_dups - o_dups, delta_color="inverse")
else:
    total = original.size or 1
    m1.metric("Linhas", f"{o_rows:,}".replace(",", "."))
    m2.metric("Colunas", o_cols)
    m3.metric("Nulos", f"{o_nulls:,}".replace(",", "."), f"{o_nulls / total:.1%} das células", delta_color="off")
    m4.metric("Duplicatas", o_dups)

st.dataframe(cl.diagnose(current), width="stretch", hide_index=True)

tab_before, tab_after = st.tabs(["Antes", "Depois"])
with tab_before:
    show_table(original)
with tab_after:
    if cleaned is None:
        st.info("Configure as opções na barra lateral e clique em **▶ Aplicar limpeza**.")
    else:
        show_table(cleaned)

if cleaned is not None:
    st.subheader("📝 Log")
    log = st.session_state.get("log") or ["Nenhuma alteração aplicada."]
    st.markdown("\n".join(f"- {line}" for line in log))

    st.subheader("⬇ Download")
    base = uploaded.name.rsplit(".", 1)[0] + "_limpo"
    d1, d2, d3 = st.columns([1, 1, 2])
    csv_sep = d3.radio("Separador do CSV", [",", ";"], horizontal=True, key="opt_out_sep")
    d1.download_button("⬇ Baixar CSV", cl.to_csv_bytes(cleaned, csv_sep), f"{base}.csv", "text/csv",
                       width="stretch")
    try:
        d2.download_button("⬇ Baixar Excel", cl.to_excel_bytes(cleaned), f"{base}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           width="stretch")
    except Exception as e:
        d2.warning(f"Excel indisponível: {e}")
