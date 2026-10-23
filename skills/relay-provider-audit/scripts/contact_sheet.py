"""把 analyze_videos.py 抽的首 / 中 / 尾帧拼成对照图。
用法：uv run --with pillow python contact_sheet.py <输出 jpg> <frames 目录> "行标签=标签前缀" ["行标签=标签前缀" ...]   （前缀 = video_analysis.json 里的 tag）"""
import sys
from PIL import Image, ImageDraw
out, fdir = sys.argv[1], sys.argv[2]; rows = [a.split("=", 1) for a in sys.argv[3:]]
W, PAD, L = 560, 8, 150
first = Image.open(f"{fdir}/{rows[0][1]}-mid.png"); H = int(first.height * W / first.width)
sheet = Image.new("RGB", (L + 3 * (W + PAD), len(rows) * (H + PAD) + 30), (24, 24, 28)); d = ImageDraw.Draw(sheet)
for j, t in enumerate(("first", "mid", "last")): d.text((L + j * (W + PAD) + 8, 8), t, fill=(220, 220, 220))
for i, (lab, tag) in enumerate(rows):
    y = 30 + i * (H + PAD); d.text((8, y + H // 2), lab, fill=(220, 220, 220))
    for j, t in enumerate(("first", "mid", "last")):
        im = Image.open(f"{fdir}/{tag}-{t}.png").convert("RGB"); im = im.resize((W, int(im.height * W / im.width)), Image.LANCZOS)
        sheet.paste(im, (L + j * (W + PAD), y))
sheet.save(out, quality=88); print(out, sheet.size)
