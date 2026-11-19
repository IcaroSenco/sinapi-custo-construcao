"""
Tratamento: lê os CSVs brutos de data/raw/, padroniza, calcula métricas derivadas
e grava as tabelas tratadas em data/processed/ (CSV) e em um banco SQLite.

Métricas calculadas:
  - participação dos materiais no custo do m² (%)
  - índice base 100 = primeiro mês da série (total, materiais e mão de obra)
  - variação em 12 meses (%)
  - custo do m² a preços constantes (corrigido pelo IPCA para o último mês da série)

Uso:
    python src/tratamento.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
PROC = RAIZ / "data" / "processed"
DB = PROC / "sinapi.db"

NOMES = {"48": "custo_total", "2119": "custo_material", "2120": "custo_mao_obra", "1198": "variacao_12m_ibge"}


def ler_longo(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho, dtype={"localidade_id": str, "variavel_id": str})
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df


def para_largo(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por período + localidade; uma coluna por variável."""
    df = df.assign(var=df["variavel_id"].map(NOMES))
    largo = (
        df.pivot_table(index=["periodo", "nivel", "localidade_id", "localidade"],
                       columns="var", values="valor", aggfunc="first")
        .reset_index()
    )
    largo.columns.name = None
    return largo


def tratar_mensal(sinapi: pd.DataFrame, ipca: pd.DataFrame) -> pd.DataFrame:
    df = para_largo(sinapi)
    df["data"] = pd.to_datetime(df["periodo"] + "-01")
    df = df.sort_values(["nivel", "localidade_id", "data"]).reset_index(drop=True)

    # Checagem de consistência: total = material + mão de obra (tolerância de arredondamento)
    dif = (df["custo_total"] - df["custo_material"] - df["custo_mao_obra"]).abs()
    if (dif > 0.05).any():
        raise ValueError(f"Total diferente de material + mão de obra em {int((dif > 0.05).sum())} linhas")

    df["part_material_pct"] = 100 * df["custo_material"] / df["custo_total"]

    g = df.groupby(["nivel", "localidade_id"], group_keys=False)
    for col in ["custo_total", "custo_material", "custo_mao_obra"]:
        df[f"indice_{col.replace('custo_', '')}"] = 100 * df[col] / g[col].transform("first")
        df[f"var_12m_{col.replace('custo_', '')}_pct"] = 100 * (df[col] / g[col].shift(12) - 1)

    # Correção pelo IPCA: valores em R$ do último mês da série
    ip = ipca[["periodo", "valor"]].rename(columns={"valor": "ipca_indice"})
    df = df.merge(ip, on="periodo", how="left", validate="many_to_one")
    if df["ipca_indice"].isna().any():
        faltando = sorted(df.loc[df["ipca_indice"].isna(), "periodo"].unique())
        raise ValueError(f"IPCA ausente para: {faltando}")
    ipca_final = ip.sort_values("periodo")["ipca_indice"].iloc[-1]
    fator = ipca_final / df["ipca_indice"]
    for col in ["custo_total", "custo_material", "custo_mao_obra"]:
        df[f"{col}_real"] = df[col] * fator

    colunas = ["periodo", "data", "nivel", "localidade_id", "localidade",
               "custo_total", "custo_material", "custo_mao_obra", "part_material_pct",
               "indice_total", "indice_material", "indice_mao_obra",
               "var_12m_total_pct", "var_12m_material_pct", "var_12m_mao_obra_pct",
               "ipca_indice", "custo_total_real", "custo_material_real", "custo_mao_obra_real"]
    return df[colunas]


def tratar_uf(uf: pd.DataFrame) -> pd.DataFrame:
    df = para_largo(uf)
    df["part_material_pct"] = 100 * df["custo_material"] / df["custo_total"]
    df["ranking_custo"] = df["custo_total"].rank(ascending=False, method="min").astype(int)
    return df.sort_values("ranking_custo").reset_index(drop=True)


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    sinapi = ler_longo(RAW / "sinapi_custo_m2_mensal.csv")
    ipca = ler_longo(RAW / "ipca_indice_mensal.csv")
    arq_uf = sorted(RAW.glob("sinapi_uf_*.csv"))[-1]
    uf = ler_longo(arq_uf)

    mensal = tratar_mensal(sinapi, ipca)
    ufs = tratar_uf(uf)

    mensal.to_csv(PROC / "custo_m2_mensal.csv", index=False, float_format="%.4f")
    ufs.to_csv(PROC / "custo_m2_uf_ultimo_mes.csv", index=False, float_format="%.4f")

    with sqlite3.connect(DB) as con:
        mensal.assign(data=mensal["data"].dt.strftime("%Y-%m-%d")).to_sql("custo_m2_mensal", con, if_exists="replace", index=False)
        ufs.to_sql("custo_m2_uf", con, if_exists="replace", index=False)
        ipca.to_sql("ipca", con, if_exists="replace", index=False)

    print(f"Série mensal: {len(mensal)} linhas | {mensal['localidade'].nunique()} localidades | "
          f"{mensal['periodo'].min()} a {mensal['periodo'].max()}")
    print(f"Foto por UF ({arq_uf.stem[-7:]}): {len(ufs)} UFs")
    print(f"Banco SQLite: {DB.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
