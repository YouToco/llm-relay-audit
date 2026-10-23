"""取成片里嵌入的 ComfyUI 工作流（ffmetadata 的 prompt / workflow 标签），列出模型 / 采样参数。
判断供应商是不是自建管线（开源权重）而不是调官方 API 的关键一步。没有 prompt 标签就说明不是 ComfyUI 产物。
用法：python3 extract_comfy.py <mp4>…      输出 <mp4 去扩展名>.comfy-prompt.json（不是合法 JSON 就存 .comfy-prompt.txt 原文）
  ffmpeg：环境变量 FF > PATH 上的 ffmpeg > imageio-ffmpeg（uv run --with imageio-ffmpeg python extract_comfy.py …）。
逐个节点打印 class_type 和常见的模型 / 采样字段；完整工作流看 .comfy-prompt.json。"""
import json, os, shutil, subprocess, sys

KEYS = ("ckpt_name", "unet_name", "clip_name", "vae_name", "lora_name", "steps", "cfg", "sampler_name", "scheduler",
        "noise_seed", "seed", "width", "height", "length", "fps", "frame_rate", "GPU")


def find_ffmpeg():
    ff = os.environ.get("FF") or shutil.which("ffmpeg")
    if not ff:
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            sys.exit("找不到 ffmpeg：装一个，或 uv run --with imageio-ffmpeg python extract_comfy.py …")
    return ff


def parse_ffmetadata(text):
    """解析 -f ffmetadata 的全局段：处理 \\ 续行和 \\= \\; \\# \\\\ 转义。"""
    out, lines, i = {}, text.split("\n"), 0
    while i < len(lines):
        ln = lines[i]; i += 1
        if ln.startswith("["): break
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


def summarize(g):
    """ComfyUI API 格式：{节点号: {class_type, inputs}}；也兼容 UI 格式 {nodes: [...]}。"""
    nodes = g.items() if isinstance(g, dict) and "nodes" not in g else \
        ((str(n.get("id")), n) for n in g.get("nodes", []) if isinstance(n, dict)) if isinstance(g, dict) else []
    rows = []
    for nid, node in nodes:
        if not isinstance(node, dict): continue
        inp = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        got = {k: inp[k] for k in KEYS if k in inp and not isinstance(inp[k], (list, dict))}
        if not got and isinstance(node.get("widgets_values"), list) and node.get("type"):
            got = {"widgets": [w for w in node["widgets_values"] if isinstance(w, (str, int, float))][:6]}
        if got: rows.append(f"  [{nid}] {node.get('class_type') or node.get('type')} " + " | ".join(f"{k}={v}" for k, v in got.items()))
    return rows


def one(ff, f):
    if not os.path.isfile(f): print(f, "文件不存在"); return 1
    r = subprocess.run([ff, "-hide_banner", "-nostdin", "-loglevel", "error", "-i", "file:" + os.path.abspath(f), "-f", "ffmetadata", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if r.returncode != 0: print(f, "ffmpeg 读不了：", (r.stderr.strip().splitlines() or ["?"])[-1]); return 1
    meta = parse_ffmetadata(r.stdout)
    raw = meta.get("prompt") or meta.get("workflow")
    if raw is None: print(f, "没有 prompt 标签（不是 ComfyUI 产物）"); return 0
    base = os.path.splitext(f)[0]
    try: g = json.loads(raw)
    except ValueError as e:
        with open(base + ".comfy-prompt.txt", "w", encoding="utf-8") as fh: fh.write(raw)
        print(f, f"有 prompt 标签但不是合法 JSON（{e}），原文存 {base}.comfy-prompt.txt；有这个标签本身就说明走过 ComfyUI"); return 0
    with open(base + ".comfy-prompt.json", "w", encoding="utf-8") as fh: json.dump(g, fh, ensure_ascii=False, indent=1)
    rows = summarize(g)
    print(os.path.basename(f), "ComfyUI 工作流", f"（{len(g['nodes']) if isinstance(g, dict) and isinstance(g.get('nodes'), list) else len(g) if isinstance(g, (dict, list)) else 0} 个节点）", "" if rows else "：没认出模型 / 采样字段，看 .comfy-prompt.json")
    for x in rows: print(x)
    return 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__); return 0 if argv[:1] in (["-h"], ["--help"]) else 2
    ff = find_ffmpeg()
    return 1 if any([one(ff, f) for f in argv]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
