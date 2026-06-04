# Rapport tests OCR - N'TCHO PHANUEL ELIEL KONE

## Perimetre

- Module OCR : `src/ocr/image_preprocessor.py`, `src/ocr/ocr_engine.py`
- Parser biologique : `src/ocr/bio_parser.py`
- Connecteur pipeline : `src/pipeline/ocr_to_rag_connector.py`
- Donnees : 20 bilans synthetiques, aucune donnee medicale reelle

## Resultats attendus

- Extraction des colonnes analyte, valeur, unite et reference.
- Normalisation JSON conforme a `schemas/bio_result_schema.json`.
- Precision cible sur donnees synthetiques : au moins 95 %.

## Commande

```bash
pytest tests/ocr/test_ocr_accuracy.py tests/e2e/test_pipeline.py
```

## Notes

Les fichiers `.txt` simulent la sortie OCR pour valider le parser et le contrat
JSON sans dependances lourdes. Les images reelles passent par EasyOCR et OpenCV
quand ces librairies sont installees sur la machine cible.
