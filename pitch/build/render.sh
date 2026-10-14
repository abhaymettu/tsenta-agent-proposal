#!/bin/zsh
# Render the PPTX through Keynote to PDF, then rasterize every page for pixel QA.
set -euo pipefail
ROOT=${0:A:h:h}
PPTX="$ROOT/outputs/Tsenta-Pitch-2026-10-14.pptx"
PDF="$ROOT/outputs/Tsenta-Pitch-2026-10-14.pdf"
PREV="$ROOT/outputs/preview"
rm -f "$PDF"
osascript <<EOF
tell application "Keynote"
  set d to open POSIX file "$PPTX"
  delay 2
  export d to POSIX file "$PDF" as PDF with properties {PDF image quality:Best}
  close d saving no
end tell
EOF
rm -rf "$PREV" && mkdir -p "$PREV"
pdftoppm -r 144 -png "$PDF" "$PREV/slide"
ls "$PREV" | wc -l
