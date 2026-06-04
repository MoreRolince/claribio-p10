"""
S2 — Déploiement Mistral 7B Q4_K_M
Critère : RAM < 6 Go, vitesse documentée
"""
import os
import time
import yaml
import psutil
from llama_cpp import Llama

def load_config(path="config/llm_config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

def download_model():
    """Télécharge le modèle depuis Hugging Face si absent."""
    from huggingface_hub import hf_hub_download
    os.makedirs("models", exist_ok=True)
    print("Téléchargement de Mistral 7B Q4_K_M (~4.1 Go)...")
    path = hf_hub_download(
        repo_id="TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
        filename="mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        local_dir="models"
    )
    print(f"Modèle téléchargé : {path}")
    return path

def benchmark_llm(cfg: dict):
    """Mesure RAM utilisée et vitesse de génération (tokens/s)."""
    llm_cfg = cfg["llm"]
    
    if not os.path.exists(llm_cfg["model_path"]):
        download_model()
    
    print("Chargement du modèle...")
    ram_before = psutil.virtual_memory().used / 1024**3

    llm = Llama(
        model_path=llm_cfg["model_path"],
        n_threads=llm_cfg["n_threads"],
        n_ctx=llm_cfg["n_ctx"],
        n_batch=llm_cfg["n_batch"],
        verbose=llm_cfg["verbose"]
    )

    ram_after = psutil.virtual_memory().used / 1024**3
    ram_used = ram_after - ram_before
    print(f"RAM utilisée par le modèle : {ram_used:.2f} Go")
    assert ram_used < 6, f"ERREUR : RAM > 6 Go ({ram_used:.2f} Go)"

    prompt = "[INST] Explique brièvement ce qu'est la TSH en biologie médicale. [/INST]"
    start = time.time()
    output = llm(prompt, max_tokens=200, temperature=0.1)
    elapsed = time.time() - start

    tokens = output["usage"]["completion_tokens"]
    speed = tokens / elapsed
    print(f"Vitesse : {speed:.1f} tokens/s sur {tokens} tokens en {elapsed:.1f}s")
    print(f"\nRéponse test :\n{output['choices'][0]['text']}")

    return {"ram_go": ram_used, "tokens_per_sec": speed}

if __name__ == "__main__":
    cfg = load_config()
    results = benchmark_llm(cfg)
    print(f"\n✅ Benchmark OK — RAM: {results['ram_go']:.2f} Go, Vitesse: {results['tokens_per_sec']:.1f} tok/s")