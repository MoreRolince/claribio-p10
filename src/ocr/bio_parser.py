"""
Parser NLP/regex pour bilans biologiques ClariBio.
Auteur : N'TCHO PHANUEL ELIEL KONE - ClariBio P10
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Any


ANALYTE_ALIASES = {
    "glycemie": "Glycemie",
    "glucose": "Glycemie",
    "tsh": "TSH",
    "hemoglobine": "Hemoglobine",
    "hémoglobine": "Hemoglobine",
    "leucocytes": "Leucocytes",
    "plaquettes": "Plaquettes",
    "creatinine": "Creatinine",
    "créatinine": "Creatinine",
    "cholesterol total": "Cholesterol total",
    "cholestérol total": "Cholesterol total",
    "crp": "CRP",
    "alat": "ALAT",
    "asat": "ASAT",
    "ferritine": "Ferritine",
}


UNIT_RE = r"(?:g/L|mg/L|mmol/L|µmol/L|umol/L|mUI/L|UI/L|G/L|T/L|%|ng/mL)"
LINE_RE = re.compile(
    rf"^(?P<name>[A-Za-zÀ-ÿ0-9 \-'/]+?)\s+"
    rf"(?P<value>[<>]?\s*\d+(?:[,.]\d+)?)\s*"
    rf"(?P<unit>{UNIT_RE})?"
    rf"(?:\s+(?P<low>\d+(?:[,.]\d+)?)\s*[-–]\s*(?P<high>\d+(?:[,.]\d+)?)\s*(?P<ref_unit>{UNIT_RE})?)?",
    re.IGNORECASE,
)


@dataclass
class BioResult:
    analyte: str
    value: float
    unit: str | None
    reference_low: float | None = None
    reference_high: float | None = None
    status: str = "unknown"
    raw_name: str = ""
    raw_line: str = ""


class BioParser:
    """Extrait analyte, valeur, unite et intervalle de reference depuis du texte OCR."""

    def parse(self, text: str, source_format: str = "generic") -> dict[str, Any]:
        results = []
        rejected = []
        for raw_line in _normalize_text(text).splitlines():
            line = raw_line.strip(" \t|;")
            if not line or _is_header(line):
                continue

            match = LINE_RE.match(line)
            if not match:
                rejected.append(line)
                continue

            parsed = self._from_match(match, raw_line=line)
            if parsed:
                results.append(asdict(parsed))
            else:
                rejected.append(line)

        return {
            "schema_version": "1.0",
            "source_format": source_format,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "patient": {"id": None, "age": None, "sex": None},
            "results": results,
            "quality": {
                "parsed_lines": len(results),
                "rejected_lines": len(rejected),
                "confidence": round(len(results) / max(len(results) + len(rejected), 1), 3),
            },
            "warnings": [f"Ligne non reconnue: {line}" for line in rejected[:10]],
        }

    def _from_match(self, match: re.Match[str], raw_line: str) -> BioResult | None:
        raw_name = match.group("name").strip()
        analyte = _normalize_analyte(raw_name)
        if not analyte:
            return None

        value = _to_float(match.group("value"))
        unit = match.group("unit") or match.group("ref_unit")
        low = _to_float(match.group("low")) if match.group("low") else None
        high = _to_float(match.group("high")) if match.group("high") else None
        status = _status(value, low, high)
        return BioResult(
            analyte=analyte,
            value=value,
            unit=unit,
            reference_low=low,
            reference_high=high,
            status=status,
            raw_name=raw_name,
            raw_line=raw_line,
        )


def _normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\t", " ")
    text = re.sub(r"[ ]{2,}", " ", text)
    return text


def _normalize_analyte(name: str) -> str | None:
    compact = re.sub(r"\s+", " ", name.strip().lower())
    compact = compact.strip(":.-")
    if compact in ANALYTE_ALIASES:
        return ANALYTE_ALIASES[compact]
    if 2 <= len(compact) <= 40 and re.search(r"[a-zA-ZÀ-ÿ]", compact):
        return compact[:1].upper() + compact[1:]
    return None


def _to_float(value: str) -> float:
    cleaned = value.replace(" ", "").replace(",", ".").replace("<", "").replace(">", "")
    return float(cleaned)


def _status(value: float, low: float | None, high: float | None) -> str:
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    if low is not None or high is not None:
        return "normal"
    return "unknown"


def _is_header(line: str) -> bool:
    lowered = line.lower()
    return any(token in lowered for token in ("analyse", "resultat", "résultat", "valeur", "reference"))


def parse_biology_report(text: str, source_format: str = "generic") -> dict[str, Any]:
    return BioParser().parse(text, source_format=source_format)
