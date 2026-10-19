#!/usr/bin/env bash
# Exports each draw.io diagram to SVG and adds the motion layer (animate.py), producing the animated
# labNN-<name>.svg that the lab READMEs embed. Guide: README.md next to this script.
#
#   shared/diagram-motion/render.sh                         every diagram listed in flows.json
#   shared/diagram-motion/render.sh NN-topic/diagrams/labNN-<name>.drawio [...]
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
cd "$root"

drawio="$(command -v drawio || command -v draw.io || true)"
if [[ -z "$drawio" && -x /Applications/draw.io.app/Contents/MacOS/draw.io ]]; then
  drawio=/Applications/draw.io.app/Contents/MacOS/draw.io
fi
if [[ -z "$drawio" ]]; then
  echo "render.sh: draw.io desktop not found, install it first" >&2
  exit 1
fi

if [[ $# -gt 0 ]]; then
  files=("$@")
else
  files=()
  while IFS= read -r line; do files+=("$line"); done < <(python3 -I "$here/animate.py" --list)
fi

# Electron refuses to run as root unless the Chromium sandbox is turned off (a root CI container).
sandbox=()
if [[ $EUID -eq 0 ]]; then
  sandbox=(--no-sandbox)
fi

for f in "${files[@]}"; do
  "$drawio" "${sandbox[@]}" -x -f svg -o "${f%.drawio}.svg" "$f" > /dev/null
done
python3 -I "$here/animate.py" "${files[@]}"
