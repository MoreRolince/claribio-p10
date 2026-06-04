"""
S2 — Constitution base RAG médicale
Sources : HAS, Vidal, SFB (corpus textuels placés dans data/medical_corpus/)
Critère : Requête sur 5 analytes retourne des chunks pertinents
"""
import os
import glob
import yaml
from tqdm import tqdm
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

def load_config(path="config/llm_config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

def load_corpus(corpus_dir: str) -> list[dict]:
    """Charge tous les fichiers .txt du corpus médical."""
    documents = []
    for filepath in glob.glob(os.path.join(corpus_dir, "**/*.txt"), recursive=True):
        with open(filepath, encoding="utf-8") as f:
            content = f.read().strip()
        if content:
            source = os.path.relpath(filepath, corpus_dir)
            documents.append({"content": content, "source": source})
    print(f"{len(documents)} documents chargés depuis {corpus_dir}")
    return documents

def build_vector_db(cfg: dict):
    rag_cfg = cfg["rag"]

    # 1. Chargement corpus
    corpus_dir = "data/medical_corpus"
    raw_docs = load_corpus(corpus_dir)
    if not raw_docs:
        print("⚠️  Aucun document trouvé — crée des fichiers .txt dans data/medical_corpus/")
        return None

    # 2. Découpage en chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=rag_cfg["chunk_size"],
        chunk_overlap=rag_cfg["chunk_overlap"],
        separators=["\n\n", "\n", ". ", " "]
    )
    all_chunks = []
    all_metadatas = []
    for doc in raw_docs:
        chunks = splitter.split_text(doc["content"])
        all_chunks.extend(chunks)
        all_metadatas.extend([{"source": doc["source"]}] * len(chunks))
    print(f"{len(all_chunks)} chunks générés")

    # 3. Embeddings + indexation ChromaDB
    print("Génération des embeddings (MiniLM-L6-v2)...")
    embeddings = HuggingFaceEmbeddings(
        model_name=rag_cfg["embedding_model"],
        model_kwargs={"device": "cpu"}
    )
    os.makedirs(rag_cfg["chroma_persist_dir"], exist_ok=True)
    vectorstore = Chroma.from_texts(
        texts=all_chunks,
        embedding=embeddings,
        metadatas=all_metadatas,
        collection_name=rag_cfg["collection_name"],
        persist_directory=rag_cfg["chroma_persist_dir"]
    )
    vectorstore.persist()
    print(f"✅ Base ChromaDB créée : {rag_cfg['chroma_persist_dir']}")
    return vectorstore

def validate_retrieval(vectorstore, cfg: dict):
    """Test de validation : 5 analytes doivent retourner des chunks pertinents."""
    test_queries = [
        "Valeurs normales de la TSH",
        "Interprétation glycémie à jeun",
        "Signification clinique hémoglobine basse",
        "Valeurs de référence créatinine",
        "Que signifie une CRP élevée"
    ]
    top_k = cfg["rag"]["top_k"]
    print("\n--- Validation du retrieval ---")
    for query in test_queries:
        results = vectorstore.similarity_search(query, k=top_k)
        print(f"\n🔍 '{query}'")
        for i, doc in enumerate(results, 1):
            snippet = doc.page_content[:120].replace("\n", " ")
            print(f"  [{i}] {snippet}...")
    print("\n✅ Validation retrieval terminée")

if __name__ == "__main__":
    cfg = load_config()
    vectorstore = build_vector_db(cfg)
    if vectorstore:
        validate_retrieval(vectorstore, cfg)