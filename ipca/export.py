"""Contrato de saída (ipca/output/data): o que os geradores de HTML e README leem.

Arquivos:
- meta.json: mês de referência, ordem das séries, quebras, regimes, grupos, pesos, destaques etc.
- mom.csv, mm3m.csv, yoy.csv, mm3m_sa.csv, saar.csv: coluna "data" ("YYYY-MM") e uma coluna por série
  (na ordem de meta["order"]), de CHART_START até o mês de referência; célula vazia = sem valor.
  Difusão: mom = % dos subitens com alta; mm3m = média de 12 meses.
- resumo.csv: coluna "serie" e Peso, MoM, MM3M, YoY, MM3M SA, MM3M SAAR no mês de referência.
- contrib_mom.csv / contrib_12m.csv: "data", "IPCA" (MoM ou YoY do cheio, %), 4 regimes e 9 grupos (p.p.).
Números com 6 casas ("%.6f").
"""
import json
import math
from pathlib import Path

import pandas as pd

from . import config
from .vetores import NUCLEOS_GRAF

FF = "%.6f"
METRICAS = ["mom", "mm3m", "yoy", "mm3m_sa", "saar"]
ARQUIVOS = [f"{k}.csv" for k in METRICAS] + ["resumo.csv", "contrib_mom.csv", "contrib_12m.csv", "meta.json"]


def _dir(out_dir):
    return Path(out_dir) if out_dir is not None else config.CONTRACT_DIR


def _ym(df):
    df = df.copy(); df.index = pd.to_datetime(df.index).strftime("%Y-%m"); df.index.name = "data"; return df


def _csv(df, path):
    df.to_csv(path, float_format=FF, lineterminator="\n", encoding="utf-8")


def meta(results):
    """Dicionário do meta.json a partir dos resultados de calc.compute."""
    ult, met = results["ult"], results["met"]
    nucs = [n for n in NUCLEOS_GRAF if n in met["yoy"].columns]
    pesos = {k: (None if not math.isfinite(v) else round(float(v), 6)) for k, v in results["resumo"]["Peso"].items()}
    return {
        "chartbook": "IPCA",
        "reference_month": ult.strftime("%Y-%m"),
        "reference_label": config.rotulo_mes(ult),
        "source": config.FONTE,
        "order": list(results["ordem"]),
        "breaks": list(results["QUEBRAS"]),
        "cores_chart": nucs,
        "regimes": list(results["REGIMES"]),
        "groups": list(results["GRUPOS"]),
        "weights": pesos,
        "highlight": list(config.DESTAQUE),
        "level_series": list(config.SERIES_NIVEL),
        "start": {"lines": config.CHART_START, "bars": config.BAR_START, "contrib_month": config.CONTRIB_START,
                  "contrib_12m": config.CONTRIB12_START, "heat_months": config.HEAT_MESES},
        "contrib_residual_pp": {"regimes": round(float(results["res_reg"]), 6),
                                "groups": round(float(results["res_gru"]), 6)},
    }


def write_contract(results, out_dir=None):
    """Grava o contrato a partir de calc.compute(raw). Devolve a pasta."""
    out = _dir(out_dir); out.mkdir(parents=True, exist_ok=True)
    met, ordem = results["met"], results["ordem"]
    reg, gru = results["REGIMES"], results["GRUPOS"]
    for k in METRICAS:
        _csv(_ym(met[k][ordem]), out / f"{k}.csv")
    r = results["resumo"].copy(); r.index.name = "serie"; _csv(r, out / "resumo.csv")
    cm = results["cont_mom"][reg + gru].copy(); cm.insert(0, "IPCA", results["ipca_mom"].reindex(cm.index))
    c12 = results["cont_12m"][reg + gru].copy(); c12.insert(0, "IPCA", results["ipca_12m"].reindex(c12.index))
    _csv(_ym(cm), out / "contrib_mom.csv")
    _csv(_ym(c12), out / "contrib_12m.csv")
    with open(out / "meta.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta(results), f, ensure_ascii=False, indent=2)
    return out


def read_contract(out_dir=None, datas="timestamp"):
    """Lê o contrato.

    Devolve {"meta": dict, "mom", "mm3m", "yoy", "mm3m_sa", "saar", "contrib_mom", "contrib_12m": DataFrame
    com índice "data" = Timestamp do 1º dia do mês (DatetimeIndex; com datas="str", texto "YYYY-MM"),
    colunas na ordem do arquivo, células vazias = NaN; "resumo": DataFrame com índice "serie"}.
    """
    d = _dir(out_dir)
    with open(d / "meta.json", encoding="utf-8") as f:
        out = {"meta": json.load(f)}
    for k in METRICAS + ["contrib_mom", "contrib_12m"]:
        df = pd.read_csv(d / f"{k}.csv", index_col="data", dtype={"data": str}, encoding="utf-8")
        if datas != "str":
            df.index = pd.DatetimeIndex(pd.to_datetime(df.index, format="%Y-%m"), name="data")
        out[k] = df.astype(float)
    out["resumo"] = pd.read_csv(d / "resumo.csv", index_col="serie", encoding="utf-8").astype(float)
    return out
