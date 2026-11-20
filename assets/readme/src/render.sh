#!/usr/bin/env bash
# Re-render the README images from the HTML sources (needs Google Chrome and the Inter + IBM Plex Mono fonts).
# Usage: ./render.sh   (run inside assets/readme/src)
set -euo pipefail
render() { google-chrome --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
  --default-background-color=00000000 --force-device-scale-factor=2 \
  --window-size="$2" --screenshot="$PWD/../$1.png" "file://$PWD/$1.html"; }
render banner 1280,400
render ecosystem 1280,620
render learning-path 1280,640
