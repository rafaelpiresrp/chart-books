"""Testes do chartbook do IPCA sobre o cache real (ipca/data/raw), sem acesso à rede.

Rodam com pytest ou direto: python tests/test_ipca.py
"""
import functools
import logging
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path: sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common import sidra  # noqa: E402
from ipca import calc, config, data, export  # noqa: E402

TOL_PP = 0.01      # contribuições do mês: resíduo só do arredondamento dos pesos (4 casas)
TOL_PP_12M = 0.05  # em 12 meses o resíduo é a soma (encadeada) de 12 resíduos mensais


@functools.lru_cache(maxsize=None)
def _res():
    """Cálculos sobre o cache real (uma vez só)."""
    return calc.compute(data.load_raw())


def _baixador_falso(raw, falha_rapido=False):
    """Simula o SIDRA a partir do cache: "last 3" devolve os 3 últimos meses, "all" devolve tudo."""
    chamadas = []
    por_tabela = {config.TABELAS[k][:2]: df for k, df in raw.items()}

    def baixar(tabela, variavel, decimais, periodos):
        chamadas.append((tabela, variavel, decimais, periodos))
        df = por_tabela[(tabela, variavel)]
        if periodos == "all": return df.copy()
        if falha_rapido: raise ConnectionError("simulado")
        n = int(str(periodos).replace("%20", " ").split()[-1])
        return df.iloc[-n:].copy()

    return baixar, chamadas


# ─── cache ──────────────────────────────────────────────────────────────────
def test_cache_formato():
    raw = data.load_raw()
    assert set(raw) == set(config.TABELAS), sorted(raw)
    for k, df in raw.items():
        assert isinstance(df.index, pd.DatetimeIndex), k
        assert (df.index.day == 1).all() and df.index.is_monotonic_increasing and df.index.is_unique, k
        assert all(isinstance(c, int) for c in df.columns), k
        assert 0 in df.columns, k
    assert data.cached_month() == f"{_res()['ult']:%Y-%m}"


def test_sidra_url_e_parse():
    url = sidra.url_sidra(7060, 63, 2, "last 3")
    assert url == "https://apisidra.ibge.gov.br/values/t/7060/n1/all/v/63/p/last%203/c315/all/d/v63%202", url
    cab = {"V": "Valor", "D3N": "Mês", "D4N": sidra.COL_C315}
    linhas = [("setembro 2026", "Índice geral", "0.82"), ("setembro 2026", "1.Alimentação e bebidas", "1.10"),
              ("setembro 2026", "11.Alimentação no domicílio", "1.20"), ("setembro 2026", "1101.Cereais", "-0.50"),
              ("setembro 2026", "1101002.Arroz", "-1.00"), ("agosto 2026", "1101002.Arroz", "..."),
              ("agosto 2026", "Índice geral", "0.10"), ("mês inválido", "Índice geral", "9")]
    m = sidra.matriz([cab] + [{"D3N": a, "D4N": b, "V": c} for a, b, c in linhas])
    assert list(m.columns) == [0, 1000000, 1100000, 1101000, 1101002], list(m.columns)
    assert list(m.index) == [pd.Timestamp(2026, 8, 1), pd.Timestamp(2026, 9, 1)]
    assert m.at[pd.Timestamp(2026, 9, 1), 1101002] == -1.0 and np.isnan(m.at[pd.Timestamp(2026, 8, 1), 1101002])
    try:
        sidra.matriz([cab]); assert False, "resposta vazia deveria falhar"
    except ValueError:
        pass


# ─── atualização incremental ────────────────────────────────────────────────
def test_mescla_substitui_meses_baixados():
    idx = pd.to_datetime(["2026-06-01", "2026-07-01", "2026-08-01"])
    velho = pd.DataFrame({0: [0.1, 0.2, 0.3], 1000000: [1.0, 2.0, 3.0]}, index=idx)
    novo = pd.DataFrame({0: [0.25, 0.35, 0.45], 2000000: [5.0, 6.0, 7.0]},
                        index=pd.to_datetime(["2026-07-01", "2026-08-01", "2026-09-01"]))
    m = data.mescla(velho, novo)
    assert list(m.index) == list(idx) + [pd.Timestamp(2026, 9, 1)]
    assert list(m[0]) == [0.1, 0.25, 0.35, 0.45]
    assert m.at[idx[0], 1000000] == 1.0 and m.loc[idx[1]:, 1000000].isna().all()
    assert np.isnan(m.at[idx[0], 2000000]) and m.at[pd.Timestamp(2026, 9, 1), 2000000] == 7.0


def test_update_raw_ultimos_3_meses_sobre_o_cache():
    orig = data.load_raw()
    baixar, chamadas = _baixador_falso(orig)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for k, df in orig.items():
            # cache defasado: sem o último mês e com os 2 anteriores errados (devem ser trocados)
            velho = df.iloc[:-1].copy(); velho.iloc[-2:] = velho.iloc[-2:] + 1.0
            data.gravar_csv(velho, data.caminho(k, tmp))
        novo = data.update_raw(tmp, baixar=baixar)
        assert [c[3] for c in chamadas] == [config.PERIODOS_RAPIDO] * len(config.TABELAS), chamadas
        for k, df in orig.items():
            pd.testing.assert_frame_equal(novo[k], df, check_freq=False)
            assert data.caminho(k, tmp).read_bytes() == data.caminho(k).read_bytes(), k
        assert not list(tmp.glob("*.tmp"))
        assert data.cached_month(tmp) == data.cached_month()


def test_update_raw_baixa_tudo_se_falhar_ou_sem_cache():
    orig = data.load_raw()
    baixar, chamadas = _baixador_falso(orig, falha_rapido=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        k0 = config.TABELA_REF
        shutil.copy(data.caminho(k0), data.caminho(k0, tmp))   # só uma tabela em cache
        lg = logging.getLogger(data.__name__); nivel = lg.level; lg.setLevel(logging.ERROR)  # falha esperada
        try:
            novo = data.update_raw(tmp, baixar=baixar)
        finally:
            lg.setLevel(nivel)
        pers = [c[3] for c in chamadas]
        assert pers.count(config.PERIODOS_RAPIDO) == 1 and pers.count("all") == len(config.TABELAS), pers
        for k, df in orig.items():
            pd.testing.assert_frame_equal(novo[k], df, check_freq=False)


# ─── cálculos ───────────────────────────────────────────────────────────────
def test_contribuicoes_somam_o_cheio():
    r = _res()
    for nome in ("REGIMES", "GRUPOS"):
        soma = r["cont_mom"][r[nome]].sum(axis=1)
        assert (r["ipca_mom"] - soma).abs().max() < TOL_PP, nome
        soma12 = r["cont_12m"][r[nome]].sum(axis=1)
        d12 = (r["ipca_12m"] - soma12).dropna()
        assert len(d12) > 100 and d12.abs().max() < TOL_PP_12M, (nome, d12.abs().max())
    assert r["res_reg"] < TOL_PP and r["res_gru"] < TOL_PP


def test_yoy_igual_a_variacao_encadeada_em_12_meses():
    r = _res(); met = r["met"]
    assert np.allclose(met["yoy"]["IPCA cheio"].dropna(), r["ipca_12m"].reindex(met["yoy"].index).dropna(),
                       rtol=0, atol=1e-9)
    nivel = set(config.SERIES_NIVEL)
    for s in r["ordem"]:
        if s in nivel: continue
        enc = ((1 + met["mom"][s] / 100).rolling(12).apply(np.prod, raw=True) - 1) * 100
        d = (met["yoy"][s] - enc).dropna()
        assert len(d) > 100 and d.abs().max() < 1e-8, (s, d.abs().max())
        assert np.isfinite(r["resumo"].at[s, "YoY"]), s


def test_pesos_dos_regimes_e_grupos_somam_100():
    r = _res(); peso = r["resumo"]["Peso"]
    assert abs(peso[r["REGIMES"]].sum() - 100) < 0.05, peso[r["REGIMES"]].sum()
    assert abs(peso[r["GRUPOS"]].sum() - 100) < 0.05, peso[r["GRUPOS"]].sum()
    assert abs(peso["Livres"] + peso["Administrados"] - 100) < 0.05
    assert peso["IPCA cheio"] == 100.0 and peso[["Núcleo MA", "Difusão"]].isna().all()


def test_resumo_e_series_de_nivel():
    r = _res(); met = r["met"]; ult = r["ult"]
    assert r["ordem"][0] == "IPCA cheio" and r["ordem"][-1] == "Difusão" and len(r["ordem"]) == 35
    for s in r["ordem"]:
        assert r["resumo"].at[s, "MoM"] == met["mom"][s].get(ult), s
    dif = met["mom"]["Difusão"]
    assert dif.between(0, 100).all()
    media12 = dif.rolling(12).mean().dropna()
    assert len(media12) > 100 and np.allclose(met["mm3m"]["Difusão"].reindex(media12.index), media12)
    for k in ("yoy", "mm3m_sa", "saar"):
        assert met[k]["Difusão"].isna().all(), k
    nucs = [met["mom"][n] for n in ["Núcleo EX0", "Núcleo EX1", "Núcleo EX2", "Núcleo EX3",
                                    "Núcleo MA", "Núcleo MS", "Núcleo DP", "Núcleo P55"]]
    assert np.allclose(pd.concat(nucs, axis=1).mean(axis=1), met["mom"]["Média dos Núcleos"])


# ─── contrato ───────────────────────────────────────────────────────────────
def test_contrato_ida_e_volta():
    r = _res()
    with tempfile.TemporaryDirectory() as tmp:
        export.write_contract(r, tmp)
        assert sorted(p.name for p in Path(tmp).iterdir()) == sorted(export.ARQUIVOS)
        c = export.read_contract(tmp)
        m = c["meta"]
        assert m["reference_month"] == f"{r['ult']:%Y-%m}" and m["order"] == r["ordem"]
        assert m["breaks"] == r["QUEBRAS"] and len(m["breaks"]) == 28 and m["level_series"] == ["Difusão"]
        assert m["cores_chart"][-1] == "Média dos Núcleos"
        for k in export.METRICAS:
            esp = r["met"][k][r["ordem"]]
            assert list(c[k].columns) == r["ordem"] and c[k].index.equals(esp.index), k
            assert np.allclose(c[k].to_numpy(), esp.to_numpy(dtype=float), rtol=0, atol=5e-7, equal_nan=True), k
        cm = c["contrib_mom"]
        assert list(cm.columns) == ["IPCA"] + r["REGIMES"] + r["GRUPOS"] and cm.index[0] == pd.Timestamp(2012, 1, 1)
        assert np.allclose(cm["IPCA"], r["ipca_mom"], atol=5e-7)
        assert np.allclose(c["contrib_12m"]["IPCA"], r["ipca_12m"], atol=5e-7, equal_nan=True)
        assert np.allclose(c["resumo"].to_numpy(), r["resumo"].to_numpy(), atol=5e-7, equal_nan=True)
        assert export.read_contract(tmp, datas="str")["mom"].index[-1] == f"{r['ult']:%Y-%m}"
        # o contrato do repositório é o que sai do cache atual
        if (config.CONTRACT_DIR / "meta.json").exists():
            if export.read_contract()["meta"]["reference_month"] == m["reference_month"]:
                for nome in export.ARQUIVOS:
                    assert (Path(tmp) / nome).read_bytes() == (config.CONTRACT_DIR / nome).read_bytes(), nome


if __name__ == "__main__":
    testes = [(n, f) for n, f in list(globals().items()) if n.startswith("test_") and callable(f)]
    falhas = 0
    for nome, f in testes:
        try:
            f(); print(f"ok     {nome}")
        except Exception:
            falhas += 1; print(f"FALHOU {nome}"); traceback.print_exc()
    print(f"{len(testes) - falhas}/{len(testes)} testes ok")
    sys.exit(1 if falhas else 0)
