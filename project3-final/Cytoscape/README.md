# Cytoscape — Rede PPI e Hub Genes (Long COVID)

Análise visual da rede de interação proteína-proteína (PPI) construída a partir dos dados GEO processados pelo pipeline Medallion em [`../Airflow/`](../Airflow/). O projeto Cytoscape responde à pergunta de pesquisa sobre **nós centrais de alta influência (hub genes)** em pacientes sintomáticos no estágio pós-COVID-19.

Documentação geral do projeto: [`../README.md`](../README.md).

## Conteúdo

| Arquivo | Descrição |
|---------|-----------|
| `TrabalhoP3v2.cys` | Sessão Cytoscape com redes, estilos, filtros e resultados de centralidade salvos. |

## Pré-requisitos

- [Cytoscape](https://cytoscape.org/) 3.x (testado com interface desktop).
- Dados de entrada gerados pelo pipeline Airflow (ver [`../Airflow/README.md`](../Airflow/README.md)).

## Dados de origem

A rede foi montada a partir das saídas Gold e Silver do pipeline:

| Artefato (em `../Airflow/data/`) | Uso no Cytoscape |
|----------------------------------|------------------|
| `gold/gold_edge_ppi_geo.csv` | Arestas PPI (STRING-DB, score ≥ 400) — rede GEO expandida |
| `gold/gold_edge_ppi.csv` | Sub-rede dos 278 genes principais (GEO × NOS0001) |
| `silver/silver_geo_nodes.csv` | Atributos de nós: `symbol`, `log2foldchange`, `pvalue`, `padj`, etc. |

Métricas da rede GEO completa importada: **5.149 nós** e **4.653 arestas** (`combined_score` médio ≈ 0,613).

## Como abrir

1. Execute o pipeline Airflow até gerar as camadas Silver/Gold (DAG `medallion_sample_pipeline`).
2. Abra o Cytoscape.
3. **File → Open** → selecione `TrabalhoP3v2.cys` nesta pasta.
4. Explore as coleções de redes salvas na sessão (rede completa e sub-redes filtradas).

Se precisar reconstruir a rede manualmente, importe `gold_edge_ppi_geo.csv` como rede de arestas e faça merge com `silver_geo_nodes.csv` pelo identificador do gene (`symbol` ou `geneid`).

## Filtros aplicados

Conforme documentado na sessão e nos slides ([`../assets/Slides/`](../assets/Slides/)):

| Filtro | Critério |
|--------|----------|
| Significância estatística | `p-value < 0,05` |
| Magnitude de expressão | `|fold change| > 1` |
| Fenótipo | Remoção de amostras associadas a *brain fog* (melhora a legibilidade da sub-rede inflamatória) |

Esses filtros reduzem o universo analítico em relação aos 2.929 genes significativos totais da camada Silver.

## Análise de centralidade

Sobre a sub-rede filtrada foi calculada a **centralidade de autovetor (Eigenvector Centrality)** via Cytoscape (**Tools → Network Analyzer → Network Analyzer** ou app equivalente).

Cinco genes emergiram como candidatos hub promissores:

| Gene | Papel biológico (resumo) |
|------|--------------------------|
| **IL1B** | Citocina pró-inflamatória |
| **ICAM1** | Adesão celular / inflamação |
| **EGF** | Sinalização de crescimento |
| **SELP** | Seleção de leucócitos (P-selectin) |
| **PF4** | Agregação plaquetária / inflamação |

A combinação de expressão diferencial (log2 fold change) com ranking de autovetor reforça a priorização desses alvos em relação à estatística univariada isolada.

## Relação com outras visualizações

- **Pipeline ETL:** [`../Airflow/`](../Airflow/) — ingestão GEO/EBI, camadas Medallion e consulta STRING-DB.
- **Pathway KEGG map05171:** [`../Airflow/pathwayApp/`](../Airflow/pathwayApp/) — overlay interativo de log2FC sobre a via *Coronavirus disease*.
- **Modelo lógico:** [`../assets/images/modelo-logico-grafos.png`](../assets/images/modelo-logico-grafos.png).

## Exportação e reprodutibilidade

Para exportar resultados a partir do Cytoscape:

- **File → Export → Network to File** — salvar sub-rede filtrada (SIF, XGMML ou CSV).
- **File → Export → Table** — exportar colunas de centralidade e atributos de expressão.

Mantenha a sessão `.cys` versionada junto com os CSVs Gold correspondentes para garantir reprodutibilidade entre execuções do pipeline.
