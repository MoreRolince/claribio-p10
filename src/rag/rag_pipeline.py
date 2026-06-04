"""
S4 — Pipeline RAG complet : ChromaDB → LangChain → llama.cpp
Critère : Réponses ancrées HAS/Vidal, 0 hallucination sur 10 tests
"""
import os
import json
import yaml
from llama_cpp import Llama
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

def load_config(path="config/llm_config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

def load_system_prompt(path="src/llm/prompts/medical_system_prompt.txt") -> str:
    with open(path, encoding="utf-8") as f:
        return f.read().strip()

class ClariBioRAGPipeline:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.llm_cfg = cfg["llm"]
        self.rag_cfg = cfg["rag"]
        self.system_prompt = load_system_prompt()
        self._load_vectorstore()
        self._load_llm()

    def _load_vectorstore(self):
        print("Chargement de la base vectorielle ChromaDB...")
        embeddings = HuggingFaceEmbeddings(
            model_name=self.rag_cfg["embedding_model"],
            model_kwargs={"device": "cpu"}
        )
        self.vectorstore = Chroma(
            collection_name=self.rag_cfg["collection_name"],
            embedding_function=embeddings,
            persist_directory=self.rag_cfg["chroma_persist_dir"]
        )
        print("✅ ChromaDB chargé")

    def _load_llm(self):
        print("Chargement de Mistral 7B...")
        self.llm = Llama(
            model_path=self.llm_cfg["model_path"],
            n_threads=self.llm_cfg["n_threads"],
            n_ctx=self.llm_cfg["n_ctx"],
            n_batch=self.llm_cfg["n_batch"],
            verbose=self.llm_cfg["verbose"]
        )
        print("✅ LLM chargé")

    def retrieve_context(self, query: str) -> tuple[str, list]:
        """Récupère les top-k chunks pertinents depuis ChromaDB."""
        docs = self.vectorstore.similarity_search(query, k=self.rag_cfg["top_k"])
        context_parts = []
        sources = []
        for doc in docs:
            context_parts.append(doc.page_content)
            sources.append(doc.metadata.get("source", "inconnu"))
        context = "\n\n---\n\n".join(context_parts)
        return context, sources

    def format_bilan(self, bilan_json: dict) -> str:
        """Formate le bilan biologique (sortie OCR) en texte lisible pour le LLM."""
        lines = ["Résultats du bilan biologique :"]
        for analyte in bilan_json.get("analytes", []):
            nom = analyte.get("nom", "?")
            valeur = analyte.get("valeur", "?")
            unite = analyte.get("unite", "")
            ref_min = analyte.get("ref_min", "")
            ref_max = analyte.get("ref_max", "")
            statut = analyte.get("statut", "")  # normal / bas / élevé
            ref_str = f"(réf: {ref_min}–{ref_max} {unite})" if ref_min and ref_max else ""
            lines.append(f"- {nom}: {valeur} {unite} {ref_str} → {statut}")
        return "\n".join(lines)

    def analyze(self, bilan_json: dict) -> dict:
        """
        Pipeline complet : bilan JSON → explication clinique LLM.
        
        Args:
            bilan_json: Sortie du module OCR (format schemas/bio_result_schema.json)
        
        Returns:
            dict avec keys: response, sources, context_used
        """
        # 1. Formatter le bilan
        bilan_text = self.format_bilan(bilan_json)

        # 2. Retrieval RAG
        query = f"Interprétation clinique : {bilan_text[:300]}"
        context, sources = self.retrieve_context(query)

        # 3. Construction du prompt complet (format Mistral Instruct)
        user_message = f"""Contexte médical de référence :
{context}

---

{bilan_text}

Génère une explication complète en respectant le format demandé."""

        full_prompt = f"[INST] <<SYS>>\n{self.system_prompt}\n<</SYS>>\n\n{user_message} [/INST]"

        # 4. Génération LLM
        output = self.llm(
            full_prompt,
            max_tokens=self.llm_cfg["max_tokens"],
            temperature=self.llm_cfg["temperature"],
            stop=["[INST]", "</s>"]
        )
        response_text = output["choices"][0]["text"].strip()

        return {
            "response": response_text,
            "sources": sources,
            "context_used": context[:500] + "..." if len(context) > 500 else context
        }


# --- Interface publique pour le connecteur OCR→RAG (src/pipeline/) ---

_pipeline_instance = None

def get_pipeline() -> ClariBioRAGPipeline:
    """Singleton — charge le pipeline une seule fois."""
    global _pipeline_instance
    if _pipeline_instance is None:
        cfg = load_config()
        _pipeline_instance = ClariBioRAGPipeline(cfg)
    return _pipeline_instance

def analyze_bilan(bilan_json: dict) -> dict:
    """Point d'entrée public appelé par ocr_to_rag_connector.py"""
    pipeline = get_pipeline()
    return pipeline.analyze(bilan_json)


if __name__ == "__main__":
    # Test rapide avec un bilan synthétique
    bilan_test = {
        "analytes": [
            {"nom": "TSH", "valeur": 0.08, "unite": "mUI/L", "ref_min": 0.4, "ref_max": 4.0, "statut": "bas"},
            {"nom": "Glycémie", "valeur": 1.32, "unite": "g/L", "ref_min": 0.7, "ref_max": 1.1, "statut": "élevé"},
            {"nom": "Hémoglobine", "valeur": 13.2, "unite": "g/dL", "ref_min": 12.0, "ref_max": 16.0, "statut": "normal"}
        ]
    }
    result = analyze_bilan(bilan_test)
    print("\n=== RÉPONSE CLARIBIO ===\n")
    print(result["response"])
    print(f"\nSources RAG utilisées : {result['sources']}")