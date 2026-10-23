"""取成片里嵌入的 ComfyUI 工作流（ffmetadata 的 prompt 标签），列出模型 / 采样参数。
判断供应商是不是自建管线（开源权重）而不是调官方 API 的关键一步。没有 prompt 标签就说明不是 ComfyUI 产物。
用法：FF=<ffmpeg> python3 extract_comfy.py <mp4>…      输出 <mp4 同名>.comfy-prompt.json
逐个节点打印 class_type 和常见的模型 / 采样字段；完整工作流看 .comfy-prompt.json。"""
import json, os, re, subprocess, sys
FF = os.environ["FF"]
B = chr(92)  # 反斜杠；ffmetadata 把 \ = ; # 和换行都加了反斜杠转义
KEYS = ("ckpt_name", "unet_name", "clip_name", "vae_name", "lora_name", "steps", "cfg", "sampler_name", "scheduler",
        "noise_seed", "seed", "width", "height", "length", "fps", "frame_rate", "GPU")
UNESC = [(B + "\n", "\n"), (B + B, B), (B + "=", "="), (B + ";", ";"), (B + "#", "#")]
for f in sys.argv[1:]:
    t = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-i", f, "-f", "ffmetadata", "-"], capture_output=True, text=True, errors="replace").stdout
    m = re.search(r"^prompt=(.*?)(?=^\w+=|\Z)", t, flags=re.M | re.S)
    if not m: print(f, "没有 prompt 标签"); continue
    raw = m.group(1)
    for a, b in UNESC: raw = raw.replace(a, b)
    g = json.loads(raw); open(re.sub(r"\.mp4$", "", f) + ".comfy-prompt.json", "w").write(json.dumps(g, ensure_ascii=False, indent=1))
    print(os.path.basename(f))
    for nid, node in g.items():
        inp = node.get("inputs", {}) if isinstance(node, dict) else {}
        got = {k: inp[k] for k in KEYS if k in inp and not isinstance(inp[k], list)}
        if got: print(f"  [{nid}] {node.get('class_type')}", " | ".join(f"{k}={v}" for k, v in got.items()))
