"""核成片：规格 / 帧数 / 编码器与合规标签 / 抽帧 / 频谱。
用法：FF=<ffmpeg 路径> uv run --with numpy --with pillow python analyze_videos.py <输出目录> "标签=文件路径" ["标签=文件路径" ...]
  FF 取法：FF=$(uv run --with imageio-ffmpeg python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
输出：<输出目录>/video_analysis.json 和 <输出目录>/frames/<标签>-first|mid|last.png；
解读：编码器 / 容器标签 / 合规标签和官方成片一致 → 没被转码；频谱只能排除明显放大，分不出原生 480p 和超分 720p。"""
import json, os, re, subprocess, sys
import numpy as np
from PIL import Image
FF = os.environ["FF"]; OUT = sys.argv[1]; VIDS = dict(a.split("=", 1) for a in sys.argv[2:])
def sh(*a): return subprocess.run(a, capture_output=True, text=True)
def tag_of(name): return re.sub(r"[^0-9A-Za-z一-鿿]+", "_", name).strip("_")
os.makedirs(f"{OUT}/frames", exist_ok=True); res = {}
for name, path in VIDS.items():
    r = {"path": path, "tag": tag_of(name)}
    info = sh(FF, "-hide_banner", "-i", path).stderr
    m = re.search(r"Video: (\w+).*?, (\d+)x(\d+).*?, (\d+) kb/s, (\d+) fps", info)
    r["codec"] = m.group(1); r["w"], r["h"], r["vkbps"], r["fps"] = map(int, m.groups()[1:])
    r["duration"] = re.search(r"Duration: ([\d:.]+)", info).group(1)
    r["audio"] = (re.search(r"Audio: (.*?), (?:fltp|s16|\w+), (\d+) kb/s", info) or [None])[0]
    r["encoder"] = re.findall(r"encoder\s+: (.*)", info)
    meta = sh("sh", "-c", f'"{FF}" -hide_banner -i "{path}" -f ffmetadata - 2>/dev/null').stdout
    a = re.search(r"^AIGC=(.*)$", meta, re.M)
    if a:
        try:
            j = json.loads(a.group(1).replace("\\", ""))
            r["aigc"] = {k: (v if len(str(v)) < 60 else str(v)[:36] + f"…({len(str(v))})") for k, v in j.items()}
        except Exception: r["aigc"] = a.group(1)[:120]
    nf = re.findall(r"frame=\s*(\d+)", sh(FF, "-hide_banner", "-i", path, "-map", "0:v:0", "-f", "null", "-").stderr.replace("\r", "\n"))
    r["frames"] = int(nf[-1]) if nf else None
    r["bpp"] = round(r["vkbps"] * 1000 / (r["w"] * r["h"] * r["fps"]), 3)
    t = r["tag"]
    for lab in ("first", "mid", "last"):
        out = f"{OUT}/frames/{t}-{lab}.png"
        if lab == "last": sh(FF, "-y", "-loglevel", "error", "-sseof", "-0.1", "-i", path, "-frames:v", "1", "-update", "1", out)
        else: sh(FF, "-y", "-loglevel", "error", "-ss", "0" if lab == "first" else "1", "-i", path, "-frames:v", "1", out)
    im = Image.open(f"{OUT}/frames/{t}-mid.png").convert("L"); W, H = im.size
    g = np.asarray(im, dtype=np.float64); g = g - g.mean()
    F = np.abs(np.fft.fftshift(np.fft.fft2(g * np.outer(np.hanning(H), np.hanning(W))))) ** 2
    yy, xx = np.indices(F.shape); rr = np.hypot((yy - H / 2) / (H / 2), (xx - W / 2) / (W / 2)); tot = F.sum()
    r["hf_gt50"], r["hf_gt75"], r["hf_gt90"] = (float(F[rr > x].sum() / tot) for x in (0.5, 0.75, 0.9))
    lap = (-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]); r["lap_var"] = float(lap.var())
    down = im.resize((W // 2, H // 2), Image.LANCZOS).resize((W, H), Image.LANCZOS)
    mse = ((np.asarray(im, dtype=np.float64) - np.asarray(down, dtype=np.float64)) ** 2).mean()
    r["psnr_down2_up"] = float(10 * np.log10(255 ** 2 / mse)) if mse > 0 else 99.0
    r["file_bytes"] = os.path.getsize(path); res[name] = r
    print(name, f"{r['w']}x{r['h']} {r['fps']}fps {r['duration']} frames={r['frames']} v={r['vkbps']}kbps bpp={r['bpp']} audio={'yes' if r['audio'] else 'no'} hf>50%={r['hf_gt50']:.4f} >75%={r['hf_gt75']:.5f} enc={r['encoder']}")
json.dump(res, open(f"{OUT}/video_analysis.json", "w"), ensure_ascii=False, indent=1)
