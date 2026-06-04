"""
Connecteur OCR -> RAG/LLM pour ClariBio.
Auteur : N'TCHO PHANUEL ELIEL KONE - ClariBio P10
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ocr.ocr_engine import OCREngine


class OCRToRAGConnector:
    """Normalise les resultats OCR dans un format consommable par le pipeline RAG."""

    def __init__(self, ocr_engine: OCREngine | None = None):
        self.ocr_engine = ocr_engine or OCREngine()

    def build_payload(
        self,
        source: str | Path,
        source_format: str = "generic",
        manual_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if manual_results is not None:
            parsed = self._manual_payload(manual_results, source_format)
        else:
            parsed = self.ocr_engine.parse_file(source, source_format=source_format)

        return {
            "input_type": "biology_report",
            "source": str(source),
            "source_format": source_format,
            "patient": parsed.get("patient", {}),
            "biomarkers": parsed.get("results", []),
            "quality": parsed.get("quality", {}),
            "warnings": parsed.get("warnings", []),
            "rag_query": self._build_rag_query(parsed.get("results", [])),
            "metadata": {
                "schema_version": parsed.get("schema_version", "1.0"),
                "generated_at": parsed.get("generated_at"),
                "ocr": parsed.get("ocr", {"source_type": "manual", "confidence": 1.0}),
            },
        }

    def _manual_payload(self, results: list[dict[str, Any]], source_format: str) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "source_format": source_format,
            "patient": {"id": None, "age": None, "sex": None},
            "results": results,
            "quality": {
                "parsed_lines": len(results),
                "rejected_lines": 0,
                "confidence": 1.0,
                "fallback": "manual_entry",
            },
            "warnings": ["Fallback manuel utilise: OCR indisponible ou incomplet."],
        }

    def _build_rag_query(self, results: list[dict[str, Any]]) -> str:
        if not results:
            return "Interpréter un bilan biologique sans marqueur extrait automatiquement."
        fragments = []
        for item in results:
            value = item.get("value")
            unit = item.get("unit") or ""
            status = item.get("status", "unknown")
            fragments.append(f"{item.get('analyte')}: {value} {unit} ({status})")
        return "Interpréter le bilan biologique suivant: " + "; ".join(fragments)


def build_ocr_rag_payload(source: str | Path, source_format: str = "generic") -> dict[str, Any]:
    return OCRToRAGConnector().build_payload(source, source_format=source_format)
