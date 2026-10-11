"""Cliente do SIDRA (IBGE): baixa uma variável de uma tabela mensal e devolve a matriz data x código.

A matriz tem índice = primeiro dia do mês (Timestamp, nome "Data") e colunas = código IBGE
canônico de 7 dígitos (0 = índice geral), como no notebook original.
"""
import logging
import re

import pandas as pd
import requests

log = logging.getLogger(__name__)

URL_BASE = "https://apisidra.ibge.gov.br/values"
TIMEOUT = 180

# Coluna com o nome da categoria na classificação c315 (IPCA)
COL_C315 = "Geral, grupo, subgrupo, item e subitem"
# Categoria "Índice geral" na c315
COD_GERAL_C315 = 7169

MESES_PARSE = {"janeiro":1,"fevereiro":2,"março":3,"abril":4,"maio":5,"junho":6,
               "julho":7,"agosto":8,"setembro":9,"outubro":10,"novembro":11,"dezembro":12}


def url_sidra(tabela, variavel, decimais=2, periodos="all", classificacao="c315", categorias="all"):
    """URL da API (mesmo formato do notebook: n1/all, p/<periodos>, <classificação>/<categorias>, d/v<var> <dec>)."""
    return (f"{URL_BASE}/t/{tabela}/n1/all/v/{variavel}"
            f"/p/{periodos}/{classificacao}/{categorias}/d/v{variavel}%20{decimais}").replace(" ", "%20")


def parse_mes(s):
    """'setembro 2026' -> Timestamp(2026-09-01); NaT se não reconhecer."""
    try:
        p = s.strip().split(" ")
        return pd.Timestamp(year=int(p[1]), month=MESES_PARSE[p[0].lower()], day=1)
    except Exception:
        return pd.NaT


def canon(cod):
    """Código no formato de 7 dígitos (1 -> 1000000, 11 -> 1100000, 1101 -> 1101000)."""
    if cod == 0: return 0
    d_len = len(str(cod))
    return {1:cod*1000000, 2:cod*100000, 4:cod*1000, 7:cod}.get(d_len, cod)


def cod_do_nome(nome):
    """'1101.Cereais, leguminosas e oleaginosas' -> 1101000; 'Índice geral' -> 0; senão None."""
    s = str(nome).strip()
    m = re.match(r"^\s*([\d\.]+?)\.\D", s) or re.match(r"^\s*([\d\.]+)\.?$", s)
    if m:
        try: return canon(int(m.group(1).replace(".", "")))
        except Exception: pass
    return 0 if "geral" in s.lower() else None


def matriz(dados, col_nome=COL_C315):
    """Resposta JSON do SIDRA (lista, 1ª linha = cabeçalho) -> matriz data x código."""
    if not isinstance(dados, list) or len(dados) < 2: raise ValueError("resposta vazia")
    cab = dados[0]; df = pd.DataFrame(dados[1:]); df.columns = [cab.get(c,c) for c in df.columns]
    out = pd.DataFrame({
        "Data":  df["Mês"].apply(parse_mes),
        "cod":   df[col_nome].apply(cod_do_nome),
        "valor": pd.to_numeric(df["Valor"], errors="coerce"),
    }).dropna(subset=["Data","cod"])
    out["cod"] = out["cod"].astype(int)
    mat = out.pivot_table(index="Data", columns="cod", values="valor").sort_index()
    mat.index = pd.to_datetime(mat.index)
    return mat


def baixar_sidra(tabela, variavel, decimais=2, periodos="all", classificacao="c315", categorias="all",
                 col_nome=COL_C315, timeout=TIMEOUT, sessao=None):
    """Baixa a variável da tabela e devolve a matriz data x código.

    periodos: "all", "last 3" (ou "last%203"), "202401-202609" etc.
    """
    url = url_sidra(tabela, variavel, decimais, periodos, classificacao, categorias)
    log.debug("SIDRA: %s", url)
    r = (sessao or requests).get(url, timeout=timeout); r.raise_for_status()
    return matriz(r.json(), col_nome)
