"""
Coleta dos dados do SINAPI (custo médio do m²) e do IPCA pela API de agregados do IBGE.

Fonte: https://servicodados.ibge.gov.br/api/docs/agregados?versao=3
  - Tabela 2296: SINAPI - custo médio do m² (total, materiais e mão de obra)
  - Tabela 1737: IPCA - número-índice

Gera três arquivos em formato "longo" (tidy) em data/raw/:
  - sinapi_custo_m2_mensal.csv  -> série mensal: Brasil, 5 regiões e São Paulo
  - sinapi_uf_<AAAA-MM>.csv      -> foto do último mês para as 27 UFs
  - ipca_indice_mensal.csv       -> IPCA número-índice, Brasil

Uso:
    python src/coleta.py                      # período padrão (201601 até o último mês publicado)
    python src/coleta.py --inicio 201801 --fim 202610
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

API = "https://servicodados.ibge.gov.br/api/v3/agregados"
RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"

# Variáveis da tabela 2296 (SINAPI)
VAR_CUSTO_TOTAL = "48"
VAR_CUSTO_MATERIAL = "2119"
VAR_CUSTO_MAO_OBRA = "2120"
VAR_VARIACAO_12M = "1198"
# Variável da tabela 1737 (IPCA)
VAR_IPCA_INDICE = "2266"

CABECALHO = ["periodo", "nivel", "localidade_id", "localidade", "variavel_id", "variavel", "valor"]


def _get(url: str) -> list[dict]:
    with urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ultimo_periodo(tabela: str) -> str:
    """Último mês publicado de uma tabela, no formato AAAAMM."""
    meta = _get(f"{API}/{tabela}/metadados")
    return str(meta["periodicidade"]["fim"])


def consultar(tabela: str, periodos: str, variaveis: list[str], localidades: str) -> list[list[str]]:
    """Consulta a API e devolve linhas no formato longo (uma linha por período/local/variável)."""
    url = (
        f"{API}/{tabela}/periodos/{periodos}/variaveis/{quote('|'.join(variaveis))}"
        f"?localidades={quote(localidades, safe='[],')}"
    )
    linhas = []
    for var in _get(url):
        for resultado in var["resultados"]:
            for serie in resultado["series"]:
                loc = serie["localidade"]
                for periodo, valor in sorted(serie["serie"].items()):
                    if valor in ("...", "-", "X", None):  # sem dado
                        continue
                    linhas.append([
                        f"{periodo[:4]}-{periodo[4:]}",
                        loc["nivel"]["id"],
                        loc["id"],
                        loc["nome"],
                        var["id"],
                        var["variavel"],
                        valor,
                    ])
    return linhas


def salvar(caminho: Path, linhas: list[list[str]]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CABECALHO)
        w.writerows(linhas)
    print(f"  {caminho.relative_to(RAIZ)}: {len(linhas)} linhas")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inicio", default="201601", help="primeiro mês (AAAAMM)")
    ap.add_argument("--fim", default=None, help="último mês (AAAAMM); padrão = último publicado")
    args = ap.parse_args()

    fim = args.fim or ultimo_periodo("2296")
    periodo_txt = f"{fim[:4]}-{fim[4:]}"
    print(f"Coletando SINAPI e IPCA de {args.inicio} a {fim}...")

    # 1) Série mensal: Brasil (N1), regiões (N2) e São Paulo (N3, código 35)
    salvar(
        RAW / "sinapi_custo_m2_mensal.csv",
        consultar("2296", f"{args.inicio}-{fim}",
                  [VAR_CUSTO_TOTAL, VAR_CUSTO_MATERIAL, VAR_CUSTO_MAO_OBRA],
                  "N1[all]|N2[all]|N3[35]"),
    )
    # 2) Foto do último mês para todas as UFs
    salvar(
        RAW / f"sinapi_uf_{periodo_txt}.csv",
        consultar("2296", fim,
                  [VAR_CUSTO_TOTAL, VAR_CUSTO_MATERIAL, VAR_CUSTO_MAO_OBRA, VAR_VARIACAO_12M],
                  "N3[all]"),
    )
    # 3) IPCA número-índice, mesmo período
    salvar(
        RAW / "ipca_indice_mensal.csv",
        consultar("1737", f"{args.inicio}-{fim}", [VAR_IPCA_INDICE], "N1[all]"),
    )


if __name__ == "__main__":
    main()
