#!/usr/bin/env bash
# Build completo del ejercicio "completa el diagrama": valida los puzzles, descarga y verifica los iconos oficiales
# y escribe el sitio estático en dist/ (abre dist/index.html directo desde el disco). Guía: AUTHORING.md.
#
#   ./build.sh [carpeta de salida]      por defecto dist
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="${1:-$root/dist}"

python3 -I "$root/tools/build.py" validate "$root/puzzles"
"$root/scripts/fetch-icons.sh" "$out/icons"
python3 -I "$root/tools/build.py" build --out "$out"
echo "build: listo, abre $out/index.html"
