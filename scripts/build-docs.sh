#!/usr/bin/env bash
# Merge docs/ into groupint-manual.md and build dist/groupint-manual.pdf
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Merging Markdown sources..."
python3 scripts/merge_docs.py

mkdir -p dist

if [[ "${BUILD_DOCS_PDF:-1}" == "0" ]]; then
  echo "==> PDF skipped (BUILD_DOCS_PDF=0)."
  exit 0
fi

if ! command -v pandoc >/dev/null 2>&1; then
  echo "WARN: pandoc not found — Markdown manual generated; PDF not built." >&2
  echo "  Arch/Manjaro: sudo pacman -S pandoc texlive-basic" >&2
  echo "  Debian/Ubuntu: sudo apt install pandoc texlive-xetex" >&2
  exit 0
fi

PDF_ENGINE=""
for engine in xelatex pdflatex lualatex tectonic; do
  if command -v "$engine" >/dev/null 2>&1; then
    PDF_ENGINE="$engine"
    break
  fi
done

if [[ -z "$PDF_ENGINE" ]]; then
  echo "No LaTeX PDF engine found (tried xelatex, pdflatex, lualatex, tectonic)." >&2
  echo "Install a TeX distribution, then re-run this script." >&2
  exit 1
fi

echo "==> Building PDF with pandoc ($PDF_ENGINE)..."
pandoc docs/groupint-manual.md -o dist/groupint-manual.pdf \
  --from markdown \
  --pdf-engine="$PDF_ENGINE" \
  --toc \
  --toc-depth=3 \
  -V geometry:margin=1in \
  -V documentclass=report \
  "${PANDOC_EXTRA[@]}"

echo "==> Done."
echo "    Markdown: docs/groupint-manual.md"
echo "    PDF:      dist/groupint-manual.pdf"
