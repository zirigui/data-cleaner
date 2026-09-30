"""Funções de leitura, diagnóstico e limpeza de dados (sem dependência do Streamlit)."""

import csv
import io
import re
import unicodedata

import numpy as np
import pandas as pd

NULL_TOKENS = ["", "na", "n/a", "nan", "null", "none", "-", "?", "sem dado"]
BOOL_MAP = {"true": True, "false": False, "verdadeiro": True, "falso": False, "sim": True, "não": False,
            "nao": False, "s": True, "n": False, "1": True, "0": False, "yes": True, "no": False}


# --------------------------------------------------------------------------- #
# Leitura
# --------------------------------------------------------------------------- #
def detect_separator(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        counts = {sep: sample.count(sep) for sep in [",", ";", "\t", "|"]}
        return max(counts, key=counts.get)


def decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def excel_sheets(data: bytes) -> list[str]:
    return pd.ExcelFile(io.BytesIO(data)).sheet_names


def read_file(data: bytes, name: str, sep: str | None = None, sheet: str | None = None) -> tuple[pd.DataFrame, str | None]:
    """Lê o arquivo e retorna (DataFrame, separador usado ou None)."""
    ext = name.rsplit(".", 1)[-1].lower()
    if ext in ("csv", "txt"):
        text = decode_bytes(data)
        sep = sep or detect_separator(text[:20000])
        return pd.read_csv(io.StringIO(text), sep=sep), sep
    if ext in ("xlsx", "xls"):
        return pd.read_excel(io.BytesIO(data), sheet_name=sheet or 0), None
    if ext == "json":
        try:
            return pd.read_json(io.BytesIO(data)), None
        except ValueError:
            import json
            return pd.json_normalize(json.loads(decode_bytes(data))), None
    if ext == "parquet":
        return pd.read_parquet(io.BytesIO(data)), None
    raise ValueError(f"Formato não suportado: .{ext}")


# --------------------------------------------------------------------------- #
# Diagnóstico
# --------------------------------------------------------------------------- #
def is_text(series: pd.Series) -> bool:
    return pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)


def numeric_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include="number").columns.tolist()


def text_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if is_text(df[c])]


def pearson_skewness(series: pd.Series) -> float:
    """Segundo coeficiente de assimetria de Pearson: 3 * (média - mediana) / desvio padrão."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 2 or s.std() == 0:
        return 0.0
    return float(3 * (s.mean() - s.median()) / s.std())


def interpret_skewness(value: float) -> str:
    if abs(value) < 0.15:
        return "simétrica"
    if abs(value) < 1:
        return "moderada " + ("à direita" if value > 0 else "à esquerda")
    return "forte " + ("à direita" if value > 0 else "à esquerda")


def diagnose(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in df.columns:
        s = df[col]
        row = {
            "coluna": col,
            "tipo": str(s.dtype),
            "nulos": int(s.isna().sum()),
            "% nulos": round(s.isna().mean() * 100, 2),
            "valores únicos": int(s.nunique(dropna=True)),
            "assimetria (Pearson)": None,
            "interpretação": "",
        }
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            sk = pearson_skewness(s)
            row["assimetria (Pearson)"] = round(sk, 3)
            row["interpretação"] = interpret_skewness(sk)
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Etapas de limpeza — cada uma retorna (df, mensagens de log)
# --------------------------------------------------------------------------- #
def to_snake_case(name: str) -> str:
    name = remove_accents(str(name)).strip().lower()
    name = re.sub(r"[^\w]+", "_", name)
    return re.sub(r"_+", "_", name).strip("_")


def remove_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def columns_step(df, drop=None, rename=None, snake_case=False):
    log = []
    if drop:
        df = df.drop(columns=drop)
        log.append(f"Colunas excluídas: {', '.join(map(str, drop))}")
    if rename:
        rename = {k: v for k, v in rename.items() if v and v != k}
        if rename:
            df = df.rename(columns=rename)
            log.append(f"Colunas renomeadas: {rename}")
    if snake_case:
        df.columns = [to_snake_case(c) for c in df.columns]
        log.append("Nomes de colunas padronizados (snake_case)")
    return df, log


def parse_number(series: pd.Series, decimal_comma: bool) -> pd.Series:
    if not is_text(series):
        return pd.to_numeric(series, errors="coerce")
    s = series.astype("string").str.strip().str.replace(r"[R$\s%]", "", regex=True)
    if decimal_comma:
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def types_step(df, conversions: dict, decimal_comma=False, dayfirst=True):
    log = []
    for col, target in conversions.items():
        before = df[col].isna().sum()
        if target == "número":
            df[col] = parse_number(df[col], decimal_comma)
        elif target == "inteiro":
            df[col] = parse_number(df[col], decimal_comma).round().astype("Int64")
        elif target == "data":
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=dayfirst)
        elif target == "texto":
            df[col] = df[col].astype("string")
        elif target == "categoria":
            df[col] = df[col].astype("category")
        elif target == "booleano":
            df[col] = df[col].astype("string").str.strip().str.lower().map(BOOL_MAP).astype("boolean")
        lost = int(df[col].isna().sum() - before)
        msg = f"'{col}' convertida para {target}"
        if lost > 0:
            msg += f" ({lost} valores inválidos viraram nulos)"
        log.append(msg)
    return df, log


def text_step(df, columns, strip=True, collapse_spaces=True, case="manter",
              accents=False, special=False, empty_as_null=True):
    log = []
    for col in columns:
        s = df[col].astype("string")
        if strip:
            s = s.str.strip()
        if collapse_spaces:
            s = s.str.replace(r"\s+", " ", regex=True)
        if case == "minúsculas":
            s = s.str.lower()
        elif case == "MAIÚSCULAS":
            s = s.str.upper()
        elif case == "Título":
            s = s.str.title()
        if accents:
            s = s.map(lambda x: remove_accents(x) if isinstance(x, str) else x).astype("string")
        if special:
            s = s.str.replace(r"[^\w\s\.,@\-]", "", regex=True)
        if empty_as_null:
            s = s.mask(s.str.strip().str.lower().isin(NULL_TOKENS))
        df[col] = s
    if columns:
        log.append(f"Texto padronizado em {len(columns)} coluna(s)")
    return df, log


def duplicates_nulls_step(df, drop_duplicates=False, dup_subset=None, keep="first",
                          drop_null_rows_in=None, drop_cols_threshold=None):
    log = []
    if drop_duplicates:
        n = len(df)
        df = df.drop_duplicates(subset=dup_subset or None, keep=keep)
        log.append(f"{n - len(df)} linha(s) duplicada(s) removida(s)")
    if drop_null_rows_in:
        n = len(df)
        df = df.dropna(subset=drop_null_rows_in)
        log.append(f"{n - len(df)} linha(s) com nulos em {drop_null_rows_in} removida(s)")
    if drop_cols_threshold is not None:
        pct = df.isna().mean() * 100
        cols = pct[pct > drop_cols_threshold].index.tolist()
        if cols:
            df = df.drop(columns=cols)
            log.append(f"Colunas com mais de {drop_cols_threshold}% de nulos excluídas: {cols}")
    return df, log


def _is_int(series: pd.Series) -> bool:
    return pd.api.types.is_integer_dtype(series)


def _fill(series: pd.Series, value) -> pd.Series:
    """fillna que arredonda o valor quando a coluna é inteira (ex.: média em Int64)."""
    if _is_int(series) and isinstance(value, float):
        value = round(value)
    return series.fillna(value)


def impute_step(df, columns, method, fixed_value=None, skew_limit=0.5):
    log = []
    for col in columns:
        n_null = int(df[col].isna().sum())
        if n_null == 0:
            continue
        s = df[col]
        numeric = pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
        used = method
        if method == "automática (Pearson)":
            if numeric:
                sk = pearson_skewness(s)
                used = "média" if abs(sk) < skew_limit else "mediana"
                used += f" (assimetria = {sk:.2f})"
                value = s.mean() if abs(sk) < skew_limit else s.median()
            else:
                used = "moda (coluna não numérica)"
                value = s.mode().iloc[0] if not s.mode().empty else None
            df[col] = _fill(s, value)
        elif method in ("média", "mediana", "interpolação linear") and not numeric:
            log.append(f"'{col}' ignorada: {method} exige coluna numérica")
            continue
        elif method == "média":
            df[col] = _fill(s, s.mean())
        elif method == "mediana":
            df[col] = _fill(s, float(s.median()))
        elif method == "moda":
            mode = s.mode()
            if not mode.empty:
                df[col] = s.fillna(mode.iloc[0])
        elif method == "valor fixo":
            value = fixed_value
            if numeric:
                try:
                    value = float(str(fixed_value).replace(",", "."))
                except ValueError:
                    log.append(f"'{col}' ignorada: valor fixo não é numérico")
                    continue
            df[col] = _fill(s, value)
        elif method == "forward fill":
            df[col] = s.ffill()
        elif method == "backward fill":
            df[col] = s.bfill()
        elif method == "interpolação linear":
            filled = s.astype(float).interpolate(limit_direction="both")
            df[col] = filled.round().astype(s.dtype) if _is_int(s) else filled
        filled = n_null - int(df[col].isna().sum())
        log.append(f"'{col}': {filled} nulo(s) preenchido(s) com {used}")
    return df, log


def outlier_bounds(series: pd.Series, method: str, factor: float) -> tuple[float, float]:
    s = series.dropna()
    if method == "IQR":
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        return q1 - factor * iqr, q3 + factor * iqr
    mean, std = s.mean(), s.std()
    return mean - factor * std, mean + factor * std


def outliers_step(df, columns, method="IQR", factor=1.5, action="remover linhas"):
    log = []
    mask_remove = pd.Series(False, index=df.index)
    for col in columns:
        low, high = outlier_bounds(df[col], method, factor)
        is_out = (df[col] < low) | (df[col] > high)
        n = int(is_out.sum())
        if action == "remover linhas":
            mask_remove |= is_out
        elif action == "limitar (winsorizar)":
            clipped = df[col].astype(float).clip(low, high)
            df[col] = clipped.round().astype(df[col].dtype) if _is_int(df[col]) else clipped
        elif action == "substituir por nulo":
            df[col] = df[col].mask(is_out)
        log.append(f"'{col}': {n} outlier(s) [{method}, limites {low:.2f} a {high:.2f}] → {action}")
    if action == "remover linhas" and columns:
        df = df[~mask_remove]
        log.append(f"{int(mask_remove.sum())} linha(s) com outliers removida(s)")
    return df, log


OPERATORS = ["==", "!=", ">", ">=", "<", "<=", "contém", "não contém", "é nulo", "não é nulo"]


def filter_step(df, filters: list[dict]):
    log = []
    for f in filters:
        col, op, raw = f["column"], f["operator"], f.get("value", "")
        s = df[col]
        value = raw
        if pd.api.types.is_numeric_dtype(s) and op in ("==", "!=", ">", ">=", "<", "<="):
            try:
                value = float(str(raw).replace(",", "."))
            except ValueError:
                log.append(f"Filtro em '{col}' ignorado: valor '{raw}' não é numérico")
                continue
        elif pd.api.types.is_datetime64_any_dtype(s) and op in ("==", "!=", ">", ">=", "<", "<="):
            value = pd.to_datetime(raw, dayfirst=True, errors="coerce")
        ops = {
            "==": lambda: s == value, "!=": lambda: s != value,
            ">": lambda: s > value, ">=": lambda: s >= value,
            "<": lambda: s < value, "<=": lambda: s <= value,
            "contém": lambda: s.astype("string").str.contains(str(raw), case=False, na=False, regex=False),
            "não contém": lambda: ~s.astype("string").str.contains(str(raw), case=False, na=False, regex=False),
            "é nulo": lambda: s.isna(), "não é nulo": lambda: s.notna(),
        }
        try:
            mask = ops[op]().fillna(False).astype(bool)
        except TypeError:
            log.append(f"Filtro em '{col}' ignorado: comparação inválida para o tipo da coluna")
            continue
        n = len(df)
        df = df[mask]
        log.append(f"Filtro '{col} {op} {raw}': {n - len(df)} linha(s) removida(s)")
    return df, log


def run_pipeline(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, list[str]]:
    """Aplica as etapas na ordem: colunas → tipos → texto → duplicatas/nulos → imputação → outliers → filtros."""
    df = df.copy()
    log: list[str] = []

    def existing(cols):
        return [c for c in (cols or []) if c in df.columns]

    df, l = columns_step(df, cfg.get("drop_columns"), cfg.get("rename"), cfg.get("snake_case", False))
    log += l
    # Após renomear, as demais etapas referenciam os nomes novos
    conversions = {c: t for c, t in cfg.get("conversions", {}).items() if c in df.columns}
    df, l = types_step(df, conversions, cfg.get("decimal_comma", False), cfg.get("dayfirst", True))
    log += l
    # Texto só se aplica a colunas que continuam textuais após a conversão de tipos
    text_cols = [c for c in existing(cfg.get("text_columns")) if is_text(df[c])]
    df, l = text_step(df, text_cols, **cfg.get("text_options", {}))
    log += l
    dup_null = dict(cfg.get("dup_null", {}))
    dup_null["dup_subset"] = existing(dup_null.get("dup_subset"))
    dup_null["drop_null_rows_in"] = existing(dup_null.get("drop_null_rows_in"))
    df, l = duplicates_nulls_step(df, **dup_null)
    log += l
    if existing(cfg.get("impute_columns")):
        df, l = impute_step(df, existing(cfg["impute_columns"]), cfg["impute_method"], cfg.get("fixed_value"), cfg.get("skew_limit", 0.5))
        log += l
    outlier_cols = [c for c in existing(cfg.get("outlier_columns")) if pd.api.types.is_numeric_dtype(df[c])]
    if outlier_cols:
        df, l = outliers_step(df, outlier_cols, cfg["outlier_method"], cfg["outlier_factor"], cfg["outlier_action"])
        log += l
    df, l = filter_step(df, [f for f in cfg.get("filters", []) if f["column"] in df.columns])
    log += l
    return df.reset_index(drop=True), log


# --------------------------------------------------------------------------- #
# Tratamento por coluna (fluxo Carregar → Tratar → Exportar)
# --------------------------------------------------------------------------- #
TYPES = ["numérico", "categórico", "booleano", "data", "texto"]
IMPUTE_OPTIONS = {
    "numérico": ["média", "mediana", "moda", "anterior", "seguinte", "interpolar", "preservar"],
    "categórico": ["moda", "anterior", "seguinte", "preservar"],
    "booleano": ["moda", "anterior", "seguinte", "preservar"],
    "data": ["anterior", "seguinte", "preservar"],
    "texto": ["moda", "anterior", "seguinte", "preservar"],
}
OUTLIER_ACTIONS = ["manter", "limitar", "nulo", "remover"]
MATCH_MODES = ["exato", "contém", "regex"]


def _clean_tokens(series: pd.Series) -> pd.Series:
    s = series.dropna().astype(str).str.strip()
    return s[~s.str.lower().isin(NULL_TOKENS)]


def looks_decimal_comma(series: pd.Series) -> bool:
    s = _clean_tokens(series).head(5000)
    comma = s.str.fullmatch(r"-?(R\$)?\s?[\d.]*,\d+%?").sum()
    dot = s.str.fullmatch(r"-?(R\$)?\s?[\d,]*\.\d+%?").sum()
    return bool(comma > dot)


def infer_type(series: pd.Series) -> str:
    """Tipo semântico da coluna, testado em uma amostra dos valores não nulos."""
    if pd.api.types.is_bool_dtype(series):
        return "booleano"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "data"
    if pd.api.types.is_numeric_dtype(series):
        return "numérico"
    s = _clean_tokens(series).head(5000)
    if s.empty:
        return "texto"
    if s.str.lower().isin(BOOL_MAP).mean() >= 0.95 and s.str.lower().nunique() <= 2:
        return "booleano"
    if parse_number(s, looks_decimal_comma(s)).notna().mean() >= 0.9:
        return "numérico"
    if s.str.contains(r"\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4}", regex=True).mean() >= 0.9:
        dates = pd.to_datetime(s, errors="coerce", dayfirst=True, format="mixed")
        if dates.notna().mean() >= 0.9:
            return "data"
    n_unique = s.nunique()
    ratio = n_unique / len(s)
    return "categórico" if ratio <= 0.5 or (n_unique <= 20 and ratio < 0.9) else "texto"


def infer_types(df: pd.DataFrame) -> dict:
    return {col: infer_type(df[col]) for col in df.columns}


def convert(series: pd.Series, target: str) -> pd.Series:
    if target == "numérico":
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            return series
        return parse_number(series, looks_decimal_comma(series))
    if target == "data":
        if pd.api.types.is_datetime64_any_dtype(series):
            return series
        return pd.to_datetime(series, errors="coerce", dayfirst=True, format="mixed")
    if target == "booleano":
        if pd.api.types.is_bool_dtype(series):
            return series
        return series.astype("string").str.strip().str.lower().map(BOOL_MAP).astype("boolean")
    return series.astype("string")


def _as_number(text) -> float | None:
    try:
        return float(str(text).strip().replace(",", "."))
    except ValueError:
        return None


def apply_rules(df: pd.DataFrame, rules: list[dict]):
    """Substituições manuais de valores. 'Substituir por' vazio transforma em nulo."""
    log = []
    for r in rules:
        find, repl, mode, case = r["find"], r.get("replace", ""), r.get("mode", "exato"), r.get("case", False)
        cols = [r["column"]] if r.get("column") in df.columns else df.columns.tolist()
        total = 0
        for col in cols:
            s = df[col]
            numeric = pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
            if mode == "exato" and numeric and _as_number(find) is not None:
                hit = (s == _as_number(find)).fillna(False).astype(bool)
                value = _as_number(repl) if repl != "" else np.nan
                new = s.mask(hit, value) if value is not None else s.astype("string").mask(hit, repl)
            else:
                text = s.astype("string")
                if mode == "exato":
                    hit = (text == find) if case else (text.str.lower() == str(find).lower())
                    hit = hit.fillna(False).astype(bool)
                    new = text.mask(hit, repl if repl != "" else pd.NA)
                else:
                    pattern = find if mode == "regex" else re.escape(find)
                    try:
                        hit = text.str.contains(pattern, case=case, regex=True, na=False).astype(bool)
                    except re.error:
                        log.append({"column": r.get("column"), "text": f"Regra ignorada: regex inválida '{find}'"})
                        break
                    replaced = text.str.replace(pattern, repl, case=case, regex=True)
                    new = text.where(~hit, replaced.mask(replaced.str.strip() == ""))
            n = int(hit.sum())
            if n:
                total += n
                df[col] = new
        where = r.get("column") or "todas as colunas"
        log.append({"column": r.get("column"),
                    "text": f"Substituição '{find}' → '{repl or 'nulo'}' ({mode}) em {where}: {total} célula(s)"})
    return df, log


def prepare(df: pd.DataFrame, cfg: dict):
    """Estrutura os dados antes do tratamento estatístico:
    colunas → texto → substituições manuais → tipos → deduplicação. Retorna (df, log, tipos)."""
    df = df.copy()
    log: list[dict] = []
    df, l = columns_step(df, [c for c in cfg.get("drop", []) if c in df.columns], cfg.get("rename"))
    log += [{"column": None, "text": t} for t in l]

    opts = {"strip": True, "collapse_spaces": True, "case": "manter", "accents": False,
            "special": False, "empty_as_null": True, **cfg.get("text", {})}
    raw_text = [c for c in df.columns if is_text(df[c])]
    df, _ = text_step(df, raw_text, **opts)
    df, l = apply_rules(df, cfg.get("rules", []))
    log += l

    types = {**infer_types(df), **{k: v for k, v in cfg.get("types", {}).items() if k in df.columns}}
    for col, target in types.items():
        before = int(df[col].isna().sum())
        df[col] = convert(df[col], target)
        lost = int(df[col].isna().sum()) - before
        if lost > 0:
            log.append({"column": col, "text": f"{lost} valor(es) inválido(s) para {target} viraram nulos"})
    if raw_text:
        log.append({"column": None, "text": f"Texto padronizado em {len(raw_text)} coluna(s)"})

    if cfg.get("dedup", True):
        n = len(df)
        df = df.drop_duplicates()
        if n - len(df):
            log.append({"column": None, "text": f"{n - len(df)} linha(s) duplicada(s) removida(s)"})
    return df, log, types


def recommend(series: pd.Series, kind: str, skew_limit: float = 0.5) -> tuple[str, str]:
    """Estratégia sugerida para preencher nulos e a justificativa."""
    if kind == "numérico":
        sk = pearson_skewness(series)
        if abs(sk) < skew_limit:
            return "média", f"Distribuição simétrica (assimetria = {sk:.2f}) → média representa bem o centro"
        return "mediana", f"Distribuição assimétrica (assimetria = {sk:.2f}) → mediana é robusta a outliers"
    if kind in ("categórico", "booleano"):
        mode = series.mode()
        if mode.empty:
            return "preservar", "Sem valores para calcular a moda"
        top = mode.iloc[0]
        return "moda", f'Variável {kind} → moda ("{top}", ocorre {int((series == top).sum())}×)'
    if kind == "data":
        return "anterior", "Datas → repete o valor da linha anterior"
    return "preservar", "Texto livre → nulos mantidos"


def fill_value(series: pd.Series, method: str):
    """Valor usado no preenchimento (ou None quando depende da linha)."""
    if method == "média":
        return series.mean()
    if method == "mediana":
        return float(series.median())
    if method == "moda":
        mode = series.mode()
        return mode.iloc[0] if not mode.empty else None
    return None


def impute_column(series: pd.Series, method: str) -> pd.Series:
    if method in ("média", "mediana", "moda"):
        value = fill_value(series, method)
        return series if value is None else _fill(series, value)
    if method == "anterior":
        return series.ffill()
    if method == "seguinte":
        return series.bfill()
    if method == "interpolar":
        filled = series.astype(float).interpolate(limit_direction="both")
        return filled.round().astype(series.dtype) if _is_int(series) else filled
    return series


def null_pattern(series: pd.Series) -> str:
    isna = series.isna().to_numpy()
    n = int(isna.sum())
    if n == 0:
        return ""
    if n == len(isna):
        return "Coluna inteira vazia"
    if isna[:n].all() or isna[-n:].all():
        return "Nulos concentrados no " + ("início" if isna[:n].all() else "fim")
    runs = int((isna[1:] & ~isna[:-1]).sum() + isna[0])
    if n >= 3 and runs == 1:
        return "Nulos em um bloco contínuo"
    return "Nulos distribuídos aleatoriamente"


def treat(df: pd.DataFrame, cfg: dict, types: dict):
    """Tratamento estatístico por coluna: nulos obrigatórios → outliers → imputação → filtros.
    Retorna (df, log, máscara de células imputadas, contagens)."""
    df = df.copy()
    log: list[dict] = []
    columns = cfg.get("columns", {})
    counts = {"imputed": 0, "outliers": 0, "rows_removed": 0}

    required = [c for c in cfg.get("drop_null_rows", []) if c in df.columns]
    if required:
        n = len(df)
        df = df.dropna(subset=required)
        log.append({"column": None, "text": f"{n - len(df)} linha(s) com nulos em {', '.join(required)} removida(s)"})

    remove = pd.Series(False, index=df.index)
    for col in df.columns:
        action = columns.get(col, {}).get("outliers", "manter")
        if types.get(col) != "numérico" or action == "manter" or df[col].dropna().empty:
            continue
        low, high = outlier_bounds(df[col], "IQR", cfg.get("iqr_factor", 1.5))
        is_out = ((df[col] < low) | (df[col] > high)).fillna(False).astype(bool)
        n = int(is_out.sum())
        if not n:
            continue
        counts["outliers"] += n
        if action == "limitar":
            clipped = df[col].astype(float).clip(low, high)
            df[col] = clipped.round().astype(df[col].dtype) if _is_int(df[col]) else clipped
            text = f"{n} outlier(s) limitado(s) ao intervalo {low:.2f} a {high:.2f}"
        elif action == "nulo":
            df[col] = df[col].mask(is_out)
            text = f"{n} outlier(s) trocado(s) por nulo"
        else:
            remove |= is_out
            text = f"{n} linha(s) com outlier marcada(s) para remoção"
        log.append({"column": col, "text": text})
    if remove.any():
        df = df[~remove]
        counts["rows_removed"] += int(remove.sum())

    before_na = df.isna()
    for col in df.columns:
        n_null = int(df[col].isna().sum())
        if not n_null:
            continue
        kind = types.get(col, "texto")
        method = columns.get(col, {}).get("impute") or recommend(df[col], kind, cfg.get("skew_limit", 0.5))[0]
        if method == "preservar":
            continue
        value = fill_value(df[col], method)
        df[col] = impute_column(df[col], method)
        filled = n_null - int(df[col].isna().sum())
        if filled:
            counts["imputed"] += filled
            log.append({"column": col, "text": f"{filled} célula(s) imputada(s) · {method.capitalize()}",
                        "value": format_value(value) if value is not None else ""})
    imputed = before_na & df.notna()

    n = len(df)
    df, l = filter_step(df, [f for f in cfg.get("filters", []) if f["column"] in df.columns])
    log += [{"column": None, "text": t} for t in l]
    counts["rows_removed"] += n - len(df)
    imputed = imputed.loc[df.index]
    return df.reset_index(drop=True), log, imputed.reset_index(drop=True), counts


def format_value(value) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(",").replace(",", "X").replace(".", ",").replace("X", ".") \
            if value != int(value) else f"{int(value):,}".replace(",", ".")
    if isinstance(value, pd.Timestamp):
        return value.strftime("%d/%m/%Y")
    return str(value)


def column_profile(series: pd.Series, kind: str, iqr_factor: float = 1.5) -> dict:
    """Resumo de uma coluna para o card da etapa Tratar."""
    s = series.dropna()
    prof = {"kind": kind, "nulls": int(series.isna().sum()), "total": len(series),
            "unique": int(s.nunique()), "pattern": null_pattern(series)}
    if kind == "numérico" and not s.empty:
        low, high = outlier_bounds(s, "IQR", iqr_factor)
        prof.update(min=float(s.min()), max=float(s.max()), mean=float(s.mean()), median=float(s.median()),
                    std=float(s.std()) if len(s) > 1 else 0.0,
                    kurt=float(s.kurt()) if len(s) > 3 else 0.0,
                    skew=pearson_skewness(s), outliers=int(((s < low) | (s > high)).sum()))
    elif kind == "data" and not s.empty:
        prof.update(min=s.min(), max=s.max())
    elif not s.empty:
        freq = s.astype(str).value_counts()
        p = freq / freq.sum()
        prof.update(top=list(zip(freq.index[:4], (p.iloc[:4] * 100).round().astype(int))),
                    entropy=float(-(p * np.log2(p)).sum()))
    return prof


def skew_label(sk: float) -> str:
    a = abs(sk)
    return "Simétrica" if a < 0.15 else "Assim. leve" if a < 0.5 else "Assim. moder." if a < 1 else "Assim. forte"


def quality(df: pd.DataFrame) -> float:
    return float(df.notna().to_numpy().mean() * 100) if df.size else 100.0


def to_json_bytes(df: pd.DataFrame) -> bytes:
    return df.to_json(orient="records", force_ascii=False, date_format="iso", indent=2).encode("utf-8")


# --------------------------------------------------------------------------- #
# Exportação
# --------------------------------------------------------------------------- #
def to_csv_bytes(df: pd.DataFrame, sep: str = ",") -> bytes:
    return df.to_csv(index=False, sep=sep).encode("utf-8-sig")


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    out = df.copy()
    for col in out.select_dtypes(include=["datetimetz"]).columns:
        out[col] = out[col].dt.tz_localize(None)
    out.to_excel(buffer, index=False, engine="openpyxl")
    return buffer.getvalue()
