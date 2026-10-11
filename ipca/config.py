"""Parâmetros do chartbook do IPCA: janelas dos gráficos, tabelas do SIDRA e caminhos.

Os caminhos partem da pasta do pacote (ipca/), nunca do diretório corrente.
"""
from pathlib import Path

# Janelas
ANO_INICIO      = 2012   # início dos dados usados nos cálculos (POF 2008-09 em diante)
CHART_START     = 2013   # início das linhas (YoY, SAAR) nas páginas por quebra
BAR_START       = 2019   # início das barras mensais (MoM) nas páginas por quebra
CONTRIB_START   = 2022   # início dos gráficos de contribuição mensal
CONTRIB12_START = 2018   # início dos gráficos de contribuição em 12 meses
HEAT_MESES      = 12     # meses (colunas) nas tabelas de calor

# Caminhos
PKG_DIR      = Path(__file__).resolve().parent
RAW_DIR      = PKG_DIR / "data" / "raw"           # cache do SIDRA (CSV)
OUTPUT_DIR   = PKG_DIR / "output"
CONTRACT_DIR = OUTPUT_DIR / "data"                # contrato lido pelos geradores de HTML e README
CHARTS_DIR   = OUTPUT_DIR / "charts"              # gráficos SVG do README
HTML_PATH    = OUTPUT_DIR / "IPCA_Chartbook.html"
README_PATH  = PKG_DIR / "README.md"

# Tabelas do SIDRA: chave do cache -> (tabela, variável, decimais)
# 7060/7061: jan/2020 em diante; 1419/1420: jan/2012 a dez/2019. 63/306: variação mensal; 66/309: peso.
TABELAS = {
    "t7060_v63":  (7060, 63, 2),    # IPCA, variação mensal
    "t7060_v66":  (7060, 66, 4),    # IPCA, peso mensal
    "t1419_v63":  (1419, 63, 2),
    "t1419_v66":  (1419, 66, 4),
    "t7061_v306": (7061, 306, 2),   # IPCA dessazonalizado, variação mensal
    "t7061_v309": (7061, 309, 4),   # IPCA dessazonalizado, peso mensal
    "t1420_v306": (1420, 306, 2),
    "t1420_v309": (1420, 309, 4),
}
TABELA_REF = "t7060_v63"   # define o mês mais recente (índice geral, variação mensal)
PERIODOS_RAPIDO = "last 3" # atualização incremental: últimos 3 meses sobre o cache

FONTE = ("IBGE, Sistema IBGE de Recuperação Automática (SIDRA): tabelas 1419 e 7060 (IPCA) "
         "e 1420 e 7061 (IPCA dessazonalizado).")

# Séries em negrito nas tabelas e séries de nível (sem YoY/SA/SAAR)
DESTAQUE = ["IPCA cheio", "Livres", "Administrados", "Serviços", "Média dos Núcleos"]
SERIES_NIVEL = ["Difusão"]

MESES_FMT = {1:"jan",2:"fev",3:"mar",4:"abr",5:"mai",6:"jun",7:"jul",8:"ago",9:"set",10:"out",11:"nov",12:"dez"}
MESES_EXTENSO = {1:"janeiro",2:"fevereiro",3:"março",4:"abril",5:"maio",6:"junho",
                 7:"julho",8:"agosto",9:"setembro",10:"outubro",11:"novembro",12:"dezembro"}


def fmt_data(dt):
    """Timestamp -> 'set/26'."""
    return f"{MESES_FMT[dt.month]}/{str(dt.year)[2:]}"


def rotulo_mes(dt):
    """Timestamp -> 'setembro de 2026'."""
    return f"{MESES_EXTENSO[dt.month]} de {dt.year}"
