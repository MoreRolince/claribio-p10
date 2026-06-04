# Guide d'installation — ClariBio sur QEMU (Raspberry Pi 5 simulé)

**Auteur :** IMBOYO MUANAMBELO DONBENI  
**Semaine :** S1 — Phase 1  
**Objectif :** Simuler un Raspberry Pi 5 (ARM64) sur PC en attendant le matériel physique

---

## Prérequis système

| Composant | Minimum requis |
|-----------|---------------|
| OS hôte | Ubuntu 22.04 / Debian 12 / macOS 13+ |
| RAM | 8 Go (4 Go alloués à QEMU) |
| Stockage libre | 20 Go |
| CPU | Architecture x86_64 ou ARM64 |

---

## Étape 1 — Installer QEMU

### Sur Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install -y qemu-system-aarch64 qemu-utils qemu-efi-aarch64
```

### Sur macOS
```bash
brew install qemu
```

### Vérifier l'installation
```bash
qemu-system-aarch64 --version
# Attendu : QEMU emulator version 8.x.x
```

---

## Étape 2 — Télécharger Raspberry Pi OS 64-bit

```bash
cd setup/qemu_config/

# Télécharger l'image officielle (environ 1 Go)
wget https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2024-11-19/2024-11-19-raspios-bookworm-arm64-lite.img.xz

# Décompresser
xz -d 2024-11-19-raspios-bookworm-arm64-lite.img.xz

# Renommer pour clarté
mv 2024-11-19-raspios-bookworm-arm64-lite.img raspios_arm64.img

# Agrandir l'image à 16 Go pour avoir de l'espace
qemu-img resize raspios_arm64.img 16G
```

---

## Étape 3 — Télécharger le firmware UEFI

```bash
# Sur Linux
cp /usr/share/qemu-efi-aarch64/QEMU_EFI.fd setup/qemu_config/

# Sur macOS (Homebrew)
cp $(brew --prefix)/share/qemu/edk2-aarch64-code.fd setup/qemu_config/QEMU_EFI.fd
```

---

## Étape 4 — Script de démarrage QEMU

Le script de démarrage est dans `setup/qemu_config/start_pi.sh` :

```bash
bash setup/qemu_config/start_pi.sh
```

Ce script démarre QEMU avec :
- 4 cœurs ARM Cortex-A76 (similaire Pi 5)
- 4 Go de RAM
- Réseau en mode user (NAT)
- Port SSH 2222 → 22 (accès SSH depuis l'hôte)

---

## Étape 5 — Premier démarrage et configuration

### Connexion SSH (après démarrage complet, ~2 minutes)
```bash
ssh -p 2222 pi@localhost
# Mot de passe par défaut : raspberry
```

### Configuration initiale dans QEMU
```bash
# Étendre la partition pour utiliser tout l'espace (16 Go)
sudo raspi-config  # → Advanced Options → Expand Filesystem

# Mettre à jour le système
sudo apt update && sudo apt upgrade -y

# Installer Python 3.11
sudo apt install -y python3 python3-venv python3-pip

# Vérifier
python3 --version
# Attendu : Python 3.12.x (Ubuntu 24.04 — compatible avec toutes les libs du projet)

# Installer les outils de développement
sudo apt install -y git curl wget build-essential
```

---

## Étape 6 — Simulation caméra et microphone

En environnement QEMU, les périphériques physiques ne sont pas disponibles.
On utilise des fichiers de test à la place.

```bash
# Dans QEMU — simuler une capture caméra
sudo apt install -y v4l-utils ffmpeg

# Créer une image de test (simule une photo de bilan biologique)
ffmpeg -f lavfi -i color=c=white:size=1920x1080:duration=1 -vframes 1 /tmp/test_capture.jpg

# Vérifier que Python peut lire l'image
python3.11 -c "from PIL import Image; img = Image.open('/tmp/test_capture.jpg'); print('Caméra simulée OK:', img.size)"

# Simuler le microphone (fichier audio de test)
ffmpeg -f lavfi -i sine=frequency=440:duration=3 /tmp/test_audio.wav
aplay /tmp/test_audio.wav 2>/dev/null && echo "Audio OK" || echo "Audio simulé (pas de sortie son en QEMU)"
```

---

## Étape 7 — Hotspot Wi-Fi (simulation réseau local)

En QEMU, le réseau est géré en NAT. Pour simuler le hotspot :

```bash
# Dans QEMU — installer hostapd et dnsmasq (pour référence Pi physique)
sudo apt install -y hostapd dnsmasq

# En attendant le Pi physique, l'interface FastAPI sera accessible via :
# http://localhost:8080 (depuis l'hôte via le port forwarding QEMU)
```

---

## Étape 8 — Cloner le projet dans QEMU

```bash
# Dans QEMU
git clone https://github.com/MoreRolince/claribio-p10.git
cd claribio-p10

# Créer l'environnement virtuel Python
python3.11 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
```

---

## Vérification finale — Critères S1

Exécuter le script de vérification :

```bash
bash setup/qemu_config/verify_s1.sh
```

| Critère | Commande de vérification | Résultat attendu |
|---------|--------------------------|------------------|
| Pi OS démarre | `uname -m` | `aarch64` |
| SSH opérationnel | `ssh -p 2222 pi@localhost echo OK` | `OK` |
| Python 3.11 installé | `python3.11 --version` | `Python 3.11.x` |
| Caméra simulée | Script verify_s1.sh | `Caméra simulée OK` |
| Micro simulé | Script verify_s1.sh | `Audio simulé OK` |

---

## Transfert vers Pi physique (S6 — quand matériel reçu)

Quand le Raspberry Pi 5 physique arrivera (coordination avec Mark Gray) :

```bash
# Depuis l'hôte — copier le projet sur le Pi
rsync -avz --exclude='.venv' --exclude='__pycache__' \
  claribio-p10/ pi@<IP_DU_PI>:/home/pi/claribio-p10/

# Sur le Pi physique — reconfigurer les périphériques réels
# Voir docs/architecture/system_architecture.md pour les détails GPIO
```

---

## Résolution de problèmes courants

| Problème | Cause probable | Solution |
|----------|---------------|----------|
| QEMU très lent | Pas d'accélération KVM | Sur Linux : `sudo modprobe kvm` puis relancer |
| SSH refusé | QEMU pas encore démarré | Attendre 2 min, réessayer |
| `qemu: uncaught target signal 4` | Image corrompue | Retélécharger l'image |
| Python 3.11 introuvable | Dépôt non mis à jour | `sudo apt update` puis réinstaller |
