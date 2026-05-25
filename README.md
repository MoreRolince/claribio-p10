# ClariBio — P10

Assistant médical IA local sur Raspberry Pi 5 pour l'interprétation des bilans biologiques.

**Présentation finale : 15 juin 2026**  
**Commanditaires : Mark Gray · Mohamed AAZI**

## Équipe

| Membre | Rôle | Branches |
|--------|------|----------|
| DARI MORE ROLINCE | Chef de projet | `feature/dari/*` |
| FABO NJATCHABOU K.A. | LLM / RAG | `feature/fabo/*` |
| N'TCHO PHANUEL E.K. | OCR / NLP / Slides | `feature/ntcho/*` |
| IMBOYO MUANAMBELO D. | Interface / Matériel | `feature/imboyo/*` |

## Architecture

```
Photo/PDF → [OCR] → [RAG + LLM] → [Interface vocale + Web + PDF]
```

## Structure du dépôt

```
src/ocr/        Module OCR (N'TCHO)
src/rag/        Base RAG et retrieval (FABO)
src/llm/        Modèle LLM et prompts (FABO)
src/voice/      STT et TTS (IMBOYO)
src/web/        Interface FastAPI (IMBOYO)
src/output/     Générateur PDF (IMBOYO)
src/pipeline/   Connecteurs entre modules
tests/          Tous les tests
docs/           Documentation et charte
setup/          Scripts d'installation QEMU et Pi
data/synthetic/ Données synthétiques UNIQUEMENT
demo/           Script et matériel de démo
```

## Règles importantes

- **Jamais de données médicales réelles** sur le dépôt
- Toujours passer par une Pull Request pour merger sur `main`
- Minimum 1 commit par jour de travail actif

## Installation

Voir [setup/README_install.md](setup/README_install.md)
