"""Cálculos do IPCA: quebras pelos vetores oficiais, núcleos, difusão, métricas e contribuições.

Funções puras (nada roda na importação). compute(raw) recebe o cache de data.load_raw/update_raw.
"""
import logging
import warnings

import numpy as np
import pandas as pd

from . import config
from .vetores import ITENS_SUAV_MS, QUEBRAS, REGIMES, GRUPOS, NUCLEOS_BC, NUCLEOS_GRAF, vetor_do_mes

log = logging.getLogger(__name__)


# ═══ DADOS ══════════════════════════════════════════════════════════════════
def emenda(velha, nova, corte):
    """Tabela antiga antes do corte (1º mês da nova) + tabela nova; colunas repetidas ficam com a 1ª."""
    df = pd.concat([velha[velha.index < corte], nova]).sort_index()
    df = df.loc[:, ~df.columns.duplicated()]
    df.index = pd.to_datetime(df.index)
    return df


def prepara(raw, ano_inicio=config.ANO_INICIO):
    """Cache -> (mom, peso, mom_sa, peso_sa), emendando 1419/7060 e 1420/7061, de ano_inicio em diante."""
    vazio = pd.DataFrame()
    mom_nova, peso_novo = raw["t7060_v63"], raw["t7060_v66"]
    mom_velha, peso_velho = raw["t1419_v63"], raw["t1419_v66"]
    sa_m_n, sa_p_n = raw.get("t7061_v306", vazio), raw.get("t7061_v309", vazio)
    sa_m_v, sa_p_v = raw.get("t1420_v306", vazio), raw.get("t1420_v309", vazio)

    corte = mom_nova.index.min()
    mom  = emenda(mom_velha, mom_nova, corte)
    peso = emenda(peso_velho, peso_novo, corte)

    if not sa_m_n.empty:
        c2 = sa_m_n.index.min()
        mom_sa  = pd.concat([sa_m_v[sa_m_v.index < c2], sa_m_n]).sort_index() if not sa_m_v.empty else sa_m_n
        peso_sa = pd.concat([sa_p_v[sa_p_v.index < c2], sa_p_n]).sort_index() if not sa_p_v.empty else sa_p_n
        mom_sa  = mom_sa.loc[:, ~mom_sa.columns.duplicated()];  mom_sa.index  = pd.to_datetime(mom_sa.index)
        peso_sa = peso_sa.loc[:, ~peso_sa.columns.duplicated()]; peso_sa.index = pd.to_datetime(peso_sa.index)
    else:
        mom_sa, peso_sa = (sa_m_v, sa_p_v) if not sa_m_v.empty else (pd.DataFrame(), pd.DataFrame())

    mom = mom[mom.index.year >= ano_inicio]
    peso = peso[peso.index.year >= ano_inicio]
    if not mom_sa.empty:
        mom_sa = mom_sa[mom_sa.index.year >= ano_inicio]
        peso_sa = peso_sa[peso_sa.index.year >= ano_inicio]
    return mom, peso, mom_sa, peso_sa


# ═══ QUEBRAS E NÚCLEOS ══════════════════════════════════════════════════════
def agrega(mom_df, peso_df, quebra):
    """Média ponderada dos componentes do vetor da quebra (vetor do período de cada mês)."""
    out = {}
    datas = mom_df.index.intersection(peso_df.index)
    for dt in datas:
        cods = vetor_do_mes(dt)[quebra]
        cc = [c for c in cods if c in mom_df.columns and c in peso_df.columns]
        if not cc: continue
        m = mom_df.loc[dt, cc]; p = peso_df.loc[dt, cc]
        mask = m.notna() & p.notna()
        den = p[mask].sum()
        if den > 0: out[dt] = float((m[mask]*p[mask]).sum()/den)
    s = pd.Series(out)
    if len(s): s.index = pd.to_datetime(s.index); s = s.sort_index()
    return s


def _itens(mom_df): return [c for c in mom_df.columns if c != 0 and c % 1000 == 0 and (c // 1000) % 100 != 0]
def _subitens(mom_df): return [c for c in mom_df.columns if c != 0 and c % 1000 != 0]


def _aparada(vd, pdd, inf=20.0, sup=80.0):
    """Média aparada ponderada (corta abaixo de inf% e acima de sup% do peso acumulado)."""
    pares = [(vd[c],pdd[c]) for c in vd if c in pdd and pd.notna(vd[c]) and pd.notna(pdd[c])]
    if not pares: return np.nan
    pares.sort(key=lambda x:x[0]); sp = sum(p for _,p in pares)
    if sp == 0: return np.nan
    pn = [p/sp*100 for _,p in pares]; vs = [v for v,_ in pares]
    acum, a = [], 0.0
    for p in pn: a += p; acum.append(a)
    paj = []
    for k in range(len(pn)):
        apre = acum[k]-pn[k]; ac = acum[k]
        if   ac<=inf: paj.append(0.0)
        elif apre>=sup: paj.append(0.0)
        elif apre<inf and ac>inf: paj.append(ac-inf)
        elif ac>sup and apre<sup: paj.append(sup-apre)
        else: paj.append(pn[k])
    s = sum(paj)
    return sum(p*v for p,v in zip(paj,vs))/s if s else np.nan


def nucleo_MA(mom_df, peso_df):
    """Médias aparadas sem suavização (itens)."""
    cods = [c for c in _itens(mom_df) if c in peso_df.columns]
    return pd.Series({dt:_aparada({c:mom_df.at[dt,c] for c in cods}, {c:peso_df.at[dt,c] for c in cods}) for dt in mom_df.index}).dropna()


def nucleo_MS(mom_df, peso_df):
    """Médias aparadas com suavização (itens de ITENS_SUAV_MS em média geométrica de 12 meses)."""
    cods = [c for c in _itens(mom_df) if c in peso_df.columns]
    mom_s = mom_df[cods].copy()
    for c in cods:
        if (c//1000) in ITENS_SUAV_MS:
            f = (1 + mom_df[c]/100)
            mom_s[c] = (f.rolling(12).apply(np.prod, raw=True)**(1/12) - 1)*100
    return pd.Series({dt:_aparada({c:mom_s.at[dt,c] for c in cods}, {c:peso_df.at[dt,c] for c in cods}) for dt in mom_s.index}).dropna()


def nucleo_DP(mom_df, peso_df, janela=48):
    """Dupla ponderação: peso / volatilidade (desvio-padrão de 48 meses da diferença para o cheio, defasado)."""
    cods = [c for c in _itens(mom_df) if c in peso_df.columns]
    ipca = mom_df[0] if 0 in mom_df.columns else mom_df[cods].mul(peso_df[cods]).sum(axis=1)/peso_df[cods].sum(axis=1)
    difs = mom_df[cods].sub(ipca, axis=0)
    vol  = difs.rolling(janela).std().shift(1)
    out = {}
    for dt in mom_df.index:
        if dt not in vol.index or vol.loc[dt].isna().all(): continue
        p = peso_df.loc[dt, cods]; m = mom_df.loc[dt, cods]
        w = (p/vol.loc[dt]).replace([np.inf,-np.inf], np.nan)
        mask = w.notna() & m.notna()
        if mask.sum()==0: continue
        wn = w[mask]/w[mask].sum()
        out[dt] = float((wn*m[mask]).sum())
    return pd.Series(out).dropna()


def nucleo_P55(mom_df, peso_df):
    """Percentil 55 ponderado dos subitens."""
    cods = [c for c in _subitens(mom_df) if c in peso_df.columns]
    out = {}
    for dt in mom_df.index:
        pares = [(mom_df.at[dt,c],peso_df.at[dt,c]) for c in cods if pd.notna(mom_df.at[dt,c]) and pd.notna(peso_df.at[dt,c])]
        if not pares: continue
        pares.sort(key=lambda x:x[0]); sp = sum(p for _,p in pares); a=0; val=pares[-1][0]
        for v,p in pares:
            a += p
            if a/sp*100 >= 55: val=v; break
        out[dt] = val
    return pd.Series(out).dropna()


def difusao(mom_df):
    """% dos subitens com variação positiva no mês."""
    cods = _subitens(mom_df)
    out = {}
    for dt in mom_df.index:
        vals = [mom_df.at[dt,c] for c in cods if pd.notna(mom_df.at[dt,c])]
        if vals: out[dt] = sum(1 for v in vals if v>0)/len(vals)*100
    return pd.Series(out).dropna()


def construir(mom_df, peso_df, com_nucleos=True):
    """Variação mensal de todas as séries: cheio, 28 quebras, núcleos MA/MS/DP/P55, difusão e média dos núcleos."""
    out = {}
    if 0 in mom_df.columns: out["IPCA cheio"] = mom_df[0].dropna()
    for q in QUEBRAS:
        s = agrega(mom_df, peso_df, q)
        if len(s): out[q] = s
    if com_nucleos:
        log.info("núcleos...")
        out["Núcleo MA"]  = nucleo_MA(mom_df, peso_df)
        out["Núcleo MS"]  = nucleo_MS(mom_df, peso_df)
        out["Núcleo DP"]  = nucleo_DP(mom_df, peso_df)
        out["Núcleo P55"] = nucleo_P55(mom_df, peso_df)
        out["Difusão"]    = difusao(mom_df)

    nucs_disp = [k for k in NUCLEOS_BC if k in out]
    if nucs_disp:
        out["Média dos Núcleos"] = pd.DataFrame({k: out[k] for k in nucs_disp}).mean(axis=1)
    return out


# ═══ MÉTRICAS ═══════════════════════════════════════════════════════════════
def reconstruir_indice(s):
    """Número-índice (base 100 no 1º mês) a partir da variação mensal."""
    s = s.dropna()
    if len(s) == 0: return pd.Series(dtype=float)
    s = s.copy(); s.index = pd.to_datetime(s.index); s = s.sort_index()
    f = (1 + s/100)
    return 100.0 * f.cumprod() / f.iloc[0]


def metricas(serie_dict_nsa, serie_dict_sa, nivel_set=None):
    """MoM, YoY (índice encadeado), MM3M, MM3M SA e SAAR; séries de nível: MM3M = média de 12 meses."""
    nivel_set = nivel_set or set()
    mom_ = pd.DataFrame(serie_dict_nsa); mom_.index = pd.to_datetime(mom_.index); mom_ = mom_.sort_index()
    mom_sa_df = pd.DataFrame(serie_dict_sa) if serie_dict_sa else pd.DataFrame()
    if not mom_sa_df.empty:
        mom_sa_df.index = pd.to_datetime(mom_sa_df.index); mom_sa_df = mom_sa_df.sort_index()

    vars_ = [n for n in mom_.columns if n not in nivel_set]

    idx = pd.DataFrame({n: reconstruir_indice(mom_[n]) for n in vars_})
    idx.index = pd.to_datetime(idx.index); idx = idx.sort_index()
    yoy = (idx/idx.shift(12) - 1)*100

    mm3m = mom_[vars_].rolling(3).mean()

    mm3m_sa = pd.DataFrame(index=mom_.index, columns=vars_, dtype=float)
    saar    = pd.DataFrame(index=mom_.index, columns=vars_, dtype=float)
    if not mom_sa_df.empty:
        for n in vars_:
            if n in mom_sa_df.columns:
                s_sa = mom_sa_df[n].rolling(3).mean().reindex(mom_.index)
                mm3m_sa[n] = s_sa
                saar[n]    = ((1 + s_sa/100)**12 - 1) * 100

    for n in nivel_set:
        if n in mom_.columns:
            mm3m[n] = mom_[n].rolling(12).mean()
            yoy[n] = np.nan; saar[n] = np.nan; mm3m_sa[n] = np.nan

    return {"mom":mom_, "yoy":yoy, "mm3m":mm3m, "mm3m_sa":mm3m_sa, "saar":saar}


def _filtra(d, ano=config.CHART_START):
    d = d.copy(); d.index = pd.to_datetime(d.index); return d[d.index.year >= ano]


def _no_mes(s, dt):
    """Valor no mês de referência (não pega valor velho se a série parou antes)."""
    return float(s.get(dt, np.nan)) if s is not None else np.nan


def peso_quebra(q, peso, dt):
    """Peso da quebra no mês (soma dos pesos do vetor); NaN para núcleos que não são recortes."""
    if q == "IPCA cheio": return 100.0
    if q not in vetor_do_mes(dt) or dt not in peso.index: return np.nan
    cc = [c for c in vetor_do_mes(dt)[q] if c in peso.columns]
    v = peso.loc[dt, cc].sum()
    return float(v) if v > 0 else np.nan


def tabela_resumo(met, ordem, peso, ult):
    """Peso, MoM, MM3M, YoY, MM3M SA e MM3M SAAR no mês de referência."""
    return pd.DataFrame({
        "Peso":      [peso_quebra(l, peso, ult)    for l in ordem],
        "MoM":       [_no_mes(met["mom"][l], ult)     for l in ordem],
        "MM3M":      [_no_mes(met["mm3m"][l], ult)    for l in ordem],
        "YoY":       [_no_mes(met["yoy"][l], ult)     for l in ordem],
        "MM3M SA":   [_no_mes(met["mm3m_sa"][l], ult) for l in ordem],
        "MM3M SAAR": [_no_mes(met["saar"][l], ult)    for l in ordem],
    }, index=ordem)


# ═══ CONTRIBUIÇÕES (p.p.) ═══════════════════════════════════════════════════
# contribuição no mês = soma(variação x peso)/100 dos componentes do vetor da quebra.
# contribuição em 12 meses (exata): soma_k [I(k-1)/I(t-12)] x contrib(k), com I = índice do IPCA cheio,
# assim as contribuições somam o YoY do cheio (a menos de arredondamento dos pesos).
def contrib(mom_df, peso_df, quebra):
    out = {}
    for dt in mom_df.index.intersection(peso_df.index):
        cc = [c for c in vetor_do_mes(dt)[quebra] if c in mom_df.columns and c in peso_df.columns]
        if not cc: continue
        m = mom_df.loc[dt, cc]; p = peso_df.loc[dt, cc]; mask = m.notna() & p.notna()
        if mask.any(): out[dt] = float((m[mask]*p[mask]).sum()/100)
    s = pd.Series(out, dtype=float); s.index = pd.to_datetime(s.index)
    return s.sort_index()


def contribuicoes(mom, peso, series_nsa):
    """(cont_mom, cont_12m, ipca_mom, ipca_12m) para regimes e grupos."""
    cont_mom = pd.DataFrame({q: contrib(mom, peso, q) for q in REGIMES + GRUPOS}).sort_index()
    ipca_mom = mom[0].dropna() if 0 in mom.columns else series_nsa["IPCA cheio"]
    cont_mom = cont_mom.reindex(ipca_mom.index)

    _I = (1 + ipca_mom/100).cumprod()
    cont_12m = cont_mom.mul(_I.shift(1), axis=0).rolling(12).sum().div(_I.shift(12), axis=0)
    ipca_12m = (_I/_I.shift(12) - 1)*100
    return cont_mom, cont_12m, ipca_mom, ipca_12m


# ═══ TUDO ═══════════════════════════════════════════════════════════════════
def compute(raw):
    """Roda todos os cálculos sobre o cache e devolve um dicionário com os resultados.

    Chaves: mom, peso, mom_sa, peso_sa (matrizes emendadas), series_nsa, series_sa (dict série -> MoM),
    met (mom/mm3m/yoy/mm3m_sa/saar de CHART_START em diante), ordem, ult (mês de referência),
    resumo, cont_mom, cont_12m, ipca_mom, ipca_12m, res_reg, res_gru (resíduo máx. das contribuições),
    nucleos_graf, QUEBRAS, REGIMES, GRUPOS.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mom, peso, mom_sa, peso_sa = prepara(raw)
        log.info("NSA: %s a %s", f"{mom.index.min():%Y-%m}", f"{mom.index.max():%Y-%m}")

        series_nsa = construir(mom, peso, True)
        series_sa = construir(mom_sa, peso_sa, True) if not mom_sa.empty else {}

        met = metricas(series_nsa, series_sa if series_sa else None, nivel_set=set(config.SERIES_NIVEL))
        for k in met: met[k] = _filtra(met[k])

        ordem = ["IPCA cheio"] + QUEBRAS + ["Núcleo MA","Núcleo MS","Núcleo DP","Núcleo P55", "Média dos Núcleos", "Difusão"]
        ordem = [l for l in ordem if l in met["mom"].columns]

        ult = met["mom"]["IPCA cheio"].dropna().index[-1] if "IPCA cheio" in met["mom"] else met["mom"].dropna(how="all").index[-1]
        resumo = tabela_resumo(met, ordem, peso, ult)

        cont_mom, cont_12m, ipca_mom, ipca_12m = contribuicoes(mom, peso, series_nsa)
        res_reg = (ipca_mom - cont_mom[REGIMES].sum(axis=1)).abs().max()
        res_gru = (ipca_mom - cont_mom[GRUPOS].sum(axis=1)).abs().max()
        log.info("Contribuições: resíduo máx. regimes %.3f p.p. | grupos %.3f p.p.", res_reg, res_gru)

        nucs = [n for n in NUCLEOS_GRAF if n in met["yoy"].columns]

    return {
        "mom": mom, "peso": peso, "mom_sa": mom_sa, "peso_sa": peso_sa,
        "series_nsa": series_nsa, "series_sa": series_sa, "met": met, "ordem": ordem, "ult": ult,
        "resumo": resumo, "cont_mom": cont_mom, "cont_12m": cont_12m, "ipca_mom": ipca_mom, "ipca_12m": ipca_12m,
        "res_reg": float(res_reg), "res_gru": float(res_gru), "nucleos_graf": nucs,
        "QUEBRAS": list(QUEBRAS), "REGIMES": list(REGIMES), "GRUPOS": list(GRUPOS),
    }
