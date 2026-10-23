"""PDF 换页检查：把每个换页处「上一页底部 + 下一页顶部」各截一条拼成一张图，逐个看有没有卡片 / 代码块 / 表格行被截成两半。
用法：uv run --with pymupdf --with pillow python -I check_pages.py <报告.pdf> <输出.png> [条高比例，默认 0.22]
只看整页缩略图会漏掉卡片和短代码块被截断；页数多时会拆成 <输出>-2.png …"""
import sys
import pymupdf as fitz
from PIL import Image, ImageDraw

pdf, out = sys.argv[1], sys.argv[2]; frac = float(sys.argv[3]) if len(sys.argv) > 3 else 0.22
doc = fitz.open(pdf); pages = []
for p in doc:
    pix = p.get_pixmap(dpi=80); pages.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
print(f"{len(pages)} 页")
strips = []
for i in range(len(pages) - 1):
    a, b = pages[i], pages[i + 1]; h = int(a.height * frac)
    s = Image.new("RGB", (a.width, h * 2 + 26), "white"); d = ImageDraw.Draw(s)
    d.text((6, 4), f"p{i+1} bottom | p{i+2} top", fill="black")  # 默认字体没有中文
    s.paste(a.crop((0, a.height - h, a.width, a.height)), (0, 16)); d.line((0, h + 20, a.width, h + 20), fill="red", width=3)
    s.paste(b.crop((0, 0, b.width, h)), (0, h + 24)); strips.append(s)
if not strips: print("只有 1 页，没有换页处"); sys.exit()
per = 4  # 一张图放 4 个换页处，免得图太长看不清
for k in range(0, len(strips), per):
    grp = strips[k:k + per]; W = grp[0].width; H = sum(s.height + 8 for s in grp)
    img = Image.new("RGB", (W, H), (180, 180, 180)); y = 0
    for s in grp: img.paste(s, (0, y)); y += s.height + 8
    name = out if k == 0 else out.replace(".png", f"-{k // per + 1}.png"); img.save(name); print("换页拼图", name)
