"""
Test E2E leger OCR -> payload RAG.
Auteur : N'TCHO PHANUEL ELIEL KONE - ClariBio P10
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from pipeline.ocr_to_rag_connector import OCRToRAGConnector


def test_ocr_to_rag_payload_contains_abnormal_values():
    source = Path(__file__).parent.parent / "data" / "synthetic_bilans" / "bilan_03_photo.txt"
    payload = OCRToRAGConnector().build_payload(source, source_format="generic")
    statuses = {item["status"] for item in payload["biomarkers"]}
    assert "high" in statuses or "low" in statuses
    assert payload["metadata"]["ocr"]["confidence"] == 1.0
