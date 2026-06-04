# Module OCR / NLP - N'TCHO PHANUEL ELIEL KONE

## Objectif

Transformer un bilan biologique en JSON normalise pour le pipeline RAG/LLM.

## Fichiers

- `image_preprocessor.py` : pretraitement photo avec CLAHE, denoising, deskew et seuillage adaptatif.
- `ocr_engine.py` : lecture TXT/PDF/image, EasyOCR optionnel pour les images.
- `bio_parser.py` : extraction analyte, valeur, unite, intervalle de reference et statut.
- `schemas/bio_result_schema.json` : contrat JSON partage avec le reste du pipeline.
- `src/pipeline/ocr_to_rag_connector.py` : payload pret pour le module RAG.

## Verification

```bash
pytest tests/ocr/test_ocr_accuracy.py tests/e2e/test_pipeline.py
```

Les tests utilisent 20 bilans synthetiques dans `tests/data/synthetic_bilans/`.
Aucune donnee medicale reelle ne doit etre ajoutee au depot.
