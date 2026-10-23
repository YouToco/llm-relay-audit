#!/bin/sh
# 把报告 HTML（可以是只有 <title><style><body> 的 HTML 片段）转成 A4 PDF：本机 Chrome 无头打印。
# 用法：html_to_pdf.sh <输入.html> <输出.pdf>
# 要点：片段没有 doctype / charset，先补外壳；末尾强制注入「标签不换行」样式（窄列会把 .tag 挤成一字一行）；Google Fonts 要联网；--virtual-time-budget 等字体和图片；报告里要有 @media print 和 @page。
set -e
IN="$1"; OUT="$2"; TMP="$(mktemp --suffix=.html)"
{ printf '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>'; cat "$IN"; printf '<style>.tag,.badge,.pill{white-space:nowrap!important;display:inline-block!important}</style></html>'; } > "$TMP"
google-chrome --headless=new --no-sandbox --disable-gpu --virtual-time-budget=15000 --no-pdf-header-footer --print-to-pdf="$OUT" "file://$TMP" 2>&1 | tail -1
rm -f "$TMP"
