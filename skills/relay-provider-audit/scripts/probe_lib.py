"""供应商探针公共调用：每个请求（含失败的每次尝试）都写进 jsonl，key 全部打码（规则 13）。

用法（在任务目录里）：
    import sys; sys.path.insert(0, "<skill>/scripts"); from probe_lib import *
    K=<key> B=https://供应商域名 LOG=artifacts/probes.jsonl python3 your_probe.py
    python3 probe_lib.py            # 打印本说明

环境变量（第一次用到才读，`import probe_lib` 不需要；缺了在调用时报清楚的错）：
    供应商：K 密钥（不入库）、B 地址、LOG 日志（默认 artifacts/probes.jsonl）、AUTH 鉴权方式（默认 bearer）
    官方：  OK 密钥、OB 地址、OLOG 日志（默认 artifacts/official.jsonl）、OAUTH 鉴权方式（默认 bearer）
    UA：    User-Agent，默认 "Anthropic/Python 0.70.0"。这是**冒充官方 SDK 的 UA**：Cloudflare 会按 UA 拦
            Python-urllib（1010，403 纯文本），带 SDK UA 才能测到真实行为。代价是供应商看到的是 SDK UA；
            UA 矩阵（空 / requests / httpx / curl / Go）逐个传 headers={"User-Agent": ...}，报告里写明用的哪个。

接口（原有签名不变）：
    call(method, path_or_url, body=None, headers=None, label="", key=None, timeout=60, retries=3,
         auth=<AUTH>, side="supplier", log=None) -> (status, parsed, headers)
      - path 以 / 开头拼 B。绝对 URL 的源（协议 + 域名 + 端口）和 B 不同（CDN 下载、官方接口）时**不带默认 key**，
        要带就显式传 key=；跨源重定向也会去掉鉴权类请求头。
      - auth："bearer"（Authorization: Bearer）| "raw"（Authorization: <key>，new-api 访问令牌）| "x-api-key"（Anthropic）
        | "x-goog-api-key"（Gemini）| "api-key"（Azure）| None（不带）。headers 里值为 None 的头会删掉（大小写不敏感）。
      - body：dict / list 发 JSON；str / bytes 原样发。parsed：JSON → 对象；文本 → str；二进制 → bytes（日志只记长度）。
      - headers：全部响应头（dict，取值大小写不敏感）。status 为 HTTP 状态码；网络失败则记一条 status=null 后抛原异常。
    官方一侧记进 artifacts/official.jsonl：
        OK=<官方key> OB=https://api.anthropic.com OAUTH=x-api-key python3 your_probe.py
        call("POST", "/v1/messages", body, headers={"anthropic-version": "2023-06-01"}, label="ok", side="official")
      或自建：off = Client("https://api.anthropic.com", os.environ["OK"], "artifacts/official.jsonl", auth="x-api-key")
              off.call(...) / off.call_stream(...)（Client 的方法和下面的模块函数一一对应）
    call_stream(同 call 的参数, sse=None) -> (status, events, headers)
      SSE 原文（打码后）写 <LOG 所在目录>/<label>.sse（重名加 -2…），jsonl 记 sse_file、ttfb_ms（收到响应头）、
      first_event_ms、first_content_ms（第一个带正文 / 思考 / 工具调用增量的事件）、ms（总耗时）、event_count、
      event_seq（事件名序列，连续同名合并成 [名, 次数]）。报告引用 {"file": "artifacts/<label>.sse", "head": 6, "tail": 3}。
      events = [{"event": 名, "data": 对象或文本}]；不是 SSE（报错 JSON 等）时第二项和 call() 一样是 parsed。
    used(path=None)：已用额度（美分）。**不可信**（见过一单 $0.29 读成 200 美分），只作参考；依次试
      /v1/dashboard/billing/usage、/api/usage/token，用的哪个记在 label 和 SUPPLIER.last_used_source。
    spent(since_ts=None, pages=10)：读 new-api 系供应商日志，type 2 记录 quota / 500000 求和 = 实扣美元（since_ts 为 unix 秒）。
      微型调用 quota 会取整成 0，要看逐笔 usage_usd 就用 vendor_log()。
    vendor_log(path="/api/log/token", pages=1, page_size=100, key_param=False)：读日志（翻页、按 id 去重）；
      key_param=True 时把 key 放查询参数 ?key=（one-api 老版本要这样；日志里照样打码）。
    poll_task(path, done=None, every=10, max_n=60, label="poll", status_path=None, preset=None) -> (最后响应, 秒数)
      preset："dashscope"（output.task_status）| "ark"（status）| "minimax"（task.status，老接口 status）；
      都不给就依次找 output.task_status / status / task.status / data.status。终态大小写不敏感，默认
      succeeded / success / completed / failed / failure / fail / canceled / cancelled / expired / unknown。
    register_secret(s)：其它要打码的串（管理令牌、新建出来的 key 等）；mask(s)：用已知密钥给任意串打码。

重试：连接没建立（DNS / 拒绝连接 / 连接超时 / TLS 握手，urllib 的 URLError）所有方法都重试；请求可能已到服务器
      （读超时、断连、重定向之后的失败）只有 GET / HEAD / OPTIONS 重试，POST / PUT / PATCH / DELETE 绝不重发（防重复扣费、重复出片）。
      重试不看 HTTP 状态码（429 / 503 按规则 9 自己复测）。每次尝试都记一条（attempt 第几次；失败带 error、phase）。
打码：K / OK / key= / 鉴权类请求头（authorization、*api-key*、*token*、*secret*、cookie）的值 / key、*token*、*secret* 类
      查询参数，以及像 key 的串（sk-…、AKIA…、AIza… 等），在 url、请求头、body、响应、响应头、.sse 里一律替换；
      空 key 或短于 6 个字符的 key 直接报错（会让打码失效）。响应头全部保留，set-cookie 只留 cookie 名，鉴权类值打码。
"""
import gzip, json, os, re, sys, threading, time, urllib.error, urllib.parse, urllib.request

DEFAULT_UA = "Anthropic/Python 0.70.0"
RETRY_SLEEP = 2  # 重试间隔（秒）
IDEMPOTENT = {"GET", "HEAD", "OPTIONS"}
DONE = {"succeeded", "success", "completed", "failed", "failure", "fail", "canceled", "cancelled", "expired", "unknown"}
PRESETS = {"dashscope": ("output.task_status",), "ark": ("status",), "minimax": ("task.status", "status")}
AUTO_STATUS = ("output.task_status", "status", "task.status", "data.status")
AUTH = {"bearer": ("Authorization", "Bearer {}"), "raw": ("Authorization", "{}"), "x-api-key": ("x-api-key", "{}"),
        "x-goog-api-key": ("x-goog-api-key", "{}"), "api-key": ("api-key", "{}")}
KEEP_H = ()  # 旧版的响应头白名单，现在全部保留；留着名字给老脚本
SENS_REQ_H = re.compile(r"authorization|api[-_]?key|token|secret|cookie|password", re.I)
SENS_QS = re.compile(r"^(key|apikey|api[-_]key|password|.*token.*|.*secret.*)$", re.I)
BIN_CT = re.compile(r"^(image|video|audio|font)/|^application/(octet-stream|pdf|zip|gzip|x-tar|x-protobuf|protobuf|grpc)", re.I)
# 和 build_report.py 的 SECRET_RE 一致：生成器会挡这些串，这里先替换掉
SECRET_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{16,}|ark-[0-9a-f]{8}-[0-9a-f-]{20,}|Bearer\s+(?!\*)[A-Za-z0-9._\-]{16,}"
                       r"|AKLT[A-Za-z0-9]{24,}|AKIA[0-9A-Z]{16}|\b[a-z]{2,6}_live_[A-Za-z0-9]{8,}|AIza[0-9A-Za-z_\-]{30,})")

# 兼容老脚本：from probe_lib import * 仍能拿到 K / B / LOG / UA（可能是 None）；真正用的值在调用时再读环境变量
K = os.environ.get("K"); B = (os.environ.get("B") or "").rstrip("/") or None
LOG = os.environ.get("LOG", "artifacts/probes.jsonl"); UA = os.environ.get("UA", DEFAULT_UA)
_SNAP = {"K": K, "B": B, "LOG": LOG, "UA": UA}  # 脚本改了 probe_lib.K 等就用改后的值，否则读当时的环境变量
_LOCK = threading.Lock(); _SECRETS = set(); _UNSET = object()


# ---------------- 打码 ----------------
def register_secret(s):
    """登记一个要打码的串（≥ 6 字符才做全文替换，更短的会误伤正文）。"""
    if isinstance(s, str) and len(s.strip()) >= 6:
        with _LOCK: _SECRETS.add(s.strip())


def _secrets():
    with _LOCK: return sorted(_SECRETS, key=len, reverse=True)  # 长的先换


def _tag(s): return "sk-***" if s.startswith("sk-") else "***"


def _redact(m):
    s = m.group(0)
    for p in ("Bearer ", "sk-", "ark-", "AKLT", "AKIA", "AIza"):
        if s.startswith(p): return p + "***"
    return s.split("_live_")[0] + "_live_***" if "_live_" in s else "***"


def _mask_str(s, secrets):
    for x in secrets:
        for v in {x, urllib.parse.quote(x, safe=""), urllib.parse.quote_plus(x)}:
            if v in s: s = s.replace(v, _tag(x))
    return SECRET_RE.sub(_redact, s)


def _mask(o, secrets):
    if isinstance(o, str): return _mask_str(o, secrets)
    if isinstance(o, dict): return {_mask(k, secrets): _mask(v, secrets) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_mask(v, secrets) for v in o]
    return o


def mask(s):
    """用已登记的密钥（含环境变量 K / OK）给任意串或对象打码。"""
    for v in ("K", "OK"): register_secret(os.environ.get(v))
    register_secret(globals().get("K"))
    return _mask(s, _secrets())


def _mask_hval(v):
    v = str(v)
    for p in ("Bearer ", "Basic "):
        if v[:len(p)].lower() == p.lower(): return p + "***"
    return "***"


def _sens_resp_h(name):
    n = name.lower()
    return (n in ("set-cookie", "set-cookie2", "cookie", "authorization", "proxy-authorization")
            or bool(re.search(r"api[-_]?key|secret|password", n)) or ("token" in n and "limit" not in n))  # 限流头 *-tokens-* 要留


def _mask_resp_h(h):
    out = {}
    for k, v in (h or {}).items():
        if k.lower().startswith("set-cookie"):
            v = "; ".join(c.split(";")[0].split("=")[0].strip() + "=***" for c in str(v).split("\n") if c.strip())
        elif _sens_resp_h(k): v = _mask_hval(v)
        out[k] = v
    return out


def _mask_url(url):
    def sub(m):
        name = urllib.parse.unquote_plus(m.group(2))
        if SENS_QS.match(name):
            register_secret(urllib.parse.unquote_plus(m.group(3))); return f"{m.group(1)}{m.group(2)}=***"
        return m.group(0)
    return re.sub(r"([?&])([^=&#]+)=([^&#]*)", sub, url)


# ---------------- 小工具 ----------------
class Headers(dict):
    """响应头：普通 dict（可 json.dumps），取值大小写不敏感。多值头用 ", " 连接（set-cookie 用换行）。"""
    def _k(self, k):
        if dict.__contains__(self, k): return k
        return next((x for x in self if x.lower() == str(k).lower()), k)
    def __getitem__(self, k): return dict.__getitem__(self, self._k(k))
    def __contains__(self, k): return dict.__contains__(self, self._k(k))
    def get(self, k, d=None): return dict.get(self, self._k(k), d)


def _hdict(msg):
    out = Headers()
    for k in msg.keys():
        if k in out: continue
        vals = msg.get_all(k) or []
        out[k] = ("\n" if k.lower().startswith("set-cookie") else ", ").join(vals)
    return out


def _origin(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme.lower(), (p.hostname or "").lower(), p.port or {"http": 80, "https": 443}.get(p.scheme.lower())


def _decode(raw, rh):
    """→ (返回给调用方的值, 记进日志的值, 额外字段)。"""
    ctype = rh.get("content-type") or ""
    if "gzip" in (rh.get("content-encoding") or "").lower():
        try: raw = gzip.decompress(raw)
        except Exception: pass
    if BIN_CT.search(ctype) or b"\x00" in raw[:4096]:
        return raw, f"(二进制 {len(raw)} 字节，{ctype or '无 content-type'})", {"resp_len": len(raw)}
    m = re.search(r"charset=([\w.-]+)", ctype, re.I)
    try: text = raw.decode(m.group(1) if m else "utf-8", errors="replace")
    except LookupError: text = raw.decode("utf-8", errors="replace")
    try: p = json.loads(text); return p, p, {}
    except Exception: return text, text[:2000], ({"resp_len": len(text)} if len(text) > 2000 else {})


def _dig(o, dotted):
    for k in dotted.split("."):
        if isinstance(o, dict): o = o.get(k)
        elif isinstance(o, list) and k.isdigit() and int(k) < len(o): o = o[int(k)]
        else: return None
    return o


def _has_content(name, d):
    """这个 SSE 事件有没有正文 / 思考 / 工具调用增量（Anthropic / OpenAI Chat / Responses / Gemini）。"""
    if name == "content_block_delta": return True
    if not isinstance(d, dict): return False
    t = d.get("type")
    if isinstance(t, str) and t.endswith(".delta") and any(x in t for x in ("output_text", "reasoning", "function_call", "refusal")): return True
    for c in d.get("choices") or []:
        dl = (c.get("delta") or {}) if isinstance(c, dict) else {}
        if any(dl.get(k) for k in ("content", "reasoning_content", "reasoning", "tool_calls", "function_call")) or (isinstance(c, dict) and c.get("text")): return True
    for c in d.get("candidates") or []:
        if any(isinstance(p, dict) and (p.get("text") or p.get("functionCall")) for p in ((c.get("content") or {}).get("parts") or [])): return True
    return False


def _sse_path(log, label, sse):
    if sse: return sse
    d = os.path.dirname(log); base = (re.sub(r"[^\w.\-]+", "_", label).strip("._") or "stream")[:80]
    p, i = os.path.join(d, base + ".sse"), 2
    while os.path.exists(p): p, i = os.path.join(d, f"{base}-{i}.sse"), i + 1
    return p


class _Redirect(urllib.request.HTTPRedirectHandler):
    """跟随重定向，但换了源就去掉鉴权类请求头；记下发生过重定向（之后的失败不算「没发出去」）。"""
    redirected = False
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        self.redirected = True
        if new is not None and _origin(newurl) != _origin(req.full_url):
            for k in list(new.headers):
                if SENS_REQ_H.search(k): new.remove_header(k)
        return new


# ---------------- 调用器 ----------------
class Client:
    """一侧（供应商 / 官方 / 自定义）的调用器：base、key、log、auth 不给就在用到时按 env 里的变量名读环境变量。"""
    def __init__(self, base=None, key=None, log=None, auth=_UNSET, ua=None, env=None, default_log="artifacts/probes.jsonl"):
        self.base, self.key, self.log, self.auth, self.ua = base, key, log, auth, ua
        self.env = env or {}; self.default_log = default_log; self.last_used_source = None

    def _get(self, name):
        v = getattr(self, name)
        if name == "auth" and v is not _UNSET: return v  # 显式给了（含 None = 不带鉴权）
        if v is _UNSET: v = None
        var = self.env.get(name, "UA" if name == "ua" else None)
        if v is None and var:
            g = globals().get(var)
            v = g if var in _SNAP and g != _SNAP[var] else os.environ.get(var)
        if name == "log": return v or self.default_log
        if name == "ua": return v or DEFAULT_UA
        if name == "auth": v = "bearer" if v is None else v
        return v.strip() if isinstance(v, str) else v

    def _prepare(self, method, path_or_url, body, headers, key, auth):
        for v in ("K", "OK"): register_secret(os.environ.get(v))
        register_secret(globals().get("K")); register_secret(self._get("key"))
        base = (self._get("base") or "").rstrip("/")
        if path_or_url.startswith(("http://", "https://")): url = path_or_url
        elif not base: raise ValueError(f"{self.env.get('base', 'base')} 没设置：相对路径 {path_or_url!r} 要拼地址（或传绝对 URL）")
        else: url = base + path_or_url
        auth = self._get("auth") if auth is _UNSET else auth
        auth = None if auth in (None, "", "none") else str(auth).lower()
        same = bool(base) and _origin(url) == _origin(base)
        h = {}
        if auth and (key is not None or same):  # 外源（CDN / 官方）不带默认 key，显式 key= 才带
            k = key if key is not None else self._get("key")
            var = "key=" if key is not None else self.env.get("key", "key")
            if not isinstance(k, str) or len(k.strip()) < 6:
                raise ValueError(f"{var} 为空或太短：先 export {var}=<key>（或传 key=）；空 key 会让日志打码失效")
            if auth not in AUTH: raise ValueError(f"auth 只能是 {' / '.join(AUTH)} / None（现在是 {auth!r}）")
            n, fmt = AUTH[auth]; h[n] = fmt.format(k.strip()); register_secret(k)
        h.update({"Content-Type": "application/json", "User-Agent": self._get("ua")})
        for k2, v in (headers or {}).items():  # 大小写不敏感合并；None = 删掉
            for old in [x for x in h if x.lower() == k2.lower()]: del h[old]
            if v is not None: h[k2] = v
        for k2, v in h.items():
            if SENS_REQ_H.search(k2):  # 「Bearer xxx」只登记 xxx，日志里留下「Bearer ***」
                sch, _, rest = str(v).partition(" ")
                register_secret(rest if sch.lower() in ("bearer", "basic", "token") and rest else str(v))
        _mask_url(url)  # 登记查询参数里的 key
        if body is None: data, blog = None, None
        elif isinstance(body, (bytes, bytearray)): data, blog = bytes(body), f"(二进制 {len(body)} 字节)"
        elif isinstance(body, str): data, blog = body.encode("utf-8"), body
        else: data, blog = json.dumps(body, ensure_ascii=False).encode("utf-8"), body
        rec = {"label": "", "ts": "", "method": method, "url": self._disp(url, base),
               "req_headers": {k2: (_mask_hval(v) if SENS_REQ_H.search(k2) else v) for k2, v in h.items()}, "body": blog}
        return url, h, data, rec, base

    @staticmethod
    def _disp(url, base):
        url = _mask_url(url)
        return "{base}" + url[len(base):] if base and url.startswith(base) else url

    def _write(self, log, rec):
        rec = dict(rec); rec["resp_headers"] = _mask_resp_h(rec.get("resp_headers"))
        line = json.dumps(_mask(rec, _secrets()), ensure_ascii=False, default=str)
        with _LOCK:
            if os.path.dirname(log): os.makedirs(os.path.dirname(log), exist_ok=True)
            with open(log, "a", encoding="utf-8") as f: f.write(line + "\n")

    def _run(self, method, url, data, h, timeout, retries, rec0, log, consume):
        """按重试规则发请求；consume(r, rec) 读响应、填 rec、返回结果。每次尝试写一条。"""
        for attempt in range(1, max(1, int(retries)) + 1):
            rec = {**rec0, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": None, "ms": None,
                   "resp_headers": None, "resp": None, "attempt": attempt}
            t0 = time.time(); rd = _Redirect()
            try:
                req = urllib.request.Request(url, data=data, method=method, headers=h)
                try: r = urllib.request.build_opener(rd).open(req, timeout=timeout)
                except urllib.error.HTTPError as e: r = e
                rec["ttfb_ms"] = int((time.time() - t0) * 1000)
                with r:
                    rec["status"] = r.getcode(); rh = _hdict(r.headers); rec["resp_headers"] = rh
                    if r.geturl() and r.geturl() != url: rec["final_url"] = self._disp(r.geturl(), (self._get("base") or "").rstrip("/"))
                    out = consume(r, rec, t0, rh)
                rec["ms"] = int((time.time() - t0) * 1000); self._write(log, rec)
                return out
            except Exception as ex:
                pre = isinstance(ex, urllib.error.URLError) and not isinstance(ex, urllib.error.HTTPError) and not rd.redirected
                rec.update(ms=int((time.time() - t0) * 1000), error=f"{type(ex).__name__}: {ex}", phase="connect" if pre else "response")
                self._write(log, rec)
                if attempt >= retries or isinstance(ex, (ValueError, TypeError)) or not (pre or method in IDEMPOTENT): raise
                time.sleep(RETRY_SLEEP)

    def call(self, method, path_or_url, body=None, headers=None, label="", key=None, timeout=60, retries=3, auth=_UNSET, log=None):
        """返回 (status, parsed, response_headers)；见模块说明。"""
        method = method.upper(); url, h, data, rec0, _ = self._prepare(method, path_or_url, body, headers, key, auth)
        rec0["label"] = label
        def consume(r, rec, t0, rh):
            raw = r.read(); parsed, logged, extra = _decode(raw, rh)
            rec["resp"] = logged; rec.update(extra)
            return rec["status"], parsed, rh
        return self._run(method, url, data, h, timeout, retries, rec0, log or self._get("log"), consume)

    def call_stream(self, method, path_or_url, body=None, headers=None, label="", key=None, timeout=60, retries=3, auth=_UNSET, log=None, sse=None):
        """SSE 调用：原文落 .sse，jsonl 记时序；返回 (status, events, headers)。"""
        method = method.upper(); log = log or self._get("log")
        url, h, data, rec0, _ = self._prepare(method, path_or_url, body, headers, key, auth); rec0["label"] = label
        def consume(r, rec, t0, rh):
            if rec["status"] >= 400 or "event-stream" not in (rh.get("content-type") or "").lower():
                parsed, logged, extra = _decode(r.read(), rh); rec["resp"] = logged; rec.update(extra)
                return rec["status"], parsed, rh
            path = _sse_path(log, label, sse); rec["sse_file"] = path; rec["resp"] = f"(SSE 流，原文见 {path})"
            events, seq, cur, secrets = [], [], {"event": None, "data": []}, _secrets()
            rec.update(first_event_ms=None, first_content_ms=None, event_count=0, event_seq=seq)
            def dispatch():
                if not cur["data"] and not cur["event"]: return
                raw = "\n".join(cur["data"])
                try: d = json.loads(raw)
                except Exception: d = raw
                name = cur["event"] or (d.get("type") if isinstance(d, dict) and isinstance(d.get("type"), str) else None) or ("[DONE]" if raw.strip() == "[DONE]" else "message")
                events.append({"event": name, "data": d}); ms = int((time.time() - t0) * 1000)
                if seq and seq[-1][0] == name: seq[-1][1] += 1
                else: seq.append([name, 1])
                rec["event_count"] = len(events)
                if rec["first_event_ms"] is None: rec["first_event_ms"] = ms
                if rec["first_content_ms"] is None and _has_content(name, d): rec["first_content_ms"] = ms
                cur["event"], cur["data"] = None, []
            if os.path.dirname(path): os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as f:
                for b in r:
                    line = b.decode("utf-8", errors="replace"); f.write(_mask_str(line, secrets)); s = line.rstrip("\r\n")
                    if s == "": dispatch()
                    elif s.startswith(":"): continue
                    else:
                        field, _, val = s.partition(":"); val = val[1:] if val.startswith(" ") else val
                        if field == "event": cur["event"] = val
                        elif field == "data": cur["data"].append(val)
                dispatch()
            rec["resp"] = f"(SSE 流 {len(events)} 个事件，原文见 {path})"
            return rec["status"], events, rh
        return self._run(method, url, data, h, timeout, retries, rec0, log, consume)

    def used(self, path=None):
        """已用额度（美分）。**不可信**：见过一单 $0.29 读成 200 美分，实扣以 spent() / 供应商日志为准。
        不给 path 就依次试 /v1/dashboard/billing/usage（total_usage 美分）、/api/usage/token（new-api，total_used 额度 ÷ 5000）。"""
        srcs = [(path, "余额 usage", lambda p: p.get("total_usage"))] if path else [
            ("/v1/dashboard/billing/usage", "余额 usage", lambda p: p.get("total_usage")),
            ("/api/usage/token", "余额 usage /api/usage/token", lambda p: (p.get("data") or {}).get("total_used") / 5000)]
        for src, label, get in srcs:
            try:
                s, p, _ = self.call("GET", src, label=label)
                v = get(p) if s == 200 and isinstance(p, dict) else None
            except Exception: v = None
            if isinstance(v, (int, float)): self.last_used_source = src; return v
        return None

    def vendor_log(self, path="/api/log/token", pages=1, page_size=100, key_param=False, label="供应商日志"):
        """new-api 系供应商：用这把 key 免费读自己的调用日志。type 2 = 成功扣费（quota 500000 = $1，other.model_price 美元价），
        type 5 = 被拒请求（content 里是响应里被抹掉的真实原因）。pages > 1 时按 p=1,2… 翻页（兼容 0 / 1 起算、不分页的站），按 id 去重。"""
        out, seen = [], set()
        for i in range(max(1, pages)):
            q = {"page_size": page_size}
            if i: q["p"] = i
            if key_param: q["key"] = self._get("key")
            s, d, _ = self.call("GET", path + ("&" if "?" in path else "?") + urllib.parse.urlencode(q), label=label if not i else f"{label} p{i}")
            data = d.get("data") if isinstance(d, dict) else None
            items = data if isinstance(data, list) else ((data.get("items") or data.get("data") or []) if isinstance(data, dict) else [])
            new = [x for x in items if json.dumps(x.get("id", x) if isinstance(x, dict) else x, sort_keys=True, default=str) not in seen]
            for x in new: seen.add(json.dumps(x.get("id", x) if isinstance(x, dict) else x, sort_keys=True, default=str))
            out += new
            if not items or len(items) < page_size or (not new and i != 1): break  # p=1 重复第一页 = 1 起算，再试 p=2
        return out

    def spent(self, since_ts=None, path="/api/log/token", pages=10, page_size=100, key_param=False):
        """供应商日志 type 2 记录 quota / 500000 求和（美元）；since_ts（unix 秒）之前的不算。每个付费动作前后读、或按 since_ts 读。"""
        logs = self.vendor_log(path, pages=pages, page_size=page_size, key_param=key_param, label="供应商日志 spent")
        return round(sum((x.get("quota") or 0) for x in logs if isinstance(x, dict) and x.get("type") == 2
                         and (since_ts is None or (x.get("created_at") or 0) >= since_ts)) / 500000, 6)

    def poll_task(self, path, done=None, every=10, max_n=60, label="poll", status_path=None, preset=None, timeout=60):
        """轮询任务到终态，返回 (最后响应, 秒数)。status_path 点路径（或列表，按序取第一个有值的）；preset 见模块说明。"""
        paths = ([status_path] if isinstance(status_path, str) else status_path) or PRESETS.get(preset) or AUTO_STATUS
        if preset and preset not in PRESETS and not status_path: raise ValueError(f"preset 只能是 {' / '.join(PRESETS)}")
        done = {str(x).lower() for x in done} if done else DONE
        t0 = time.time(); q = None; errs = 0
        for i in range(max_n):
            time.sleep(every)
            try: s, q, _ = self.call("GET", path, label=f"{label} {i}", timeout=timeout)
            except Exception:
                errs += 1
                if errs >= 3: raise
                continue
            errs = 0
            st = next((v for v in (_dig(q, p) for p in paths) if v is not None), None)
            if (isinstance(st, str) and st.lower() in done) or s >= 400: break
        return q, int(time.time() - t0)


SUPPLIER = Client(env={"base": "B", "key": "K", "log": "LOG", "auth": "AUTH"})
OFFICIAL = Client(env={"base": "OB", "key": "OK", "log": "OLOG", "auth": "OAUTH"}, default_log="artifacts/official.jsonl")


def _side(side):
    if side in ("supplier", None): return SUPPLIER
    if side == "official": return OFFICIAL
    if isinstance(side, Client): return side
    raise ValueError("side 只能是 supplier / official 或一个 Client")


def call(method, path_or_url, body=None, headers=None, label="", key=None, timeout=60, retries=3, auth=_UNSET, side="supplier", log=None):
    """返回 (status, parsed, response_headers)。path 以 / 开头会拼上 B（side="official" 拼 OB）。"""
    return _side(side).call(method, path_or_url, body, headers, label, key, timeout, retries, auth, log)


def call_stream(method, path_or_url, body=None, headers=None, label="", key=None, timeout=60, retries=3, auth=_UNSET, side="supplier", log=None, sse=None):
    """SSE 调用，返回 (status, events, response_headers)；原文落 .sse，jsonl 记时序。"""
    return _side(side).call_stream(method, path_or_url, body, headers, label, key, timeout, retries, auth, log, sse)


def used(path=None, side="supplier"): return _side(side).used(path)
def spent(since_ts=None, path="/api/log/token", pages=10, page_size=100, key_param=False, side="supplier"):
    return _side(side).spent(since_ts, path, pages, page_size, key_param)
def vendor_log(path="/api/log/token", pages=1, page_size=100, key_param=False, side="supplier"):
    return _side(side).vendor_log(path, pages, page_size, key_param)
def poll_task(path, done=None, every=10, max_n=60, label="poll", status_path=None, preset=None, timeout=60, side="supplier"):
    return _side(side).poll_task(path, done, every, max_n, label, status_path, preset, timeout)


used.__doc__ = Client.used.__doc__; spent.__doc__ = Client.spent.__doc__
vendor_log.__doc__ = Client.vendor_log.__doc__; poll_task.__doc__ = Client.poll_task.__doc__

if __name__ == "__main__":
    print(__doc__.strip())
