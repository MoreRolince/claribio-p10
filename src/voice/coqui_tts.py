"""
Module Coqui TTS — Synthèse vocale française
Auteur : IMBOYO MUANAMBELO DONBENI — ClariBio P10 — S5

Critère : Synthèse fluide et intelligible sur réponses LLM de 200 mots
"""

import re
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Modèle voix française naturelle — optimisé pour Pi 5
FR_MODEL = "tts_models/fr/mai/tacotron2-DDC"


class CoquiTTS:
    """
    Interface TTS basée sur Coqui TTS.
    Optimisée pour le Raspberry Pi 5 (synthèse séquentielle par paragraphe).

    Usage:
        tts = CoquiTTS()
        tts.speak("Vos résultats sont normaux.")
        tts.speak_paragraphs(long_text)
        audio_path = tts.synthesize("Texte", output="out.wav")
    """

    MAX_CHUNK_CHARS = 300   # Limite par chunk pour éviter la latence sur Pi 5

    def __init__(self, model_name: str = FR_MODEL):
        self._model_name = model_name
        self._tts = None
        self._simulation_mode = False

    def _load_model(self):
        """Chargement paresseux du modèle TTS."""
        if self._tts is not None:
            return
        try:
            from TTS.api import TTS
            logger.info(f"Chargement du modèle TTS '{self._model_name}'...")
            self._tts = TTS(model_name=self._model_name, progress_bar=False)
            logger.info("Modèle TTS chargé")
        except ImportError:
            logger.warning("TTS non installé — mode simulation activé")
            self._simulation_mode = True
        except Exception as e:
            logger.warning(f"TTS erreur ({e}) — mode simulation activé")
            self._simulation_mode = True

    # ------------------------------------------------------------------
    # Découpage du texte
    # ------------------------------------------------------------------

    @staticmethod
    def split_paragraphs(text: str) -> list[str]:
        """Découpe le texte en paragraphes non vides."""
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        return paragraphs if paragraphs else [text.strip()]

    @staticmethod
    def split_sentences(text: str) -> list[str]:
        """Découpe un paragraphe en phrases."""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [s for s in sentences if s]

    def _chunk_text(self, text: str) -> list[str]:
        """
        Découpe le texte en morceaux ≤ MAX_CHUNK_CHARS
        en respectant les limites de phrases.
        """
        sentences = self.split_sentences(text)
        chunks = []
        current = ""

        for sentence in sentences:
            if len(current) + len(sentence) + 1 <= self.MAX_CHUNK_CHARS:
                current = (current + " " + sentence).strip()
            else:
                if current:
                    chunks.append(current)
                current = sentence

        if current:
            chunks.append(current)

        return chunks if chunks else [text]

    # ------------------------------------------------------------------
    # Synthèse
    # ------------------------------------------------------------------

    def synthesize(self, text: str, output_path: str | None = None) -> str:
        """
        Synthétise le texte en audio WAV.
        Retourne le chemin du fichier généré.
        """
        self._load_model()

        if output_path is None:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".wav", prefix="claribio_tts_", delete=False
            )
            output_path = tmp.name
            tmp.close()

        if self._simulation_mode:
            self._simulate_wav(output_path)
            return output_path

        text_clean = self._clean_text(text)
        self._tts.tts_to_file(text=text_clean, file_path=output_path)
        logger.info(f"Audio synthétisé : {output_path}")
        return output_path

    def speak(self, text: str):
        """
        Synthétise et joue le texte directement.
        Découpe automatiquement si > MAX_CHUNK_CHARS.
        """
        chunks = self._chunk_text(text)
        for chunk in chunks:
            audio_path = self.synthesize(chunk)
            self._play(audio_path)
            Path(audio_path).unlink(missing_ok=True)

    def speak_paragraphs(self, text: str):
        """
        Lecture séquentielle paragraphe par paragraphe.
        Optimisé pour les réponses LLM longues (200+ mots).
        """
        paragraphs = self.split_paragraphs(text)
        logger.info(f"Lecture de {len(paragraphs)} paragraphe(s)")
        for i, para in enumerate(paragraphs, 1):
            logger.info(f"Paragraphe {i}/{len(paragraphs)}")
            self.speak(para)

    def synthesize_paragraphs(self, text: str, output_dir: str = "/tmp") -> list[str]:
        """
        Synthétise chaque paragraphe dans un fichier séparé.
        Retourne la liste des chemins générés.
        """
        paragraphs = self.split_paragraphs(text)
        paths = []
        for i, para in enumerate(paragraphs):
            path = f"{output_dir}/claribio_tts_para_{i:03d}.wav"
            self.synthesize(para, output_path=path)
            paths.append(path)
        return paths

    # ------------------------------------------------------------------
    # Lecture audio
    # ------------------------------------------------------------------

    def _play(self, audio_path: str):
        """Joue un fichier WAV."""
        try:
            import pyaudio
            import wave
            wf = wave.open(audio_path, "rb")
            pa = pyaudio.PyAudio()
            stream = pa.open(
                format=pa.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
            )
            chunk = 1024
            data = wf.readframes(chunk)
            while data:
                stream.write(data)
                data = wf.readframes(chunk)
            stream.stop_stream()
            stream.close()
            pa.terminate()
        except ImportError:
            logger.warning("PyAudio non disponible — lecture audio ignorée")
        except Exception as e:
            logger.warning(f"Erreur lecture audio : {e}")

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_text(text: str) -> str:
        """Nettoie le texte pour la synthèse (supprime markdown, etc.)."""
        text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)   # bold/italic
        text = re.sub(r"#{1,6}\s+", "", text)                    # titres markdown
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)   # liens
        text = re.sub(r"`[^`]+`", "", text)                      # code inline
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _simulate_wav(self, output_path: str):
        """Génère un fichier WAV silencieux pour le mode simulation."""
        import wave
        import struct
        sample_rate = 22050
        duration = 0.5
        n_samples = int(sample_rate * duration)
        with wave.open(output_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack("<" + "h" * n_samples, *([0] * n_samples)))


# ---------------------------------------------------------------------------
# Point d'entrée rapide
# ---------------------------------------------------------------------------

def speak(text: str):
    """Synthétise et joue le texte directement."""
    CoquiTTS().speak(text)


def synthesize(text: str, output_path: str = "/tmp/claribio_output.wav") -> str:
    """Synthétise le texte et retourne le chemin du fichier WAV."""
    return CoquiTTS().synthesize(text, output_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_text = (
        "Vos résultats biologiques ont été analysés. "
        "Votre glycémie est dans les valeurs normales. "
        "Votre bilan thyroïdien ne montre pas d'anomalie. "
        "Je vous recommande de consulter votre médecin pour discuter de ces résultats."
    )
    print("ClariBio — Test TTS Coqui")
    print(f"Texte ({len(test_text.split())} mots) : {test_text[:80]}...")
    speak(test_text)
    print("Synthèse terminée")
