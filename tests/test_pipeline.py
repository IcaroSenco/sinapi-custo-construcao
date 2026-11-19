"""Testes do pipeline (rodar com: python -m pytest -q)."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import coleta  # noqa: E402
import tratamento  # noqa: E402

# Recorte no mesmo formato que a API v3 do IBGE devolve
RESPOSTA_API = [
    {
        "id": "48",
        "variavel": "Custo médio m² - moeda corrente",
        "unidade": "Reais",
        "resultados": [{
            "classificacoes": [],
            "series": [{
                "localidade": {"id": "35", "nivel": {"id": "N3", "nome": "Unidade da Federação"}, "nome": "São Paulo"},
                "serie": {"202609": "2093.45", "202610": "2096.45", "202608": "..."},
            }],
        }],
    }
]


def test_consultar_converte_para_formato_longo(monkeypatch):
    monkeypatch.setattr(coleta, "_get", lambda url: RESPOSTA_API)
    linhas = coleta.consultar("2296", "202608-202610", ["48"], "N3[35]")
    # o valor "..." (sem dado) é descartado e os períodos ficam ordenados
    assert linhas == [
        ["2026-09", "N3", "35", "São Paulo", "48", "Custo médio m² - moeda corrente", "2093.45"],
        ["2026-10", "N3", "35", "São Paulo", "48", "Custo médio m² - moeda corrente", "2096.45"],
    ]


def test_dados_tratados_sao_consistentes():
    raw = tratamento.RAW
    mensal = tratamento.tratar_mensal(
        tratamento.ler_longo(raw / "sinapi_custo_m2_mensal.csv"),
        tratamento.ler_longo(raw / "ipca_indice_mensal.csv"),
    )
    # total = material + mão de obra
    soma = mensal["custo_material"] + mensal["custo_mao_obra"]
    assert ((mensal["custo_total"] - soma).abs() < 0.05).all()
    # índice começa em 100 e, no último mês, o valor real é igual ao nominal
    primeiro = mensal.groupby("localidade").first()
    ultimo = mensal.groupby("localidade").last()
    assert (primeiro["indice_total"].round(6) == 100).all()
    assert ((ultimo["custo_total_real"] - ultimo["custo_total"]).abs() < 1e-6).all()


def test_variacao_12m_bate_com_a_publicada_pelo_ibge():
    """A variação em 12 meses calculada para SP deve bater com a variável 1198 publicada pelo IBGE."""
    raw = tratamento.RAW
    mensal = tratamento.tratar_mensal(
        tratamento.ler_longo(raw / "sinapi_custo_m2_mensal.csv"),
        tratamento.ler_longo(raw / "ipca_indice_mensal.csv"),
    )
    uf = tratamento.tratar_uf(tratamento.ler_longo(sorted(raw.glob("sinapi_uf_*.csv"))[-1]))
    calculada = mensal.query("localidade == 'São Paulo'")["var_12m_total_pct"].iloc[-1]
    publicada = uf.query("localidade == 'São Paulo'")["variacao_12m_ibge"].iloc[0]
    assert abs(calculada - publicada) < 0.01
    # e o custo do m² de SP na série mensal é o mesmo da foto por UF
    assert abs(mensal.query("localidade == 'São Paulo'")["custo_total"].iloc[-1]
               - uf.query("localidade == 'São Paulo'")["custo_total"].iloc[0]) < 0.005
    assert isinstance(uf, pd.DataFrame) and len(uf) == 27
