"""
Interface web FastAPI — ClariBio
Auteur : IMBOYO MUANAMBELO DONBENI — ClariBio P10 — S5

Critère : Interface accessible depuis navigateur sur même réseau, sans internet
Port : 8080
"""

import io
import json
import logging
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Chemins
BASE_DIR    = Path(__file__).parent
STATIC_DIR  = BASE_DIR / "static"
UPLOAD_DIR  = Path("/tmp/claribio_uploads")
REPORT_DIR  = Path("/tmp/claribio_reports")

UPLOAD_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# App FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ClariBio",
    description="Assistant médical IA local — Interprétation de bilans biologiques",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Historique de session (en mémoire — pas de données réelles persistées)
_session_history: list[dict] = []

# WebSocket connections actives
_ws_clients: list[WebSocket] = []


# ---------------------------------------------------------------------------
# Schémas Pydantic
# ---------------------------------------------------------------------------

class AnalyseRequest(BaseModel):
    texte_manuel: str | None = None
    session_id: str | None = None


class AnalyseResponse(BaseModel):
    session_id: str
    analytes: list[dict]
    explication: str
    questions: list[str]
    statut: str


# ---------------------------------------------------------------------------
# Utilitaires pipeline
# ---------------------------------------------------------------------------

def _run_ocr(file_bytes: bytes, filename: str) -> dict:
    """Lance l'OCR sur le document uploadé."""
    try:
        sys.path.insert(0, str(BASE_DIR.parent))
        # Import dynamique pour éviter les erreurs si module pas encore disponible
        from ocr.bio_parser import parse_biological_report  # type: ignore
        return parse_biological_report(file_bytes, filename)
    except ImportError:
        logger.warning("Module OCR non disponible — données de démonstration")
        return _demo_ocr_result()
    except Exception as e:
        logger.error(f"Erreur OCR : {e}")
        return _demo_ocr_result()


def _run_rag_llm(ocr_result: dict) -> dict:
    """Lance le pipeline RAG + LLM."""
    try:
        from rag.rag_pipeline import analyze  # type: ignore
        return analyze(ocr_result)
    except ImportError:
        logger.warning("Module RAG/LLM non disponible — réponse de démonstration")
        return _demo_llm_result(ocr_result)
    except Exception as e:
        logger.error(f"Erreur RAG/LLM : {e}")
        return _demo_llm_result(ocr_result)


def _generate_pdf(analysis: dict, session_id: str) -> str:
    """Génère le rapport PDF et retourne son chemin."""
    try:
        from output.pdf_generator import PDFGenerator  # type: ignore
        output_path = str(REPORT_DIR / f"rapport_{session_id}.pdf")
        PDFGenerator().generate(analysis, output_path=output_path)
        return output_path
    except Exception as e:
        logger.error(f"Erreur PDF : {e}")
        return ""


async def _broadcast(message: dict):
    """Envoie un message à tous les clients WebSocket connectés."""
    disconnected = []
    for ws in _ws_clients:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _ws_clients.remove(ws)


# ---------------------------------------------------------------------------
# Routes API
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    """Page principale de l'interface."""
    return _html_interface()


@app.post("/api/upload", response_model=AnalyseResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload d'un document biologique (photo JPG/PNG ou PDF).
    Lance le pipeline OCR → RAG → LLM.
    """
    session_id = str(uuid.uuid4())[:8]
    t0 = time.time()

    # Validation du fichier
    allowed = {".jpg", ".jpeg", ".png", ".pdf"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"Format non supporté : {ext}. Acceptés : {allowed}")

    # Lecture du fichier
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(400, "Fichier vide")

    await _broadcast({"event": "progress", "step": "ocr", "message": "Lecture du document..."})

    # Pipeline
    ocr_result  = _run_ocr(file_bytes, file.filename or "document")
    await _broadcast({"event": "progress", "step": "llm", "message": "Analyse IA en cours..."})

    llm_result  = _run_rag_llm(ocr_result)
    pdf_path    = _generate_pdf(llm_result, session_id)

    elapsed = round(time.time() - t0, 2)
    logger.info(f"Session {session_id} traitée en {elapsed}s")

    # Historique
    entry = {
        "session_id": session_id,
        "filename": file.filename,
        "timestamp": datetime.now().isoformat(),
        "elapsed": elapsed,
        "analytes": llm_result.get("analytes", []),
        "pdf_path": pdf_path,
    }
    _session_history.append(entry)

    await _broadcast({"event": "done", "session_id": session_id})

    return AnalyseResponse(
        session_id=session_id,
        analytes=llm_result.get("analytes", []),
        explication=llm_result.get("explication_llm", ""),
        questions=llm_result.get("questions_medecin", []),
        statut="success",
    )


@app.post("/api/analyse-texte", response_model=AnalyseResponse)
async def analyse_texte(request: AnalyseRequest):
    """
    Analyse depuis saisie manuelle (fallback si OCR échoue).
    """
    session_id = request.session_id or str(uuid.uuid4())[:8]
    texte = request.texte_manuel or ""

    if not texte.strip():
        raise HTTPException(400, "Texte vide")

    ocr_result = {"texte_brut": texte, "analytes": [], "source": "manuel"}
    llm_result = _run_rag_llm(ocr_result)
    pdf_path   = _generate_pdf(llm_result, session_id)

    return AnalyseResponse(
        session_id=session_id,
        analytes=llm_result.get("analytes", []),
        explication=llm_result.get("explication_llm", ""),
        questions=llm_result.get("questions_medecin", []),
        statut="success",
    )


@app.post("/api/voice", response_model=dict)
async def voice_input():
    """
    Enregistre depuis le microphone et retourne la transcription.
    """
    try:
        from voice.whisper_stt import transcribe  # type: ignore
        text = transcribe()
        return {"text": text, "statut": "success"}
    except Exception as e:
        logger.error(f"Erreur STT : {e}")
        return {"text": "", "statut": "error", "message": str(e)}


@app.get("/api/rapport/{session_id}")
async def download_rapport(session_id: str):
    """Télécharge le rapport PDF d'une session."""
    pdf_path = REPORT_DIR / f"rapport_{session_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, "Rapport non trouvé")

    return StreamingResponse(
        io.BytesIO(pdf_path.read_bytes()),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="claribio_{session_id}.pdf"'
        },
    )


@app.get("/api/historique")
async def get_historique():
    """Retourne l'historique de la session courante."""
    # On ne retourne que les métadonnées, pas les données médicales
    return JSONResponse([
        {
            "session_id": e["session_id"],
            "filename": e["filename"],
            "timestamp": e["timestamp"],
            "elapsed": e["elapsed"],
            "nb_analytes": len(e.get("analytes", [])),
        }
        for e in _session_history
    ])


@app.delete("/api/historique")
async def clear_historique():
    """Vide l'historique de session (RGPD)."""
    _session_history.clear()
    return {"message": "Historique vidé"}


@app.get("/api/health")
async def health():
    """Endpoint de santé."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket pour les mises à jour en temps réel."""
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_clients.remove(websocket)


# ---------------------------------------------------------------------------
# Données de démonstration
# ---------------------------------------------------------------------------

def _demo_ocr_result() -> dict:
    return {
        "texte_brut": "Résultats biologiques de démonstration",
        "analytes": [
            {"nom": "Glycémie", "valeur": 5.2, "unite": "mmol/L",
             "reference_min": 3.9, "reference_max": 6.1, "statut": "normal"},
            {"nom": "TSH", "valeur": 4.8, "unite": "mUI/L",
             "reference_min": 0.4, "reference_max": 4.0, "statut": "limite"},
        ],
        "source": "demo",
    }


def _demo_llm_result(ocr_result: dict) -> dict:
    analytes = ocr_result.get("analytes", [])
    return {
        "patient": {"nom": "Patient Test", "date_analyse": datetime.now().strftime("%d/%m/%Y")},
        "analytes": analytes if analytes else _demo_ocr_result()["analytes"],
        "explication_llm": (
            "Analyse de démonstration (module LLM non disponible).\n\n"
            "Vos résultats biologiques ont été traités. "
            "Consultez votre médecin pour une interprétation complète."
        ),
        "questions_medecin": [
            "Ces résultats nécessitent-ils une consultation urgente ?",
            "Faut-il renouveler ces analyses prochainement ?",
            "Y a-t-il des changements de mode de vie recommandés ?",
        ],
    }


# ---------------------------------------------------------------------------
# Interface HTML intégrée (pas de framework externe — fonctionne hors-ligne)
# ---------------------------------------------------------------------------

def _html_interface() -> str:
    return """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ClariBio — Assistant Médical IA</title>
<style>
  :root {
    --blue: #1a5276; --blue-light: #2e86c1; --green: #1e8449;
    --orange: #d35400; --red: #922b21; --gray: #f0f4f8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f7fa; color: #333; }
  header { background: var(--blue); color: white; padding: 16px 24px;
           display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 1.5rem; }
  header span { font-size: 0.85rem; opacity: 0.8; }
  .container { max-width: 900px; margin: 24px auto; padding: 0 16px; }
  .card { background: white; border-radius: 12px; padding: 20px;
          box-shadow: 0 2px 8px rgba(0,0,0,.08); margin-bottom: 20px; }
  .card h2 { font-size: 1rem; color: var(--blue); margin-bottom: 14px;
             border-bottom: 2px solid var(--blue); padding-bottom: 6px; }
  .upload-zone { border: 2px dashed #ccc; border-radius: 8px; padding: 32px;
                 text-align: center; cursor: pointer; transition: .2s; }
  .upload-zone:hover { border-color: var(--blue-light); background: #eaf4fb; }
  .btn { padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer;
         font-size: 0.9rem; font-weight: 600; transition: .2s; }
  .btn-primary { background: var(--blue); color: white; }
  .btn-primary:hover { background: var(--blue-light); }
  .btn-voice { background: var(--green); color: white; }
  .btn-voice:hover { background: #27ae60; }
  .btn-danger { background: #c0392b; color: white; font-size: 0.8rem; padding: 6px 12px; }
  .progress { display: none; padding: 12px; background: #eaf4fb;
              border-radius: 8px; color: var(--blue); font-size: 0.9rem; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th { background: var(--blue); color: white; padding: 8px 12px; text-align: left; }
  td { padding: 8px 12px; border-bottom: 1px solid #eee; }
  tr:nth-child(even) td { background: var(--gray); }
  .badge { padding: 2px 8px; border-radius: 12px; font-size: 0.8rem;
           font-weight: 600; color: white; }
  .badge-normal   { background: var(--green); }
  .badge-limite   { background: var(--orange); }
  .badge-critique { background: var(--red); }
  .badge-inconnu  { background: #888; }
  .explication { font-size: 0.9rem; line-height: 1.6; white-space: pre-wrap; }
  .question { padding: 6px 0 6px 16px; border-left: 3px solid var(--blue-light);
              margin-bottom: 6px; font-size: 0.9rem; }
  .historique-item { padding: 8px; background: var(--gray); border-radius: 6px;
                     margin-bottom: 6px; font-size: 0.85rem;
                     display: flex; justify-content: space-between; align-items: center; }
  .hidden { display: none; }
  input[type="file"] { display: none; }
  textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px;
             resize: vertical; font-size: 0.9rem; height: 100px; }
  .disclaimer { font-size: 0.75rem; color: #888; padding: 10px;
                background: #fafafa; border-radius: 6px; border: 1px solid #eee; }
  @media (max-width: 600px) { .container { padding: 0 8px; } }
</style>
</head>
<body>
<header>
  <div>
    <h1>🧬 ClariBio</h1>
    <span>Assistant médical IA — Interprétation de bilans biologiques</span>
  </div>
</header>

<div class="container">

  <!-- Upload -->
  <div class="card">
    <h2>📄 Déposer un document biologique</h2>
    <div class="upload-zone" onclick="document.getElementById('fileInput').click()">
      <p>📎 Cliquez ou déposez une photo / PDF de votre bilan</p>
      <p style="font-size:.8rem;color:#888;margin-top:6px">JPG, PNG, PDF acceptés</p>
    </div>
    <input type="file" id="fileInput" accept=".jpg,.jpeg,.png,.pdf" onchange="uploadFile(this)">
    <div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap">
      <button class="btn btn-voice" onclick="voiceInput()">🎙️ Saisie vocale</button>
    </div>
    <div id="progress" class="progress">⏳ <span id="progressMsg">Traitement...</span></div>
  </div>

  <!-- Saisie manuelle -->
  <div class="card">
    <h2>✏️ Saisie manuelle (si OCR insuffisant)</h2>
    <textarea id="manualText" placeholder="Ex: Glycémie 5.2 mmol/L (normale 3.9-6.1)&#10;TSH 4.8 mUI/L (normale 0.4-4.0)"></textarea>
    <button class="btn btn-primary" style="margin-top:10px" onclick="analyseTexte()">Analyser</button>
  </div>

  <!-- Résultats -->
  <div class="card hidden" id="resultCard">
    <h2>📊 Résultats biologiques</h2>
    <div id="sessionInfo" style="font-size:.8rem;color:#888;margin-bottom:10px"></div>
    <table id="resultTable">
      <thead><tr><th>Analyte</th><th>Valeur</th><th>Unité</th><th>Référence</th><th>Statut</th></tr></thead>
      <tbody id="resultBody"></tbody>
    </table>
    <div style="margin-top:12px">
      <button class="btn btn-primary" id="downloadBtn" onclick="downloadPDF()">⬇️ Télécharger le rapport PDF</button>
    </div>
  </div>

  <!-- Explication LLM -->
  <div class="card hidden" id="explCard">
    <h2>🤖 Interprétation IA</h2>
    <div class="explication" id="explication"></div>
  </div>

  <!-- Questions médecin -->
  <div class="card hidden" id="questCard">
    <h2>💬 Questions à poser à votre médecin</h2>
    <div id="questions"></div>
  </div>

  <!-- Historique -->
  <div class="card">
    <h2>🕐 Historique de session</h2>
    <div id="historique"><em style="color:#888;font-size:.85rem">Aucune analyse cette session</em></div>
    <button class="btn btn-danger" style="margin-top:10px" onclick="clearHistorique()">🗑️ Effacer (RGPD)</button>
  </div>

  <!-- Disclaimer -->
  <div class="disclaimer">
    ⚠️ <strong>Avertissement :</strong> ClariBio est un outil d'aide à la compréhension uniquement.
    Il ne remplace pas l'avis d'un médecin. Aucune donnée n'est envoyée sur internet.
    Toutes les analyses sont effectuées localement.
  </div>
</div>

<script>
let currentSession = null;
const ws = new WebSocket(`ws://${location.host}/ws`);
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.event === 'progress') showProgress(msg.message);
  if (msg.event === 'done') { hideProgress(); loadHistorique(); }
};

function showProgress(msg) {
  const el = document.getElementById('progress');
  el.style.display = 'block';
  document.getElementById('progressMsg').textContent = msg;
}
function hideProgress() { document.getElementById('progress').style.display = 'none'; }

async function uploadFile(input) {
  if (!input.files[0]) return;
  const fd = new FormData();
  fd.append('file', input.files[0]);
  showProgress('Lecture du document...');
  try {
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(await res.text());
    displayResults(await res.json());
  } catch (e) { hideProgress(); alert('Erreur : ' + e.message); }
}

async function analyseTexte() {
  const texte = document.getElementById('manualText').value.trim();
  if (!texte) { alert('Veuillez saisir du texte.'); return; }
  showProgress('Analyse en cours...');
  try {
    const res = await fetch('/api/analyse-texte', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ texte_manuel: texte })
    });
    if (!res.ok) throw new Error(await res.text());
    displayResults(await res.json());
  } catch (e) { hideProgress(); alert('Erreur : ' + e.message); }
}

async function voiceInput() {
  showProgress('Enregistrement vocal...');
  try {
    const res = await fetch('/api/voice', { method: 'POST' });
    const data = await res.json();
    if (data.text) {
      document.getElementById('manualText').value = data.text;
      hideProgress();
    } else { hideProgress(); alert('Transcription impossible.'); }
  } catch (e) { hideProgress(); alert('Erreur microphone : ' + e.message); }
}

function displayResults(data) {
  hideProgress();
  currentSession = data.session_id;
  document.getElementById('sessionInfo').textContent =
    `Session : ${data.session_id} · ${data.analytes.length} analyte(s)`;

  const tbody = document.getElementById('resultBody');
  tbody.innerHTML = '';
  for (const a of data.analytes) {
    const cls = { normal: 'normal', limite: 'limite', critique: 'critique' }[a.statut] || 'inconnu';
    const ref = (a.reference_min && a.reference_max) ? `${a.reference_min} – ${a.reference_max}` : '—';
    tbody.innerHTML += `<tr>
      <td>${a.nom}</td><td>${a.valeur}</td><td>${a.unite||'—'}</td>
      <td>${ref}</td>
      <td><span class="badge badge-${cls}">${a.statut||'—'}</span></td>
    </tr>`;
  }
  document.getElementById('resultCard').classList.remove('hidden');

  if (data.explication) {
    document.getElementById('explication').textContent = data.explication;
    document.getElementById('explCard').classList.remove('hidden');
  }
  if (data.questions?.length) {
    const qdiv = document.getElementById('questions');
    qdiv.innerHTML = data.questions.map(q => `<div class="question">• ${q}</div>`).join('');
    document.getElementById('questCard').classList.remove('hidden');
  }
  loadHistorique();
}

async function downloadPDF() {
  if (!currentSession) return;
  window.open(`/api/rapport/${currentSession}`, '_blank');
}

async function loadHistorique() {
  try {
    const res = await fetch('/api/historique');
    const items = await res.json();
    const div = document.getElementById('historique');
    if (!items.length) {
      div.innerHTML = '<em style="color:#888;font-size:.85rem">Aucune analyse cette session</em>';
      return;
    }
    div.innerHTML = items.reverse().map(i => `
      <div class="historique-item">
        <span>📄 ${i.filename || 'Texte manuel'} — ${i.nb_analytes} analyte(s) — ${i.elapsed}s</span>
        <button class="btn btn-primary" style="padding:4px 10px;font-size:.8rem"
          onclick="window.open('/api/rapport/${i.session_id}','_blank')">PDF</button>
      </div>`).join('');
  } catch (e) { console.error(e); }
}

async function clearHistorique() {
  if (!confirm('Effacer tout l\'historique de session ?')) return;
  await fetch('/api/historique', { method: 'DELETE' });
  loadHistorique();
  currentSession = null;
  ['resultCard','explCard','questCard'].forEach(id =>
    document.getElementById(id).classList.add('hidden'));
}

loadHistorique();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Lancement
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )
