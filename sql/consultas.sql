-- Consultas de exemplo sobre o banco data/processed/sinapi.db (SQLite)
-- Cada consulta começa com um comentário "-- name: <nome>" e é executada por src/analise.py,
-- que salva o resultado em reports/consultas/<nome>.csv

-- name: ranking_uf_custo_m2
-- Ranking das UFs pelo custo do m² no último mês, com a fatia de materiais
SELECT ranking_custo                       AS posicao,
       localidade                          AS uf,
       ROUND(custo_total, 2)               AS custo_m2,
       ROUND(custo_material, 2)            AS material,
       ROUND(custo_mao_obra, 2)            AS mao_de_obra,
       ROUND(part_material_pct, 1)         AS pct_material,
       ROUND(variacao_12m_ibge, 2)         AS var_12m_pct
FROM custo_m2_uf
ORDER BY ranking_custo;

-- name: variacao_anual_brasil_sp
-- Variação de dezembro a dezembro (ou até o último mês do ano corrente), usando LAG
WITH fim_de_ano AS (
    SELECT localidade,
           SUBSTR(periodo, 1, 4) AS ano,
           custo_total,
           ROW_NUMBER() OVER (PARTITION BY localidade, SUBSTR(periodo, 1, 4) ORDER BY periodo DESC) AS rn
    FROM custo_m2_mensal
    WHERE localidade IN ('Brasil', 'São Paulo')
)
SELECT localidade,
       ano,
       ROUND(custo_total, 2) AS custo_m2_fim_do_ano,
       ROUND(100.0 * (custo_total / LAG(custo_total) OVER (PARTITION BY localidade ORDER BY ano) - 1), 2) AS var_anual_pct
FROM fim_de_ano
WHERE rn = 1
ORDER BY localidade, ano;

-- name: maiores_altas_mensais_materiais
-- Os 10 meses com maior alta mensal no custo de materiais (Brasil)
SELECT periodo,
       ROUND(custo_material, 2) AS material,
       ROUND(100.0 * (custo_material / LAG(custo_material) OVER (ORDER BY periodo) - 1), 2) AS var_mes_pct
FROM custo_m2_mensal
WHERE localidade = 'Brasil'
ORDER BY var_mes_pct DESC
LIMIT 10;

-- name: regioes_acumulado
-- Alta acumulada desde o início da série, por região, separada em material e mão de obra
SELECT localidade,
       ROUND(indice_total - 100, 1)    AS alta_total_pct,
       ROUND(indice_material - 100, 1) AS alta_material_pct,
       ROUND(indice_mao_obra - 100, 1) AS alta_mao_obra_pct,
       ROUND(custo_total, 2)           AS custo_m2_atual
FROM custo_m2_mensal
WHERE periodo = (SELECT MAX(periodo) FROM custo_m2_mensal)
ORDER BY alta_total_pct DESC;
