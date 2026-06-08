# Ollama + RAG — classificação de sintomas por gene

Esta pasta concentra tudo relacionado ao **Ollama** (LLM local) e à **RAG** (`gene_symptom_rag.py`) que classifica sintomas de long COVID para os genes em `data/gold/gold_geo_nodes.csv`.

```text
ollama/
├── docker-compose.yml          # serviço Ollama
├── gene_symptom_rag.py         # index + classify (RAG + API Ollama)
├── requirements-rag.txt        # dependências Python da RAG
├── knowledge/                  # bases externas (STRING, HPO, DisGeNET, …)
├── scripts/
│   └── filter_string_for_genes.py
└── .contexto/                  # cache ChromaDB + NCBI/MyGene (gerado no index)
```

---

## Pré-requisitos

- **Docker** instalado e em execução
- **Python 3.10+** (para a RAG) — ou use o container Python descrito abaixo
- Pipeline gold já gerada: `data/gold/gold_geo_nodes.csv`

---

## 1. Subir o Ollama com Docker Compose

Na pasta `ollama/`:

```bash
cd ollama
docker compose up -d
```

Verifique se o container está rodando:

```bash
docker compose ps
curl http://localhost:11434/api/tags
```

### Container `ollama` já existe

Se aparecer erro de nome em conflito:

```bash
docker stop ollama
docker rm ollama
docker compose up -d
```

### Baixar o modelo (MedGemma 1.5 — foco clínico/biomédico)

```bash
docker exec -it ollama ollama pull MedAIBase/MedGemma1.5:4b
```

Ou, equivalente ao `ollama run`:

```bash
docker exec -it ollama ollama run MedAIBase/MedGemma1.5:4b
```

Na primeira execução o Ollama baixa o modelo automaticamente.

```bash
docker exec -it ollama ollama run MedAIBase/MedGemma1.5:4b "Responda apenas: OK"
```

### Parar / remover

```bash
docker compose down          # para o serviço
docker compose down -v       # para e remove o volume de modelos
```

---

## 2. API do Ollama (sem RAG)

O Ollama expõe HTTP em **`http://localhost:11434`**.

### Listar modelos instalados

```bash
curl http://localhost:11434/api/tags
```

### Gerar texto (endpoint `/api/generate`)

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "MedAIBase/MedGemma1.5:4b",
  "prompt": "Liste 3 sintomas comuns de long COVID.",
  "stream": false
}'
```

### Chat (endpoint `/api/chat`)

```bash
curl http://localhost:11434/api/chat -d '{
  "model": "MedAIBase/MedGemma1.5:4b",
  "messages": [
    {"role": "user", "content": "O que é PASC?"}
  ],
  "stream": false
}'
```

Resposta útil: campo `response` (generate) ou `message.content` (chat).

---

## 3. Instalar dependências da RAG

Os comandos abaixo devem ser executados na **raiz do repositório** (`mo430-data-pipeline/`).

### Opção A — Container Python (recomendada se o venv local falhar)

```bash
cd ..   # raiz do repo, se ainda estiver em ollama/

docker run --rm -it \
  -v "$PWD:/app" \
  -w /app \
  --network host \
  python:3.12 \
  bash
```

Dentro do container (rede UNICAMP pode exigir `--trusted-host`):

```bash
pip install --trusted-host pypi.org \
            --trusted-host files.pythonhosted.org \
            -r ollama/requirements-rag.txt
```

### Opção B — venv local

```bash
python3 -m venv ollama/.venv-rag
source ollama/.venv-rag/bin/activate
pip install -r ollama/requirements-rag.txt
```

---

## 4. RAG + Ollama: fluxo completo

A RAG **não substitui** a API do Ollama — ela **prepara contexto** (genes, STRING, HPO, NCBI, …) e **envia um prompt** ao Ollama via `/api/generate`.

```text
gold_geo_nodes.csv + ollama/knowledge/
        │
        ▼
   gene_symptom_rag.py index
        │
        ├── ChromaDB (ollama/.contexto/chroma_db)
        └── cache NCBI/MyGene (ollama/.contexto/external_gene_cache/)
        │
        ▼
   gene_symptom_rag.py classify
        │
        ├── busca top-k chunks no ChromaDB (por gene)
        ├── monta prompt com sintomas permitidos
        ├── POST http://localhost:11434/api/generate
        └── grava data/gold/gold_geo_nodes_symptoms.csv
```

### Passo 1 — Indexar conhecimento

Na raiz do repo (com dependências instaladas):

```bash
python ollama/gene_symptom_rag.py index
```

Opções úteis:

| Flag | Efeito |
|------|--------|
| `--no-fetch-external` | Não consulta NCBI/MyGene (só arquivos locais) |
| `--genes data/gold/gold_geo_nodes.csv` | CSV de entrada (default) |

Indexação completa com APIs externas leva alguns minutos (~279 genes).

### Passo 2 — Classificar sintomas

Piloto (5 genes):

```bash
python ollama/gene_symptom_rag.py classify --limit 5
```

Classificação completa:

```bash
python ollama/gene_symptom_rag.py classify
```

Opções úteis:

| Flag | Default | Descrição |
|------|---------|-----------|
| `--model` | `MedAIBase/MedGemma1.5:4b` | Modelo Ollama |
| `--ollama-url` | `http://localhost:11434` | URL da API |
| `--output` | `data/gold/gold_geo_nodes_symptoms.csv` | Saída |
| `--limit N` | — | Processar só N genes |
| `--top-k` | `7` | Chunks RAG por gene |

### Passo 3 — Conferir resultado

```bash
head data/gold/gold_geo_nodes_symptoms.csv
```

Colunas: `symbol`, `geneid`, `sintomas`, `confianca`, `justificativa`, `fontes_rag`.

---

## 5. Ollama a partir do container Python

Se a RAG roda **dentro** de um container e o Ollama no host, use:

```bash
python ollama/gene_symptom_rag.py classify \
  --ollama-url http://localhost:11434 \
  --limit 5
```

Com `--network host`, `localhost:11434` funciona. Sem isso, use o IP do host ou conecte os dois serviços na mesma rede Docker.

---

## 6. Bases de conhecimento (`knowledge/`)

| Pasta / arquivo | Conteúdo |
|-----------------|----------|
| `knowledge/string/` | Anotações STRING (filtradas com `scripts/filter_string_for_genes.py`) |
| `knowledge/hpo/genes_to_phenotype.txt` | Fenótipos HPO |
| `knowledge/disgenet/` | Associações gene–doença (download manual) |
| `knowledge/long_covid_symptoms.txt` | Vocabulário fechado de sintomas |

Detalhes e links de download: [`knowledge/README.md`](knowledge/README.md).

Filtrar STRING para os genes gold:

```bash
python ollama/scripts/filter_string_for_genes.py
```

---

## 7. Solução de problemas

| Problema | O que fazer |
|----------|-------------|
| `Conflict. The container name "/ollama" is already in use` | `docker stop ollama && docker rm ollama`, depois `docker compose up -d` |
| `Connection refused` na porta 11434 | `docker compose ps` — container parado? |
| `No module named chromadb` | Instale `ollama/requirements-rag.txt` |
| Erro SSL no `pip` (rede UNICAMP) | Use `--trusted-host pypi.org --trusted-host files.pythonhosted.org` |
| `Coleção vazia` no classify | Rode `index` antes de `classify` |
| Modelo não encontrado | `docker exec -it ollama ollama pull MedAIBase/MedGemma1.5:4b` |

---

## Referência rápida

```bash
# Ollama
cd ollama && docker compose up -d
docker exec -it ollama ollama pull MedAIBase/MedGemma1.5:4b

# RAG (na raiz do repo)
python ollama/gene_symptom_rag.py index
python ollama/gene_symptom_rag.py classify --limit 5
python ollama/gene_symptom_rag.py classify --model MedAIBase/MedGemma1.5:4b
```

Documentação oficial Ollama: https://github.com/ollama/ollama/blob/main/docs/api.md
