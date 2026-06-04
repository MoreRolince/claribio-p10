"""
Moteur OCR ClariBio.
Auteur : N'TCHO PHANUEL ELIEL KONE - ClariBio P10
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .bio_parser import BioParser
from .image_preprocessor import ImagePreprocessor


class OCREngine:
    """
    Lit un bilan depuis TXT, PDF ou image.

    TXT est supporte pour les donnees synthetiques et les tests. PDF et image
    utilisent les dependances disponibles localement.
    """

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

    def __init__(self, languages: list[str] | None = None):
        self.languages = languages or ["fr", "en"]
        self.parser = BioParser()
        self.preprocessor = ImagePreprocessor()
        self._reader = None

    def extract_text(self, source: str | Path) -> dict[str, Any]:
        path = Path(source)
        suffix = path.suffix.lower()
        if suffix == ".txt":
            text = path.read_text(encoding="utf-8")
            return {"text": text, "source_type": "txt", "confidence": 1.0}
        if suffix == ".pdf":
            return self._extract_pdf_text(path)
        if suffix in self.IMAGE_EXTENSIONS:
            return self._extract_image_text(path)
        raise ValueError(f"Format non supporte: {suffix}")

    def parse_file(self, source: str | Path, source_format: str = "generic") -> dict[str, Any]:
        extraction = self.extract_text(source)
        parsed = self.parser.parse(extraction["text"], source_format=source_format)
        parsed["ocr"] = {
            "source": str(source),
            "source_type": extraction["source_type"],
            "confidence": extraction["confidence"],
        }
        return parsed

    def _extract_pdf_text(self, path: Path) -> dict[str, Any]:
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(str(path))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except ImportError as exc:
                raise RuntimeError("Installer pypdf ou PyPDF2 pour lire les PDF") from exc
        return {"text": text, "source_type": "pdf", "confidence": 0.9 if text.strip() else 0.0}

    def _extract_image_text(self, path: Path) -> dict[str, Any]:
        try:
            import easyocr
        except ImportError as exc:
            raise RuntimeError("EasyOCR non installe. Installer avec: pip install easyocr") from exc

        if self._reader is None:
            self._reader = easyocr.Reader(self.languages, gpu=False)

        image = self.preprocessor.preprocess_file(path)
        rows = self._reader.readtext(image, detail=1, paragraph=False)
        texts = [row[1] for row in rows]
        confidences = [float(row[2]) for row in rows if len(row) > 2]
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return {"text": "\n".join(texts), "source_type": "image", "confidence": round(confidence, 3)}


def parse_report_file(source: str | Path, source_format: str = "generic") -> dict[str, Any]:
    return OCREngine().parse_file(source, source_format=source_format)
