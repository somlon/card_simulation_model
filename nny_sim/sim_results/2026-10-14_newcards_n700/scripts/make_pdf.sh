#!/bin/bash
# md → html(pandoc) → pdf(chromium headless). 한글 글꼴: WenQuanYi Zen Hei
#   bash make_pdf.sh <입력.md> <출력.pdf> [제목]
set -e
export LANG=C.UTF-8 LC_ALL=C.UTF-8
IN="$1"; OUT="$2"; TITLE="${3:-보고서}"
D=$(mktemp -d)
cat > "$D/style.css" <<'EOF'
@page { size: A4; margin: 16mm 14mm 16mm 14mm; }
body { font-family: "WenQuanYi Zen Hei", sans-serif; font-size: 10pt; line-height: 1.55; color: #111; max-width: none; margin: 0; }
h1 { font-size: 18pt; border-bottom: 2px solid #333; padding-bottom: 4px; page-break-before: always; }
h1:first-of-type { page-break-before: avoid; }
h2 { font-size: 14pt; border-bottom: 1px solid #999; padding-bottom: 2px; margin-top: 1.6em; }
h3 { font-size: 12pt; margin-top: 1.3em; }
h4 { font-size: 10.5pt; margin-top: 1.1em; }
h2, h3, h4 { page-break-after: avoid; }
table { border-collapse: collapse; margin: 0.6em 0; font-size: 8.6pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #aaa; padding: 2px 5px; vertical-align: top; }
th { background: #eee; }
code { font-family: "WenQuanYi Zen Hei Mono", monospace; font-size: 8.8pt; background: #f4f4f4; }
pre { font-family: "WenQuanYi Zen Hei Mono", monospace; font-size: 7.6pt; line-height: 1.35; background: #f7f7f7; border: 1px solid #ddd; padding: 6px; white-space: pre-wrap; word-break: break-all; }
pre code { background: none; font-size: inherit; }
blockquote { border-left: 3px solid #bbb; margin-left: 0; padding-left: 10px; color: #333; }
nav#TOC { page-break-after: always; }
nav#TOC ul { list-style: none; padding-left: 1.2em; }
EOF
pandoc "$IN" -f markdown-implicit_figures -t html5 -s --toc --toc-depth=2 \
  --metadata title="$TITLE" --css "$D/style.css" --embed-resources -o "$D/out.html"
/opt/pw-browsers/chromium --headless=new --no-sandbox --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$OUT" "file://$D/out.html" 2>/dev/null
ls -l "$OUT"
rm -rf "$D"
