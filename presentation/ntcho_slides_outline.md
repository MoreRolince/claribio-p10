# Slides finale - contribution N'TCHO PHANUEL ELIEL KONE

## Structure proposee en 15 slides maximum

1. Accroche : un bilan biologique illisible ne doit pas bloquer l'explication clinique.
2. Probleme : formats heterogenes, photos floues, PDF structures, risques d'erreur de saisie.
3. Solution ClariBio : OCR local puis interpretation RAG/LLM sans donnees reelles en ligne.
4. Architecture globale : Photo/PDF -> OCR -> Parser JSON -> RAG -> LLM -> Interface/PDF.
5. Module OCR : EasyOCR + pretraitement OpenCV.
6. Pretraitement : CLAHE, binarisation adaptative, deskew, denoising.
7. Parser biologique : analyte, valeur, unite, intervalle de reference, statut.
8. Schema JSON : contrat stable pour FABO et le pipeline RAG.
9. Fallback manuel : securite si OCR partiel ou format inconnu.
10. Donnees de test : 20 bilans synthetiques Cerba, Synlab et photo.
11. Resultats : cible precision >= 95 % sur donnees synthetiques.
12. Demo live : charger un bilan synthetique et afficher le payload RAG.
13. RGPD : traitement local, pas de donnees medicales reelles dans Git.
14. Limites : manuscrits difficiles, scans tres flous, besoin de validation medicale.
15. Perspectives : enrichir les formats, ajouter calibration OCR et validation metier.

## Elements visuels a preparer

- Schema de flux OCR -> RAG -> LLM -> Interface.
- Capture du JSON normalise.
- Tableau court des metriques parser/OCR.
