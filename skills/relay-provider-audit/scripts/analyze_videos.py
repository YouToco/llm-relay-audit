"""核成片：规格 / 帧数 / 编码器与合规标签 / 抽帧 / 频谱。
用法：uv run --with numpy --with pillow python analyze_videos.py <输出目录> "标签=文件路径" ["标签=文件路径" ...]
  ffmpeg：环境变量 FF > PATH 上的 ffmpeg > imageio-ffmpeg（uv run --with imageio-ffmpeg …）；
  ffprobe：环境变量 FFPROBE > FF 同目录 > PATH；都没有（或 FFPROBE=none）就退回解析 `ffmpeg -i` 的输出。没装 numpy / pillow 就跳过频谱，其余照出。
读：编码 / profile / 分辨率 / 帧率（29.97 也行）/ 码率（流没标就用容器码率）/ 帧数 / 音轨 / 容器标签 / AIGC 标签 / 码流里的 x264 core、x265 build。
输出：<输出目录>/video_analysis.json 和 <输出目录>/frames/<tag>-first|mid|last.png（tag 由标签生成，见 json）；
解读：编码器 / 容器标签 / 合规标签和官方成片一致 → 没被转码；频谱只能排除明显放大，分不出原生 480p 和超分 720p。"""
import json, os, re, shutil, subprocess, sys
from fractions import Fraction


def find_ffmpeg():
    ff = os.environ.get("FF") or shutil.which("ffmpeg")
    if not ff:
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            sys.exit("找不到 ffmpeg：装一个，或 FF=$(uv run --with imageio-ffmpeg python -c \"import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())\")")
    return ff


def find_ffprobe(ff):
    env = os.environ.get("FFPROBE")
    if env: return None if env.lower() == "none" else env
    d, base = os.path.split(ff)
    cand = os.path.join(d, base.replace("ffmpeg", "ffprobe")) if "ffmpeg" in base else ""
    if cand and cand != ff and os.path.isfile(cand) and os.access(cand, os.X_OK): return cand
    return shutil.which("ffprobe")


def run(*a):
    """只用参数列表调子进程，不经 shell。"""
    return subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)


def src(path):
    """file: 前缀：防止 ffmpeg 把 'http:'、'concat:' 之类的文件名当协议，也防止以 - 开头被当选项。"""
    return "file:" + os.path.abspath(path)


def tag_of(name): return re.sub(r"[^0-9A-Za-z一-鿿]+", "_", name).strip("_") or "v"


def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None


def rate(s):
    try:
        f = Fraction(str(s))
        return float(f) if f > 0 else None
    except (ValueError, ZeroDivisionError): return None


def short(v, n=60): v = str(v); return v if len(v) < n else v[:36] + f"…({len(v)})"


def parse_aigc(v):
    if v is None: return None
    try:
        j = json.loads(v)
        return {k: short(x) for k, x in j.items()} if isinstance(j, dict) else short(v, 120)
    except ValueError: return short(v, 120)


def parse_ffmetadata(text):
    """解析 -f ffmetadata 的全局段：处理 \\ 续行和 \\= \\; \\# \\\\ 转义。"""
    out, lines, i = {}, text.split("\n"), 0
    while i < len(lines):
        ln = lines[i]; i += 1
        if ln.startswith("["): break  # 后面是 [STREAM] / [CHAPTER]
        if not ln or ln.startswith(";") or ln.startswith("#"): continue
        while (len(ln) - len(ln.rstrip("\\"))) % 2 == 1 and i < len(lines):  # 奇数个反斜杠结尾 = 续行
            ln = ln[:-1] + "\n" + lines[i]; i += 1
        k, esc, cur = None, False, []
        for ch in ln:
            if esc: cur.append(ch); esc = False
            elif ch == "\\": esc = True
            elif ch == "=" and k is None: k = "".join(cur); cur = []
            else: cur.append(ch)
        if k is not None: out[k] = "".join(cur)
    return out


def probe_ffprobe(fp, path):
    r = run(fp, "-v", "error", "-of", "json", "-show_streams", "-show_format", "-i", src(path))
    if r.returncode != 0: raise RuntimeError(r.stderr.strip()[-300:] or "ffprobe 失败")
    j = json.loads(r.stdout or "{}")
    st = j.get("streams", []); fm = j.get("format", {})
    v = next((s for s in st if s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")), None)
    a = next((s for s in st if s.get("codec_type") == "audio"), None)
    if v is None: raise RuntimeError("没有视频流")
    ftags = fm.get("tags") or {}; vtags = v.get("tags") or {}
    vb = num(v.get("bit_rate")); fb = num(fm.get("bit_rate"))
    return {
        "codec": v.get("codec_name"), "profile": v.get("profile"), "pix_fmt": v.get("pix_fmt"),
        "w": v.get("width"), "h": v.get("height"),
        "fps": rate(v.get("avg_frame_rate")) or rate(v.get("r_frame_rate")), "fps_raw": v.get("avg_frame_rate") or v.get("r_frame_rate"),
        "vkbps": round(vb / 1000) if vb else None, "vkbps_source": "stream" if vb else ("format" if fb else None),
        "fmt_kbps": round(fb / 1000) if fb else None,
        "duration": num(fm.get("duration")) or num(v.get("duration")),
        "nb_frames": int(v["nb_frames"]) if str(v.get("nb_frames", "")).isdigit() else None,
        "audio": None if a is None else {"codec": a.get("codec_name"), "kbps": round(num(a.get("bit_rate")) / 1000) if num(a.get("bit_rate")) else None,
                                          "sample_rate": a.get("sample_rate"), "channels": a.get("channels")},
        "encoder": [x for x in (ftags.get("encoder"), vtags.get("encoder"), vtags.get("handler_name"), vtags.get("vendor_id")) if x],
        "format_tags": {k: short(x) for k, x in ftags.items()},
        "aigc": parse_aigc(ftags.get("AIGC")),
        "_fb": fb,
    }


def probe_ffmpeg(ff, path):
    """没有 ffprobe 时解析 `ffmpeg -i`：帧率可能是 29.97、码率可能缺。"""
    info = run(ff, "-hide_banner", "-nostdin", "-i", src(path)).stderr
    sl = next((l for l in info.splitlines() if re.search(r"Stream #\S+.*: Video: ", l) and "attached pic" not in l), None)
    if sl is None: raise RuntimeError((info.strip().splitlines() or ["ffmpeg 读不了"])[-1])
    body = sl.split("Video: ", 1)[1]
    m = re.match(r"(\w+)(?: \(([^)]*)\))?", body)
    res = re.search(r"(?<![0-9a-fx])(\d{2,5})x(\d{2,5})(?![0-9])", body)
    kb = re.search(r"(\d+) kb/s", body); fps = re.search(r"([\d.]+)(k?) fps", body) or re.search(r"([\d.]+)(k?) tbr", body)
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    al = next((l for l in info.splitlines() if re.search(r"Stream #\S+.*: Audio: ", l)), None)
    meta = parse_ffmetadata(run(ff, "-hide_banner", "-nostdin", "-loglevel", "error", "-i", src(path), "-f", "ffmetadata", "-").stdout)
    fb = re.search(r"bitrate: (\d+) kb/s", info)
    return {
        "codec": m.group(1) if m else None, "profile": m.group(2) if m else None, "pix_fmt": None,
        "w": int(res.group(1)) if res else None, "h": int(res.group(2)) if res else None,
        "fps": (float(fps.group(1)) * (1000 if fps.group(2) else 1)) if fps else None, "fps_raw": fps.group(0) if fps else None,
        "vkbps": int(kb.group(1)) if kb else None, "vkbps_source": "stream" if kb else ("format" if fb else None),
        "fmt_kbps": int(fb.group(1)) if fb else None,
        "duration": int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3)) if dur else None,
        "nb_frames": None,
        "audio": None if al is None else {"codec": (re.search(r"Audio: (\w+)", al) or [None, None])[1],
                                          "kbps": int(re.search(r"(\d+) kb/s", al).group(1)) if re.search(r"(\d+) kb/s", al) else None},
        "encoder": re.findall(r"^\s*(?:encoder|handler_name|vendor_id)\s*: (.*)$", info, re.M),
        "format_tags": {k: short(x) for k, x in meta.items()},
        "aigc": parse_aigc(meta.get("AIGC")),
        "_fb": int(fb.group(1)) * 1000 if fb else None,
    }


SEI = re.compile(rb"x264 - core \d+(?: r\d+ [0-9a-f]+)?|x265 \(build \d+\)[\x20-\x7e]{0,60}")


def encoder_sei(path, limit=512 << 20):
    """扫码流里的编码器 SEI（x264 core / x265 build），容器标签改了它也还在；分块读，最多 512MB。"""
    found, tail, seen = {}, b"", 0
    with open(path, "rb") as fh:
        while seen < limit and len(found) < 2:
            buf = fh.read(4 << 20)
            if not buf: break
            seen += len(buf); chunk = tail + buf
            for m in SEI.finditer(chunk):
                found.setdefault(m.group(0)[:4], m.group(0).decode("ascii", "replace").split(" - H.265")[0].strip())
            tail = chunk[-160:]
    return list(found.values())


def grab(ff, path, out, *seek):
    if os.path.exists(out): os.remove(out)
    run(ff, "-y", "-nostdin", "-loglevel", "error", *seek, "-i", src(path), "-frames:v", "1", "-update", "1", out)
    return os.path.exists(out) and os.path.getsize(out) > 0


def spectrum(png):
    """中帧频谱 + 拉普拉斯方差 + 降采样往返 PSNR；缺 numpy / pillow 返回 None。"""
    try:
        import numpy as np
        from PIL import Image
    except ImportError: return None
    im = Image.open(png).convert("L"); W, H = im.size
    if W < 4 or H < 4: return None
    g = np.asarray(im, dtype=np.float64); g = g - g.mean()
    F = np.abs(np.fft.fftshift(np.fft.fft2(g * np.outer(np.hanning(H), np.hanning(W))))) ** 2
    yy, xx = np.indices(F.shape); rr = np.hypot((yy - H / 2) / (H / 2), (xx - W / 2) / (W / 2)); tot = F.sum() or 1.0
    r = {f"hf_gt{x}": float(F[rr > x / 100].sum() / tot) for x in (50, 75, 90)}
    lap = (-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]); r["lap_var"] = float(lap.var())
    down = im.resize((W // 2, H // 2), Image.LANCZOS).resize((W, H), Image.LANCZOS)
    mse = ((np.asarray(im, dtype=np.float64) - np.asarray(down, dtype=np.float64)) ** 2).mean()
    r["psnr_down2_up"] = float(10 * np.log10(255 ** 2 / mse)) if mse > 0 else 99.0
    return r


def analyze(ff, fp, name, path, fdir, tag):
    r = {"path": path, "tag": tag}
    if not os.path.isfile(path): r["error"] = "文件不存在"; return r
    try: info = probe_ffprobe(fp, path) if fp else probe_ffmpeg(ff, path)
    except (RuntimeError, ValueError) as e: r["error"] = str(e); return r
    fb = info.pop("_fb"); r.update(info); r["probe"] = "ffprobe" if fp else "ffmpeg -i"
    if r["vkbps"] is None and fb: r["vkbps"] = round(fb / 1000)  # 流没标码率就用容器总码率（含音频，偏高）
    nf = re.findall(r"frame=\s*(\d+)", run(ff, "-hide_banner", "-nostdin", "-i", src(path), "-map", "0:v:0", "-f", "null", "-").stderr.replace("\r", "\n"))
    r["frames"] = int(nf[-1]) if nf else r.get("nb_frames")
    r["bpp"] = round(r["vkbps"] * 1000 / (r["w"] * r["h"] * r["fps"]), 3) if r["vkbps"] and r["w"] and r["h"] and r["fps"] else None
    d = r["duration"] or 0
    pngs = {lab: os.path.join(fdir, f"{tag}-{lab}.png") for lab in ("first", "mid", "last")}
    ok = {"first": grab(ff, path, pngs["first"], "-ss", "0"),
          "mid": grab(ff, path, pngs["mid"], "-ss", f"{d / 2:.3f}")}
    ok["last"] = grab(ff, path, pngs["last"], "-sseof", "-0.1") or grab(ff, path, pngs["last"], "-ss", f"{max(d - 0.1, 0):.3f}")
    r["encoder_sei"] = encoder_sei(path)
    r["frames_png"] = {k: (v if ok[k] else None) for k, v in pngs.items()}
    if ok["mid"]:
        sp = spectrum(pngs["mid"])
        if sp: r.update(sp)
        else: r["spectrum"] = "跳过（缺 numpy / pillow）"
    r["file_bytes"] = os.path.getsize(path)
    return r


def main(argv):
    if len(argv) < 2 or argv[0] in ("-h", "--help"):
        print(__doc__); return 0 if argv[:1] in (["-h"], ["--help"]) else 2
    out, pairs = argv[0], argv[1:]
    vids = []
    for a in pairs:
        if "=" not in a: print(f"参数要写成 标签=文件路径：{a!r}", file=sys.stderr); return 2
        vids.append(a.split("=", 1))
    ff = find_ffmpeg(); fp = find_ffprobe(ff)
    fdir = os.path.join(out, "frames"); os.makedirs(fdir, exist_ok=True)
    res, used, bad = {}, set(), 0
    for name, path in vids:
        tag = tag_of(name); t, n = tag, 2
        while t in used: t = f"{tag}_{n}"; n += 1
        used.add(t)
        r = analyze(ff, fp, name, path, fdir, t); res[name] = r
        if r.get("error"): bad += 1; print(name, "失败：", r["error"], file=sys.stderr); continue
        hf = f"hf>50%={r['hf_gt50']:.4f} >75%={r['hf_gt75']:.5f}" if "hf_gt50" in r else "频谱跳过"
        print(name, f"{r['w']}x{r['h']} {r['codec']}/{r['profile']} {r['fps'] and round(r['fps'], 3)}fps {r['duration']}s frames={r['frames']}",
              f"v={r['vkbps']}kbps({r['vkbps_source']}) bpp={r['bpp']} audio={'yes' if r['audio'] else 'no'} {hf} enc={r['encoder']}",
              f"sei={r['encoder_sei']} aigc={'yes' if r.get('aigc') else 'no'}", flush=True)
    with open(os.path.join(out, "video_analysis.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
