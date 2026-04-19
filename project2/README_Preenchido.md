# Projeto Identificacao de Hub Genes na Rede Proteomica de Long COVID
# Project Identification of Hub Genes in the Proteomics Network of Long COVID

# Descricao Resumida do Projeto

Este projeto investiga redes proteomicas associadas as sequelas pos-COVID-19 (Long COVID ou PASC - Post-Acute Sequelae of SARS-CoV-2 infection), com foco em ciencia de redes para identificar proteinas centrais (hub genes) relacionadas a sintomas persistentes e multissistemicos. A motivacao vem da alta morbidade da sindrome e da necessidade de integrar dados biologicos complexos para apoiar hipoteses mecanisticas e possiveis alvos terapeuticos.

# Slides

Apresentacao da Entrega 2: `project2/assets/slides/entrega2.pdf` (arquivo final a ser colocado nesta pasta).

# Fundamentacao Teorica

A sindrome pos-COVID-19 exige abordagem de biologia de sistemas para compreender a heterogeneidade clinica observada em pacientes com sintomas persistentes. A literatura recente indica que redes de interacao proteina-proteina (PPI), combinadas com metodos topologicos de grafos, sao adequadas para revelar proteinas reguladoras de alta influencia na progressao da doenca. Em especial, estudos de multi-omica e inferencia causal apontam genes como TP53, CREBBP e SMAD3 como potenciais controladores de rede no contexto de Long COVID. Assim, o projeto prioriza a modelagem da rede biologica para apoiar descoberta de biomarcadores e geracao de hipoteses de intervencao.

# Perguntas de Pesquisa

1. Quais proteinas atuam como nos centrais de alta influencia (hub genes) na rede de interacao de pacientes sintomaticos no estagio pos-COVID-19?
2. Quais modulos de proteinas (comunidades) se associam aos principais grupos de sintomas persistentes da sindrome?
3. Quais caminhos biologicos podem ser priorizados para investigacao translacional a partir dos hubs encontrados?

No estagio atual, a contribuicao direta para essas perguntas esta na definicao da modelagem de rede, no mapeamento das fontes de dados e na especificacao das tecnicas de analise que serao executadas.

# Metodologia

A metodologia segue um fluxo de ciencia de redes em cinco etapas:

1. **Coleta e curadoria de dados**: levantamento de interacoes PPI e bases de suporte clinico/molecular.
2. **Construcao do grafo de propriedades**: modelagem de entidades (proteinas, sintomas, doenca, paciente, farmacos) e relacoes biologicas.
3. **Analise topologica**: calculo de centralidade (grau, betweenness, closeness e autovetor) para priorizar candidatos a hub genes.
4. **Deteccao de comunidades**: identificacao de clusters funcionais para relacionar modulos da rede com fenotipos clinicos.
5. **Interpretacao biologica**: cruzamento dos resultados com literatura e bases de referencia para validar coerencia biologica.

## Bases de Dados e Evolucao

Base de Dados | Endereco na Web | Resumo descritivo
----- | ----- | -----
STRING-DB | https://string-db.org/ | Base principal para recuperar interacoes proteina-proteina (PPI) associadas a COVID-19 e genes de interesse.
NIH RECOVER | https://recovercovid.org/ | Coorte e iniciativa clinica para investigacao de Long COVID, util para contexto fenotipico e estratificacao de sintomas.
GEO (Gene Expression Omnibus) | https://www.ncbi.nlm.nih.gov/geo/ | Repositorio de expressao genica (bulk e single-cell) para apoiar validacao e refinamento de alvos moleculares.

**Evolucao no uso das bases ate aqui**

- **STRING-DB**: definida como fonte principal para extracao inicial da rede PPI.
- **NIH RECOVER**: definida como base de apoio para contextualizacao clinica dos achados de rede.
- **GEO**: definida para futura validacao de padroes de expressao relacionados aos hubs priorizados.

**Transformacoes e tratamentos planejados/executados no estagio atual**

- Padronizacao de identificadores de genes/proteinas entre fontes.
- Definicao de criterios de qualidade para filtrar interacoes (confianca minima e relevancia biologica).
- Estrategia de separacao entre dados brutos (`raw`), intermediarios (`interim`) e consolidados (`processed`) ja estruturada no repositorio.

## Modelo Logico

O modelo logico em grafo de propriedades foi revisado a partir da Entrega 1 e mantem as entidades principais:

- Proteina/Gene
- Sintoma
- Doenca (Long COVID)
- Paciente
- Farmaco
- Virus (SARS-CoV-2)

Relacoes centrais consideradas:

- `Interage_com` (PPI entre proteinas)
- `Causa` (virus -> doenca)
- `Trata` (farmaco -> sintoma)
- `Associado_a`, `Tem_como_Alvo`, `Apresenta`, `Possui`, entre outras relacoes de suporte

Figura do modelo logico:

![Modelo Logico de Grafos](assets/images/modelo-logico-grafos.png)

## Integracao entre Bases

Os principais desafios de integracao identificados sao:

- diferencas de identificadores moleculares entre bases;
- variacao de granularidade entre dados biologicos e dados clinicos;
- necessidade de alinhar evidencias de PPI com fenotipos de Long COVID.

Como estrategia, o grupo definiu um processo incremental: primeiro consolidar a camada molecular (PPI), depois integrar evidencias clinicas e, por fim, qualificar os resultados por suporte bibliografico.

## Analise Preliminar

Neste estagio intermediario, a analise preliminar esta focada na preparacao do pipeline e no desenho do grafo. A execucao completa dos calculos de centralidade e deteccao de comunidades sera apresentada com maior profundidade na entrega final, com figuras quantitativas e comparacao entre modulos da rede.

## Evolucao do Projeto

Da Entrega 1 para a Entrega 2, o projeto evoluiu nos seguintes pontos:

- consolidacao do problema em torno de hub genes em Long COVID;
- refinamento das perguntas de pesquisa para criterios verificaveis;
- maturacao da metodologia de ciencia de redes com etapas explicitas;
- organizacao do repositorio seguindo padrao da disciplina;
- preparacao da estrutura para reproducibilidade de dados e pipelines.

Tambem foram identificadas dificuldades esperadas, especialmente na integracao entre fontes heterogeneas e no balanceamento entre robustez biologica e viabilidade computacional. Essas limitacoes orientaram o planejamento incremental adotado pelo grupo.

# Ferramentas

- **Bases de dados**: STRING-DB, NIH RECOVER, GEO.
- **Analise e processamento**: Python e R (bibliotecas para manipulacao de dados e grafos).
- **Visualizacao de redes**: Cytoscape e recursos graficos de notebooks.
- **Gestao de referencias**: Zotero.
- **Documentacao e colaboracao**: GitHub e markdown.

# Referencias Bibliograficas

1. Sun, J. et al. A multi-omics strategy to understand PASC through the RECOVER cohorts: a paradigm for a systems biology approach to the study of chronic conditions. Frontiers in Systems Biology, 2025. doi:10.3389/fsysb.2024.1422384.
2. Pinero, S. et al. Integrative Multi-Omics Framework for Causal Gene Discovery in Long COVID. PLOS Computational Biology, 2025. doi:10.1371/journal.pcbi.1013725.
3. Zoodsma, M. et al. Targeted proteomics identifies circulating biomarkers associated with active COVID-19 and post-COVID-19. Frontiers in Immunology, 2022. doi:10.3389/fimmu.2022.1027122.
4. Liu, Z. et al. Identification and evaluation of candidate COVID-19 critical genes and medicinal drugs related to plasma cells. BMC Infectious Diseases, 2024. doi:10.1186/s12879-024-10000-3.
5. Carnivali, G. S. Analisando caracteristicas da rede genetica gerada por genes vinculados ao Covid-19. IAJMH, 2020. doi:10.31005/iajmh.v3i0.97.
6. Carnivali, G. S. Study on the interactions between genes linked to COVID-19 and genes expressed in the human body. Journal of Proteomics and Bioinformatics, 2021.
