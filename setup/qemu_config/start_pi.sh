#!/bin/bash
# Script de démarrage QEMU — Ubuntu 24.04 ARM64 (simule Raspberry Pi 5)
# Auteur : IMBOYO MUANAMBELO DONBENI — ClariBio P10 — S1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="$SCRIPT_DIR/ubuntu-arm64.img"
FIRMWARE="$SCRIPT_DIR/QEMU_EFI.fd"
CLOUD_INIT="$SCRIPT_DIR/cloud-init.iso"

if [ ! -f "$IMAGE" ]; then
    echo "ERREUR : Image Ubuntu ARM64 introuvable : $IMAGE"
    exit 1
fi

echo "Démarrage de QEMU — Ubuntu 24.04 ARM64 (simulant Raspberry Pi 5)"
echo "SSH disponible sur : ssh -p 2223 pi@localhost (mot de passe : claribio2026)"
echo "Interface web ClariBio : http://localhost:8888"
echo "Attendre ~1 minute au premier démarrage (cloud-init)"
echo ""

qemu-system-aarch64 \
    -machine virt \
    -cpu cortex-a76 \
    -smp 4 \
    -m 4096 \
    -bios "$FIRMWARE" \
    -drive file="$IMAGE",format=qcow2,if=virtio \
    -drive file="$CLOUD_INIT",format=raw,if=virtio,readonly=on \
    -netdev user,id=net0,hostfwd=tcp::2223-:22,hostfwd=tcp::8888-:8080 \
    -device virtio-net-pci,netdev=net0 \
    -device virtio-rng-pci \
    -nographic \
    -serial mon:stdio
