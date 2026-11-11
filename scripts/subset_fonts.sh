#!/usr/bin/env bash
# Rebuilds fonts/*.woff2 from full font files. Only needed when the glyph set changes.
# Usage: scripts/subset_fonts.sh <playfair-500.woff2> <playfair-500-italic.woff2> <hanken-400.woff2> <hanken-600.woff2> <jetbrains-mono-regular.ttf>
# Needs fonttools + brotli (pip install fonttools brotli). All five families are SIL OFL 1.1.
set -euo pipefail
cd "$(dirname "$0")/.."
# Printable ASCII, middle dot, and the arrows the cards use.
UNI="U+0020-007E,U+00B7,U+2190-2193,U+2197"
sub() { pyftsubset "$1" --unicodes="$UNI" --layout-features=kern --no-hinting --desubroutinize --flavor=woff2 --output-file="fonts/$2.woff2"; }
sub "$1" display
sub "$2" display-italic
sub "$3" body
sub "$4" body-semibold
sub "$5" mono
ls -l fonts
