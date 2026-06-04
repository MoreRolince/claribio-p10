"""
Module Whisper STT — Reconnaissance vocale française
Auteur : IMBOYO MUANAMBELO DONBENI — ClariBio P10 — S5

Critère : Transcription correcte sur 50 phrases médicales, WER < 10%
"""

import io
import wave
import threading
import queue
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Détection d'activité vocale (VAD) — basée sur l'énergie RMS
# ---------------------------------------------------------------------------

def _rms(data: np.ndarray) -> float:
    """Calcule le niveau RMS d'un buffer audio."""
    return float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))


class VAD:
    """
    Détecteur d'activité vocale simple basé sur l'énergie RMS.
    Démarre l'enregistrement quand la voix est détectée,
    l'arrête après SILENCE_DURATION secondes de silence.
    """

    THRESHOLD = 500          # Seuil RMS pour détecter la voix
    SILENCE_DURATION = 1.5   # Secondes de silence avant d'arrêter
    SAMPLE_RATE = 16000
    CHUNK = 1024

    def __init__(self):
        self._active = False
        self._silence_frames = 0
        self._frames_per_second = self.SAMPLE_RATE / self.CHUNK
        self._silence_limit = int(self.SILENCE_DURATION * self._frames_per_second)

    def process(self, chunk: np.ndarray) -> tuple[bool, bool]:
        """
        Traite un chunk audio.
        Retourne (is_speech, should_stop).
        """
        level = _rms(chunk)
        is_speech = level > self.THRESHOLD

        if is_speech:
            self._active = True
            self._silence_frames = 0
        elif self._active:
            self._silence_frames += 1

        should_stop = self._active and self._silence_frames >= self._silence_limit
        return is_speech, should_stop

    def reset(self):
        self._active = False
        self._silence_frames = 0


# ---------------------------------------------------------------------------
# Enregistreur audio
# ---------------------------------------------------------------------------

class AudioRecorder:
    """
    Enregistre l'audio depuis le microphone avec détection VAD.
    Utilise PyAudio si disponible, sinon mode simulation.
    """

    SAMPLE_RATE = 16000
    CHANNELS = 1
    CHUNK = 1024
    MAX_DURATION = 30  # secondes max

    def __init__(self):
        self._pyaudio = None
        self._simulation_mode = False
        self._try_init_pyaudio()

    def _try_init_pyaudio(self):
        try:
            import pyaudio
            self._pyaudio = pyaudio.PyAudio()
            logger.info("PyAudio initialisé")
        except ImportError:
            logger.warning("PyAudio non disponible — mode simulation activé")
            self._simulation_mode = True
        except Exception as e:
            logger.warning(f"PyAudio erreur ({e}) — mode simulation activé")
            self._simulation_mode = True

    def record(self, max_duration: int = MAX_DURATION) -> bytes:
        """
        Enregistre jusqu'à détection de fin de parole ou max_duration secondes.
        Retourne les données WAV en bytes.
        """
        if self._simulation_mode:
            return self._simulate_recording()
        return self._record_real(max_duration)

    def _record_real(self, max_duration: int) -> bytes:
        import pyaudio
        pa = self._pyaudio
        vad = VAD()
        frames = []
        max_frames = int(self.SAMPLE_RATE / self.CHUNK * max_duration)

        stream = pa.open(
            format=pyaudio.paInt16,
            channels=self.CHANNELS,
            rate=self.SAMPLE_RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )

        logger.info("Enregistrement démarré — parlez...")
        try:
            for _ in range(max_frames):
                raw = stream.read(self.CHUNK, exception_on_overflow=False)
                chunk = np.frombuffer(raw, dtype=np.int16)
                frames.append(raw)
                _, should_stop = vad.process(chunk)
                if should_stop:
                    logger.info("Fin de parole détectée")
                    break
        finally:
            stream.stop_stream()
            stream.close()

        return self._frames_to_wav(frames)

    def _simulate_recording(self) -> bytes:
        """Mode simulation : génère un silence de 1 seconde."""
        logger.info("Mode simulation — génération audio factice")
        silence = np.zeros(self.SAMPLE_RATE, dtype=np.int16)
        return self._np_to_wav(silence)

    def _frames_to_wav(self, frames: list[bytes]) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(self.SAMPLE_RATE)
            wf.writeframes(b"".join(frames))
        return buf.getvalue()

    def _np_to_wav(self, data: np.ndarray) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(self.SAMPLE_RATE)
            wf.writeframes(data.tobytes())
        return buf.getvalue()

    def __del__(self):
        if self._pyaudio:
            try:
                self._pyaudio.terminate()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Transcripteur Whisper
# ---------------------------------------------------------------------------

class WhisperSTT:
    """
    Interface principale STT basée sur OpenAI Whisper (modèle small, 244 Mo).

    Usage:
        stt = WhisperSTT()
        text = stt.transcribe_file("audio.wav")
        text = stt.transcribe_microphone()
    """

    MODEL_SIZE = "small"   # 244 Mo — bon compromis vitesse/précision pour Pi 5
    LANGUAGE = "fr"

    def __init__(self, model_size: str = MODEL_SIZE):
        self._model = None
        self._model_size = model_size
        self._recorder = AudioRecorder()

    def _load_model(self):
        """Chargement paresseux du modèle Whisper."""
        if self._model is None:
            try:
                import whisper
                logger.info(f"Chargement du modèle Whisper '{self._model_size}'...")
                self._model = whisper.load_model(self._model_size)
                logger.info("Modèle Whisper chargé")
            except ImportError:
                raise RuntimeError(
                    "openai-whisper non installé. "
                    "Exécutez : pip install openai-whisper"
                )

    def transcribe_file(self, audio_path: str) -> dict:
        """
        Transcrit un fichier audio.
        Retourne {"text": str, "language": str, "segments": list}
        """
        self._load_model()
        result = self._model.transcribe(
            audio_path,
            language=self.LANGUAGE,
            task="transcribe",
            fp16=False,          # Pas de GPU sur Pi 5
            temperature=0.0,     # Déterministe
        )
        logger.info(f"Transcription : {result['text'][:100]}...")
        return {
            "text": result["text"].strip(),
            "language": result.get("language", self.LANGUAGE),
            "segments": result.get("segments", []),
        }

    def transcribe_microphone(self) -> dict:
        """
        Enregistre depuis le microphone et transcrit.
        Retourne {"text": str, "language": str, "segments": list}
        """
        logger.info("Démarrage enregistrement microphone...")
        wav_bytes = self._recorder.record()

        # Sauvegarde temporaire pour Whisper
        tmp_path = Path("/tmp/claribio_stt_input.wav")
        tmp_path.write_bytes(wav_bytes)

        result = self.transcribe_file(str(tmp_path))
        tmp_path.unlink(missing_ok=True)
        return result

    def transcribe_bytes(self, audio_bytes: bytes) -> dict:
        """
        Transcrit depuis des bytes WAV directement.
        """
        tmp_path = Path("/tmp/claribio_stt_bytes.wav")
        tmp_path.write_bytes(audio_bytes)
        result = self.transcribe_file(str(tmp_path))
        tmp_path.unlink(missing_ok=True)
        return result


# ---------------------------------------------------------------------------
# Point d'entrée rapide
# ---------------------------------------------------------------------------

def transcribe(source: str | bytes | None = None) -> str:
    """
    Fonction utilitaire rapide.
    - source=None       → enregistre depuis le micro
    - source=str        → transcrit le fichier audio
    - source=bytes      → transcrit les bytes WAV
    """
    stt = WhisperSTT()
    if source is None:
        return stt.transcribe_microphone()["text"]
    elif isinstance(source, str):
        return stt.transcribe_file(source)["text"]
    else:
        return stt.transcribe_bytes(source)["text"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("ClariBio — Test STT Whisper")
    print("Parlez après le signal...")
    text = transcribe()
    print(f"Transcription : {text}")
