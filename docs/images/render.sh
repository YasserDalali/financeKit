#!/usr/bin/env bash
# Render sheets to PNG at 2x with headless Chrome. Usage: ./render.sh name [name...]  (names without .svg)
# The background is transparent, so the rounded corners show the page behind the image (light or dark).
cd "$(dirname "$0")"
for n in "$@"; do
  google-chrome --headless --no-sandbox --disable-gpu --hide-scrollbars --default-background-color=00000000 \
    --force-device-scale-factor=2 --window-size=1600,$(grep -o "viewBox=\"0 0 1600 [0-9]*" "$n.svg" | head -1 | grep -o "[0-9]*$") \
    --screenshot="$PWD/$n.png" "file://$PWD/$n.svg" >/dev/null 2>&1 && echo "rendered $n"
done
