#!/bin/bash

# Simple PDF generation from praval.md using pandoc
# Usage: ./simple_pdf.sh

echo "📚 Generating PDF from praval.md..."

pandoc praval.md \
  -o "Praval_Complete_Manual.pdf" \
  --pdf-engine=xelatex \
  --number-sections \
  --highlight-style=tango \
  -V geometry:margin=1in \
  -V fontsize:10pt \
  -V documentclass:article \
  -V colorlinks:true \
  -V linkcolor:blue \
  -V urlcolor:blue \
  --wrap=auto \
  --columns=78 \
  --standalone

if [ $? -eq 0 ]; then
  echo "✅ PDF generated successfully: Praval_Complete_Manual.pdf"
  echo "📏 File size: $(du -h Praval_Complete_Manual.pdf | cut -f1)"
else
  echo "❌ PDF generation failed"
  echo "Make sure you have pandoc and xelatex installed:"
  echo "  brew install pandoc"
  echo "  brew install --cask mactex"
fi