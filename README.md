# chart-books

Chartbooks da economia brasileira, feitos com dados oficiais e atualizados automaticamente.

| Chartbook | Conteúdo | Arquivo |
|---|---|---|
| IPCA | Quebras, núcleos, difusão e contribuições | [`ipca/output/IPCA_Chartbook.html`](ipca/output/IPCA_Chartbook.html) |

O chartbook é uma página HTML interativa. Como o GitHub mostra o HTML como código, baixe o arquivo e abra no navegador. As séries calculadas ficam em [`ipca/output/data`](ipca/output/data), em CSV.

## Atualização

O GitHub Actions roda nos dias 10 e 13 de cada mês. Se o IBGE já divulgou um mês novo, ele baixa os dados, recalcula tudo e salva no repositório. Para rodar na hora: aba **Actions**, **IPCA**, **Run workflow**.

Para rodar no computador:

```
pip install -r requirements.txt
python -m ipca.build --force
```

Dados: IBGE, SIDRA (tabelas 1419, 7060, 1420 e 7061).
