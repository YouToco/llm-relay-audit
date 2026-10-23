"""供应商探针公共调用：全部请求与响应写进 jsonl（key 打码），失败自动重试网络抖动。
用法（在任务目录里）：
    import sys; sys.path.insert(0, "<skill>/scripts"); from probe_lib import *
    K=<key> B=https://供应商域名 LOG=artifacts/probes.jsonl python3 your_probe.py
环境变量：K 密钥（不入库）、B 地址、LOG 日志路径。"""
import json, os, time, urllib.request, urllib.error
K = os.environ["K"]; B = os.environ["B"].rstrip("/"); LOG = os.environ.get("LOG", "artifacts/probes.jsonl")
KEEP_H = ("x-request-id", "x-oneapi-request-id", "x-new-api-version", "server", "content-type",
          "x-dashscope-request-id", "req-cost-time", "date", "last-modified", "etag")

def mask(s):
    return s.replace(K, "sk-***") if isinstance(s, str) else s

def call(method, path_or_url, body=None, headers=None, label="", key=None, timeout=60, retries=3):
    """返回 (status, parsed_json_or_text, response_headers)。path 以 / 开头会拼上 B。"""
    url = path_or_url if path_or_url.startswith("http") else B + path_or_url
    # 带 UA：Cloudflare 会按 UA 拦 Python-urllib（1010，403 纯文本）；UA 环境变量可覆盖
    h = {"Authorization": f"Bearer {key or K}", "Content-Type": "application/json", "User-Agent": os.environ.get("UA", "Anthropic/Python 0.70.0")}
    if headers: h.update(headers)
    h = {k: v for k, v in h.items() if v is not None}
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, method=method, headers=h); t0 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r: status, raw, rh = r.status, r.read().decode(), dict(r.headers)
            except urllib.error.HTTPError as e: status, raw, rh = e.code, e.read().decode(), dict(e.headers)
            break
        except Exception as e:  # SSL EOF 之类的网络抖动
            if attempt == retries - 1: raise
            time.sleep(2)
    try: parsed = json.loads(raw)
    except Exception: parsed = raw[:2000]
    rec = {"label": label, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "method": method,
           "url": url.replace(B, "{base}"), "req_headers": {k: ("Bearer ***" if k == "Authorization" else v) for k, v in h.items()},
           "body": body, "status": status, "ms": int((time.time() - t0) * 1000),
           "resp_headers": {k: v for k, v in rh.items() if k.lower() in KEEP_H}, "resp": parsed}
    os.makedirs(os.path.dirname(LOG) or ".", exist_ok=True)
    with open(LOG, "a") as f: f.write(mask(json.dumps(rec, ensure_ascii=False)) + "\n")
    return status, parsed, rh

def used(path="/v1/dashboard/billing/usage"):
    """key 已用额度（new-api 系：美分；别的供应商没有就别用）。每个付费 / 疑似付费动作前后各读一次，差值 = 实扣。"""
    s, p, _ = call("GET", path, label="余额 usage")
    return p.get("total_usage") if isinstance(p, dict) else None

def vendor_log(path="/api/log/token"):
    """new-api 系供应商：用这把 key 免费读自己的调用日志。type 2 = 出片（other.model_price 美元价；quota 500000 = $1），
    type 5 = 被拒请求（content 里是响应里被抹掉的真实原因）。"""
    s, p, _ = call("GET", path, label="供应商日志")
    return p.get("data", []) if isinstance(p, dict) else []

def poll_task(path, done=("SUCCEEDED", "FAILED", "CANCELED", "UNKNOWN"), every=10, max_n=60, label="poll"):
    """轮询 DashScope 形状的任务到终态，返回 (最后响应, 秒数)。"""
    t0 = time.time(); q = None
    for i in range(max_n):
        time.sleep(every)
        s, q, _ = call("GET", path, label=f"{label} {i}")
        st = ((q or {}).get("output") or {}).get("task_status") if isinstance(q, dict) else None
        if st in done or s >= 400: break
    return q, int(time.time() - t0)
