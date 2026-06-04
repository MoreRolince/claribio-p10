"""
Générateur de rapport PDF — ClariBio
Auteur : IMBOYO MUANAMBELO DONBENI — ClariBio P10 — S5

Critère : PDF généré en < 2s, lisible et imprimable A4
"""

import io
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Codes couleur selon statut des valeurs biologiques
COLOR_NORMAL   = (0.18, 0.65, 0.18)   # Vert
COLOR_LIMITE   = (0.95, 0.55, 0.0)    # Orange
COLOR_CRITIQUE = (0.85, 0.1, 0.1)     # Rouge
COLOR_INCONNU  = (0.5, 0.5, 0.5)      # Gris

DISCLAIMER = (
    "⚠️  AVERTISSEMENT MÉDICAL : Ce rapport est généré automatiquement à titre "
    "informatif uniquement. Il ne constitue pas un diagnostic médical et ne remplace "
    "pas l'avis d'un professionnel de santé qualifié. Consultez votre médecin pour "
    "l'interprétation de vos résultats."
)


def _get_status_color(status: str) -> tuple:
    """Retourne la couleur RGB selon le statut."""
    s = (status or "").lower()
    if s in ("normal", "ok", "n"):
        return COLOR_NORMAL
    elif s in ("limite", "borderline", "élevé", "bas"):
        return COLOR_LIMITE
    elif s in ("critique", "critical", "très élevé", "très bas", "alerte"):
        return COLOR_CRITIQUE
    return COLOR_INCONNU


def _status_label(status: str) -> str:
    s = (status or "").lower()
    if s in ("normal", "ok", "n"):
        return "Normal"
    elif s in ("limite", "borderline", "élevé", "bas"):
        return "Limite"
    elif s in ("critique", "critical", "très élevé", "très bas", "alerte"):
        return "Critique"
    return "Inconnu"


# ---------------------------------------------------------------------------
# Générateur principal
# ---------------------------------------------------------------------------

class PDFGenerator:
    """
    Génère un rapport PDF A4 à partir des résultats biologiques.

    Input (dict):
    {
        "patient": {"nom": "...", "date_naissance": "...", "date_analyse": "..."},
        "analytes": [
            {
                "nom": "Glycémie",
                "valeur": 5.2,
                "unite": "mmol/L",
                "reference_min": 3.9,
                "reference_max": 6.1,
                "statut": "normal"
            },
            ...
        ],
        "explication_llm": "Texte explicatif généré par le LLM...",
        "questions_medecin": ["Question 1 ?", "Question 2 ?", "Question 3 ?"]
    }
    """

    PAGE_WIDTH  = 595   # A4 points
    PAGE_HEIGHT = 842

    MARGIN_LEFT   = 50
    MARGIN_RIGHT  = 50
    MARGIN_TOP    = 50
    MARGIN_BOTTOM = 50

    def __init__(self):
        self._check_reportlab()

    def _check_reportlab(self):
        try:
            import reportlab
        except ImportError:
            raise RuntimeError(
                "reportlab non installé. Exécutez : pip install reportlab"
            )

    def generate(self, data: dict, output_path: str | None = None) -> bytes:
        """
        Génère le rapport PDF.
        Retourne les bytes du PDF. Si output_path fourni, écrit aussi le fichier.
        """
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, KeepTogether
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=self.MARGIN_LEFT,
            rightMargin=self.MARGIN_RIGHT,
            topMargin=self.MARGIN_TOP,
            bottomMargin=self.MARGIN_BOTTOM,
            title="Rapport ClariBio",
            author="ClariBio P10",
        )

        styles = getSampleStyleSheet()
        content_width = self.PAGE_WIDTH - self.MARGIN_LEFT - self.MARGIN_RIGHT

        # Styles personnalisés
        style_title = ParagraphStyle(
            "ClariBioTitle",
            parent=styles["Title"],
            fontSize=20,
            textColor=colors.HexColor("#1a5276"),
            spaceAfter=6,
        )
        style_subtitle = ParagraphStyle(
            "ClariBioSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#555555"),
            spaceAfter=4,
        )
        style_section = ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#1a5276"),
            spaceBefore=12,
            spaceAfter=6,
        )
        style_body = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
        )
        style_disclaimer = ParagraphStyle(
            "Disclaimer",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#888888"),
            leading=11,
            borderPad=4,
        )
        style_question = ParagraphStyle(
            "Question",
            parent=styles["Normal"],
            fontSize=10,
            leftIndent=15,
            spaceAfter=3,
        )

        story = []

        # ---- En-tête ----
        story.append(Paragraph("ClariBio", style_title))
        story.append(Paragraph("Rapport d'analyse biologique — Interprétation IA", style_subtitle))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a5276")))
        story.append(Spacer(1, 8))

        # ---- Informations patient ----
        patient = data.get("patient", {})
        date_analyse = patient.get("date_analyse") or datetime.now().strftime("%d/%m/%Y")
        patient_info = [
            ["Patient :", patient.get("nom", "Anonyme")],
            ["Date de naissance :", patient.get("date_naissance", "—")],
            ["Date d'analyse :", date_analyse],
            ["Généré le :", datetime.now().strftime("%d/%m/%Y à %H:%M")],
        ]
        t_patient = Table(patient_info, colWidths=[120, content_width - 120])
        t_patient.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(t_patient)
        story.append(Spacer(1, 12))

        # ---- Tableau des valeurs biologiques ----
        story.append(Paragraph("Résultats biologiques", style_section))

        analytes = data.get("analytes", [])
        if analytes:
            table_data = [["Analyte", "Valeur", "Unité", "Référence", "Statut"]]
            for a in analytes:
                ref_min = a.get("reference_min", "")
                ref_max = a.get("reference_max", "")
                ref_str = f"{ref_min} – {ref_max}" if ref_min and ref_max else "—"
                statut = a.get("statut", "inconnu")
                color_rgb = _get_status_color(statut)
                color_rl = colors.Color(*color_rgb)

                valeur_str = f"{a.get('valeur', '—')}"
                row = [
                    a.get("nom", "—"),
                    valeur_str,
                    a.get("unite", "—"),
                    ref_str,
                    _status_label(statut),
                ]
                table_data.append(row)

            col_widths = [160, 60, 70, 130, 75]
            t = Table(table_data, colWidths=col_widths)

            ts = TableStyle([
                # En-tête
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.HexColor("#f0f4f8"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ])

            # Coloration de la colonne statut par ligne
            for i, a in enumerate(analytes, start=1):
                color_rgb = _get_status_color(a.get("statut", ""))
                color_rl = colors.Color(*color_rgb)
                ts.add("TEXTCOLOR", (4, i), (4, i), color_rl)
                ts.add("FONTNAME", (4, i), (4, i), "Helvetica-Bold")

            t.setStyle(ts)
            story.append(t)
        else:
            story.append(Paragraph("Aucun analyte disponible.", style_body))

        story.append(Spacer(1, 14))

        # ---- Explication LLM ----
        explication = data.get("explication_llm", "")
        if explication:
            story.append(Paragraph("Interprétation clinique", style_section))
            for para in explication.split("\n"):
                para = para.strip()
                if para:
                    story.append(Paragraph(para, style_body))
                    story.append(Spacer(1, 4))

        story.append(Spacer(1, 10))

        # ---- Questions pour le médecin ----
        questions = data.get("questions_medecin", [])
        if not questions:
            questions = _generate_default_questions(analytes)

        story.append(KeepTogether([
            Paragraph("Questions à poser à votre médecin", style_section),
            *[Paragraph(f"• {q}", style_question) for q in questions[:3]],
        ]))

        story.append(Spacer(1, 20))

        # ---- Disclaimer ----
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=colors.HexColor("#cccccc")))
        story.append(Spacer(1, 6))
        story.append(Paragraph(DISCLAIMER, style_disclaimer))

        # ---- Build ----
        doc.build(story)
        pdf_bytes = buf.getvalue()

        if output_path:
            Path(output_path).write_bytes(pdf_bytes)
            logger.info(f"Rapport PDF sauvegardé : {output_path} "
                        f"({len(pdf_bytes) // 1024} Ko)")

        return pdf_bytes


# ---------------------------------------------------------------------------
# Générateur de questions par défaut
# ---------------------------------------------------------------------------

def _generate_default_questions(analytes: list[dict]) -> list[str]:
    """Génère 3 questions automatiques selon les anomalies détectées."""
    anomalies = [
        a["nom"] for a in analytes
        if a.get("statut", "").lower() not in ("normal", "ok", "n")
    ]
    questions = []

    if anomalies:
        questions.append(
            f"Ces résultats anormaux ({', '.join(anomalies[:2])}) "
            "nécessitent-ils une consultation urgente ?"
        )
        questions.append(
            "Faut-il refaire ces analyses dans un délai précis ?"
        )
        questions.append(
            "Ces résultats peuvent-ils être liés à mes traitements actuels ?"
        )
    else:
        questions = [
            "À quelle fréquence dois-je renouveler ce bilan biologique ?",
            "Ces résultats sont-ils cohérents avec mon état de santé général ?",
            "Y a-t-il des mesures préventives à adopter suite à ce bilan ?",
        ]

    return questions[:3]


# ---------------------------------------------------------------------------
# Données de démonstration
# ---------------------------------------------------------------------------

DEMO_DATA = {
    "patient": {
        "nom": "Patient Test",
        "date_naissance": "01/01/1980",
        "date_analyse": datetime.now().strftime("%d/%m/%Y"),
    },
    "analytes": [
        {"nom": "Glycémie",    "valeur": 5.2,  "unite": "mmol/L",  "reference_min": 3.9, "reference_max": 6.1,  "statut": "normal"},
        {"nom": "TSH",         "valeur": 4.8,  "unite": "mUI/L",   "reference_min": 0.4, "reference_max": 4.0,  "statut": "limite"},
        {"nom": "Hémoglobine", "valeur": 10.2, "unite": "g/dL",    "reference_min": 12.0,"reference_max": 16.0, "statut": "critique"},
        {"nom": "Créatinine",  "valeur": 78.0, "unite": "µmol/L",  "reference_min": 44.0,"reference_max": 97.0, "statut": "normal"},
        {"nom": "Cholestérol", "valeur": 5.8,  "unite": "mmol/L",  "reference_min": 0.0, "reference_max": 5.2,  "statut": "limite"},
    ],
    "explication_llm": (
        "Votre bilan biologique présente quelques points d'attention.\n\n"
        "Votre glycémie est dans les valeurs normales, ce qui indique un bon "
        "contrôle de votre glycémie à jeun. Aucune action urgente n'est requise "
        "concernant ce paramètre.\n\n"
        "Votre TSH est légèrement au-dessus des valeurs de référence, ce qui peut "
        "suggérer un début d'hypothyroïdie. Une surveillance et une consultation "
        "médicale sont recommandées.\n\n"
        "Votre taux d'hémoglobine est bas, ce qui indique une anémie. Ce résultat "
        "nécessite une attention médicale dans les prochains jours.\n\n"
        "⚠️ Ce rapport est généré par une IA à titre informatif uniquement."
    ),
    "questions_medecin": [
        "Mon taux d'hémoglobine bas nécessite-t-il un traitement urgent ?",
        "Faut-il surveiller ma thyroïde plus régulièrement ?",
        "Mon cholestérol limite nécessite-t-il un changement alimentaire ?",
    ],
}


# ---------------------------------------------------------------------------
# Point d'entrée rapide
# ---------------------------------------------------------------------------

def generate_demo_report(output_path: str = "/tmp/claribio_rapport_demo.pdf") -> str:
    """Génère un rapport de démonstration."""
    import time
    gen = PDFGenerator()
    t0 = time.time()
    gen.generate(DEMO_DATA, output_path=output_path)
    elapsed = time.time() - t0
    logger.info(f"Rapport généré en {elapsed:.2f}s")
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path = generate_demo_report()
    print(f"Rapport de démonstration : {path}")
