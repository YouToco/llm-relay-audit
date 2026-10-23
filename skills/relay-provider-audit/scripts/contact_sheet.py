"""把 analyze_videos.py 抽的首 / 中 / 尾帧拼成对照图（不需要 ffmpeg，只要 pillow）。
用法：uv run --with pillow python contact_sheet.py <输出 jpg> <frames 目录> "行标签=tag" ["行标签=tag" ...]
  tag = video_analysis.json 里每条的 tag（帧文件名 <tag>-first|mid|last.png 的前缀）；只写 tag 不写「=」时行标签就用 tag。
  中文行标签要 CJK 字体：环境变量 FONT=<ttf/ttc 路径>，不给就在常见位置找，找不到用默认字体（中文可能显示成方块）。
  缺帧的格子画灰底「缺」，不报错。"""
import os, sys

FONTS = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
         "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", "/System/Library/Fonts/PingFang.ttc",
         "/System/Library/Fonts/STHeiti Light.ttc", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]


def font(ImageFont, size=18):
    for p in [os.environ.get("FONT")] + FONTS:
        if p and os.path.isfile(p):
            try: return ImageFont.truetype(p, size)
            except OSError: pass
    try: return ImageFont.load_default(size)
    except TypeError: return ImageFont.load_default()


def text(d, xy, s, f):
    try: d.text(xy, s, fill=(220, 220, 220), font=f)
    except UnicodeEncodeError:  # 老版 pillow 的位图字体只认 latin-1
        d.text(xy, s.encode("ascii", "backslashreplace").decode(), fill=(220, 220, 220), font=f)


def main(argv):
    if len(argv) < 3 or argv[0] in ("-h", "--help"):
        print(__doc__); return 0 if argv[:1] in (["-h"], ["--help"]) else 2
    try: from PIL import Image, ImageDraw, ImageFont
    except ImportError: print("缺 pillow：uv run --with pillow python contact_sheet.py …", file=sys.stderr); return 2
    out, fdir = argv[0], argv[1]
    rows = [a.split("=", 1) if "=" in a else [a, a] for a in argv[2:]]
    cols = ("first", "mid", "last")
    path = lambda tag, t: os.path.join(fdir, f"{tag}-{t}.png")
    ref = next((path(tag, t) for _, tag in rows for t in ("mid", "first", "last") if os.path.isfile(path(tag, t))), None)
    if ref is None: print(f"{fdir} 里一张帧都没找到（要 <tag>-first|mid|last.png）", file=sys.stderr); return 1
    W, PAD, L = 560, 8, 150
    with Image.open(ref) as im0: H = max(1, int(im0.height * W / im0.width))
    f = font(ImageFont)
    sheet = Image.new("RGB", (L + 3 * (W + PAD), len(rows) * (H + PAD) + 30), (24, 24, 28)); d = ImageDraw.Draw(sheet)
    for j, t in enumerate(cols): text(d, (L + j * (W + PAD) + 8, 6), t, f)
    miss = 0
    for i, (lab, tag) in enumerate(rows):
        y = 30 + i * (H + PAD); text(d, (8, y + H // 2 - 10), lab, f)
        for j, t in enumerate(cols):
            x = L + j * (W + PAD); p = path(tag, t)
            if not os.path.isfile(p):
                d.rectangle([x, y, x + W - 1, y + H - 1], fill=(60, 60, 64)); text(d, (x + W // 2 - 10, y + H // 2 - 10), "缺", f); miss += 1
                continue
            with Image.open(p) as im:
                im = im.convert("RGB"); im = im.resize((W, max(1, int(im.height * W / im.width))), Image.LANCZOS)
                sheet.paste(im.crop((0, 0, W, min(H, im.height))), (x, y))
    sheet.save(out, quality=88); print(out, sheet.size, f"缺 {miss} 张" if miss else "")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
