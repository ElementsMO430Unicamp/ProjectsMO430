#!/usr/bin/env python3
"""RAG para classificar sintomas de long COVID associados a genes em gold_geo_nodes.csv.

Fluxo:
  1. index  — indexa genes + conhecimento externo (NCBI, MyGene, arquivos locais)
  2. classify — consulta ChromaDB + Ollama e grava gold_geo_nodes_symptoms.csv

Exemplos (na raiz do repositório):
  python ollama/gene_symptom_rag.py index
  python ollama/gene_symptom_rag.py classify --limit 5
  python ollama/gene_symptom_rag.py classify --model MedAIBase/MedGemma1.5:4b
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import chromadb
import pandas as pd
import requests
from sentence_transformers import SentenceTransformer

OLLAMA_DIR = Path(__file__).resolve().parent
REPO_ROOT = OLLAMA_DIR.parent

COLLECTION_NAME = "gene_symptoms"
DEFAULT_EMBEDDING_MODEL = "NeuML/pubmedbert-base-embeddings"
FALLBACK_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "MedAIBase/MedGemma1.5:4b"
DEFAULT_GENES_CSV = "data/gold/gold_geo_nodes.csv"
DEFAULT_OUTPUT_CSV = "data/gold/gold_geo_nodes_symptoms.csv"
DEFAULT_SYMPTOMS_FILE = str(OLLAMA_DIR / "knowledge" / "long_covid_symptoms.txt")
DEFAULT_PROJECT = str(REPO_ROOT)

NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
MYGENE_API = "https://mygene.info/v3"
NCBI_BATCH_SIZE = 100
NCBI_PAUSE_SEC = 0.35


def load_symptom_taxonomy(path: Path) -> list[str]:
    if not path.is_file():
        return _default_symptoms()
    symptoms: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        symptoms.append(line)
    return symptoms or _default_symptoms()


def _default_symptoms() -> list[str]:
    return [
        "cefaleia",
        "fadiga",
        "dispneia",
        "tosse",
        "mialgia",
        "inflamação",
        "distúrbios gastrointestinais",
        "perda de apetite",
        "brain fog",
        "distúrbios do sono",
    ]


def _safe_str(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    return str(value).strip()


def _chunk_text(text: str, max_chars: int = 700) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    parts = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    current = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(current) + len(part) + 1 <= max_chars:
            current = f"{current} {part}".strip()
        else:
            if current:
                chunks.append(current)
            current = part
    if current:
        chunks.append(current)
    return chunks


class ExternalGeneFetcher:
    """Busca anotações públicas via NCBI Gene e MyGene.info."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, geneid: str) -> Path:
        return self.cache_dir / f"{geneid}.json"

    def fetch(self, geneid: str, symbol: str, force: bool = False) -> dict[str, Any]:
        cache_file = self._cache_path(geneid)
        if cache_file.is_file() and not force:
            return json.loads(cache_file.read_text(encoding="utf-8"))

        ncbi = self._fetch_ncbi(geneid)
        mygene = self._fetch_mygene(geneid)
        payload = {
            "geneid": geneid,
            "symbol": symbol,
            "ncbi": ncbi,
            "mygene": mygene,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(NCBI_PAUSE_SEC)
        return payload

    def _fetch_ncbi(self, geneid: str) -> dict[str, Any]:
        url = f"{NCBI_EUTILS}/esummary.fcgi"
        try:
            response = requests.get(
                url,
                params={"db": "gene", "id": geneid, "retmode": "json"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            gene = data.get("result", {}).get(geneid, {})
            return {
                "description": gene.get("description"),
                "summary": gene.get("summary"),
                "aliases": gene.get("otheraliases"),
                "other_designations": gene.get("otherdesignations"),
            }
        except requests.RequestException as exc:
            return {"error": str(exc)}

    def _fetch_mygene(self, geneid: str) -> dict[str, Any]:
        url = f"{MYGENE_API}/gene/{geneid}"
        fields = "symbol,name,summary,go,disease,pathway"
        try:
            response = requests.get(url, params={"fields": fields}, timeout=30)
            response.raise_for_status()
            data = response.json()
            go_terms: list[str] = []
            go = data.get("go") or {}
            for category in ("BP", "MF", "CC"):
                for entry in go.get(category, []) or []:
                    if not isinstance(entry, str):
                        term = entry.get("term")
                        if term:
                            go_terms.append(term)
            diseases: list[str] = []
            for entry in data.get("disease") or []:
                if isinstance(entry, dict):
                    name = entry.get("name") or entry.get("disease_name")
                    if name:
                        diseases.append(str(name))
                elif entry:
                    diseases.append(str(entry))
            pathways: list[str] = []
            for entry in data.get("pathway") or []:
                if isinstance(entry, dict):
                    name = entry.get("name")
                    if name:
                        pathways.append(str(name))
            return {
                "name": data.get("name"),
                "summary": data.get("summary"),
                "go_terms": sorted(set(go_terms)),
                "diseases": sorted(set(diseases))[:20],
                "pathways": sorted(set(pathways))[:15],
            }
        except requests.RequestException as exc:
            return {"error": str(exc)}


class DisGeNETLoader:
    """Carrega associações gene-doença se o usuário baixou o TSV manualmente."""

    CANDIDATE_FILES = (
        "curated_gene_disease_associations.tsv",
        "curated_gene_disease_associations.tsv.gz",
    )

    def __init__(self, disgenet_dir: Path) -> None:
        self.disgenet_dir = disgenet_dir
        self.by_geneid: dict[str, list[str]] = {}

    def load(self, target_geneids: set[str]) -> int:
        path = self._find_file()
        if path is None:
            return 0

        opener = gzip.open if path.suffix == ".gz" else open
        count = 0
        with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
            header = handle.readline().strip().split("\t")
            gene_col = self._pick_column(header, ("geneid", "geneId", "GeneId", "NCBI_gene_id"))
            disease_col = self._pick_column(
                header, ("disease_name", "diseaseName", "diseaseNameUI", "disease")
            )
            if gene_col is None or disease_col is None:
                print(f"[-] DisGeNET: colunas gene/disease não encontradas em {path.name}")
                return 0

            for line in handle:
                cols = line.rstrip("\n").split("\t")
                if len(cols) <= max(gene_col, disease_col):
                    continue
                geneid = cols[gene_col].strip()
                if geneid not in target_geneids:
                    continue
                disease = cols[disease_col].strip()
                if not disease:
                    continue
                self.by_geneid.setdefault(geneid, [])
                if disease not in self.by_geneid[geneid]:
                    self.by_geneid[geneid].append(disease)
                    count += 1
        print(f"[+] DisGeNET: {count} associações carregadas de {path.name}")
        return count

    def _find_file(self) -> Path | None:
        for name in self.CANDIDATE_FILES:
            path = self.disgenet_dir / name
            if path.is_file():
                return path
        return None

    @staticmethod
    def _pick_column(header: list[str], candidates: tuple[str, ...]) -> int | None:
        normalized = {col.strip().lower(): idx for idx, col in enumerate(header)}
        for candidate in candidates:
            idx = normalized.get(candidate.lower())
            if idx is not None:
                return idx
        return None

    def diseases_for(self, geneid: str) -> list[str]:
        return self.by_geneid.get(str(geneid), [])


class HPOLoader:
    """Carrega fenótipos HPO se genes_to_phenotype.txt estiver em ollama/knowledge/hpo/."""

    CANDIDATE_FILES = ("genes_to_phenotype.txt", "genes_to_phenotype.txt.gz")

    def __init__(self, hpo_dir: Path) -> None:
        self.hpo_dir = hpo_dir
        self.by_geneid: dict[str, list[str]] = {}

    def load(self, target_geneids: set[str]) -> int:
        path = self._find_file()
        if path is None:
            return 0

        opener = gzip.open if path.suffix == ".gz" else open
        count = 0
        with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if line.startswith("#") or not line.strip():
                    continue
                cols = line.rstrip("\n").split("\t")
                if len(cols) < 4:
                    continue
                geneid = cols[0].strip()
                if not geneid.isdigit():
                    continue
                if geneid not in target_geneids:
                    continue
                phenotype = cols[3].strip()
                if not phenotype:
                    continue
                self.by_geneid.setdefault(geneid, [])
                if phenotype not in self.by_geneid[geneid]:
                    self.by_geneid[geneid].append(phenotype)
                    count += 1
        print(f"[+] HPO: {count} fenótipos carregados de {path.name}")
        return count

    def _find_file(self) -> Path | None:
        for name in self.CANDIDATE_FILES:
            path = self.hpo_dir / name
            if path.is_file():
                return path
        return None

    def phenotypes_for(self, geneid: str) -> list[str]:
        return self.by_geneid.get(str(geneid), [])


class STRINGLoader:
    """Carrega anotações STRING filtradas para os genes gold.

    Procura automaticamente em ollama/knowledge/string/:
      - 9606.protein.info.v12.0.gold_genes.txt[.gz]
      - 9606.protein.enrichment.terms.v12.0.gold_genes.txt[.gz]

    Gere esses arquivos com: python scripts/filter_string_for_genes.py
    """

    INFO_FILES = (
        "9606.protein.info.v12.0.gold_genes.txt",
        "9606.protein.info.v12.0.gold_genes.txt.gz",
    )
    ENRICHMENT_FILES = (
        "9606.protein.enrichment.terms.v12.0.gold_genes.txt",
        "9606.protein.enrichment.terms.v12.0.gold_genes.txt.gz",
    )
    INFO_FALLBACK = (
        "9606.protein.info.v12.0.txt",
        "9606.protein.info.v12.0.txt.gz",
    )
    ENRICHMENT_PRIORITY = (
        "Biological Process (Gene Ontology)",
        "Molecular Function (Gene Ontology)",
        "Cellular Component (Gene Ontology)",
        "Annotated Keywords (UniProt)",
        "Disease (Gene Ontology)",
        "Pathway (KEGG)",
        "Pathway (Reactome)",
    )
    MAX_TERMS_PER_CATEGORY = 12

    def __init__(self, string_dir: Path) -> None:
        self.string_dir = string_dir
        self.by_symbol: dict[str, dict[str, Any]] = {}
        self.symbol_to_string_id: dict[str, str] = {}

    @staticmethod
    def _open_text(path: Path):
        if path.suffix == ".gz":
            return gzip.open(path, "rt", encoding="utf-8", errors="replace")
        return path.open("r", encoding="utf-8", errors="replace")

    def _find_file(self, candidates: tuple[str, ...]) -> Path | None:
        for name in candidates:
            path = self.string_dir / name
            if path.is_file():
                return path
        return None

    def load(self, target_symbols: set[str]) -> int:
        info_path = self._find_file(self.INFO_FILES)
        using_fallback = False
        if info_path is None:
            info_path = self._find_file(self.INFO_FALLBACK)
            using_fallback = info_path is not None

        if info_path is None:
            print("[-] STRING: nenhum arquivo protein.info encontrado em ollama/knowledge/string/")
            return 0

        if using_fallback:
            print(
                "[!] STRING: usando protein.info completo (filtro por símbolo). "
                "Para enrichment, rode: python scripts/filter_string_for_genes.py"
            )

        proteins_loaded = self._load_protein_info(info_path, target_symbols)
        enrich_path = self._find_file(self.ENRICHMENT_FILES)
        terms_loaded = 0
        if enrich_path is not None:
            terms_loaded = self._load_enrichment_terms(enrich_path)
        elif self.symbol_to_string_id:
            print(
                "[!] STRING: enrichment filtrado não encontrado. "
                "Rode: python scripts/filter_string_for_genes.py"
            )

        print(
            f"[+] STRING: {proteins_loaded} proteínas, {terms_loaded} termos de enrichment "
            f"({info_path.name}{', ' + enrich_path.name if enrich_path else ''})"
        )
        return proteins_loaded

    def _load_protein_info(self, path: Path, target_symbols: set[str]) -> int:
        count = 0
        with self._open_text(path) as handle:
            header = handle.readline()
            if not header.startswith("#"):
                raise ValueError(f"Cabeçalho inesperado em {path}")

            for line in handle:
                if not line.strip():
                    continue
                cols = line.rstrip("\n").split("\t", 3)
                if len(cols) < 4:
                    continue
                string_id, symbol, _size, annotation = cols
                if symbol not in target_symbols:
                    continue

                self.symbol_to_string_id[symbol] = string_id
                self.by_symbol[symbol] = {
                    "string_id": string_id,
                    "annotation": annotation.strip(),
                    "enrichment": {},
                }
                count += 1
        return count

    def _load_enrichment_terms(self, path: Path) -> int:
        count = 0
        string_id_to_symbol = {v: k for k, v in self.symbol_to_string_id.items()}

        with self._open_text(path) as handle:
            header = handle.readline()
            if not header.startswith("#"):
                raise ValueError(f"Cabeçalho inesperado em {path}")

            for line in handle:
                if not line.strip():
                    continue
                cols = line.rstrip("\n").split("\t", 3)
                if len(cols) < 4:
                    continue
                string_id, category, _term_id, description = cols
                symbol = string_id_to_symbol.get(string_id)
                if symbol is None:
                    continue

                enrichment = self.by_symbol[symbol]["enrichment"]
                bucket = enrichment.setdefault(category, [])
                if description not in bucket:
                    bucket.append(description)
                    count += 1
        return count

    def annotation_for(self, symbol: str) -> str:
        entry = self.by_symbol.get(symbol)
        if not entry:
            return ""
        return entry.get("annotation", "")

    def enrichment_text_for(self, symbol: str) -> str:
        entry = self.by_symbol.get(symbol)
        if not entry:
            return ""

        enrichment: dict[str, list[str]] = entry.get("enrichment") or {}
        if not enrichment:
            return ""

        lines: list[str] = []
        seen_categories = set()

        for category in self.ENRICHMENT_PRIORITY:
            terms = enrichment.get(category)
            if not terms:
                continue
            seen_categories.add(category)
            label = category.replace(" (Gene Ontology)", "")
            lines.append(f"{label}: " + "; ".join(terms[: self.MAX_TERMS_PER_CATEGORY]))

        for category in sorted(enrichment):
            if category in seen_categories:
                continue
            terms = enrichment[category]
            if not terms:
                continue
            label = category.replace(" (Gene Ontology)", "")
            lines.append(f"{label}: " + "; ".join(terms[: self.MAX_TERMS_PER_CATEGORY]))

        return "\n".join(lines)


class GeneSymptomRAG:
    def __init__(
        self,
        project_dir: Path,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        ollama_url: str = DEFAULT_OLLAMA_URL,
    ) -> None:
        self.project_dir = project_dir.resolve()
        self.ollama_dir = OLLAMA_DIR
        self.context_dir = self.ollama_dir / ".contexto"
        self.db_path = self.context_dir / "chroma_db"
        self.cache_dir = self.context_dir / "external_gene_cache"
        self.knowledge_dir = self.ollama_dir / "knowledge"
        self.ollama_url = ollama_url.rstrip("/")

        os.makedirs(self.db_path, exist_ok=True)
        self.encoder = self._load_encoder(embedding_model)
        self.chroma_client = chromadb.PersistentClient(path=str(self.db_path))
        self.collection = self.chroma_client.get_or_create_collection(name=COLLECTION_NAME)
        self.fetcher = ExternalGeneFetcher(self.cache_dir)

    @staticmethod
    def _load_encoder(model_name: str) -> SentenceTransformer:
        try:
            print(f"[+] Carregando encoder: {model_name}")
            return SentenceTransformer(model_name)
        except Exception as exc:
            print(f"[-] Falha ao carregar {model_name}: {exc}")
            print(f"[+] Usando fallback: {FALLBACK_EMBEDDING_MODEL}")
            return SentenceTransformer(FALLBACK_EMBEDDING_MODEL)

    def reset_collection(self) -> None:
        try:
            self.chroma_client.delete_collection(name=COLLECTION_NAME)
        except Exception:
            pass
        self.collection = self.chroma_client.create_collection(name=COLLECTION_NAME)

    def _build_gene_document(
        self,
        row: pd.Series,
        external: dict[str, Any] | None,
        disgenet_diseases: list[str],
        hpo_phenotypes: list[str],
        string_annotation: str,
        string_enrichment: str,
        nih_clusters: list[str],
    ) -> str:
        symbol = _safe_str(row.get("symbol"))
        geneid = _safe_str(row.get("geneid"))
        description = _safe_str(row.get("description"))
        log2fc = _safe_str(row.get("log2foldchange"))
        padj = _safe_str(row.get("padj"))
        direction = "upregulated" if self._is_upregulated(row.get("log2foldchange")) else "downregulated"

        lines = [
            f"Gene symbol: {symbol}",
            f"Gene ID (NCBI): {geneid}",
            f"Descrição GEO: {description}",
            f"Expressão em long COVID: log2FC={log2fc}, padj={padj}, direção={direction}",
        ]

        if external:
            ncbi = external.get("ncbi") or {}
            mygene = external.get("mygene") or {}
            if ncbi.get("summary"):
                lines.append(f"Resumo NCBI: {ncbi['summary']}")
            if mygene.get("summary") and mygene.get("summary") != ncbi.get("summary"):
                lines.append(f"Resumo MyGene: {mygene['summary']}")
            if mygene.get("go_terms"):
                lines.append("Processos GO: " + "; ".join(mygene["go_terms"][:25]))
            if mygene.get("diseases"):
                lines.append("Doenças associadas (MyGene): " + "; ".join(mygene["diseases"][:15]))
            if mygene.get("pathways"):
                lines.append("Vias (MyGene): " + "; ".join(mygene["pathways"][:10]))

        if disgenet_diseases:
            lines.append("Doenças associadas (DisGeNET): " + "; ".join(disgenet_diseases[:20]))

        if hpo_phenotypes:
            lines.append("Fenótipos HPO: " + "; ".join(hpo_phenotypes[:20]))

        if string_annotation:
            lines.append(f"Anotação STRING: {string_annotation[:1200]}")

        if string_enrichment:
            lines.append("Termos STRING (GO/keywords/vias):\n" + string_enrichment)

        if nih_clusters:
            lines.append(
                "Clusters de sintomas observados no estudo (NIH): " + "; ".join(sorted(nih_clusters))
            )

        return "\n".join(lines)

    @staticmethod
    def _is_upregulated(value: Any) -> bool:
        try:
            return float(value) >= 0
        except (TypeError, ValueError):
            return True

    def _load_nih_clusters(self) -> list[str]:
        nih_path = self.project_dir / "data" / "raw" / "nih" / "NIH.csv"
        if not nih_path.is_file():
            return []
        df = pd.read_csv(nih_path)
        if "symptom_cluster" not in df.columns:
            return []
        clusters = df["symptom_cluster"].dropna().astype(str).str.strip()
        clusters = [c for c in clusters.unique().tolist() if c and c.lower() != "nan"]
        return clusters

    def _index_extra_knowledge_files(self) -> list[tuple[str, str, dict[str, str]]]:
        """Indexa .txt/.md em ollama/knowledge/ (exceto taxonomia, README e STRING)."""
        docs: list[tuple[str, str, dict[str, str]]] = []
        if not self.knowledge_dir.is_dir():
            return docs

        skip_names = {
            "long_covid_symptoms.txt",
            "README.md",
            "string_symbols_missing_gold_genes.txt",
            "genes_to_phenotype.txt",
            "curated_gene_disease_associations.tsv",
        }
        structured_dirs = {"string", "hpo", "disgenet"}
        string_prefixes = (
            "9606.protein.info",
            "9606.protein.enrichment.terms",
        )

        for path in sorted(self.knowledge_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".txt", ".md"}:
                continue
            if path.name in skip_names or path.name.upper() == "README.MD":
                continue
            if structured_dirs.intersection(path.parts):
                continue
            if "string" in path.parts and path.name.startswith(string_prefixes):
                continue

            text = path.read_text(encoding="utf-8", errors="replace")
            for idx, chunk in enumerate(_chunk_text(text)):
                docs.append(
                    (
                        f"knowledge::{path.relative_to(self.project_dir)}::{idx}",
                        chunk,
                        {
                            "arquivo": str(path.relative_to(self.project_dir)),
                            "tipo": "conhecimento",
                            "geneid": "",
                            "symbol": "",
                        },
                    )
                )
        return docs

    def index_genes(
        self,
        genes_csv: Path,
        fetch_external: bool = True,
        reset: bool = True,
    ) -> None:
        if not genes_csv.is_file():
            raise FileNotFoundError(f"CSV de genes não encontrado: {genes_csv}")

        if reset:
            self.reset_collection()

        df = pd.read_csv(genes_csv)
        if "geneid" not in df.columns:
            raise ValueError("O CSV precisa da coluna 'geneid'.")

        target_geneids = {str(int(g)) if pd.notna(g) else "" for g in df["geneid"]}
        target_geneids.discard("")
        target_symbols = {_safe_str(s) for s in df["symbol"] if _safe_str(s) != "N/A"}

        disgenet = DisGeNETLoader(self.knowledge_dir / "disgenet")
        disgenet.load(target_geneids)
        hpo = HPOLoader(self.knowledge_dir / "hpo")
        hpo.load(target_geneids)
        string_db = STRINGLoader(self.knowledge_dir / "string")
        string_db.load(target_symbols)
        nih_clusters = self._load_nih_clusters()

        documents: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, str]] = []

        for _, row in df.iterrows():
            geneid = _safe_str(row.get("geneid"))
            symbol = _safe_str(row.get("symbol"))
            external = None
            if fetch_external and geneid != "N/A":
                print(f"[+] Enriquecendo gene {symbol} ({geneid})...")
                external = self.fetcher.fetch(geneid=geneid, symbol=symbol)

            doc = self._build_gene_document(
                row=row,
                external=external,
                disgenet_diseases=disgenet.diseases_for(geneid),
                hpo_phenotypes=hpo.phenotypes_for(geneid),
                string_annotation=string_db.annotation_for(symbol),
                string_enrichment=string_db.enrichment_text_for(symbol),
                nih_clusters=nih_clusters,
            )
            documents.append(doc)
            ids.append(f"gene::{geneid}")
            metadatas.append(
                {
                    "arquivo": str(genes_csv.relative_to(self.project_dir)),
                    "tipo": "gene",
                    "geneid": geneid,
                    "symbol": symbol,
                }
            )

        extra_docs = self._index_extra_knowledge_files()
        for doc_id, doc, meta in extra_docs:
            documents.append(doc)
            ids.append(doc_id)
            metadatas.append(meta)

        if nih_clusters:
            nih_doc = (
                "Contexto clínico do estudo (NIH):\n"
                "Clusters de sintomas registrados em pacientes com PASC/long COVID:\n"
                + "\n".join(f"- {c}" for c in nih_clusters)
            )
            documents.append(nih_doc)
            ids.append("nih::symptom_clusters")
            metadatas.append(
                {
                    "arquivo": "data/raw/nih/NIH.csv",
                    "tipo": "cohort",
                    "geneid": "",
                    "symbol": "",
                }
            )

        embeddings = self.encoder.encode(documents).tolist()
        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
        print(f"\n[+] Indexação concluída: {len(documents)} documentos em {self.db_path}")

    def retrieve(self, query: str, top_k: int = 7, geneid: str | None = None) -> list[dict[str, str]]:
        if self.collection.count() == 0:
            raise RuntimeError("Coleção vazia. Rode 'index' antes de 'classify'.")

        query_embedding = self.encoder.encode([query]).tolist()
        where = {"geneid": str(geneid)} if geneid else None
        try:
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=min(top_k, self.collection.count()),
                where=where,
            )
        except Exception:
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=min(top_k, self.collection.count()),
            )

        docs: list[dict[str, str]] = []
        if not results["documents"] or not results["documents"][0]:
            return docs

        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            docs.append(
                {
                    "texto": doc,
                    "arquivo": meta.get("arquivo", ""),
                    "tipo": meta.get("tipo", ""),
                    "symbol": meta.get("symbol", ""),
                    "geneid": meta.get("geneid", ""),
                }
            )
        return docs

    def ask_ollama(self, prompt: str, model: str, temperature: float = 0.1) -> str:
        url = f"{self.ollama_url}/api/generate"
        response = requests.post(
            url,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=300,
        )
        response.raise_for_status()
        return response.json().get("response", "")

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                raise ValueError("Resposta do Ollama não contém JSON válido.") from None
            return json.loads(match.group(0))

    def build_classification_prompt(
        self,
        row: pd.Series,
        context_chunks: list[dict[str, str]],
        allowed_symptoms: list[str],
    ) -> str:
        symbol = _safe_str(row.get("symbol"))
        geneid = _safe_str(row.get("geneid"))
        description = _safe_str(row.get("description"))
        log2fc = _safe_str(row.get("log2foldchange"))
        padj = _safe_str(row.get("padj"))

        context_text = "\n\n---\n\n".join(
            f"[{chunk.get('tipo', 'doc')} | {chunk.get('arquivo', '')}]\n{chunk['texto']}"
            for chunk in context_chunks
        )
        symptoms_list = "\n".join(f"- {s}" for s in allowed_symptoms)

        return f"""Você é um assistente de bioinformática clínica.
Classifique sintomas de long COVID possivelmente relacionados ao gene abaixo.

Use APENAS o contexto fornecido. Se a evidência for fraca, retorne poucos sintomas e confiança "baixa".
Escolha sintomas SOMENTE da lista permitida.

CONTEXTO RECUPERADO (RAG):
{context_text}

GENE ALVO:
- symbol: {symbol}
- geneid: {geneid}
- descrição GEO: {description}
- log2FC: {log2fc}
- padj: {padj}

SINTOMAS PERMITIDOS:
{symptoms_list}

Responda SOMENTE com JSON válido (sem markdown):
{{
  "symbol": "{symbol}",
  "geneid": "{geneid}",
  "sintomas": ["sintoma1", "sintoma2"],
  "confianca": "alta|media|baixa",
  "justificativa": "1-3 frases em português citando o contexto"
}}
"""

    def classify_gene(
        self,
        row: pd.Series,
        allowed_symptoms: list[str],
        model: str,
        top_k: int = 7,
    ) -> dict[str, Any]:
        symbol = _safe_str(row.get("symbol"))
        geneid = _safe_str(row.get("geneid"))
        query = (
            f"sintomas clínicos, doenças e fenótipos associados ao gene {symbol} "
            f"(geneid {geneid}) em long COVID, inflamação e PASC"
        )
        context = self.retrieve(query=query, top_k=top_k, geneid=geneid)
        if not context:
            context = self.retrieve(query=query, top_k=top_k)

        prompt = self.build_classification_prompt(row, context, allowed_symptoms)
        raw = self.ask_ollama(prompt, model=model)
        parsed = self._extract_json(raw)

        parsed["sintomas"] = [
            s for s in parsed.get("sintomas", []) if s in allowed_symptoms
        ]
        parsed["fontes_rag"] = "; ".join(
            sorted({c.get("arquivo", "") for c in context if c.get("arquivo")})
        )
        parsed["resposta_bruta"] = raw
        return parsed

    def classify_all(
        self,
        genes_csv: Path,
        output_csv: Path,
        symptoms_file: Path,
        model: str,
        limit: int | None = None,
        top_k: int = 7,
    ) -> None:
        if not genes_csv.is_file():
            raise FileNotFoundError(f"CSV de genes não encontrado: {genes_csv}")

        allowed_symptoms = load_symptom_taxonomy(symptoms_file)
        df = pd.read_csv(genes_csv)
        if limit is not None:
            df = df.head(limit)

        rows_out: list[dict[str, Any]] = []
        total = len(df)
        for idx, (_, row) in enumerate(df.iterrows(), start=1):
            symbol = _safe_str(row.get("symbol"))
            print(f"[{idx}/{total}] Classificando {symbol}...")
            try:
                result = self.classify_gene(
                    row=row,
                    allowed_symptoms=allowed_symptoms,
                    model=model,
                    top_k=top_k,
                )
                rows_out.append(
                    {
                        "symbol": result.get("symbol", symbol),
                        "geneid": result.get("geneid", _safe_str(row.get("geneid"))),
                        "sintomas": "; ".join(result.get("sintomas", [])),
                        "confianca": result.get("confianca", "baixa"),
                        "justificativa": result.get("justificativa", ""),
                        "fontes_rag": result.get("fontes_rag", ""),
                    }
                )
            except Exception as exc:
                print(f"[-] Erro em {symbol}: {exc}")
                rows_out.append(
                    {
                        "symbol": symbol,
                        "geneid": _safe_str(row.get("geneid")),
                        "sintomas": "",
                        "confianca": "erro",
                        "justificativa": str(exc),
                        "fontes_rag": "",
                    }
                )

        output_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows_out).to_csv(output_csv, index=False)
        print(f"\n[+] Resultado salvo em: {output_csv}")


def _resolve(project: str, relative: str) -> Path:
    return (Path(project).resolve() / relative).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG gene → sintomas (long COVID) com Ollama")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    parser_index = subparsers.add_parser("index", help="Indexa genes e conhecimento externo")
    parser_index.add_argument(
        "--project",
        type=str,
        default=DEFAULT_PROJECT,
        help="Raiz do repositório (pipeline de dados)",
    )
    parser_index.add_argument(
        "--genes",
        type=str,
        default=DEFAULT_GENES_CSV,
        help="CSV gold com genes (default: data/gold/gold_geo_nodes.csv)",
    )
    parser_index.add_argument(
        "--no-fetch-external",
        action="store_true",
        help="Não consultar NCBI/MyGene (usa só CSV + arquivos locais)",
    )
    parser_index.add_argument(
        "--no-reset",
        action="store_true",
        help="Não recriar a coleção ChromaDB (append não suportado; use só se souber o que faz)",
    )

    parser_classify = subparsers.add_parser("classify", help="Classifica sintomas via RAG + Ollama")
    parser_classify.add_argument("--project", type=str, default=DEFAULT_PROJECT)
    parser_classify.add_argument("--genes", type=str, default=DEFAULT_GENES_CSV)
    parser_classify.add_argument("--output", type=str, default=DEFAULT_OUTPUT_CSV)
    parser_classify.add_argument(
        "--symptoms-file",
        type=str,
        default=DEFAULT_SYMPTOMS_FILE,
        help="Lista de sintomas permitidos (um por linha)",
    )
    parser_classify.add_argument("--model", type=str, default=DEFAULT_OLLAMA_MODEL)
    parser_classify.add_argument("--ollama-url", type=str, default=DEFAULT_OLLAMA_URL)
    parser_classify.add_argument("--limit", type=int, default=None, help="Processar só N genes (piloto)")
    parser_classify.add_argument("--top-k", type=int, default=7)

    args = parser.parse_args()
    project = Path(args.project).resolve()

    if args.comando == "index":
        rag = GeneSymptomRAG(project_dir=project)
        rag.index_genes(
            genes_csv=_resolve(args.project, args.genes),
            fetch_external=not args.no_fetch_external,
            reset=not args.no_reset,
        )
    elif args.comando == "classify":
        rag = GeneSymptomRAG(project_dir=project, ollama_url=args.ollama_url)
        rag.classify_all(
            genes_csv=_resolve(args.project, args.genes),
            output_csv=_resolve(args.project, args.output),
            symptoms_file=_resolve(args.project, args.symptoms_file),
            model=args.model,
            limit=args.limit,
            top_k=args.top_k,
        )


if __name__ == "__main__":
    main()
