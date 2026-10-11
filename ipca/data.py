"""Cache dos dados brutos do SIDRA (CSV em ipca/data/raw) e atualização a partir da API.

Formato do cache (t{tabela}_v{variavel}.csv): 1ª coluna = data "YYYY-MM-DD" (índice "Data"),
demais colunas = código IBGE de 7 dígitos (0 = índice geral), valores como vieram do SIDRA.
"""
import logging
import os
from pathlib import Path

import pandas as pd

from common import sidra
from . import config

log = logging.getLogger(__name__)


def _dir(raw_dir):
    return Path(raw_dir) if raw_dir is not None else config.RAW_DIR


def caminho(chave, raw_dir=None):
    """Arquivo do cache de uma tabela (chave como "t7060_v63")."""
    return _dir(raw_dir) / f"{chave}.csv"


def ler_csv(path):
    """Lê uma matriz do cache (colunas voltam a ser códigos inteiros)."""
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.columns = [int(c) for c in df.columns]
    return df


def gravar_csv(df, path):
    """Grava uma matriz no cache; escreve num temporário e troca no fim (o cache antigo fica intacto se cair)."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    df = df.copy(); df.index = pd.to_datetime(df.index); df.index.name = "Data"
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(tmp, date_format="%Y-%m-%d", lineterminator="\n")
    os.replace(tmp, path)


def load_raw(raw_dir=None):
    """Lê o cache: {"t7060_v63": DataFrame, ...} (só as tabelas que existem em disco)."""
    out = {}
    for chave in config.TABELAS:
        p = caminho(chave, raw_dir)
        if p.exists(): out[chave] = ler_csv(p)
    if not out: raise FileNotFoundError(f"cache vazio em {_dir(raw_dir)}")
    return out


def mescla(velho, novo):
    """Junta os meses novos ao cache: as linhas do cache nos meses baixados são substituídas."""
    return pd.concat([velho[~velho.index.isin(novo.index)], novo]).sort_index()


def atualiza_tabela(chave, raw_dir=None, baixar=None):
    """Atualiza uma tabela do cache: últimos 3 meses sobre o cache ou, sem cache/se falhar, tudo de novo."""
    baixar = baixar or sidra.baixar_sidra
    tabela, variavel, decimais = config.TABELAS[chave]
    p = caminho(chave, raw_dir)
    if p.exists():
        try:
            velho = ler_csv(p)
            novo = baixar(tabela, variavel, decimais, config.PERIODOS_RAPIDO)
            df = mescla(velho, novo)
            gravar_csv(df, p)
            log.info("%s: últimos meses (%s) sobre o cache", chave, ", ".join(f"{d:%Y-%m}" for d in novo.index))
            return df
        except Exception as e:
            log.warning("%s: falha no rápido (%s), baixando tudo", chave, e)
    df = baixar(tabela, variavel, decimais, "all")
    gravar_csv(df, p)
    log.info("%s: série completa (%s a %s)", chave, f"{df.index.min():%Y-%m}", f"{df.index.max():%Y-%m}")
    return df


def update_raw(raw_dir=None, baixar=None):
    """Atualiza as 8 tabelas do cache e devolve o cache relido (mesmo formato de load_raw).

    baixar: função (tabela, variavel, decimais, periodos) -> matriz; padrão common.sidra.baixar_sidra.
    """
    for chave in config.TABELAS:
        atualiza_tabela(chave, raw_dir, baixar)
    return load_raw(raw_dir)


def latest_available_month():
    """Último mês publicado no SIDRA ("YYYY-MM"), com uma consulta pequena (índice geral, último período)."""
    tabela, variavel, decimais = config.TABELAS[config.TABELA_REF]
    m = sidra.baixar_sidra(tabela, variavel, decimais, periodos="last 1", categorias=sidra.COD_GERAL_C315)
    s = m[0].dropna() if 0 in m.columns else m.dropna(how="all")
    return f"{s.index.max():%Y-%m}"


def cached_month(raw_dir=None):
    """Último mês do cache ("YYYY-MM", índice geral da tabela 7060) ou None se não houver cache."""
    p = caminho(config.TABELA_REF, raw_dir)
    if not p.exists(): return None
    df = ler_csv(p)
    s = df[0].dropna() if 0 in df.columns else df.dropna(how="all")
    return f"{s.index.max():%Y-%m}" if len(s) else None
