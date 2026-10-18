#!/usr/bin/env bash
# Descarga los paquetes oficiales de iconos de las cuatro nubes (icons/packages.tsv), verifica su sha256 y
# extrae a dist/icons/ solo los iconos que usan los puzzles. Ni los paquetes ni los iconos se commitean (ICONS.md).
#
#   scripts/fetch-icons.sh [carpeta de salida]      por defecto dist/icons
#
# ARCH_ICON_CACHE  caché de descargas (por defecto .cache/icons, ignorada por git)
# ARCH_ICON_LOCAL  carpetas con paquetes ya descargados, separadas por ':'; se copian solo si su sha256 coincide
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out="${1:-$root/dist/icons}"
cache="${ARCH_ICON_CACHE:-$root/.cache/icons}"
mkdir -p "$cache"

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d ' ' -f 1
  else
    shasum -a 256 "$1" | cut -d ' ' -f 1
  fi
}

# Copia el paquete desde una carpeta local si existe con la huella esperada.
from_local() {
  local file="$1" sum="$2" dest="$3" dirs="${ARCH_ICON_LOCAL:-}" dir
  while [[ -n "$dirs" ]]; do
    dir="${dirs%%:*}"
    if [[ "$dirs" == *:* ]]; then dirs="${dirs#*:}"; else dirs=""; fi
    if [[ -n "$dir" && -f "$dir/$file" && "$(sha256 "$dir/$file")" == "$sum" ]]; then
      cp "$dir/$file" "$dest"
      echo "icons: $file copiado de $dir"
      return 0
    fi
  done
  return 1
}

while IFS=$'\t' read -r id file sum url; do
  case "$id" in '' | '#'*) continue ;; esac
  dest="$cache/$file"
  if [[ -f "$dest" && "$(sha256 "$dest")" == "$sum" ]]; then
    echo "icons: $id ya está en la caché"
    continue
  fi
  if from_local "$file" "$sum" "$dest"; then
    continue
  fi
  echo "icons: descargando $id de $url"
  tmp="$(mktemp "$cache/.descarga.XXXXXX")"
  if ! curl -fsSL --proto '=https' --tlsv1.2 --retry 3 -o "$tmp" "$url"; then
    rm -f "$tmp"
    echo "icons: no se pudo descargar $id; revisa la URL vigente en la página oficial (ICONS.md)" >&2
    exit 1
  fi
  got="$(sha256 "$tmp")"
  if [[ "$got" != "$sum" ]]; then
    rm -f "$tmp"
    echo "icons: el sha256 de $id no coincide (esperado $sum, recibido $got)." >&2
    echo "icons: el proveedor cambió el paquete; revísalo y actualiza icons/packages.tsv e ICONS.md." >&2
    exit 1
  fi
  mv "$tmp" "$dest"
done <"$root/icons/packages.tsv"

python3 -I "$root/tools/icons.py" --cache "$cache" --out "$out"
