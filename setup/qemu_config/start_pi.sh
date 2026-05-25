#!/bin/bash
# Script de démarrage QEMU — Raspberry Pi 5 simulé (ARM64)
# Auteur : IMBOYO MUANAMBELO DONBENI — ClariBio P10 — S1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="$SCRIPT_DIR/raspios_arm64.img"
FIRMWARE="$SCRIPT_DIR/QEMU_EFI.fd"

if [ ! -f "$IMAGE" ]; then
    echo "ERREUR : Image Raspberry Pi OS introuvable : $IMAGE"
    echo "Suivre l'Étape 2 de setup/README_install.md"
    exit 1
fi

if [ ! -f "$FIRMWARE" ]; then
    echo "ERREUR : Firmware UEFI introuvable : $FIRMWARE"
    echo "Suivre l'Étape 3 de setup/README_install.md"
    exit 1
fi

echo "Démarrage de QEMU — Raspberry Pi 5 ARM64"
echo "SSH disponible sur : ssh -p 2222 pi@localhost"
echo "Interface web ClariBio : http://localhost:8080"
echo ""

qemu-system-aarch64 \
    -machine virt \
    -cpu cortex-a76 \
    -smp 4 \
    -m 4096 \
    -bios "$FIRMWARE" \
    -drive file="$IMAGE",format=raw,if=virtio \
    -netdev user,id=net0,hostfwd=tcp::2222-:22,hostfwd=tcp::8080-:8080 \
    -device virtio-net-pci,netdev=net0 \
    -device virtio-rng-pci \
    -nographic \
    -serial mon:stdio
