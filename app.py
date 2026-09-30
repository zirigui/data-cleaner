import hashlib
import html
import json

import pandas as pd
import streamlit as st

import cleaner as cl
import charts as ch

st.set_page_config(page_title="Limpador de Dados", page_icon=":material/cleaning_services:", layout="wide")

STEPS = ["Carregar", "Tratar", "Exportar"]
SEPARATORS = {"Automático": None, "Vírgula (,)": ",", "Ponto e vírgula (;)": ";", "Tab": "\t", "Barra vertical (|)": "|"}
UPLOAD_TYPES = ["csv", "tsv", "txt", "json", "xlsx", "xls", "parquet"]
FEATURES = [
    ("Deduplicação automática", "cyan"), ("Detecção de tipo", "violet"), ("Imputação estatística", "green"),
    ("Assimetria de Pearson", "amber"), ("Outliers por IQR", "orange"), ("Forward / Backward fill", "blue"),
]
KIND_STYLE = {"numérico": ("NUM", "cyan"), "categórico": ("CAT", "violet"), "booleano": ("BOOL", "blue"),
              "data": ("DATA", "pink"), "texto": ("TXT", "slate")}
KIND_FILTERS = {"Numérico": "numérico", "Categórico": "categórico", "Booleano": "booleano", "Data": "data",
                "Texto": "texto"}
IMPUTE_LABELS = {"média": "Média", "mediana": "Mediana", "moda": "Moda", "anterior": "Anterior",
                 "seguinte": "Seguinte", "interpolar": "Interpolar", "preservar": "Preservar"}
IMPUTE_HELP = {
    "média": "Preenche com a média da coluna.",
    "mediana": "Preenche com a mediana, menos sensível a valores extremos.",
    "moda": "Preenche com o valor mais frequente.",
    "anterior": "Forward fill: repete o valor da linha anterior.",
    "seguinte": "Backward fill: usa o valor da linha seguinte.",
    "interpolar": "Interpolação linear entre os vizinhos.",
    "preservar": "Os nulos são mantidos.",
}
OUTLIER_LABELS = {"manter": "Manter", "limitar": "Limitar", "nulo": "Tornar nulo", "remover": "Remover linha"}
PREVIEW_ROWS = 1000

st.html(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    :root {
      --bg: #071112; --surface: #0c1a1c; --surface-2: #122427; --border: #1b3236; --text: #e6f0ef;
      --muted: #6f8a8c; --faint: #3b5456; --accent: #ff7a59; --accent-2: #2dd4bf;
      --cyan: #2dd4bf; --violet: #c4a1ff; --green: #a3e635; --amber: #facc15; --orange: #fb923c; --red: #fb7185; --blue: #7dd3fc; --pink: #f9a8d4; --slate: #9aa7a6;
      --mono: 'IBM Plex Mono', ui-monospace, monospace; --sans: 'Plus Jakarta Sans', sans-serif;
    }
    [data-testid="stToolbar"], [data-testid="stToolbarActions"], .stAppDeployButton,
    [data-testid="stMainMenu"], #MainMenu, [data-testid="stDecoration"] { display: none !important; }
    header[data-testid="stHeader"] { height: 0; background: transparent; }
    .block-container { max-width: 1280px; padding: 1rem 1.25rem 3rem; }

    /* Cards */
    div[class*="st-key-card"] { background: var(--surface); border: 1px solid var(--border) !important;
                                border-radius: 18px; padding: 1.1rem 1.25rem; }
    div[class*="st-key-colcard"] { background: var(--surface); border: 1px solid var(--border) !important;
                                   border-radius: 18px; padding: 1rem 1.1rem; }
    /* Linhas internas dos cards não quebram no celular */
    div[class*="st-key-colcard"] [data-testid="stHorizontalBlock"],
    .st-key-card_file [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; }
    div[class*="st-key-colcard"] [data-testid="stColumn"],
    .st-key-card_file [data-testid="stColumn"] { min-width: 0 !important; }
    div[class*="st-key-colcard"]:hover { border-color: #2b4a4f !important; transform: translateY(-1px); }
    div[class*="st-key-colcard"] { transition: border-color .15s, transform .15s; }
    [data-testid="stExpander"] details { background: var(--surface); border: 1px solid var(--border);
                                         border-radius: 14px; }
    [data-testid="stExpander"] summary { padding: .9rem 1.2rem; }

    /* Cabeçalho */
    .dc-brand { display: flex; align-items: center; gap: .6rem; height: 42px; font-family: var(--sans); }
    .dc-brand b { font-weight: 800; font-size: 1.1rem; letter-spacing: -.02em; }
    .dc-brand small { display: block; font-family: var(--mono); font-size: .62rem; color: var(--muted);
                      letter-spacing: .04em; margin-top: -2px; }
    .dc-logo { width: 32px; height: 32px; border-radius: 10px; display: grid; place-items: center;
               background: linear-gradient(135deg, #ff7a59, #ffb259); color: #2a0f06; font-size: 1rem;
               box-shadow: 0 4px 18px rgba(255,122,89,.25); }
    .dc-stepper { display: flex; justify-content: center; }
    .dc-track { display: inline-flex; align-items: center; gap: .25rem; padding: .3rem; border-radius: 999px;
                background: var(--surface); border: 1px solid var(--border); }
    .dc-step { display: flex; align-items: center; gap: .45rem; font-size: .84rem; color: var(--muted);
               white-space: nowrap; padding: .35rem .85rem .35rem .4rem; border-radius: 999px; }
    .dc-step .n { width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center;
                  font-family: var(--mono); font-size: .7rem; font-weight: 600; background: transparent;
                  border: 1px dashed var(--faint); color: var(--muted); }
    .dc-step.current { background: var(--accent); color: #2a0f06; font-weight: 700; }
    .dc-step.current .n { background: #2a0f06; border: none; color: var(--accent); }
    .dc-step.done { color: var(--green); font-weight: 600; }
    .dc-step.done .n { background: rgba(163,230,53,.12); border: 1px solid var(--green); color: var(--green); }
    .dc-line { display: none; }
    @media (max-width: 640px) { .dc-step .t { display: none; } .dc-step.current .t { display: inline; } }
    .dc-rule { height: 1px; margin: .5rem -1.25rem 1.5rem;
               background: linear-gradient(90deg, transparent, #ff7a59 20%, #2dd4bf 80%, transparent); opacity: .45; }
    .dc-strip { height: 3px; border-radius: 3px; margin: -.35rem 0 .9rem; width: 42px; }
    html, body, .stApp, button, input, textarea { font-family: var(--sans); }
    @media (max-width: 640px) { .dc-line { width: 14px; } .dc-step .t { display: none; }
                                .dc-step.current .t { display: inline; } }

    /* Upload: a área inteira abre o seletor de arquivos */
    section[data-testid="stFileUploaderDropzone"] {
      position: relative; min-height: 280px; border: 1.5px dashed #24403f; border-radius: 22px;
      background: transparent; display: flex; flex-direction: column; justify-content: center;
      align-items: center; padding: 2.5rem 1rem; transition: border-color .15s, background .15s; }
    section[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--accent);
                                                          background: rgba(255,122,89,.04); }
    section[data-testid="stFileUploaderDropzone"] > span { position: absolute; inset: 0; z-index: 2; }
    section[data-testid="stFileUploaderDropzone"] > span button { width: 100%; height: 100%; opacity: 0;
                                                                  cursor: pointer; }
    [data-testid="stFileUploaderDropzoneInstructions"] { margin: 0; text-align: center; }
    [data-testid="stFileUploaderDropzoneInstructions"] > div > span { display: none; }
    [data-testid="stFileUploaderDropzoneInstructions"] > div::before {
      content: "↑"; display: grid; place-items: center; width: 60px; height: 60px; margin: 0 auto 1.4rem;
      border-radius: 14px; background: var(--surface-2); border: 1px solid var(--border); color: var(--muted);
      font-size: 1.5rem; }
    [data-testid="stFileUploaderDropzoneInstructions"]::before {
      content: "Arraste um arquivo ou clique para selecionar"; display: block; font-size: 1.15rem;
      font-weight: 600; color: var(--text); margin-bottom: .45rem; order: 2; }
    [data-testid="stFileUploaderDropzoneInstructions"]::after {
      content: ".csv · .tsv · .txt · .json · .xlsx · .parquet"; display: block; font-family: var(--mono);
      font-size: .8rem; color: var(--muted); order: 3; }
    [data-testid="stFileUploaderDropzoneInstructions"] { display: flex; flex-direction: column; }
    [data-testid="stFileUploaderDropzoneInstructions"] > div { order: 1; }
    .dc-chips { display: grid; grid-template-columns: repeat(3, minmax(0, 180px)); gap: .5rem;
                justify-content: center; margin-top: 1.25rem; }
    @media (max-width: 640px) { .dc-chips { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    .dc-chip { font-family: var(--mono); font-size: .74rem; text-align: center; padding: .6rem .8rem;
               border-radius: 999px !important;
               border-radius: 10px; border: 1px solid; }

    /* Tipografia utilitária */
    .dc-mono { font-family: var(--mono); }
    .dc-label { font-family: var(--mono); font-size: .68rem; letter-spacing: .06em; text-transform: uppercase;
                color: var(--muted); }
    .dc-title { font-size: .82rem; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
                color: #b9cfcd; margin-bottom: .75rem; }
    .dc-small { font-family: var(--mono); font-size: .72rem; color: var(--muted); }
    .c-cyan { color: var(--cyan); } .c-violet { color: var(--violet); } .c-green { color: var(--green); }
    .c-amber { color: var(--amber); } .c-orange { color: var(--orange); } .c-red { color: var(--red); }
    .c-blue { color: var(--blue); } .c-pink { color: var(--pink); } .c-slate { color: var(--slate); }
    .c-muted { color: var(--muted); } .c-accent { color: var(--accent); }
    .bg-cyan { background: rgba(45,212,191,.07); border-color: rgba(45,212,191,.28) !important; }
    .bg-violet { background: rgba(196,161,255,.07); border-color: rgba(196,161,255,.28) !important; }
    .bg-green { background: rgba(163,230,53,.07); border-color: rgba(163,230,53,.28) !important; }
    .bg-amber { background: rgba(250,204,21,.07); border-color: rgba(250,204,21,.28) !important; }
    .bg-orange { background: rgba(251,146,60,.07); border-color: rgba(251,146,60,.28) !important; }
    .bg-red { background: rgba(251,113,133,.07); border-color: rgba(251,113,133,.28) !important; }
    .bg-blue { background: rgba(125,211,252,.07); border-color: rgba(125,211,252,.28) !important; }
    .bg-pink { background: rgba(249,168,212,.07); border-color: rgba(249,168,212,.28) !important; }
    .bg-slate { background: rgba(154,167,166,.07); border-color: rgba(154,167,166,.28) !important; }

    /* Arquivo */
    .dc-file { display: flex; align-items: center; gap: .9rem; }
    .dc-file .name { font-weight: 600; font-size: .92rem; }
    .dc-file .ico { color: var(--accent); }
    .dc-dims { display: flex; gap: 1.5rem; justify-content: flex-end; text-align: center; }
    .dc-dims b { display: block; font-size: 1.05rem; font-weight: 600; }

    /* KPIs */
    .dc-kpis { display: flex; flex-wrap: wrap; align-items: center; gap: 1.5rem 2.5rem; }
    .dc-rings { display: flex; align-items: center; gap: 1rem; }
    .dc-ring { text-align: center; }
    .dc-ring .dial { width: 72px; height: 72px; border-radius: 50%; display: grid; place-items: center;
                     margin: 0 auto; }
    .dc-ring .dial span { width: 58px; height: 58px; border-radius: 50%; background: var(--surface);
                          display: grid; place-items: center; font-family: var(--mono); font-size: .8rem;
                          font-weight: 600; }
    .dc-ring .cap { font-family: var(--mono); font-size: .72rem; color: var(--muted); margin-top: .35rem; }
    .dc-arrow { text-align: center; font-family: var(--mono); font-size: .7rem; }
    .dc-kpi { min-width: 150px; flex: 1; }
    .dc-kpi b { display: block; font-size: 1.9rem; font-weight: 700; line-height: 1.1; }
    @media (max-width: 640px) { .dc-kpi { flex: 1 1 40%; min-width: 120px; } }
    .dc-kpi span { font-family: var(--mono); font-size: .72rem; color: var(--muted); }

    /* Completude */
    .dc-comp { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: .55rem 2.5rem; }
    .dc-comp-row { display: grid; grid-template-columns: 44px minmax(60px, 140px) 1fr 44px; align-items: center;
                   gap: .75rem; font-size: .85rem; }
    .dc-comp-row .pct { font-family: var(--mono); font-size: .72rem; text-align: right; }
    .dc-bar { height: 7px; border-radius: 99px; background: #15292c; overflow: hidden; }
    .dc-bar > i { display: block; height: 100%; border-radius: 99px; }
    .dc-badge { font-family: var(--mono); font-size: .62rem; font-weight: 600; padding: .15rem .4rem;
                border-radius: 5px; border: 1px solid; text-align: center; letter-spacing: .04em;
                display: inline-block; }
    .dc-trunc { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

    /* Card de coluna */
    .dc-colhead { display: flex; justify-content: space-between; align-items: center; gap: .5rem;
                  margin-bottom: .8rem; }
    .dc-colhead .name { font-weight: 700; font-size: 1rem; }
    .dc-row { display: flex; justify-content: space-between; align-items: baseline; font-size: .82rem; }
    .dc-row .v { font-family: var(--mono); font-size: .75rem; }
    .dc-note { font-family: var(--mono); font-size: .68rem; color: var(--muted); margin: .4rem 0 .9rem; }
    .dc-hist { display: flex; align-items: flex-end; gap: 2px; height: 46px; margin: .35rem 0 .6rem; }
    .dc-hist i { flex: 1; background: linear-gradient(180deg, #2dd4bf, #14867a); border-radius: 1px 1px 0 0; min-height: 0; }
    .dc-hist i.out { background: var(--orange); }
    .dc-range { display: flex; justify-content: space-between; font-family: var(--mono); font-size: .66rem;
                color: var(--muted); }
    .dc-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: .35rem; margin: .5rem 0; }
    .dc-stats div { background: var(--surface-2); border-radius: 8px; padding: .45rem .3rem; text-align: center; }
    .dc-stats span { display: block; font-family: var(--mono); font-size: .6rem; color: var(--muted); }
    .dc-stats b { font-family: var(--mono); font-size: .8rem; font-weight: 600; }
    .dc-cats { display: grid; grid-template-columns: minmax(60px, 90px) 1fr 36px; gap: .45rem .7rem;
               align-items: center; margin: .5rem 0 .6rem; font-family: var(--mono); font-size: .7rem; }
    .dc-cats .pct { text-align: right; color: var(--muted); }
    .dc-cats .dc-bar { height: 4px; }
    .dc-meta { font-family: var(--mono); font-size: .68rem; color: var(--muted); display: flex; gap: .9rem;
               flex-wrap: wrap; }
    .dc-sep { border-top: 1px solid var(--border); margin: .9rem 0 .7rem; }
    .dc-value { background: var(--surface-2); border-radius: 8px; padding: .5rem .7rem; font-family: var(--mono);
                font-size: .75rem; color: var(--muted); margin: .45rem 0; }
    .dc-value b { font-weight: 600; }
    .dc-why { font-size: .72rem; color: var(--muted); line-height: 1.45; }
    .dc-ok { font-family: var(--mono); font-size: .72rem; color: var(--green); }
    .dc-pill { font-family: var(--mono); font-size: .68rem; padding: .2rem .5rem; border-radius: 6px;
               border: 1px solid; }

    /* Exportar */
    .dc-stat-title { display: flex; align-items: center; gap: .5rem; font-weight: 600; font-size: .88rem; }
    .dc-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .dc-stat-big { font-size: 2.2rem; font-weight: 700; margin: .5rem 0 .15rem; line-height: 1.1; }
    .dc-log { display: flex; flex-direction: column; gap: .4rem; }
    .dc-log div { display: grid; grid-template-columns: 14px minmax(90px, 150px) 1fr auto; gap: .75rem;
                  align-items: center; background: var(--surface-2); border-radius: 8px; padding: .55rem .8rem;
                  font-size: .84rem; }
    .dc-log .col { font-family: var(--mono); font-weight: 600; font-size: .8rem; }
    .dc-log .val { font-family: var(--mono); font-size: .75rem; color: var(--muted); text-align: right; }
    @media (max-width: 640px) { .dc-log div { grid-template-columns: 14px 1fr; }
                                .dc-log .val { grid-column: 2; text-align: left; } }

    /* Widgets */
    .stButton button, .stDownloadButton button { border-radius: 999px; font-weight: 700; }
    [data-testid="stBaseButton-secondary"] { background: transparent; }
    [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primary"] p,
    [data-testid="stPopoverButton"][kind="primary"], [data-testid="stPopoverButton"][kind="primary"] p {
      color: #2a0f06 !important; }
    [data-testid="stBaseButton-primary"] { box-shadow: 0 6px 22px rgba(255,122,89,.22); }
    [data-testid="stButtonGroup"] button { font-family: var(--mono); font-size: .72rem; }
    </style>
    """
)

# Streamlit descarta o estado de widgets que não aparecem na tela; reatribuir as
# chaves mantém as escolhas ao navegar entre as etapas.
for _key in list(st.session_state.keys()):
    if _key.startswith("opt_"):
        st.session_state[_key] = st.session_state[_key]

state = st.session_state
state.setdefault("step", 1)
state.setdefault("rules", [])
for _key, _value in {"opt_null_tokens": True, "opt_dedup": True, "opt_iqr": 1.5, "opt_skew": 0.5,
                     "opt_sort": "Nulos↓", "opt_csv_sep": ",", "opt_n_filters": 0}.items():
    state.setdefault(_key, _value)


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def esc(value) -> str:
    return html.escape(str(value))


def fmt_int(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def fmt_num(x: float) -> str:
    if abs(x) >= 1000:
        return f"{x:,.0f}".replace(",", ".")
    return f"{x:,.2f}".rstrip("0").rstrip(".").replace(".", ",")


def fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024


def col_key(col) -> str:
    return hashlib.md5(str(col).encode()).hexdigest()[:10]


def pct_color(pct: float) -> str:
    return "green" if pct >= 99.95 else "amber" if pct >= 70 else "red"


def go(step: int):
    state.step = step
    st.rerun()


def reset_all():
    for key in list(state.keys()):
        if key.startswith("opt_") or key in ("file_id", "file_name", "file_data", "rules", "used_sep"):
            del state[key]


@st.cache_data(show_spinner="Lendo arquivo...")
def load(data: bytes, name: str, sep: str | None, sheet: str | None):
    return cl.read_file(data, name, sep, sheet)


@st.cache_data
def sheets(data: bytes):
    return cl.excel_sheets(data)


def raw_data():
    if "file_data" not in state:
        return None
    try:
        df, used = load(state.file_data, state.file_name, SEPARATORS[state.get("opt_sep", "Automático")],
                        state.get("opt_sheet"))
        state.used_sep = used
        return df
    except Exception as e:
        st.error(f"Não foi possível ler o arquivo: {e}")
        return None


@st.cache_data(show_spinner=False)
def run_prepare(file_id: str, _df: pd.DataFrame, cfg_json: str):
    return cl.prepare(_df, json.loads(cfg_json))


@st.cache_data(show_spinner=False)
def run_treat(file_id: str, _prep: pd.DataFrame, cfg_json: str, types_json: str):
    return cl.treat(_prep, json.loads(cfg_json), json.loads(types_json))


@st.cache_data(show_spinner=False)
def profiles(file_id: str, _prep: pd.DataFrame, cfg_json: str, types_json: str):
    types, factor = json.loads(types_json), json.loads(cfg_json).get("iqr_factor", 1.5)
    return {c: cl.column_profile(_prep[c], types[c], factor) for c in _prep.columns}


def base_config() -> dict:
    """Configuração da estruturação (antes do tratamento estatístico)."""
    return {
        "rules": state.rules,
        "drop": state.get("opt_drop", []),
        "rename": {c: state.get(f"opt_rename_{col_key(c)}", c) for c in state.get("opt_rename_cols", [])},
        "types": {c: t for c, t in state.get("type_overrides", {}).items()},
        "text": {"case": state.get("opt_case", "manter"), "accents": state.get("opt_accents", False),
                 "special": state.get("opt_special", False), "empty_as_null": state.get("opt_null_tokens", True)},
        "dedup": state.get("opt_dedup", True),
    }


def treat_config(columns) -> dict:
    per_col = {}
    for c in columns:
        k = col_key(c)
        per_col[c] = {"impute": state.get(f"opt_imp_{k}"), "outliers": state.get(f"opt_out_{k}", "manter")}
    filters = []
    for i in range(int(state.get("opt_n_filters", 0))):
        if state.get(f"opt_fcol_{i}") is not None:
            filters.append({"column": state.get(f"opt_fcol_{i}"), "operator": state.get(f"opt_fop_{i}", "=="),
                            "value": state.get(f"opt_fval_{i}", "")})
    return {"columns": per_col, "drop_null_rows": state.get("opt_null_rows", []),
            "iqr_factor": state.get("opt_iqr", 1.5), "skew_limit": state.get("opt_skew", 0.5), "filters": filters}


def pipeline():
    """Executa as duas fases da limpeza com cache. Retorna um dicionário com tudo que as telas usam."""
    raw = raw_data()
    if raw is None:
        return None
    for key in list(state.get("type_overrides", {})):
        if f"opt_type_{col_key(key)}" not in state:
            state.type_overrides.pop(key)
    cfg = base_config()
    cfg_json = json.dumps(cfg, default=str, sort_keys=True)
    fid = f'{state.file_id}|{state.get("opt_sep")}|{state.get("opt_sheet")}'
    try:
        prep, plog, types = run_prepare(fid, raw, cfg_json)
    except Exception as e:
        st.error(f"Erro ao preparar os dados: {e}")
        return None
    tcfg = treat_config(prep.columns)
    tcfg_json, types_json = json.dumps(tcfg, default=str, sort_keys=True), json.dumps(types, sort_keys=True)
    try:
        out, tlog, imputed, counts = run_treat(fid + cfg_json, prep, tcfg_json, types_json)
    except Exception as e:
        st.error(f"Erro ao tratar os dados: {e}")
        return None
    profs = profiles(fid + cfg_json, prep, tcfg_json, types_json)
    return {"raw": raw, "prep": prep, "types": types, "out": out, "imputed": imputed, "counts": counts,
            "log": plog + tlog, "profiles": profs, "dups": len(raw) - len(prep)}


# --------------------------------------------------------------------------- #
# Cabeçalho
# --------------------------------------------------------------------------- #
def stepper_html(current: int) -> str:
    parts = []
    for i, name in enumerate(STEPS, start=1):
        cls = "current" if i == current else "done" if i < current else ""
        n = "✓" if i < current else str(i)
        parts.append(f'<div class="dc-step {cls}"><span class="n">{n}</span><span class="t">{name}</span></div>')
    return '<div class="dc-stepper"><div class="dc-track">' + "".join(parts) + "</div></div>"


def header(result=None):
    brand, steps, actions = st.columns([1.2, 3, 1.4], vertical_alignment="center")
    brand.html('<div class="dc-brand"><span class="dc-logo">&#10022;</span><div><b>Limpador</b>'
               "<small>dados prontos para análise</small></div></div>")
    steps.html(stepper_html(state.step))
    if state.step > 1:
        a1, a2 = actions.columns(2)
        if a1.button("Trocar arquivo", width="stretch"):
            reset_all()
            go(1)
        if state.step == 2:
            if a2.button("Exportar", type="primary", icon=":material/arrow_forward:", icon_position="right",
                         width="stretch"):
                go(3)
        elif result is not None:
            with a2.popover("Baixar", icon=":material/download:", type="primary", width="stretch"):
                download_buttons(result["out"], key="top")
    st.html('<div class="dc-rule"></div>')


def download_buttons(df: pd.DataFrame, key: str, primary: str = "json"):
    base = state.file_name.rsplit(".", 1)[0] + "_limpo"
    sep = state.get("opt_csv_sep", ",")
    st.download_button("Baixar CSV", cl.to_csv_bytes(df, sep), f"{base}.csv", "text/csv", key=f"csv_{key}",
                       icon=":material/download:", width="stretch")
    try:
        st.download_button("Baixar Excel", cl.to_excel_bytes(df), f"{base}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"xlsx_{key}",
                           icon=":material/download:", width="stretch")
    except Exception as e:
        st.caption(f"Excel indisponível: {e}")
    st.download_button("Baixar JSON", cl.to_json_bytes(df), f"{base}.json", "application/json",
                       key=f"json_{key}", icon=":material/download:", width="stretch",
                       type="primary" if primary == "json" else "secondary")


# --------------------------------------------------------------------------- #
# Etapa 1 — Carregar
# --------------------------------------------------------------------------- #
def step_upload():
    st.write("")
    uploaded = st.file_uploader("Arquivo", type=UPLOAD_TYPES, label_visibility="collapsed", key="uploader")
    chips = "".join(f'<div class="dc-chip c-{color} bg-{color}">{name}</div>' for name, color in FEATURES)
    st.html(f'<div class="dc-chips">{chips}</div>')
    if uploaded is not None:
        reset_all()
        state.file_id = f"{uploaded.name}-{uploaded.size}"
        state.file_name, state.file_data = uploaded.name, uploaded.getvalue()
        del state["uploader"]
        go(2)


# --------------------------------------------------------------------------- #
# Etapa 2 — Tratar
# --------------------------------------------------------------------------- #
def ring(pct: float, color: str, caption: str) -> str:
    return (f'<div class="dc-ring"><div class="dial" style="background:conic-gradient(var(--{color}) '
            f'{pct:.1f}%, #15292c 0)"><span class="c-{color}">{pct:.0f}%</span></div>'
            f'<div class="cap">{caption}</div></div>')


def file_card(res):
    with st.container(key="card_file"):
        left, right = st.columns([3, 2], vertical_alignment="center")
        ext = state.file_name.rsplit(".", 1)[-1].upper()
        detail = ext
        if state.get("used_sep"):
            detail += f' · delim "{esc(state.used_sep).replace(chr(9), "tab")}"'
        detail += f" · {fmt_bytes(len(state.file_data))}"
        left.html(f'<div class="dc-file"><span class="ico">&#128462;</span><div><div class="name">'
                  f'{esc(state.file_name)}</div><div class="dc-small">{detail}</div></div></div>')
        with right:
            d, opt = st.columns([3, 1], vertical_alignment="center")
            d.html(f'<div class="dc-dims"><div><b>{fmt_int(len(res["raw"]))}</b><span class="dc-small">Linhas'
                   f'</span></div><div><b>{res["raw"].shape[1]}</b><span class="dc-small">Colunas</span></div></div>')
            with opt.popover("", icon=":material/tune:", help="Opções de leitura"):
                ext = ext.lower()
                if ext in ("csv", "tsv", "txt"):
                    st.selectbox("Separador", list(SEPARATORS), key="opt_sep")
                elif ext in ("xlsx", "xls"):
                    st.selectbox("Planilha", sheets(state.file_data), key="opt_sheet")
                else:
                    st.caption("Sem opções de leitura para este formato.")


def kpis(res):
    prep, out, profs = res["prep"], res["out"], res["profiles"]
    before, after = cl.quality(prep), cl.quality(out)
    diff = after - before
    outliers = sum(p.get("outliers", 0) for p in profs.values())
    problems = sum(1 for p in profs.values() if p["nulls"] or p.get("outliers", 0))
    items = [(res["dups"], "Duplicatas removidas", "muted" if not res["dups"] else "cyan"),
             (res["counts"]["imputed"], "Células imputadas", "amber"),
             (outliers, "Outliers detectados", "orange"),
             (problems, "Colunas com problemas", "accent")]
    blocks = "".join(f'<div class="dc-kpi"><b class="c-{"muted" if not v else c}">{fmt_int(v)}</b>'
                     f"<span>{label}</span></div>" for v, label, c in items)
    with st.container(key="card_kpis"):
        st.html(f'<div class="dc-kpis"><div class="dc-rings">{ring(before, pct_color(before), "Antes")}'
                f'<div class="dc-arrow c-accent">&#8594;<br><span class="c-green">{diff:+.0f}pp</span></div>'
                f'{ring(after, pct_color(after), "Depois")}</div>{blocks}</div>')


def value_options(prep: pd.DataFrame, col) -> list[str]:
    """Valores existentes (mais frequentes primeiro) para escolher na substituição manual."""
    cols = [col] if col in prep.columns else prep.columns.tolist()
    counts = pd.concat([prep[c].dropna().astype(str) for c in cols]).value_counts() if cols else pd.Series()
    return counts.index[:300].tolist()


def rules_panel(res):
    prep = res["prep"]
    columns = prep.columns.tolist()
    n = len(state.rules)
    title = "Substituições manuais de valores" + (f"  ·  {n} regra(s)" if n else "")
    with st.expander(title, icon=":material/find_replace:", expanded=bool(n)):
        st.caption("Escolha a coluna e o valor que quer trocar, antes do tratamento estatístico. "
                   "Deixe *Substituir por* vazio para transformar em nulo.")
        nonce = state.setdefault("rule_nonce", 0)
        c = st.columns([1.4, 1.9, 1.9, 1.9, 0.6, 1.5], vertical_alignment="bottom")
        labels = {"Todas as colunas": None} | {str(x): x for x in columns}
        col_label = c[0].selectbox("Coluna", list(labels), key="rule_col")
        col = labels[col_label]
        find = c[1].selectbox("Localizar", value_options(prep, col), index=None, accept_new_options=True,
                              placeholder="Valor a localizar…", key=f"rule_find_{nonce}")
        repl = c[2].text_input("Substituir por", placeholder="Novo valor (vazio = nulo)…",
                             key=f"rule_repl_{nonce}")
        mode = c[3].segmented_control("Tipo", ["Exato", "Contém", "Regex"], default="Exato", key="rule_mode")
        case = c[4].checkbox("Aa", help="Diferenciar maiúsculas e minúsculas", key="rule_case")
        if c[5].button("Adicionar regra", icon=":material/add:", width="stretch", disabled=not find):
            state.rules = state.rules + [{"column": col, "find": str(find), "replace": repl,
                                          "mode": (mode or "Exato").lower(), "case": case}]
            state.rule_nonce += 1
            st.rerun()
        for i, r in enumerate(state.rules):
            a, b = st.columns([12, 1], vertical_alignment="center")
            target = esc(r["column"] if r["column"] is not None else "todas")
            a.html(f'<div class="dc-small"><span class="c-accent">{target}</span> · "{esc(r["find"])}" → '
                   f'"{esc(r["replace"]) or "nulo"}" · {r["mode"]}{" · Aa" if r["case"] else ""}</div>')
            if b.button("", icon=":material/close:", key=f"del_rule_{i}", help="Remover regra"):
                state.rules = state.rules[:i] + state.rules[i + 1:]
                st.rerun()


def show_chart(chart, table: pd.DataFrame, empty_msg: str = "Nada a mostrar."):
    if chart is None:
        st.caption(empty_msg)
        return
    spec_height = chart.to_dict().get("height")
    height = spec_height + 70 if isinstance(spec_height, int) else "content"
    st.altair_chart(chart, width="stretch", height=height, theme=None)
    with st.expander("Ver dados do gráfico"):
        st.dataframe(table, hide_index=True, width="stretch")


def charts_panel(res):
    df = res["prep"]
    num_cols, cat_cols = cl.numeric_columns(df), cl.text_columns(df)
    with st.container(key="card_charts"):
        st.html('<div class="dc-title">Gráficos</div>')
        t_nulls, t_dist, t_cat, t_corr = st.tabs(["Nulos", "Distribuição", "Categorias", "Correlação"])
        with t_nulls:
            show_chart(*ch.nulls_bar(df), empty_msg="Nenhuma coluna tem valores nulos.")
        with t_dist:
            if not num_cols:
                st.caption("Nenhuma coluna numérica.")
            else:
                a, b = st.columns([2, 1], vertical_alignment="bottom")
                col = a.selectbox("Coluna", num_cols, key="opt_chart_num")
                with_out = b.toggle("Incluir outliers no eixo", key="opt_chart_out")
                sk = cl.pearson_skewness(df[col])
                st.caption(f"Assimetria de Pearson {sk:+.2f} ({cl.interpret_skewness(sk)})")
                show_chart(*ch.distribution(df[col], state.get("opt_iqr", 1.5), include_outliers=with_out))
        with t_cat:
            if not cat_cols:
                st.caption("Nenhuma coluna de texto.")
            else:
                col = st.selectbox("Coluna", cat_cols, key="opt_chart_cat")
                st.caption(f"{fmt_int(df[col].nunique())} valores distintos")
                show_chart(*ch.top_values(df[col]))
        with t_corr:
            show_chart(*ch.correlation(df), empty_msg="São necessárias ao menos duas colunas numéricas.")


def compare_panel(res):
    before, after = res["prep"], res["out"]
    with st.container(key="card_compare"):
        st.html('<div class="dc-title">Antes e depois</div>')
        t_nulls, t_dist = st.tabs(["Nulos", "Distribuição"])
        with t_nulls:
            show_chart(*ch.nulls_compare(before, after), empty_msg="Não havia nulos no arquivo.")
        with t_dist:
            shared = [c for c in cl.numeric_columns(after) if c in before.columns]
            if not shared:
                st.caption("Nenhuma coluna numérica para comparar.")
            else:
                col = st.selectbox("Coluna", shared, key="opt_cmp_col")
                show_chart(*ch.distribution_compare(before[col], after[col]))


def completeness(res):
    rows = []
    for col, p in res["profiles"].items():
        pct = 100 - p["nulls"] / max(p["total"], 1) * 100
        tag, color = KIND_STYLE[p["kind"]]
        pc = pct_color(pct)
        name = esc(col) if str(col).strip() and not str(col).startswith("Unnamed") else '<span class="c-muted">—</span>'
        rows.append(f'<div class="dc-comp-row"><span class="dc-badge c-{color} bg-{color}">{tag}</span>'
                    f'<span class="dc-trunc">{name}</span><div class="dc-bar"><i style="width:{pct:.1f}%;'
                    f'background:var(--{pc})"></i></div><span class="pct c-{pc}">{pct:.0f}%</span></div>')
    with st.container(key="card_comp"):
        st.html(f'<div class="dc-title">Completude por coluna</div><div class="dc-comp">{"".join(rows)}</div>')


def histogram_html(series: pd.Series, prof: dict, factor: float, bins: int = 14) -> str:
    s = series.dropna().astype(float)
    if s.empty:
        return ""
    counts, edges = pd.cut(s, bins=bins, retbins=True, include_lowest=True)
    freq = counts.value_counts(sort=False).to_numpy()
    low, high = cl.outlier_bounds(s, "IQR", factor)
    peak = max(freq.max(), 1)
    bars = []
    for i, f in enumerate(freq):
        mid = (edges[i] + edges[i + 1]) / 2
        cls = ' class="out"' if (mid < low or mid > high) and f else ""
        bars.append(f'<i{cls} style="height:{f / peak * 100:.0f}%"></i>')
    return (f'<div class="dc-range"><span>{fmt_num(prof["min"])}</span><span class="c-cyan">'
            f'{cl.skew_label(prof["skew"])}</span><span>{fmt_num(prof["max"])}</span></div>'
            f'<div class="dc-hist">{"".join(bars)}</div>')


def column_card(col, prof: dict, series: pd.Series, res, idx: int):
    k = col_key(col)
    tag, color = KIND_STYLE[prof["kind"]]
    total, nulls = prof["total"], prof["nulls"]
    pct = nulls / max(total, 1) * 100
    nc = "green" if not nulls else "amber" if pct < 30 else "red"
    display = esc(col) if str(col).strip() and not str(col).startswith("Unnamed") else "(sem nome)"
    factor = state.get("opt_iqr", 1.5)

    with st.container(key=f"colcard_{k}"):
        head, menu = st.columns([6, 1], vertical_alignment="center")
        head.html(f'<div class="dc-strip" style="background:var(--{color})"></div><div class="dc-colhead"><span class="name dc-trunc">{display}</span>'
                  f'<span class="dc-badge c-{color} bg-{color}">{prof["kind"].upper()}</span></div>')
        with menu.popover("", icon=":material/more_vert:", help="Tipo e exclusão"):
            current = res["types"][col]
            choice = st.selectbox("Tipo da coluna", cl.TYPES, index=cl.TYPES.index(current), key=f"opt_type_{k}")
            if choice != current or col in state.get("type_overrides", {}):
                state.setdefault("type_overrides", {})[col] = choice
            if st.button("Excluir coluna", icon=":material/delete:", key=f"drop_{k}", width="stretch"):
                state.opt_drop = state.get("opt_drop", []) + [col]
                st.rerun()

        body = [f'<div class="dc-row"><span class="c-muted">Nulos</span><span class="v c-{nc}">'
                f"{fmt_int(nulls)}/{fmt_int(total)} · {pct:.0f}%</span></div>"
                f'<div class="dc-bar" style="margin-top:.4rem"><i style="width:{max(pct, 0.5 if nulls else 0):.1f}%;'
                f'background:var(--{nc})"></i></div>']
        body.append(f'<div class="dc-note">{"· " + prof["pattern"] if prof["pattern"] else "&nbsp;"}</div>')

        kind = prof["kind"]
        if kind == "numérico" and "mean" in prof:
            body.append(histogram_html(series, prof, factor))
            body.append(f'<div class="dc-stats"><div><span>μ</span><b>{fmt_num(prof["mean"])}</b></div>'
                        f'<div><span>MED</span><b>{fmt_num(prof["median"])}</b></div>'
                        f'<div><span>σ</span><b>{fmt_num(prof["std"])}</b></div></div>')
            out = prof["outliers"]
            out_html = f'<span class="c-orange">{out} outlier{"s" if out != 1 else ""} (IQR)</span>' if out else ""
            body.append(f'<div class="dc-meta"><span>{fmt_int(prof["unique"])} únicos</span>'
                        f'<span>curt={prof["kurt"]:.1f}</span>{out_html}</div>')
        elif kind == "data" and "min" in prof:
            body.append(f'<div class="dc-stats" style="grid-template-columns:1fr 1fr"><div><span>INÍCIO</span>'
                        f'<b>{prof["min"]:%d/%m/%Y}</b></div><div><span>FIM</span><b>{prof["max"]:%d/%m/%Y}</b>'
                        f'</div></div><div class="dc-meta"><span>{fmt_int(prof["unique"])} únicos</span></div>')
        elif "top" in prof:
            rows = "".join(f'<span class="dc-trunc">{esc(v)}</span><div class="dc-bar"><i style="width:{p}%;'
                           f'background:var(--{color});opacity:.7"></i></div><span class="pct">{p}%</span>'
                           for v, p in prof["top"])
            body.append(f'<div class="dc-cats">{rows}</div><div class="dc-meta"><span>{fmt_int(prof["unique"])} '
                        f'únicos</span><span>H={prof["entropy"]:.2f} bit</span></div>')
        st.html("".join(body))

        has_out = kind == "numérico" and prof.get("outliers", 0)
        if not nulls and not has_out:
            st.html('<div class="dc-sep"></div><div class="dc-ok">&#10003; Coluna completa</div>')
            return

        if nulls:
            rec, why = cl.recommend(series, kind, state.get("opt_skew", 0.5))
            options = cl.IMPUTE_OPTIONS[kind]
            key = f"opt_imp_{k}"
            if state.get(key) not in options:
                state[key] = rec
            treated = int(res["imputed"][col].sum()) if col in res["imputed"] else 0
            badge = (f'<span class="dc-pill c-amber bg-amber">{treated} tratado{"s" if treated != 1 else ""}</span>'
                     if treated else '<span class="dc-pill c-muted" style="border-color:var(--border)">nulos '
                                     'mantidos</span>')
            st.html(f'<div class="dc-sep"></div><div class="dc-row"><span class="dc-label">Estratégia</span>'
                    f"{badge}</div>")
            method = st.segmented_control("Estratégia", options, format_func=IMPUTE_LABELS.get, key=key,
                                          label_visibility="collapsed") or rec
            value = cl.fill_value(series, method)
            shown = cl.format_value(value) if value is not None else IMPUTE_HELP[method].split(":")[0]
            explain = why if method == rec else IMPUTE_HELP[method]
            st.html(f'<div class="dc-value">Valor: <b class="c-{color}">{esc(shown)}</b></div>'
                    f'<div class="dc-why">{esc(explain)}</div>')

        if has_out:
            st.html('<div class="dc-sep"></div><div class="dc-row"><span class="dc-label">Outliers (IQR)</span>'
                    f'<span class="dc-pill c-orange bg-orange">{prof["outliers"]} detectado'
                    f'{"s" if prof["outliers"] != 1 else ""}</span></div>')
            key = f"opt_out_{k}"
            state.setdefault(key, "manter")
            st.segmented_control("Outliers", cl.OUTLIER_ACTIONS, format_func=OUTLIER_LABELS.get, key=key,
                                 label_visibility="collapsed")
            with st.popover("Ver distribuição", icon=":material/bar_chart:", width="stretch"):
                chart, _ = ch.distribution(series, factor, include_outliers=True)
                if chart is not None:
                    st.altair_chart(chart, width="stretch")


def columns_section(res):
    profs = res["profiles"]
    problems = [c for c, p in profs.items() if p["nulls"] or p.get("outliers", 0)]
    head, search, flt, sort = st.columns([1.2, 1.6, 4.2, 1.8], vertical_alignment="center")
    q = search.text_input("Buscar", placeholder="Buscar…", key="opt_search", label_visibility="collapsed",
                          icon=":material/search:")
    options = ["Todas", f"Problemas ({len(problems)})"] + [k for k, v in KIND_FILTERS.items()
                                                            if any(p["kind"] == v for p in profs.values())]
    if state.get("opt_filter") and state.opt_filter.startswith("Problemas"):
        state.opt_filter = options[1]
    if state.get("opt_filter") not in options:
        state.opt_filter = options[1] if problems else "Todas"
    choice = flt.pills("Filtro", options, key="opt_filter", label_visibility="collapsed") or "Todas"
    order = sort.pills("Ordenar", ["Nulos↓", "A-Z", "Tipo"], key="opt_sort",
                       label_visibility="collapsed") or "Nulos↓"

    cols = list(profs)
    if choice.startswith("Problemas"):
        cols = [c for c in cols if c in problems]
    elif choice in KIND_FILTERS:
        cols = [c for c in cols if profs[c]["kind"] == KIND_FILTERS[choice]]
    if q:
        cols = [c for c in cols if q.lower() in str(c).lower()]
    if order == "Nulos↓":
        cols.sort(key=lambda c: (-profs[c]["nulls"], -profs[c].get("outliers", 0)))
    elif order == "A-Z":
        cols.sort(key=lambda c: str(c).lower())
    else:
        cols.sort(key=lambda c: (cl.TYPES.index(profs[c]["kind"]), str(c).lower()))
    head.html(f'<div style="font-weight:700;font-size:1.05rem">Colunas <span class="dc-small">'
              f"{len(cols)}/{len(profs)}</span></div>")

    if not cols:
        st.caption("Nenhuma coluna corresponde ao filtro.")
        return
    for start in range(0, len(cols), 3):
        grid = st.columns(3)
        for slot, col in zip(grid, cols[start:start + 3]):
            with slot:
                column_card(col, profs[col], res["prep"][col], res, start)


def advanced_panel(res):
    with st.expander("Mais opções de limpeza", icon=":material/tune:"):
        t_text, t_cols, t_rows = st.tabs(["Texto", "Colunas", "Linhas e filtros"])
        with t_text:
            a, b = st.columns(2, gap="large")
            a.toggle("Tratar vazios, NA, null e - como nulos", key="opt_null_tokens")
            a.toggle("Remover acentos", key="opt_accents")
            a.toggle("Remover caracteres especiais", key="opt_special")
            b.radio("Maiúsculas e minúsculas", ["manter", "minúsculas", "MAIÚSCULAS", "Título"], key="opt_case",
                    horizontal=True)
            st.caption("Espaços nas pontas e espaços duplicados são sempre removidos.")
        with t_cols:
            all_cols = res["raw"].columns.tolist()
            a, b = st.columns(2, gap="large")
            a.multiselect("Excluir colunas", all_cols, key="opt_drop")
            remaining = [c for c in all_cols if c not in state.get("opt_drop", [])]
            to_rename = b.multiselect("Renomear colunas", remaining, key="opt_rename_cols")
            for c in to_rename:
                state.setdefault(f"opt_rename_{col_key(c)}", str(c))
                b.text_input(f"Novo nome para {c}", key=f"opt_rename_{col_key(c)}")
        with t_rows:
            a, b = st.columns(2, gap="large")
            a.toggle("Remover linhas duplicadas", key="opt_dedup")
            a.multiselect("Remover linhas com nulos nas colunas", res["prep"].columns.tolist(), key="opt_null_rows")
            b.number_input("Fator IQR para outliers", 0.5, 10.0, step=0.5, key="opt_iqr")
            b.number_input("Limite de |assimetria| para usar a média", 0.0, 5.0, step=0.1, key="opt_skew",
                           help="Assimetria de Pearson = 3 × (média − mediana) / desvio padrão. Abaixo do limite, "
                                "a sugestão é a média; acima, a mediana.")
            st.write("**Filtros**")
            n = st.number_input("Quantidade de filtros", 0, 10, key="opt_n_filters")
            cols = res["prep"].columns.tolist()
            for i in range(int(n)):
                c1, c2, c3 = st.columns([2, 1, 2])
                c1.selectbox("Coluna", cols, key=f"opt_fcol_{i}")
                op = c2.selectbox("Operador", cl.OPERATORS, key=f"opt_fop_{i}")
                if op not in ("é nulo", "não é nulo"):
                    c3.text_input("Valor", key=f"opt_fval_{i}")
            if n:
                st.caption("Linhas que não atendem aos filtros são removidas.")


def step_treat(res):
    file_card(res)
    kpis(res)
    rules_panel(res)
    completeness(res)
    charts_panel(res)
    advanced_panel(res)
    st.write("")
    columns_section(res)
    st.write("")
    _, right = st.columns([3, 1])
    if right.button("Continuar para exportação", type="primary", icon=":material/arrow_forward:",
                    icon_position="right", width="stretch"):
        go(3)


# --------------------------------------------------------------------------- #
# Etapa 3 — Exportar
# --------------------------------------------------------------------------- #
def stat_card(key, dot, title, value, color, sub, extra=""):
    with st.container(key=f"card_{key}"):
        st.html(f'<div class="dc-stat-title"><span class="dc-dot" style="background:var(--{dot})"></span>'
                f'{title}</div><div class="dc-stat-big c-{color}">{value}<span style="font-size:.95rem;'
                f'font-weight:500;margin-left:.6rem" class="c-green">{extra}</span></div>'
                f'<div class="dc-small">{sub}</div>')


def highlight(df: pd.DataFrame, mask: pd.DataFrame):
    style = "background-color: rgba(250,204,21,.12); color: #facc15"
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    styles[mask.reindex(index=df.index, columns=df.columns, fill_value=False).astype(bool)] = style
    return df.style.apply(lambda _: styles, axis=None).format(precision=2, na_rep="")


def step_export(res):
    out, prep = res["out"], res["prep"]
    before, after = cl.quality(prep), cl.quality(out)
    s1, s2, s3 = st.columns(3)
    with s1:
        stat_card("q", "green", "Qualidade", f"{after:.0f}%", pct_color(after),
                  f"{fmt_int(len(out))} linhas · {out.shape[1]} colunas", f"{after - before:+.0f}pp")
    with s2:
        stat_card("i", "amber", "Imputações", fmt_int(res["counts"]["imputed"]), "amber",
                  "células preenchidas por estatística")
    with s3:
        stat_card("d", "red", "Deduplicação", fmt_int(res["dups"]), "red" if res["dups"] else "muted",
                  "duplicatas removidas")

    st.write("")
    entries = [e for e in res["log"] if "0 célula(s)" not in e["text"]]
    colors = {c: KIND_STYLE[t][1] for c, t in res["types"].items()}
    rows = []
    for e in entries:
        col = e.get("column")
        color = colors.get(col, "slate")
        name = esc(col) if col is not None else "Geral"
        rows.append(f'<div><span class="dc-dot" style="background:var(--amber)"></span>'
                    f'<span class="col c-{color} dc-trunc">{name}</span><span>{esc(e["text"])}</span>'
                    f'<span class="val">{esc(e.get("value", ""))}</span></div>')
    body = "".join(rows) or '<div class="dc-small">Nenhuma alteração aplicada.</div>'
    with st.container(key="card_log"):
        st.html(f'<div class="dc-title">Log de alterações</div><div class="dc-log">{body}</div>')

    st.write("")
    compare_panel(res)
    st.write("")
    with st.container(key="card_table"):
        t_out, t_raw = st.tabs([f"Dados Tratados ({fmt_int(len(out))})", f"Dados Originais ({fmt_int(len(res['raw']))})"])
        with t_out:
            n_imp = int(res["imputed"].to_numpy().sum())
            if n_imp:
                st.html('<div class="dc-small" style="text-align:right"><span class="c-amber">&#9679; imputado'
                        "</span></div>")
            view = out.head(PREVIEW_ROWS)
            if len(out) > PREVIEW_ROWS:
                st.caption(f"Primeiras {fmt_int(PREVIEW_ROWS)} de {fmt_int(len(out))} linhas")
            try:
                styled = highlight(view, res["imputed"].head(PREVIEW_ROWS)) if n_imp else \
                    view.style.format(precision=2, na_rep="")
                st.dataframe(styled, width="stretch")
            except Exception:
                st.dataframe(view.astype(str), width="stretch")
        with t_raw:
            st.dataframe(res["raw"].head(PREVIEW_ROWS).astype(str), width="stretch")

    st.write("")
    back, _, sep, d1, d2, d3 = st.columns([1.4, 1.2, 1, 1.1, 1.1, 1.1], vertical_alignment="bottom")
    if back.button("Voltar e ajustar", icon=":material/arrow_back:", type="tertiary"):
        go(2)
    sep.segmented_control("Separador do CSV", [",", ";"], key="opt_csv_sep")
    base = state.file_name.rsplit(".", 1)[0] + "_limpo"
    d1.download_button("Baixar CSV", cl.to_csv_bytes(out, state.get("opt_csv_sep") or ","), f"{base}.csv",
                       "text/csv", icon=":material/download:", width="stretch")
    try:
        d2.download_button("Baixar Excel", cl.to_excel_bytes(out), f"{base}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           icon=":material/download:", width="stretch")
    except Exception as e:
        d2.caption(f"Excel indisponível: {e}")
    d3.download_button("Baixar JSON", cl.to_json_bytes(out), f"{base}.json", "application/json",
                       icon=":material/download:", type="primary", width="stretch")


# --------------------------------------------------------------------------- #
# Página
# --------------------------------------------------------------------------- #
result = pipeline() if state.step > 1 else None
if state.step > 1 and result is None and "file_data" not in state:
    state.step = 1
header(result)

if state.step == 1:
    step_upload()
elif result is not None and state.step == 2:
    step_treat(result)
elif result is not None:
    step_export(result)
