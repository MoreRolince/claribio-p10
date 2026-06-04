"""
Tests OCR/parser - 20 bilans synthetiques.
Auteur : N'TCHO PHANUEL ELIEL KONE - ClariBio P10
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ocr.bio_parser import BioParser
from ocr.ocr_engine import OCREngine
from pipeline.ocr_to_rag_connector import OCRToRAGConnector


SYNTHETIC_DIR = Path(__file__).parent.parent / "data" / "synthetic_bilans"


def test_parser_extracts_expected_markers():
    text = "Glycemie 5,2 mmol/L 3,9-5,8\nTSH 6.1 mUI/L 0.4-4.0"
    result = BioParser().parse(text, source_format="generic")
    assert result["quality"]["parsed_lines"] == 2
    assert result["results"][0]["analyte"] == "Glycemie"
    assert result["results"][1]["status"] == "high"


def test_ocr_engine_reads_synthetic_txt():
    path = SYNTHETIC_DIR / "bilan_01_cerba.txt"
    result = OCREngine().parse_file(path, source_format="cerba")
    assert result["ocr"]["source_type"] == "txt"
    assert result["quality"]["confidence"] >= 0.95
    assert len(result["results"]) >= 5


def test_accuracy_on_20_synthetic_reports():
    engine = OCREngine()
    files = sorted(SYNTHETIC_DIR.glob("bilan_*.txt"))
    assert len(files) == 20

    parsed = 0
    expected = 0
    for path in files:
        result = engine.parse_file(path, source_format=_format_from_name(path.name))
        parsed += result["quality"]["parsed_lines"]
        expected += 5

    accuracy = parsed / expected
    assert accuracy >= 0.95


def test_connector_builds_rag_payload():
    path = SYNTHETIC_DIR / "bilan_02_synlab.txt"
    payload = OCRToRAGConnector().build_payload(path, source_format="synlab")
    assert payload["input_type"] == "biology_report"
    assert payload["biomarkers"]
    assert "Interpre" in payload["rag_query"]


def test_manual_fallback_payload():
    connector = OCRToRAGConnector()
    payload = connector.build_payload(
        "manual",
        manual_results=[{"analyte": "CRP", "value": 12.0, "unit": "mg/L", "status": "high"}],
    )
    assert payload["quality"]["fallback"] == "manual_entry"
    assert payload["biomarkers"][0]["analyte"] == "CRP"


def _format_from_name(name: str) -> str:
    if "cerba" in name:
        return "cerba"
    if "synlab" in name:
        return "synlab"
    return "generic"
