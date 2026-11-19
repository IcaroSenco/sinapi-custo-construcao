"""
Análise: gera os gráficos (reports/figures/), executa as consultas SQL (reports/consultas/)
e escreve um resumo com os principais números (reports/resumo.md).

Uso:
    python src/analise.py
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"
FIG = RAIZ / "reports" / "figures"
CONS = RAIZ / "reports" / "consultas"
DB = PROC / "sinapi.db"

# Paleta categórica (ordem fixa) e tintas de texto
AZUL, LARANJA, VERDE_AGUA = "#2a78d6", "#eb6834", "#1baf7a"
CINZA_REF = "#8a8984"
TINTA, TINTA_2, GRADE, FUNDO = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": FUNDO, "axes.facecolor": FUNDO, "savefig.facecolor": FUNDO,
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.edgecolor": GRADE, "axes.labelcolor": TINTA_2, "axes.titlecolor": TINTA,
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "xtick.color": TINTA_2, "ytick.color": TINTA_2,
    "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "legend.frameon": False, "legend.labelcolor": TINTA,
    "lines.linewidth": 2,
})

reais = FuncFormatter(lambda v, _: f"R$ {v:,.0f}".replace(",", "."))
pct = FuncFormatter(lambda v, _: f"{v:.0f}%")


def br(v: float, casas: int = 1) -> str:
    """Número no formato brasileiro."""
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mes_txt(periodo: str) -> str:
    meses = "jan fev mar abr mai jun jul ago set out nov dez".split()
    ano, mes = periodo.split("-")
    return f"{meses[int(mes) - 1]}/{ano}"


def rodape(fig, texto: str = "Fonte: IBGE/Caixa – SINAPI (tabela 2296) e IPCA (tabela 1737). Elaboração: Icaro F. de Senço.") -> None:
    fig.text(0.01, 0.01, texto, fontsize=8, color=TINTA_2, ha="left", va="bottom")


def eixo_tempo(ax, x=None) -> None:
    if x is not None:
        anos = range(x.iloc[0].year, x.iloc[-1].year + 1, 2)
        ax.set_xticks([pd.Timestamp(f"{a}-01-01") for a in anos])
    else:
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="x", visible=False)


def rotulo_final(ax, x, y, texto, cor_marca) -> None:
    ax.plot([x], [y], "o", ms=5, color=cor_marca, mec=FUNDO, mew=2, zorder=5)
    ax.annotate(texto, (x, y), xytext=(6, 0), textcoords="offset points", va="center",
                fontsize=9, color=TINTA)


def fig_indices(br_df: pd.DataFrame, ipca_rel: pd.Series, ini: str, fim: str) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.6))
    x = br_df["data"]
    series = [
        (br_df["indice_material"], "Materiais", AZUL),
        (br_df["indice_total"], "Custo total do m²", LARANJA),
        (br_df["indice_mao_obra"], "Mão de obra", VERDE_AGUA),
        (ipca_rel, "IPCA (inflação geral)", CINZA_REF),
    ]
    for y, nome, cor in series:
        ax.plot(x, y, color=cor, label=nome, ls="--" if cor == CINZA_REF else "-")
        rotulo_final(ax, x.iloc[-1], y.iloc[-1], f"{nome.split(' (')[0]}: +{br(y.iloc[-1] - 100, 0)}%", cor)
    ax.axhline(100, color=TINTA_2, lw=0.8)
    ax.set_title(f"Custo da construção no Brasil subiu mais que a inflação ({mes_txt(ini)} = 100)")
    ax.set_ylabel("Índice")
    eixo_tempo(ax, x)
    ax.set_xlim(x.iloc[0], x.iloc[-1] + pd.Timedelta(days=900))
    ax.legend(loc="upper left", ncol=2)
    rodape(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = FIG / "01_indices_vs_ipca.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def fig_var12(br_df: pd.DataFrame) -> Path:
    d = br_df.dropna(subset=["var_12m_material_pct"])
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(d["data"], d["var_12m_material_pct"], color=AZUL, label="Materiais")
    ax.plot(d["data"], d["var_12m_mao_obra_pct"], color=VERDE_AGUA, label="Mão de obra")
    pico = d.loc[d["var_12m_material_pct"].idxmax()]
    ax.annotate(f"Pico: +{br(pico['var_12m_material_pct'])}% em 12 meses\n({mes_txt(pico['periodo'])})",
                (pico["data"], pico["var_12m_material_pct"]), xytext=(25, -10), textcoords="offset points",
                fontsize=9, color=TINTA, arrowprops=dict(arrowstyle="-", color=TINTA_2, lw=0.8))
    ax.axhline(0, color=TINTA_2, lw=0.8)
    ax.yaxis.set_major_formatter(pct)
    ax.set_title("Variação em 12 meses do custo do m² – Brasil")
    eixo_tempo(ax)
    ax.legend(loc="upper left")
    rodape(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = FIG / "02_variacao_12_meses.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def fig_real(br_df: pd.DataFrame, sp_df: pd.DataFrame, fim: str) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5))
    for d, nome, cor in [(sp_df, "São Paulo", AZUL), (br_df, "Brasil", LARANJA)]:
        ax.plot(d["data"], d["custo_total_real"], color=cor, label=nome)
        rotulo_final(ax, d["data"].iloc[-1], d["custo_total_real"].iloc[-1],
                     f"{nome}: R$ {br(d['custo_total_real'].iloc[-1], 0)}", cor)
    ax.yaxis.set_major_formatter(reais)
    ax.set_title(f"Custo do m² corrigido pela inflação (valores em R$ de {mes_txt(fim)})")
    eixo_tempo(ax, br_df["data"])
    ax.set_xlim(br_df["data"].iloc[0], br_df["data"].iloc[-1] + pd.Timedelta(days=700))
    ax.legend(loc="upper left")
    rodape(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = FIG / "03_custo_real_brasil_sp.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def fig_uf(uf: pd.DataFrame, media_br: float, fim: str) -> Path:
    d = uf.sort_values("custo_total")
    fig, ax = plt.subplots(figsize=(10, 8.5))
    ax.set_axisbelow(True)
    y = range(len(d))
    ax.barh(y, d["custo_material"], color=AZUL, height=0.72, label="Materiais", edgecolor=FUNDO, linewidth=1)
    ax.barh(y, d["custo_mao_obra"], left=d["custo_material"], color=VERDE_AGUA, height=0.72,
            label="Mão de obra", edgecolor=FUNDO, linewidth=1)
    for i, (_, r) in enumerate(d.iterrows()):
        destaque = r["localidade"] == "São Paulo"
        ax.text(r["custo_total"] + 15, i, f"R$ {br(r['custo_total'], 0)}", va="center", fontsize=8.5,
                color=TINTA, fontweight="bold" if destaque else "normal",
                bbox=dict(facecolor=FUNDO, edgecolor="none", pad=0.5), zorder=4)
    ax.set_yticks(list(y))
    ax.set_yticklabels(d["localidade"])
    for lbl in ax.get_yticklabels():
        if lbl.get_text() == "São Paulo":
            lbl.set_fontweight("bold")
            lbl.set_color(TINTA)
    ax.xaxis.set_major_formatter(reais)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, d["custo_total"].max() * 1.12)
    ax.set_title(f"Custo do m² por estado – {mes_txt(fim)} (média Brasil: R$ {br(media_br, 0)})")
    ax.legend(loc="lower right")
    rodape(fig)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    out = FIG / "04_ranking_estados.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def rodar_consultas() -> dict[str, pd.DataFrame]:
    CONS.mkdir(parents=True, exist_ok=True)
    texto = (RAIZ / "sql" / "consultas.sql").read_text(encoding="utf-8")
    blocos = re.split(r"^-- name: (\w+)\s*$", texto, flags=re.M)[1:]
    resultados = {}
    with sqlite3.connect(DB) as con:
        for nome, sql in zip(blocos[::2], blocos[1::2]):
            df = pd.read_sql_query(sql, con)
            df.to_csv(CONS / f"{nome}.csv", index=False)
            resultados[nome] = df
    return resultados


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    m = pd.read_csv(PROC / "custo_m2_mensal.csv", parse_dates=["data"], dtype={"localidade_id": str})
    uf = pd.read_csv(PROC / "custo_m2_uf_ultimo_mes.csv", dtype={"localidade_id": str})

    br_df = m[m["localidade"] == "Brasil"].reset_index(drop=True)
    sp_df = m[(m["localidade"] == "São Paulo")].reset_index(drop=True)
    ini, fim = br_df["periodo"].iloc[0], br_df["periodo"].iloc[-1]
    ipca_rel = 100 * br_df["ipca_indice"] / br_df["ipca_indice"].iloc[0]

    figs = [fig_indices(br_df, ipca_rel, ini, fim), fig_var12(br_df), fig_real(br_df, sp_df, fim),
            fig_uf(uf, br_df["custo_total"].iloc[-1], fim)]
    cons = rodar_consultas()

    # ---- Resumo com os números principais ----
    ult_br, ult_sp = br_df.iloc[-1], sp_df.iloc[-1]
    alta_ipca = ipca_rel.iloc[-1] - 100
    ganho_real_br = 100 * (ult_br["custo_total_real"] / br_df["custo_total_real"].iloc[0] - 1)
    ganho_real_sp = 100 * (ult_sp["custo_total_real"] / sp_df["custo_total_real"].iloc[0] - 1)
    pico = br_df.loc[br_df["var_12m_material_pct"].idxmax()]
    top, base = uf.iloc[0], uf.iloc[-1]
    pos_sp = int(uf.loc[uf["localidade"] == "São Paulo", "ranking_custo"].iloc[0])
    reg = cons["regioes_acumulado"]

    linhas = [
        f"# Resumo – custo da construção (SINAPI), {mes_txt(ini)} a {mes_txt(fim)}",
        "",
        f"- O custo médio do m² no **Brasil** foi de R$ {br(br_df['custo_total'].iloc[0], 2)} para "
        f"**R$ {br(ult_br['custo_total'], 2)}** (+{br(ult_br['indice_total'] - 100)}%). "
        f"No mesmo período, a inflação (IPCA) foi de +{br(alta_ipca)}%.",
        f"- Descontada a inflação, o m² ficou **{br(ganho_real_br)}% mais caro** no Brasil e "
        f"{br(ganho_real_sp)}% em São Paulo.",
        f"- **Materiais** subiram +{br(ult_br['indice_material'] - 100)}% e **mão de obra** "
        f"+{br(ult_br['indice_mao_obra'] - 100)}%. A fatia de materiais no custo do m² passou de "
        f"{br(br_df['part_material_pct'].iloc[0])}% para {br(ult_br['part_material_pct'])}%.",
        f"- O pico da alta de materiais foi em **{mes_txt(pico['periodo'])}**: "
        f"+{br(pico['var_12m_material_pct'])}% em 12 meses (efeito da pandemia nas cadeias de insumos).",
        f"- Em {mes_txt(fim)}, o m² mais caro era o de **{top['localidade']}** (R$ {br(top['custo_total'], 2)}) e o "
        f"mais barato o de **{base['localidade']}** (R$ {br(base['custo_total'], 2)}). "
        f"São Paulo ocupava a {pos_sp}ª posição (R$ {br(ult_sp['custo_total'], 2)}).",
        f"- Entre as regiões, a maior alta acumulada foi no **{reg.iloc[0]['localidade']}** "
        f"(+{br(reg.iloc[0]['alta_total_pct'])}%).",
        "",
        "Gráficos em `reports/figures/` e resultados das consultas SQL em `reports/consultas/`.",
    ]
    (RAIZ / "reports" / "resumo.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    print("\n".join(linhas))
    print("\nGráficos:", *[f.relative_to(RAIZ) for f in figs], sep="\n  ")


if __name__ == "__main__":
    main()
