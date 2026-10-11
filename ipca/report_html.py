"""Chartbook do IPCA em HTML interativo: lê só o contrato (output/data) e grava um arquivo único.

CSS, JS e dados vão embutidos: o arquivo abre offline, direto do disco. Os gráficos são desenhados
no navegador por common/web/chartbook.js a partir das especificações montadas aqui (cores do palette.py).

    python -m ipca.report_html            # grava ipca/output/IPCA_Chartbook.html
"""
from pathlib import Path

import pandas as pd

from common import html as H
from common import palette as P

from . import config
from .export import read_contract

FONTE = "Fonte: IBGE (SIDRA); cálculos do autor."
AUTOR = "Rafael Pires"

# tabelas de calor: chave do contrato -> (botão, título)
CALOR = [
    ("mom", "MoM", "Variação mensal (%)"),
    ("mm3m", "MM3M", "Média móvel de 3 meses da variação mensal (%)"),
    ("yoy", "YoY", "Variação em 12 meses (%)"),
    ("mm3m_sa", "MM3M SA", "Média móvel de 3 meses dessazonalizada (%)"),
    ("saar", "MM3M SAAR", "Média móvel de 3 meses dessazonalizada e anualizada (%)"),
    ("contrib_mom", "Contribuição mensal", "Contribuição para a variação mensal do IPCA (p.p.)"),
    ("contrib_12m", "Contribuição em 12 meses", "Contribuição para a variação em 12 meses do IPCA (p.p.)"),
]
# linhas que abrem um bloco (respiro antes) no resumo
BLOCOS_RESUMO = ("Administrados", "Alimentação no domicílio", "Comercializáveis", "Bens não duráveis",
                 "Núcleo EX-FE", "EX3 Serviços", "Alimentação e bebidas", "Núcleo MA", "Difusão")
COLUNAS_RESUMO = [
    ("Peso", "Peso no IPCA no mês de referência (%)"),
    ("MoM", "Variação no mês (%)"),
    ("MM3M", "Média móvel de 3 meses da variação mensal (%)"),
    ("YoY", "Variação em 12 meses (%)"),
    ("MM3M SA", "Média móvel de 3 meses da variação mensal dessazonalizada (%)"),
    ("MM3M SAAR", "MM3M SA anualizada (%)"),
]


# ── dados embutidos ──────────────────────────────────────────────────────────
def _tabela_js(df, casas=4):
    """DataFrame (índice 'AAAA-MM') -> {'inicio', 'n', 'series': {coluna: [valores]}}, meses contínuos."""
    idx = pd.PeriodIndex(list(df.index), freq="M")
    cheio = pd.period_range(idx.min(), idx.max(), freq="M")
    d = df.copy()
    d.index = idx
    d = d.sort_index().reindex(cheio)
    return {"inicio": str(cheio[0]), "n": len(cheio),
            "series": {str(c): H.valores(d[c].tolist(), casas) for c in d.columns}}


def _v(df, ym, col):
    """Valor de df[col] no mês ym (None se faltar)."""
    try:
        x = df.at[ym, col]
    except KeyError:
        return None
    return None if pd.isna(x) else float(x)


def _pct(x, dec=2):
    s = H.num(x, dec)
    return f"{s}%" if s else "–"


# ── blocos ───────────────────────────────────────────────────────────────────
def _destaques(c):
    """Quadro de destaques: variação em 12 meses, no mês e MM3M SAAR das principais séries."""
    m = c["meta"]
    r = c["resumo"]

    def v(serie, col, dec=2):
        return _pct(_v(r, serie, col), dec)

    itens = []
    for s in ("IPCA cheio", "Livres", "Administrados", "Serviços", "Média dos Núcleos"):
        nome = "Média dos núcleos" if s == "Média dos Núcleos" else s
        itens.append((nome, v(s, "YoY"), "em 12 meses", [f"{v(s, 'MoM')} no mês", f"{v(s, 'MM3M SAAR')} MM3M SAAR"]))
    itens.append(("Difusão", v("Difusão", "MoM"), "dos subitens com alta no mês",
                  [f"{v('Difusão', 'MM3M')} na média", "de 12 meses"]))
    dl = "".join(f'<div class="destaque-item"><dt>{H.esc(n)}</dt><dd><span class="destaque-valor">{H.esc(x)}</span>'
                 f'<span class="destaque-det">{H.esc(d)}</span>'
                 f'<span class="destaque-mais">{"<br>".join(H.esc(t) for t in mais)}</span></dd></div>'
                 for n, x, d, mais in itens)
    return ('<section class="secao" id="destaques" aria-labelledby="t-destaques"><div class="caixa">'
            f'<h2 id="t-destaques">Destaques de {H.esc(m["reference_label"])}</h2>'
            f'<dl class="destaques">{dl}</dl></div>'
            '<p class="caixa-nota">Variações em %. MoM: no mês; YoY: em 12 meses; MM3M SAAR: média móvel de 3 meses '
            'com ajuste sazonal, anualizada. Difusão: proporção dos subitens com alta de preços no mês.</p></section>')


def _resumo(c, num):
    m = c["meta"]
    r = c["resumo"]
    linhas = [(s, [r.at[s, col] if s in r.index and col in r.columns else None for col, _ in COLUNAS_RESUMO])
              for s in m["order"]]
    tab = H.tabela(COLUNAS_RESUMO, linhas, primeira="Série", destaque=set(m["highlight"]), casas=2,
                   casas_col={"Peso": 1}, csv=f"ipca_resumo_{m['reference_month']}", classe="tab resumo-tab",
                   blocos=BLOCOS_RESUMO)
    nota = ("Peso: participação no IPCA no mês de referência; os núcleos MA, MS, DP e P55 e a média dos núcleos "
            "não têm peso próprio. Difusão: proporção dos subitens com alta no mês (coluna MoM) e sua média de "
            "12 meses (coluna MM3M). Definições nas notas, no fim da página.")
    return ('<section class="secao" id="resumo" aria-labelledby="t-resumo"><h2 id="t-resumo">Resumo</h2>'
            '<div class="figura" id="tab-resumo">'
            + H.cabecalho("Tabela", num("Tabela"), f"Resumo de {m['reference_label']} (%)",
                          "Peso, variação no mês, médias móveis de 3 meses e variação em 12 meses de cada série.")
            + tab + f'<p class="tab-nota">{H.esc(nota)}</p>'
            + H.rodape(FONTE, csv_tabela="#tab-resumo") + "</div></section>")


def _contribuicoes(c, num, graficos, escopos):
    m = c["meta"]
    ult, ref = m["reference_month"], H.mes_extenso(m["reference_month"])
    cm = c["contrib_mom"]
    st = m["start"]
    preto = H.cor(P.TOTAL)

    def itens(nomes):
        out = [{"rotulo": "IPCA", "valor": _v(cm, ult, "IPCA"), "cor": H.cor(P.BARRA_ULTIMA), "destaque": True,
                "texto": "Variação no mês", "unidade": "%"}]
        out += [{"rotulo": k, "valor": _v(cm, ult, k), "cor": H.cor(P.BARRA),
                 "texto": "Contribuição", "unidade": " p.p."} for k in nomes]
        return out

    html = ['<section class="secao" id="contribuicoes" aria-labelledby="t-contrib"><h2 id="t-contrib">Contribuições</h2>',
            f'<p class="intro">Quanto cada grupo e cada regime de preços somou à variação do IPCA, em pontos '
            f'percentuais (p.p.). As contribuições somam a variação do índice, a menos de arredondamentos.</p>',
            '<div class="duas">']
    for chave, nome, nomes in (("grupo", "grupo", m["groups"]), ("regime", "regime", m["regimes"])):
        gid = f"contrib_mes_{chave}"
        graficos[gid] = {"tipo": "barras_h", "itens": itens(nomes), "casas": 2,
                         "csv": f"ipca_contribuicao_{ult}_{chave}", "csv_rotulo": "componente",
                         "csv_valor": "contribuição (p.p.); IPCA: variação (%)"}
        html.append(H.figura(gid, num("Gráfico"), f"Contribuições para o IPCA de {ref}, por {nome}",
                             "Em p.p.; a primeira barra é a variação do IPCA no mês (%).", FONTE))
    html.append("</div>")

    for chave, nome, nomes, cores in (("regime", "regime", m["regimes"], P.REGIMES),
                                      ("grupo", "grupo", m["groups"], P.GRUPOS)):
        gid = f"contrib_{chave}"

        def series(tab, total):
            out = [{"nome": k, "tabela": tab, "col": k, "tipo": "empilhada", "cor": H.cor(cores.get(k, P.CINZA)),
                    "unidade": " p.p."} for k in nomes]
            out.append({"nome": total, "tabela": tab, "col": "IPCA", "tipo": "linha", "cor": preto,
                        "largura": 2, "unidade": "%"})
            return out

        sub_m = f"Contribuição para a variação mensal do IPCA, em p.p., desde {st['contrib_month']}. Linha: IPCA no mês (%)."
        sub_a = f"Contribuição para a variação em 12 meses do IPCA, em p.p., desde {st['contrib_12m']}. Linha: IPCA em 12 meses (%)."
        escopos[gid] = {"estado": {"freq": "mensal"},
                        "controles": [{"tipo": "botoes", "chave": "freq", "rotulo": "Horizonte",
                                       "opcoes": [["mensal", "Mensal"], ["12m", "Em 12 meses"]]}]}
        graficos[gid] = {
            "tipo": "tempo", "inicio": f"{st['contrib_month']}-01", "casas": 2, "largura_barra": .7,
            "titulo": f"Contribuições por {nome}: variação mensal", "subtitulo": sub_m,
            "series": series("contrib_mom", "IPCA no mês"), "dica_primeiro": "IPCA no mês",
            "csv": f"ipca_contribuicoes_{chave}_mensal",
            "variantes": [{"chave": "freq", "valor": "12m", "spec": {
                "inicio": f"{st['contrib_12m']}-01", "largura_barra": .8,
                "titulo": f"Contribuições por {nome}: variação em 12 meses", "subtitulo": sub_a,
                "series": series("contrib_12m", "IPCA em 12 meses"), "dica_primeiro": "IPCA em 12 meses",
                "csv": f"ipca_contribuicoes_{chave}_12_meses"}}],
        }
        html.append(H.figura(gid, num("Gráfico"), graficos[gid]["titulo"], sub_m, FONTE, controles=True))
    html.append("</section>")
    return "".join(html)


def _nucleos(c, num, graficos):
    m = c["meta"]
    ini = m["start"]["bars"]
    nucs = m["cores_chart"]
    media = nucs[-1] if nucs else None

    def curto(k):
        return "Média dos núcleos" if k == media else k.replace("Núcleo ", "")

    def series(tab):
        return [{"nome": curto(k), "tabela": tab, "col": k, "tipo": "linha", "cor": H.cor(P.NUCLEOS.get(k, P.CINZA)),
                 "largura": 2.6 if k == media else 1.3, "unidade": "%"} for k in nucs]

    html = ['<section class="secao" id="nucleos" aria-labelledby="t-nucleos"><h2 id="t-nucleos">Núcleos</h2>',
            f'<p class="intro">Núcleos de inflação desde {ini}: EX0 a EX3, por exclusão; MA e MS, médias aparadas; '
            'DP, dupla ponderação; P55, percentil 55. Clique nos nomes da legenda para esconder ou mostrar cada '
            'série.</p><div class="duas">']
    for gid, tab, tit, sub in (("nucleos_12m", "yoy", "Núcleos: variação em 12 meses",
                                f"Em %, desde {ini}. Linha grossa: média dos núcleos."),
                               ("nucleos_saar", "saar", "Núcleos: MM3M SAAR",
                                f"Em %, desde {ini}; com ajuste sazonal, anualizada.")):
        graficos[gid] = {"tipo": "tempo", "inicio": f"{ini}-01", "casas": 2, "series": series(tab),
                         "dica_primeiro": curto(media) if media else None, "csv": f"ipca_{gid}"}
        html.append(H.figura(gid, num("Gráfico"), tit, sub, FONTE))
    html.append("</div></section>")
    return "".join(html)


def _calor(c, num, escopos):
    m = c["meta"]
    n = int(m["start"]["heat_months"])
    ordem, destaque = m["order"], {"IPCA cheio", "Média dos Núcleos"}
    paineis = []
    for chave, botao, titulo in CALOR:
        df = c[chave]
        if chave.startswith("contrib"):
            total = "IPCA (MoM, %)" if chave == "contrib_mom" else "IPCA (YoY, %)"
            cols = ["IPCA"] + m["regimes"] + m["groups"]
            d = df[[k for k in cols if k in df.columns]].dropna(how="all").iloc[-n:]
            rot = {"IPCA": total}
            dest = {total}
            blocos = (m["regimes"][0], m["groups"][0])
        else:
            d = df[[k for k in ordem if k in df.columns]].dropna(how="all").iloc[-n:]
            rot, dest, blocos = {}, destaque, BLOCOS_RESUMO
        linhas = [(rot.get(k, k), d[k].tolist()) for k in d.columns if d[k].notna().any()]
        tab = H.tabela([H.mes_curto(x) for x in d.index], linhas, primeira="", destaque=dest, calor=True,
                       casas=2, csv=f"ipca_calor_{chave}", legenda=titulo, classe="tab calor", blocos=blocos)
        paineis.append(f'<div data-valor="{H.esc(chave)}">{tab}</div>')
    escopos["calor"] = {"estado": {"tabela": "mom"}, "paineis": "tabela",
                        "controles": [{"tipo": "botoes", "chave": "tabela", "rotulo": "Medida",
                                       "opcoes": [[k, b] for k, b, _ in CALOR]}]}
    return ('<section class="secao" id="calor" aria-labelledby="t-calor"><h2 id="t-calor">Tabelas de calor</h2>'
            '<div class="figura" id="tab-calor">'
            + H.cabecalho("Tabela", num("Tabela"), f"Últimos {n} meses, por medida",
                          "Cada linha tem a sua escala: verde nos menores valores da linha, quase branco no meio, "
                          "marrom nos maiores. Escolha a medida:")
            + '<div class="controles" data-controles="calor"></div>'
            + f'<div class="paineis" data-paineis="calor">{"".join(paineis)}</div>'
            + H.rodape(FONTE, csv_tabela="#tab-calor") + "</div></section>")


def _explorar(c, num, graficos, escopos):
    m = c["meta"]
    ult, st = m["reference_month"], m["start"]
    ordem, nivel = m["order"], set(m.get("level_series") or [])
    r = c["resumo"]
    ref = H.mes_curto(ult)

    textos = {}
    for s in ordem:
        if s in nivel:
            textos[s] = (f"Em {ref}: {_pct(_v(c['mom'], ult, s), 1)} dos subitens subiram; "
                         f"média de 12 meses: {_pct(_v(c['mm3m'], ult, s), 1)}.")
            continue
        peso = m["weights"].get(s)
        partes = [f"Peso em {ref}: {H.num(peso, 1)}%"] if peso is not None and s != "IPCA cheio" else []
        partes += [f"no mês: {_pct(_v(c['mom'], ult, s))}", f"MM3M: {_pct(_v(c['mm3m'], ult, s))}",
                   f"em 12 meses: {_pct(_v(c['yoy'], ult, s))}", f"MM3M SAAR: {_pct(_v(c['saar'], ult, s))}"]
        texto = "; ".join(partes)
        textos[s] = texto[0].upper() + texto[1:] + "."
    periodos = [[f"{st['lines']}-01", f"Desde {st['lines']}"],
                [H.mes_soma(ult, -59), "5 anos"],
                [H.mes_soma(ult, -23), "2 anos"]]
    escopos["explorar"] = {
        "estado": {"serie": ordem[0], "periodo": periodos[0][0]},
        "controles": [{"tipo": "lista", "chave": "serie", "rotulo": "Série", "opcoes": [[s, s] for s in ordem]},
                      {"tipo": "botoes", "chave": "periodo", "rotulo": "Período", "opcoes": periodos}],
        "nota": {"por": "serie", "textos": textos},
    }
    mensal = {
        "tipo": "tempo", "escopos": ["explorar"], "inicio": "{periodo}", "casas": 2,
        "titulo": "{serie}: variação mensal e média móvel de 3 meses",
        "subtitulo": f"Em %. Barras: variação no mês (MoM); em marrom, {ref}. Linha: média móvel de 3 meses (MM3M).",
        "series": [{"nome": "MoM", "tabela": "mom", "col": "{serie}", "tipo": "barra", "cor": H.cor(P.BARRA),
                    "ultima": H.cor(P.BARRA_ULTIMA), "unidade": "%"},
                   {"nome": "MM3M", "tabela": "mm3m", "col": "{serie}", "tipo": "linha", "cor": H.cor(P.LINHA_1),
                    "largura": 2, "unidade": "%"}],
        "csv": "ipca_{serie}_mensal",
        "variantes": [{"chave": "serie", "valor": s, "spec": {
            "titulo": f"{s}: % dos subitens com alta no mês", "zero": False, "casas": 1,
            "subtitulo": f"Barras: difusão (% dos subitens com alta); em marrom, {ref}. Linha: média de 12 meses.",
            "series": [{"nome": "Difusão", "tabela": "mom", "col": s, "tipo": "barra", "cor": H.cor(P.BARRA),
                        "ultima": H.cor(P.BARRA_ULTIMA), "unidade": "%"},
                       {"nome": "Média de 12 meses", "tabela": "mm3m", "col": s, "tipo": "linha",
                        "cor": H.cor(P.LINHA_1), "largura": 2, "unidade": "%"}]}} for s in ordem if s in nivel],
    }
    anual = {
        "tipo": "tempo", "escopos": ["explorar"], "inicio": "{periodo}", "casas": 2,
        "titulo": "{serie}: variação em 12 meses e MM3M SAAR",
        "subtitulo": "Em %. MM3M SAAR: média móvel de 3 meses da variação mensal dessazonalizada, anualizada.",
        "series": [{"nome": "Em 12 meses", "tabela": "yoy", "col": "{serie}", "tipo": "linha", "cor": H.cor(P.LINHA_1),
                    "largura": 2.2, "unidade": "%"},
                   {"nome": "MM3M SAAR", "tabela": "saar", "col": "{serie}", "tipo": "linha", "cor": H.cor(P.LINHA_2),
                    "largura": 1.6, "unidade": "%"}],
        "csv": "ipca_{serie}_12_meses_saar",
        "variantes": [{"chave": "serie", "valor": s, "spec": {
            "titulo": f"{s}: sem variação em 12 meses nem MM3M SAAR", "subtitulo": "",
            "vazio": "A difusão é um nível (% dos subitens com alta no mês), não uma taxa de variação: "
                     "não tem variação em 12 meses nem MM3M SAAR."}} for s in ordem if s in nivel],
    }
    graficos["explorar_mensal"], graficos["explorar_anual"] = mensal, anual
    s0 = ordem[0]
    return ('<section class="secao" id="explorar" aria-labelledby="t-explorar"><h2 id="t-explorar">Explorar uma série</h2>'
            '<p class="intro">Escolha uma das séries do chartbook e o período. Passe o mouse (ou o dedo) sobre os '
            'gráficos para ler os valores de cada mês; com o gráfico em foco, as setas do teclado andam pelos meses.</p>'
            '<div class="controles controles-secao" data-controles="explorar"></div>'
            + H.figura("explorar_mensal", num("Gráfico"), mensal["titulo"].replace("{serie}", s0), mensal["subtitulo"], FONTE)
            + H.figura("explorar_anual", num("Gráfico"), anual["titulo"].replace("{serie}", s0), anual["subtitulo"], FONTE)
            + "</section>")


def _notas(c):
    m = c["meta"]
    res = m.get("contrib_residual_pp") or {}
    itens = [
        ("MoM", "variação no mês (%)."),
        ("MM3M", "média móvel de 3 meses das variações mensais (%)."),
        ("YoY", "variação acumulada em 12 meses (%)."),
        ("MM3M SA", "média móvel de 3 meses das variações mensais dessazonalizadas pelo IBGE (%)."),
        ("MM3M SAAR", "MM3M SA anualizada: [(1 + MM3M SA/100)¹² − 1] × 100."),
        ("Contribuição", "variação de cada componente vezes o seu peso, em p.p. Em 12 meses, a soma exata das "
                         "contribuições mensais reponderadas pelo índice, de modo que somam a variação em 12 meses do IPCA."),
        ("Difusão", "% dos subitens com variação positiva no mês; a linha é a média de 12 meses."),
        ("Média dos Núcleos", "média simples dos núcleos EX0, EX1, EX2, EX3, MA, MS, DP e P55."),
    ]
    dl = "".join(f"<dt>{H.esc(a)}</dt><dd>{H.esc(b)}</dd>" for a, b in itens)
    residuo = ""
    if res:
        residuo = (f"<p>Diferença máxima entre a soma das contribuições mensais e o IPCA: "
                   f"{H.num(res.get('regimes'), 3)} p.p. (regimes) e {H.num(res.get('groups'), 3)} p.p. (grupos).</p>")
    return ('<section class="secao" id="notas" aria-labelledby="t-notas"><div class="caixa notas">'
            f'<h2 id="t-notas">Notas</h2><dl>{dl}</dl>{residuo}'
            f'<p>Fonte: {H.esc(m["source"])}</p></div></section>')


# ── página ───────────────────────────────────────────────────────────────────
def montar(c):
    """Contrato (read_contract com datas='str') -> HTML completo (texto)."""
    m = c["meta"]
    ult = m["reference_month"]
    num = H.Contador()
    graficos, escopos = {}, {}
    corpo_secoes = [
        _destaques(c),
        _resumo(c, num),
        _contribuicoes(c, num, graficos, escopos),
        _nucleos(c, num, graficos),
        _calor(c, num, escopos),
        _explorar(c, num, graficos, escopos),
        _notas(c),
    ]
    indice = [("destaques", "Destaques"), ("resumo", "Resumo"), ("contribuicoes", "Contribuições"),
              ("nucleos", "Núcleos"), ("calor", "Tabelas de calor"), ("explorar", "Explorar uma série"),
              ("notas", "Notas")]
    nav = ('<nav class="indice" aria-label="Índice"><ol>'
           + "".join(f'<li><a href="#{a}">{H.esc(b)}</a></li>' for a, b in indice) + "</ol></nav>")
    cab = ('<header class="doc-cab"><h1>Chartbook do IPCA</h1>'
           f'<p class="doc-sub">Inflação ao consumidor em {H.esc(m["reference_label"])}</p>'
           f'<p class="doc-autor">{AUTOR}</p>'
           f'<p class="doc-links">Mês de referência: {H.esc(H.mes_ano(ult))}. Dados: IBGE (SIDRA).</p></header>')
    rodape = (f'<footer class="doc-rodape"><p class="fig-fonte">{AUTOR}. Chartbook do IPCA de '
              f'{H.esc(m["reference_label"])}. {H.esc(FONTE)}</p></footer>')
    corpo = f'<div class="pagina">{cab}{nav}<main>{"".join(corpo_secoes)}</main>{rodape}</div>'

    tabelas = {k: _tabela_js(c[k]) for k in ("mom", "mm3m", "yoy", "mm3m_sa", "saar", "contrib_mom", "contrib_12m")}
    dados = {"chartbook": m.get("chartbook", "IPCA"), "referencia": ult, "tabelas": tabelas,
             "graficos": graficos, "escopos": escopos, "cores": H.cores()}
    return H.pagina(f"Chartbook do IPCA: {m['reference_label']}", corpo, dados,
                    descricao=f"Chartbook interativo do IPCA de {m['reference_label']}: resumo, contribuições, "
                              "núcleos, tabelas de calor e todas as séries.", autor=AUTOR)


def build_html(contract_dir=None, out_html=None) -> Path:
    """Contrato -> ipca/output/IPCA_Chartbook.html (arquivo único, abre offline). Devolve o caminho."""
    c = read_contract(contract_dir, datas="str")
    return H.salvar(montar(c), out_html if out_html is not None else config.HTML_PATH)


if __name__ == "__main__":
    print(build_html())
