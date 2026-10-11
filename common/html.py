"""HTML autocontido para os chartbooks: um arquivo só, com CSS, JS e dados embutidos.

Abre offline, direto do disco (file://), sem CDN, fontes da web ou qualquer requisição.
Aqui ficam as peças genéricas (números em pt-BR, tabelas, cabeçalhos de gráfico, montagem da página);
cada chartbook monta o próprio corpo (ex.: ipca/report_html.py). Os gráficos são desenhados no navegador
por web/chartbook.js, a partir das especificações e dos dados embutidos em JSON.
"""
import html as _html
import json
import math
import re
import unicodedata
from pathlib import Path

from common import palette

DIR_WEB = Path(__file__).resolve().parent / "web"
ID_DADOS = "chartbook-dados"

MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
MESES_FULL = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
              "setembro", "outubro", "novembro", "dezembro")

# Só o próprio arquivo: nada de rede (estilos e scripts embutidos; imagens só em data:)
CSP = "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:"


# ── texto e números ──────────────────────────────────────────────────────────
def esc(s):
    """Escapa texto para HTML (atributos inclusive)."""
    return _html.escape(str(s), quote=True)


def _finito(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def num(x, dec=2, sinal=False):
    """Número em pt-BR (1.234,56) com sinal de menos tipográfico; vazio se faltar."""
    x = _finito(x)
    if x is None:
        return ""
    s = f"{abs(x):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if x < 0 and round(abs(x), dec) != 0:
        return "\u2212" + s
    if sinal and round(x, dec) != 0:
        return "+" + s
    return s


def mes_curto(ym):
    """'2026-09' -> 'set/26'."""
    a, m = str(ym)[:7].split("-")
    return f"{MESES[int(m) - 1]}/{a[2:]}"


def mes_ano(ym):
    """'2026-09' -> 'set/2026'."""
    a, m = str(ym)[:7].split("-")
    return f"{MESES[int(m) - 1]}/{a}"


def mes_extenso(ym):
    """'2026-09' -> 'setembro de 2026'."""
    a, m = str(ym)[:7].split("-")
    return f"{MESES_FULL[int(m) - 1]} de {a}"


def mes_soma(ym, k):
    """'2026-09' + k meses -> 'AAAA-MM'."""
    a, m = str(ym)[:7].split("-")
    i = int(a) * 12 + int(m) - 1 + k
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def slug(s):
    """'Alimentação no domicílio' -> 'alimentacao_no_domicilio'."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def valores(seq, casas=4):
    """Sequência numérica -> lista para o JSON (arredondada; faltante = None)."""
    out = []
    for v in seq:
        v = _finito(v)
        out.append(None if v is None else round(v, casas) + 0.0)
    return out


# ── cores (palette.py) ───────────────────────────────────────────────────────
def cores():
    """Paleta do palette.py como {'verde': '#213024', ...} (só as constantes de cor)."""
    out = {}
    for k, v in vars(palette).items():
        if k.isupper() and isinstance(v, str) and re.fullmatch(r"[0-9A-Fa-f]{6}", v):
            out[k.lower()] = "#" + v.upper()
    return out


def cor(h):
    """'A8693A' -> '#A8693A'."""
    return "#" + str(h).lstrip("#").upper()


def css_cores():
    """Variáveis CSS com a paleta (--verde, --marrom, --painel...)."""
    return ":root{" + ";".join(f"--{k.replace('_', '-')}:{v}" for k, v in cores().items()) + "}"


# ── blocos de HTML ───────────────────────────────────────────────────────────
class Contador:
    """Numeração de 'Gráfico N' e 'Tabela N' na ordem da página."""

    def __init__(self):
        self.n = {}

    def __call__(self, tipo):
        self.n[tipo] = self.n.get(tipo, 0) + 1
        return self.n[tipo]


def cabecalho(tipo, numero, titulo, subtitulo="", nivel=3):
    """Fio verde, 'Gráfico N: título' em negrito e subtítulo, como no estilo LaTeX."""
    sub = f'<p class="fig-sub">{esc(subtitulo)}</p>' if subtitulo else ""
    return (f'<div class="fig-cab"><h{nivel} class="fig-titulo"><span class="fig-num">{esc(tipo)} {numero}:</span> '
            f'<span class="fig-titulo-texto">{esc(titulo)}</span></h{nivel}>{sub}</div>')


def rodape(fonte, csv_grafico=None, csv_tabela=None):
    """Linha da fonte e botão 'Baixar CSV' (gerado no navegador a partir dos dados embutidos)."""
    if csv_grafico:
        botao = f'<button type="button" class="baixar" data-csv-grafico="{esc(csv_grafico)}">Baixar CSV</button>'
    elif csv_tabela:
        botao = f'<button type="button" class="baixar" data-csv-tabela="{esc(csv_tabela)}">Baixar CSV</button>'
    else:
        botao = ""
    return f'<div class="fig-rodape"><p class="fig-fonte">{esc(fonte)}</p>{botao}</div>'


def figura(id_grafico, numero, titulo, subtitulo, fonte, controles=False, classe=""):
    """Gráfico interativo: cabeçalho, painel creme (o JS desenha dentro), fonte e CSV.

    controles=True reserva o lugar dos botões do próprio gráfico (escopo com o mesmo id).
    """
    ctr = f'<div class="controles" data-controles="{esc(id_grafico)}"></div>' if controles else ""
    cls = ("figura " + classe).strip()
    return (f'<figure class="{cls}" id="fig-{esc(id_grafico)}">'
            + cabecalho("Gráfico", numero, titulo, subtitulo)
            + f'<div class="painel" data-grafico="{esc(id_grafico)}">{ctr}'
            + '<noscript><p class="grafico-vazio">O gráfico interativo precisa de JavaScript.</p></noscript></div>'
            + rodape(fonte, csv_grafico=id_grafico) + "</figure>")


def tabela(colunas, linhas, primeira="", destaque=(), calor=False, casas=2, casas_col=None,
           csv=None, legenda=None, classe="tab", blocos=()):
    """Tabela em estilo booktabs (fios verdes), com números em pt-BR.

    linhas: lista de (rótulo, valores). calor=True pinta cada célula pela escala da própria linha
    (palette.heat: verde nos menores, quase branco no meio, marrom nos maiores).
    colunas: rótulos (texto) ou pares (rótulo, título longo para o <abbr>).
    blocos: rótulos das linhas que abrem um bloco (ganham um respiro antes, como \\addlinespace).
    """
    casas_col = casas_col or {}
    cab = [f'<th scope="col" class="col-nome">{esc(primeira)}</th>']
    nomes = []
    for c in colunas:
        rot, longo = (c if isinstance(c, (tuple, list)) else (c, None))
        nomes.append(rot)
        cab.append(f'<th scope="col"><abbr title="{esc(longo)}">{esc(rot)}</abbr></th>' if longo
                   else f'<th scope="col">{esc(rot)}</th>')
    corpo = []
    for i, (rotulo, vals) in enumerate(linhas):
        vals = [_finito(v) for v in vals]
        fin = [v for v in vals if v is not None]
        lo, hi = (min(fin), max(fin)) if fin else (0.0, 0.0)
        cl = [c for c, sim in (("destaque", rotulo in destaque), ("bloco", i > 0 and rotulo in blocos)) if sim]
        cls = f' class="{" ".join(cl)}"' if cl else ""
        tds = []
        for nome, v in zip(nomes, vals):
            dd = casas_col.get(nome, casas)
            est = ""
            if calor and v is not None and len(fin) > 1:
                est = f' style="background:#{palette.heat(v, lo, hi)}"'
            tds.append(f"<td{est}>{num(v, dd)}</td>")
        corpo.append(f'<tr{cls}><th scope="row">{esc(rotulo)}</th>{"".join(tds)}</tr>')
    # legenda fora da área que rola (no celular a tabela começa mostrando as últimas colunas)
    cap = f'<p class="tab-legenda">{esc(legenda)}</p>' if legenda else ""
    rot = f' aria-label="{esc(legenda)}"' if legenda else ""
    dcsv = f' data-csv="{esc(csv)}"' if csv else ""
    return (f'{cap}<div class="tabela-rolagem"><table class="{classe}"{dcsv}{rot}><thead><tr>{"".join(cab)}</tr></thead>'
            f'<tbody>{"".join(corpo)}</tbody></table></div>')


# ── página ───────────────────────────────────────────────────────────────────
def json_embutido(obj):
    """JSON seguro dentro de <script> (sem '</script>', sem NaN)."""
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return (s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def _ler_web(nome):
    txt = (DIR_WEB / nome).read_text(encoding="utf-8")
    if re.search(r"</(script|style)", txt, re.I):
        raise ValueError(f"{nome} não pode conter </script> nem </style>")
    return txt


def pagina(titulo, corpo, dados, descricao="", autor="Rafael Pires", lang="pt-BR"):
    """Documento completo: CSS (paleta + chartbook.css), corpo, dados em JSON e chartbook.js, tudo embutido."""
    dados = dict(dados)
    dados.setdefault("cores", cores())
    return (
        "<!doctype html>\n"
        f'<html lang="{esc(lang)}">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">\n'
        f'<meta name="author" content="{esc(autor)}">\n'
        + (f'<meta name="description" content="{esc(descricao)}">\n' if descricao else "")
        + f"<title>{esc(titulo)}</title>\n"
        '<link rel="icon" href="data:,">\n'
        f"<style>\n{css_cores()}\n{_ler_web('chartbook.css')}</style>\n"
        "</head>\n<body>\n"
        f"{corpo}\n"
        f'<script type="application/json" id="{ID_DADOS}">{json_embutido(dados)}</script>\n'
        f"<script>\n{_ler_web('chartbook.js')}</script>\n"
        "</body>\n</html>\n"
    )


def salvar(texto, caminho):
    """Grava o HTML (UTF-8, fim de linha \\n). Devolve o Path."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    return caminho
