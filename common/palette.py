"""Paleta do site (rafaelpiresrp.github.io) e o papel de cada cor nos gráficos.

O HTML interativo e os gráficos SVG do README leem as cores daqui.
Os códigos vão sem '#'.
"""

# Cores do site
VERDE = "213024"        # verde escuro: série principal, fios, destaques
VERDE_ESC = "172119"    # verde mais escuro: eixos
CREME = "ECE4D3"        # creme
MUSGO = "AEA78F"        # musgo
MARROM = "A8693A"       # marrom: segunda série, destaques

# Tons derivados das cores do site (misturadas com branco ou preto)
VERDE_55 = "858D87"
VERDE_30 = "BCC1BD"
MARROM_55 = "CFAC93"
MARROM_30 = "E5D2C4"
MUSGO_ESC = "7A7564"
MUSGO_65 = "CAC6B6"
MUSGO_35 = "E3E0D8"
CINZA = "8C8C8C"
PRETO = "000000"

# Papéis
BARRA = MUSGO_65            # barras mensais (MoM)
BARRA_ULTIMA = MARROM       # última barra, mês de referência
LINHA_1 = VERDE             # primeira linha (MM3M, YoY)
LINHA_2 = MARROM            # segunda linha (SAAR)
TOTAL = PRETO               # linha do total sobre as contribuições empilhadas
GRADE = "D9D9D9"            # grade
RECESSAO = "EDEDED"         # sombreado cinza claro
PAINEL = "F4F2EC"           # painel creme atrás dos gráficos interativos

REGIMES = {
    "Alimentação no domicílio": MARROM,
    "Bens industriais": MUSGO,
    "Serviços": VERDE,
    "Administrados": MARROM_55,
}

GRUPOS = {
    "Alimentação e bebidas": MARROM,
    "Habitação": VERDE,
    "Artigos de residência": MUSGO_35,
    "Vestuário": CINZA,
    "Transportes": MUSGO_ESC,
    "Saúde e cuidados pessoais": MARROM_55,
    "Despesas pessoais": VERDE_55,
    "Educação": MUSGO,
    "Comunicação": VERDE_30,
}

# Núcleos: linhas finas; a média dos núcleos é a linha grossa
NUCLEOS = {
    "Núcleo EX0": MUSGO,
    "Núcleo EX3": MARROM_55,
    "Núcleo MA": VERDE_55,
    "Núcleo MS": MARROM,
    "Núcleo DP": MUSGO_ESC,
    "Núcleo P55": CINZA,
    "Média dos Núcleos": VERDE,
}

# Tabelas de calor: valores baixos em verde, meio quase branco, altos em marrom (cada linha na sua escala)
HEAT_BAIXO = "A6ACA7"
HEAT_MEIO = "F7F5F0"
HEAT_ALTO = "D8A57F"


def rgb(h):
    """'A8693A' -> (168, 105, 58)."""
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def heat(x, lo, hi):
    """Cor da célula com valor x numa linha cujos valores finitos vão de lo a hi."""
    t = (x - lo) / (hi - lo) if hi > lo else 0.5
    a, b, f = (HEAT_BAIXO, HEAT_MEIO, t / 0.5) if t < 0.5 else (HEAT_MEIO, HEAT_ALTO, (t - 0.5) / 0.5)
    a, b = rgb(a), rgb(b)
    return "%02X%02X%02X" % tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3))
