#!/bin/sh
# 把报告 HTML（可以是只有 <title><style><body> 的 HTML 片段）转成 A4 PDF：本机 Chrome / Chromium 无头打印。
# 用法：html_to_pdf.sh <输入.html> <输出.pdf> [html lang，默认 zh-CN]
# 找浏览器：$CHROME → google-chrome / google-chrome-stable / chromium / chromium-browser → macOS 的 /Applications 里的 Chrome / Chromium。
# 要点：片段没有 doctype / charset，先补外壳；末尾强制注入「标签不换行」样式（窄列会把 .tag 挤成一字一行）；
# 字体只用本机字体（report_style.html 不连外网，没有的字回落到系统字体）；--virtual-time-budget 等图片排版；报告里要有 @media print 和 @page。
# 只有 root 跑才加 --no-sandbox；临时文件放 mktemp -d，退出时清掉；Chrome 失败或没写出 PDF 就非 0 退出（127 = 没找到浏览器）。
set -eu
[ $# -ge 2 ] || { echo "用法：html_to_pdf.sh <输入.html> <输出.pdf> [lang]" >&2; exit 2; }
IN=$1; OUT=$2; HLANG=${3:-zh-CN}
[ -f "$IN" ] || { echo "找不到输入：$IN" >&2; exit 2; }

find_chrome() {
  if [ -n "${CHROME:-}" ]; then
    if [ -x "$CHROME" ]; then echo "$CHROME"; return 0; fi
    if command -v "$CHROME" >/dev/null 2>&1; then command -v "$CHROME"; return 0; fi
    echo "CHROME=$CHROME 不是可执行文件" >&2; return 1
  fi
  for c in google-chrome google-chrome-stable chromium chromium-browser; do
    if command -v "$c" >/dev/null 2>&1; then command -v "$c"; return 0; fi
  done
  for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" "/Applications/Chromium.app/Contents/MacOS/Chromium" \
           "$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" "$HOME/Applications/Chromium.app/Contents/MacOS/Chromium"; do
    if [ -x "$c" ]; then echo "$c"; return 0; fi
  done
  return 1
}
if ! CH=$(find_chrome); then
  echo "找不到 Chrome / Chromium，没法转 PDF。装一个：macOS 装 Google Chrome（或 brew install --cask chromium）；Ubuntu / Debian 装 google-chrome-stable 或 apt install chromium；" >&2
  echo "装在别处就设环境变量 CHROME=<浏览器可执行文件路径>。HTML 已经生成，也可以用浏览器打开后手动「打印 → 存为 PDF」。" >&2
  exit 127
fi

TMPD=$(mktemp -d "${TMPDIR:-/tmp}/report-pdf.XXXXXX")
trap 'rm -rf "$TMPD"' EXIT
trap 'exit 130' INT TERM
PAGE="$TMPD/page.html"; LOG="$TMPD/chrome.log"
{ printf '<!doctype html><html lang="%s"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>' "$HLANG"
  cat "$IN"
  printf '<style>.tag,.badge,.pill{white-space:nowrap!important;display:inline-block!important}</style></html>'; } > "$PAGE"

SANDBOX=""; [ "$(id -u)" = 0 ] && SANDBOX="--no-sandbox"
rm -f "$OUT"
# 独立的临时 profile：不和正在用的 Chrome 抢 profile 锁
if ! "$CH" --headless=new $SANDBOX --disable-gpu --no-first-run --no-default-browser-check --user-data-dir="$TMPD/profile" \
     --virtual-time-budget=15000 --no-pdf-header-footer --print-to-pdf="$OUT" "file://$PAGE" >"$LOG" 2>&1; then
  echo "Chrome 转 PDF 失败（$CH）：" >&2; tail -n 20 "$LOG" >&2; exit 1
fi
if [ ! -s "$OUT" ]; then echo "Chrome 没写出 PDF：$OUT" >&2; tail -n 20 "$LOG" >&2; exit 1; fi
