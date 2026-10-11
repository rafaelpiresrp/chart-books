"""Atualiza o chartbook do IPCA: baixa o mês novo do SIDRA, recalcula e refaz o HTML.

Uso, da raiz do repositório:
  python -m ipca.build            # atualiza se o IBGE divulgou mês novo
  python -m ipca.build --force    # refaz tudo mesmo sem mês novo
  python -m ipca.build --offline  # usa só o cache, sem baixar nada
"""
import argparse

from ipca import calc, data, export, report_html


def main(argv=None):
    ap = argparse.ArgumentParser(description="Atualiza o chartbook do IPCA.")
    ap.add_argument("--force", action="store_true", help="refaz mesmo sem mês novo")
    ap.add_argument("--offline", action="store_true", help="não baixa dados do SIDRA")
    a = ap.parse_args(argv)

    cache = data.cached_month()
    novo = False
    if not a.offline:
        disponivel = data.latest_available_month()
        novo = cache is None or disponivel > cache
        print(f"SIDRA: {disponivel} | cache: {cache}")
        if novo:
            data.update_raw()
            print("Dados atualizados.")
    if not (novo or a.force):
        print("Sem mês novo. Nada a fazer.")
        return 0

    res = calc.compute(data.load_raw())
    export.write_contract(res)
    html = report_html.build_html()
    print(f"Pronto: {res['ult']:%Y-%m}. {html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
