"""probe_lib 离线测试：本地 http.server 回显请求头 / body、出 SSE、故意慢、计数；不联网。
运行：python3 -m unittest discover -s tests（仓库根目录）"""
import http.server, json, os, shutil, subprocess, sys, tempfile, threading, time, unittest, urllib.parse

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "relay-provider-audit", "scripts")
for v in ("K", "B", "LOG", "UA", "OK", "OB", "OLOG", "AUTH", "OAUTH"): os.environ.pop(v, None)  # import 不依赖环境变量
os.environ["no_proxy"] = os.environ["NO_PROXY"] = "127.0.0.1,localhost"
sys.path.insert(0, SCRIPTS)
import probe_lib as pl  # noqa: E402

pl.RETRY_SLEEP = 0
KEY = "sk-test-" + "A1b2C3d4" * 4            # 供应商 key
OTHER = "other-secret-" + "Z9" * 10          # key= 传入
XKEY = "official-xapikey-" + "Q7" * 8        # x-api-key 头
QKEY = "query-key-" + "M5" * 8               # 查询参数里的 key
LEAK = "sk-" + "L" * 40                      # 服务器自己吐出来、没登记过的 key
HITS, TASKS = {}, {}


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def do_GET(self): self.route()
    def do_POST(self): self.route()

    def send(self, code, body, ctype="application/json", extra=()):
        b = body if isinstance(body, bytes) else (json.dumps(body) if not isinstance(body, str) else body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        for k, v in extra: self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)

    def route(self):
        u = urllib.parse.urlsplit(self.path); q = dict(urllib.parse.parse_qsl(u.query)); p = u.path
        n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n).decode() if n else ""
        HITS[p] = HITS.get(p, 0) + 1
        if p == "/echo":
            return self.send(200, {"headers": dict(self.headers), "path": self.path, "body": body, "leak": LEAK})
        if p == "/slow":
            time.sleep(1.0)
            try: return self.send(200, {"ok": True})
            except Exception: return
        if p == "/hdrs":
            return self.send(200, {"ok": 1}, extra=[("request-id", "req_011abc"), ("anthropic-organization-id", "org-1"),
                             ("anthropic-ratelimit-tokens-remaining", "79000"), ("x-ratelimit-remaining-tokens", "99"),
                             ("retry-after", "7"), ("x-amzn-requestid", "amzn-1"), ("x-envoy-upstream-service-time", "321"),
                             ("azureai-model-family", "gpt"), ("Set-Cookie", "sess=SECRETCOOKIEVALUE123; Path=/; HttpOnly"),
                             ("Set-Cookie", "__cf_bm=abcdefghijklmnop; Path=/"), ("x-session-token", "tok-should-hide-123")])
        if p == "/bin":
            return self.send(200, b"\x89PNG\x00\x01\x02" * 10, ctype="image/png")
        if p == "/badutf8":
            return self.send(200, b"caf\xe9 \xff ok", ctype="text/plain")
        if p == "/redirect":
            self.send_response(302); self.send_header("Location", FOREIGN + "/echo"); self.send_header("Content-Length", "0"); self.end_headers(); return
        if p == "/sse":
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Connection", "close"); self.end_headers()
            auth = self.headers.get("Authorization", "")
            evs = [("message_start", {"type": "message_start", "echo": auth}), ("ping", {"type": "ping"}),
                   ("content_block_delta", {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi"}}),
                   ("content_block_delta", {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "!"}}),
                   ("message_stop", {"type": "message_stop"})]
            for i, (name, d) in enumerate(evs):
                self.wfile.write(f"event: {name}\ndata: {json.dumps(d)}\n\n".encode()); self.wfile.flush()
                if i == 1: time.sleep(0.15)
            self.close_connection = True; return
        if p.startswith("/task/"):
            kind = p.split("/")[2]; TASKS[kind] = TASKS.get(kind, 0) + 1; fin = TASKS[kind] >= 3
            shapes = {"dashscope": {"output": {"task_status": "SUCCEEDED" if fin else "RUNNING"}},
                      "ark": {"id": "cgt-1", "status": "succeeded" if fin else "running"},
                      "minimax": {"task": {"id": "1", "status": "succeeded" if fin else "queued"}},
                      "minimax_v1": {"task_id": "1", "status": "Success" if fin else "Processing"}}
            return self.send(200, shapes[kind])
        if p == "/api/log/token":  # 1 起算翻页，每页 page_size 条，共 5 条
            allr = [{"id": i, "type": 2 if i != 3 else 5, "quota": 250000, "created_at": 1000 + i} for i in range(1, 6)]
            ps = int(q.get("page_size", 100)); pg = int(q.get("p", 1)) or 1
            return self.send(200, {"success": True, "data": allr[(pg - 1) * ps: pg * ps]})
        if p == "/v1/dashboard/billing/usage":
            return self.send(404, "<html>not found</html>", ctype="text/html")
        if p == "/api/usage/token":
            return self.send(200, {"code": True, "data": {"total_used": 50000}})
        return self.send(404, {"error": "no route"})


def _serve():
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); s.daemon_threads = True
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_address[1]}"


SRV, BASE = _serve()
SRV2, FOREIGN = _serve()  # 另一个源（端口不同 = 源不同），当 CDN / 官方


def tearDownModule():
    for s in (SRV, SRV2): s.shutdown(); s.server_close()


def read(p):
    with open(p, encoding="utf-8") as f: return f.read()


def lower(d): return {k.lower(): v for k, v in d.items()}


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(); self.log = os.path.join(self.dir, "artifacts", "probes.jsonl")
        self.c = pl.Client(BASE, KEY, self.log)
        HITS.clear(); TASKS.clear()

    def tearDown(self): shutil.rmtree(self.dir, ignore_errors=True)

    def text(self): return read(self.log)
    def recs(self): return [json.loads(l) for l in self.text().splitlines() if l.strip()]


class TestImport(unittest.TestCase):
    def test_import_and_usage_without_env(self):
        env = {k: v for k, v in os.environ.items() if k not in ("K", "B", "LOG")}
        r = subprocess.run([sys.executable, "-c", "import probe_lib; from probe_lib import *; print(K, B)"], cwd=SCRIPTS, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("None None", r.stdout)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "probe_lib.py")], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0); self.assertIn("用法", r.stdout); self.assertIn("call_stream", r.stdout)


class TestMasking(Base):
    def test_all_keys_masked_everywhere(self):
        s, p, h = self.c.call("POST", f"/echo?key={QKEY}&model=x", body={"api_key": KEY, "note": OTHER},
                              headers={"x-api-key": XKEY, "X-Custom-Token": "tok-" + "T" * 20}, label="mask", key=OTHER)
        self.assertEqual(s, 200)
        self.assertEqual(p["headers"]["Authorization"], f"Bearer {OTHER}")  # key= 覆盖默认 key
        self.assertEqual(p["leak"], LEAK)  # 返回给调用方的是原文
        t = self.text()
        for secret in (KEY, OTHER, XKEY, QKEY, LEAK, "tok-" + "T" * 20, urllib.parse.quote(KEY)):
            self.assertNotIn(secret, t)
        r = self.recs()[0]
        self.assertEqual(r["req_headers"]["Authorization"], "Bearer ***")
        self.assertEqual(r["req_headers"]["x-api-key"], "***")
        self.assertTrue(r["url"].startswith("{base}/echo?key=***&model=x"), r["url"])
        self.assertEqual(r["body"]["api_key"], "sk-***")
        self.assertEqual(r["resp"]["leak"], "sk-***")
        self.assertEqual(r["resp"]["headers"]["Authorization"], "Bearer ***")

    def test_default_key_masked_when_echoed(self):
        self.c.call("GET", "/echo", label="k")
        t = self.text(); self.assertNotIn(KEY, t); self.assertIn("Bearer ***", t)

    def test_empty_or_missing_K_rejected(self):
        os.environ["B"] = BASE; os.environ["K"] = ""; os.environ["LOG"] = self.log
        try:
            with self.assertRaises(ValueError) as cm: pl.call("GET", "/echo", label="x")
            self.assertIn("K", str(cm.exception))
            del os.environ["K"]
            with self.assertRaises(ValueError): pl.call("GET", "/echo", label="x")
            self.assertFalse(os.path.exists(self.log))  # 没发、也没写坏日志
            s, p, _ = pl.call("GET", "/echo", label="noauth", auth=None)  # 不带鉴权就不需要 K
            self.assertEqual(s, 200); self.assertNotIn("authorization", lower(p["headers"]))
        finally:
            for v in ("K", "B", "LOG"): os.environ.pop(v, None)

    def test_module_call_reads_env_lazily(self):
        os.environ.update(K=KEY, B=BASE, LOG=self.log)
        try:
            s, p, _ = pl.call("GET", "/echo", label="lazy")
            self.assertEqual(p["headers"]["Authorization"], f"Bearer {KEY}"); self.assertNotIn(KEY, self.text())
        finally:
            for v in ("K", "B", "LOG"): os.environ.pop(v, None)

    def test_official_side(self):
        olog = os.path.join(self.dir, "artifacts", "official.jsonl")
        os.environ.update(OK=XKEY, OB=FOREIGN, OLOG=olog, OAUTH="x-api-key")
        try:
            s, p, _ = pl.call("POST", "/echo", {"m": 1}, headers={"anthropic-version": "2023-06-01"}, label="ok", side="official")
            self.assertEqual(lower(p["headers"]).get("x-api-key"), XKEY); self.assertNotIn("authorization", lower(p["headers"]))
            t = read(olog); self.assertNotIn(XKEY, t)
            self.assertEqual(json.loads(t)["url"], "{base}/echo")
        finally:
            for v in ("OK", "OB", "OLOG", "OAUTH"): os.environ.pop(v, None)


class TestOrigin(Base):
    def test_no_auth_to_foreign_origin(self):
        s, p, _ = self.c.call("GET", FOREIGN + "/echo", label="cdn")
        self.assertNotIn("authorization", lower(p["headers"]))
        s, p, _ = self.c.call("GET", BASE + "/echo", label="same")  # 同源绝对 URL 照常带
        self.assertEqual(p["headers"]["Authorization"], f"Bearer {KEY}")
        s, p, _ = self.c.call("GET", FOREIGN + "/echo", label="explicit", key=OTHER)  # 显式 key= 才带
        self.assertEqual(p["headers"]["Authorization"], f"Bearer {OTHER}")

    def test_cross_origin_redirect_drops_auth(self):
        s, p, _ = self.c.call("GET", "/redirect", label="redir", headers={"x-api-key": XKEY})
        self.assertEqual(s, 200)
        self.assertNotIn("authorization", lower(p["headers"])); self.assertNotIn("x-api-key", lower(p["headers"]))
        self.assertTrue(self.recs()[0]["final_url"].startswith(FOREIGN))


class TestRetry(Base):
    def test_post_not_resent_after_read_timeout(self):
        with self.assertRaises(Exception): self.c.call("POST", "/slow", body={"prompt": "paid"}, label="slow", timeout=0.3, retries=3)
        time.sleep(1.2)
        self.assertEqual(HITS.get("/slow"), 1)
        r = self.recs(); self.assertEqual(len(r), 1)
        self.assertIsNone(r[0]["status"]); self.assertEqual(r[0]["phase"], "response"); self.assertIn("timed out", r[0]["error"])

    def test_get_retried_on_read_timeout(self):
        with self.assertRaises(Exception): self.c.call("GET", "/slow", label="slowget", timeout=0.3, retries=3)
        time.sleep(1.2)
        self.assertEqual(HITS.get("/slow"), 3)
        self.assertEqual([x["attempt"] for x in self.recs()], [1, 2, 3])

    def test_post_retried_when_connection_refused(self):
        import socket
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        c = pl.Client(f"http://127.0.0.1:{port}", KEY, self.log)
        with self.assertRaises(Exception): c.call("POST", "/x", body={"a": 1}, label="dead", retries=2)
        r = self.recs(); self.assertEqual(len(r), 2)
        self.assertTrue(all(x["status"] is None and x["phase"] == "connect" and x["error"] for x in r))


class TestResponse(Base):
    def test_all_headers_kept_sensitive_masked(self):
        s, p, h = self.c.call("GET", "/hdrs", label="h")
        self.assertEqual(h["REQUEST-ID"], "req_011abc")  # 返回的头大小写不敏感
        rh = {k.lower(): v for k, v in self.recs()[0]["resp_headers"].items()}
        for k in ("request-id", "anthropic-organization-id", "anthropic-ratelimit-tokens-remaining", "x-ratelimit-remaining-tokens",
                  "retry-after", "x-amzn-requestid", "x-envoy-upstream-service-time", "azureai-model-family", "content-type", "content-length"):
            self.assertIn(k, rh)
        self.assertEqual(rh["anthropic-ratelimit-tokens-remaining"], "79000")
        self.assertEqual(rh["set-cookie"], "sess=***; __cf_bm=***")
        self.assertEqual(rh["x-session-token"], "***")
        self.assertNotIn("SECRETCOOKIEVALUE123", self.text()); self.assertNotIn("tok-should-hide-123", self.text())

    def test_binary_and_bad_utf8(self):
        s, p, _ = self.c.call("GET", "/bin", label="bin")
        self.assertIsInstance(p, bytes); self.assertEqual(len(p), 70)
        r = self.recs()[0]; self.assertIn("70 字节", r["resp"]); self.assertEqual(r["resp_len"], 70)
        s, p, _ = self.c.call("GET", "/badutf8", label="bad")
        self.assertIn("ok", p); self.assertIn("�", p)


class TestStream(Base):
    def test_call_stream_writes_sse_and_timing(self):
        s, evs, h = self.c.call_stream("POST", "/sse", body={"stream": True}, label="stream ok/1")
        self.assertEqual(s, 200)
        self.assertEqual([e["event"] for e in evs], ["message_start", "ping", "content_block_delta", "content_block_delta", "message_stop"])
        r = self.recs()[0]
        self.assertEqual(r["event_count"], 5)
        self.assertEqual(r["event_seq"], [["message_start", 1], ["ping", 1], ["content_block_delta", 2], ["message_stop", 1]])
        self.assertTrue(r["sse_file"].endswith("stream_ok_1.sse"), r["sse_file"])
        for k in ("ttfb_ms", "first_event_ms", "first_content_ms", "ms"): self.assertIsInstance(r[k], int, k)
        self.assertGreaterEqual(r["first_content_ms"] - r["first_event_ms"], 100)  # 服务器在 ping 后停了 150ms
        self.assertLessEqual(r["first_content_ms"], r["ms"])
        raw = read(r["sse_file"])
        self.assertIn("event: content_block_delta", raw); self.assertNotIn(KEY, raw); self.assertIn("Bearer sk-***", raw)
        self.c.call_stream("POST", "/sse", label="stream ok/1")  # 重名不覆盖
        self.assertTrue(self.recs()[1]["sse_file"].endswith("stream_ok_1-2.sse"))

    def test_call_stream_non_sse_falls_back(self):
        s, p, _ = self.c.call_stream("GET", "/nope", label="err")
        self.assertEqual(s, 404); self.assertEqual(p, {"error": "no route"}); self.assertNotIn("sse_file", self.recs()[0])


class TestHelpers(Base):
    def test_poll_task_presets(self):
        for preset, path, final in (("dashscope", "/task/dashscope", lambda q: q["output"]["task_status"]),
                                    ("ark", "/task/ark", lambda q: q["status"]),
                                    ("minimax", "/task/minimax", lambda q: q["task"]["status"]),
                                    ("minimax", "/task/minimax_v1", lambda q: q["status"])):
            q, sec = self.c.poll_task(path, every=0, max_n=10, preset=preset, label=preset)
            self.assertIn(final(q).lower(), ("succeeded", "success"), path)
        self.assertEqual(TASKS, {"dashscope": 3, "ark": 3, "minimax": 3, "minimax_v1": 3})
        TASKS.clear()
        q, _ = self.c.poll_task("/task/ark", every=0, max_n=10)  # 不给 preset 也能认出 status
        self.assertEqual(q["status"], "succeeded"); self.assertEqual(TASKS["ark"], 3)
        TASKS.clear()
        q, _ = self.c.poll_task("/task/dashscope", ("SUCCEEDED", "FAILED"), 0, 10)  # 老写法（位置参数、大写终态）
        self.assertEqual(q["output"]["task_status"], "SUCCEEDED")

    def test_vendor_log_pages_and_spent(self):
        logs = self.c.vendor_log(pages=10, page_size=2)
        self.assertEqual([x["id"] for x in logs], [1, 2, 3, 4, 5])
        self.assertEqual(len(self.c.vendor_log()), 5)  # pages=1：只读一次
        self.assertEqual(self.c.spent(page_size=2), 2.0)  # 4 条 type 2 × 250000 / 500000
        self.assertEqual(self.c.spent(since_ts=1004, page_size=2), 1.0)

    def test_used_fallback_records_source(self):
        self.assertEqual(self.c.used(), 10)  # 50000 额度 ÷ 5000 = 10 美分
        self.assertEqual(self.c.last_used_source, "/api/usage/token")
        self.assertEqual([x["label"] for x in self.recs()], ["余额 usage", "余额 usage /api/usage/token"])


if __name__ == "__main__":
    unittest.main()
