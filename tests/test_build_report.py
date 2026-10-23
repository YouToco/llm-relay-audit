"""build_report.py 的回归测试：只用标准库，不联网；没有 Chrome 时跳过 PDF 用例。
在仓库根目录跑：python3 -m unittest discover -s tests"""
import base64, copy, json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "relay-provider-audit")
SCRIPTS = os.path.join(SKILL, "scripts")
BR = os.path.join(SCRIPTS, "build_report.py")
EX = os.path.join(SKILL, "assets", "examples")
sys.path.insert(0, SCRIPTS)
import build_report as br  # noqa: E402
import check_pages  # noqa: E402

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
HAVE_CHROME = any(shutil.which(c) for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")) or bool(os.environ.get("CHROME"))
# 拼出来的假 key（不在源码里写成整串，免得仓库的密钥扫描误报）
J = "".join
FAKE_KEYS = {
    "openai": J(["sk-", "proj-", "A" * 40]), "anthropic": J(["sk-", "ant-api03-", "b" * 40]), "short_sk": J(["sk-", "a1b2c3d4e5f6g7"]),
    "xai": J(["xai-", "C" * 60]), "glm": J(["0123456789abcdef" * 2, ".", "AbCdEfGh12345678"]),
    "jwt": J(["eyJhbGciOiJIUzI1NiJ9", ".", "eyJzdWIiOiIxIn0", ".", "I" * 43]), "jwt2": J(["eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9", ".", "R" * 100]),
    "uuid_labelled": J(["api_key: ", "3f2a1b4c-5d6e-4f70-8a9b-0c1d2e3f4a5b"]), "x_api_key": J(["x-api-key: ", "J" * 40]),
    "query": J(["https://x.test/v1?key=", "K" * 39]), "bearer_lower": J(["bearer ", "L" * 40]), "ghp": J(["ghp_", "D" * 36]),
    "github_pat": J(["github_pat_", "E1" * 20]), "hf": J(["hf_", "E" * 34]), "gsk": J(["gsk_", "F" * 48]), "r8": J(["r8_", "G" * 37]),
    "ya29": J(["ya29.", "H" * 60]), "aws_secret": J(["aws_secret_access_key = ", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"]),
    "aws_ctx_key": J(["key ", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"]), "stripe": J(["sk_", "live_", "N" * 24]), "dk_live": J(["dk_", "live_", "O" * 20]),
    "akia": J(["AKIA", "P" * 16]), "aiza": J(["AIza", "Q" * 35]), "ark": J(["ark-", "0123abcd-", "4567-89ab-cdef-0123456789ab"]),
}
NOT_KEYS = ["task_id: 3f2a1b4c-5d6e-4f70-8a9b-0c1d2e3f4a5b", "Bearer ***", "x-api-key: ***", "task-0001abcdef1234567890", "sk-learn",
            "risk-assessment-for-relays", "?key=***", "Authorization: Bearer sk-***", "https://cdn.example-relay.test/v/0001.mp4",
            "msg_01XFDUDYJgAACzvnptvVoYEL", "chatcmpl-abc123", "token_count", "key frame"]


def text(p):
    if not os.path.exists(p): return None
    with open(p, encoding="utf-8") as f: return f.read()


def body(h): return h.rsplit("</style>", 1)[-1]  # 去掉内联 CSS（注释是中文）


def load(kind="text"):
    with open(os.path.join(EX, kind, "findings.json"), encoding="utf-8") as f: return json.load(f)


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="br-test-"); self.addCleanup(shutil.rmtree, self.tmp, True)

    def task(self, F, kind="text", raw=None):
        """在临时目录放一份任务：样例 artifacts + findings.json（F 可以是改过的 dict，raw 直接写文本）。"""
        d = tempfile.mkdtemp(dir=self.tmp); shutil.copytree(os.path.join(EX, kind, "artifacts"), os.path.join(d, "artifacts"))
        for f in os.listdir(os.path.join(d, "artifacts")):
            if f.endswith((".html", ".pdf")): os.remove(os.path.join(d, "artifacts", f))
        with open(os.path.join(d, "img.png"), "wb") as f: f.write(PNG)
        p = os.path.join(d, "findings.json")
        with open(p, "w", encoding="utf-8") as f: f.write(raw if raw is not None else json.dumps(F, ensure_ascii=False))
        return p

    def run_br(self, *args, env=None):
        r = subprocess.run([sys.executable, "-I", BR, *args], capture_output=True, text=True, env=env)
        self.assertNotIn("Traceback", r.stderr, r.stderr); return r

    def check(self, F, kind="text", *flags):
        return self.run_br(self.task(F, kind), "--check", *flags)

    def assertFails(self, F, needle, kind="text", *flags):
        r = self.check(F, kind, *flags); self.assertNotEqual(r.returncode, 0, r.stdout); self.assertIn(needle, r.stderr); return r

    def assertPasses(self, F, kind="text", *flags):
        r = self.check(F, kind, *flags); self.assertEqual(r.returncode, 0, r.stderr); return r

    def build(self, F, kind="text", *flags):
        p = self.task(F, kind); r = self.run_br(p, *flags); self.assertEqual(r.returncode, 0, r.stderr)
        art = os.path.join(os.path.dirname(p), "artifacts")
        return text(os.path.join(art, "report.html")), text(os.path.join(art, "internal-card.html")), r


# ---------------- 样例 ----------------
class Examples(Case):
    def test_examples_pass_check(self):
        for k in ("text", "video"):
            r = self.run_br(os.path.join(EX, k, "findings.json"), "--check"); self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("校验通过", r.stdout)

    def test_examples_render(self):
        h, c, _ = self.build(load("text")); self.assertIn("<h2>1 声称 vs 实测</h2>", h); self.assertIn("内部决策卡", c); self.assertIn("Bearer ***", h)
        h, c, _ = self.build(load("video"), "video"); self.assertIn("参数透传：官方字段还在不在", h); self.assertIn("全被封装", h)

    def test_examples_no_secret_false_positive(self):
        for k in ("text", "video"):
            self.assertEqual(br.scan_artifacts(os.path.join(EX, k)), [])
            h, c, _ = self.build(load(k), k); self.assertEqual(br.find_secrets(h) + br.find_secrets(c), [])


# ---------------- 1. key 检测 ----------------
class Secrets(Case):
    def test_patterns(self):
        for name, k in FAKE_KEYS.items():
            with self.subTest(name): self.assertTrue(br.find_secrets(f"see {k} here"), name)
        for s in NOT_KEYS:
            with self.subTest(s): self.assertEqual(br.find_secrets(s), [], s)

    def test_escaped_html_still_caught(self):
        self.assertTrue(br.find_secrets("&quot;x-api-key&quot;: &quot;" + "J" * 40 + "&quot;"))

    def test_secret_in_summary_blocks(self):
        for name in ("xai", "glm", "jwt", "uuid_labelled", "bearer_lower", "aws_secret"):
            F = load(); F["summary"] = "key " + FAKE_KEYS[name]
            with self.subTest(name): self.assertFails(F, "像 key 的串")

    def test_appendix_masks_auth_headers_and_scan_warns(self):
        F = load(); p = self.task(F); jl = os.path.join(os.path.dirname(p), "artifacts", "supplier.jsonl")
        rows = [json.loads(l) for l in text(jl).splitlines() if l.strip()]
        rows[0]["req_headers"].update({"x-api-key": FAKE_KEYS["glm"], "Cookie": "session=" + "Z9" * 20, "authorization": "Bearer " + "L" * 40})
        rows[0]["url"] += "?key=" + "K" * 39
        with open(jl, "w", encoding="utf-8") as f: f.write("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
        F["exchanges"][0]["supplier"]["label"] = rows[0]["label"]
        with open(p, "w", encoding="utf-8") as f: json.dump(F, f, ensure_ascii=False)
        r = self.run_br(p); self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("原始记录里像 key 的串", r.stdout); self.assertIn("supplier.jsonl:1", r.stdout)
        h = text(os.path.join(os.path.dirname(p), "artifacts", "report.html"))
        self.assertIn("x-api-key: ***", h); self.assertIn("Cookie: ***", h); self.assertIn("?key=***", h); self.assertNotIn("Z9Z9", h)
        r = self.run_br(p, "--scan"); self.assertEqual(r.returncode, 1); self.assertIn("supplier.jsonl:1", r.stderr)
        self.assertNotIn(FAKE_KEYS["glm"], r.stderr)  # 只打印前几个字符

    def test_scan_clean(self):
        r = self.run_br(self.task(load()), "--scan"); self.assertEqual(r.returncode, 0); self.assertIn("没扫到", r.stdout)

    def test_scan_sse(self):
        p = self.task(load())
        with open(os.path.join(os.path.dirname(p), "artifacts", "stream.sse"), "w", encoding="utf-8") as f: f.write("data: {}\n\nauthorization: bearer " + "Q1" * 20 + "\n")
        r = self.run_br(p, "--scan"); self.assertEqual(r.returncode, 1); self.assertIn("stream.sse:3", r.stderr)


# ---------------- 2. 内部名字泄露 ----------------
class Leaks(Case):
    def leak(self, mut):
        F = load(); F["internal"]["existing_lines"].append({"line": "VendorA", "supplier": "VendorA"}); mut(F); return self.assertFails(F, "内部才能写的名字")

    def test_bypasses(self):
        cases = {
            "plain": lambda F: F.__setitem__("summary", "比 VendorA 便宜"),
            "case": lambda F: F.__setitem__("summary", "比 vendora 便宜"),
            "md_split": lambda F: F.__setitem__("summary", "Vendor**A**"),
            "md_code": lambda F: F.__setitem__("summary", "Vendor`A`"),
            "zero_width": lambda F: F.__setitem__("summary", "Vendor​A"),
            "alt": lambda F: F["sections"].append({"title": "t", "image": {"path": "img.png", "alt": "VendorA 截图"}}),
            "caption": lambda F: F["sections"].append({"title": "t", "image": {"path": "img.png", "caption": "VendorA 截图"}}),
            "pdf_name": lambda F: F["meta"].__setitem__("pdf_name", "VendorA-vs-ExampleRelay.pdf"),
            "bar_label": lambda F: F["sections"].append({"title": "t", "bars": {"items": [{"label": "VendorA", "value": 1, "hot": True}]}}),
        }
        for n, mut in cases.items():
            with self.subTest(n): self.leak(mut)

    def test_escaped_terms(self):
        for term, text in (("A&B Cloud", "比 A&B Cloud 便宜"), ("<内部>", "见 <内部>"), ("Tom's line", "Tom's line 便宜"), ("Cloud \"X\"", "用 cloud \"x\"")):
            F = load(); F["internal"]["redact_terms"].append(term); F["summary"] = text
            with self.subTest(term): self.assertFails(F, "内部才能写的名字")

    def test_own_names_not_flagged(self):
        F = load(); F["internal"]["existing_lines"].append({"line": "exampleRELAY", "supplier": "ExampleRelay"}); self.assertPasses(F)


# ---------------- 3. 标签注入 ----------------
class TagInjection(Case):
    def test_bad_tag_rejected(self):
        F = load(); F["sections"].append({"title": "t", "table": {"head": ["a"], "rows": [[{"tag": 'good" onmouseover="alert(1)', "label": "x"}]]}})
        self.assertFails(F, "只能是 good / warn / bad")
        F = load(); F["errors"]["rows"][0]["supplier"] = {"tag": "x\"><script>", "label": "y"}; self.assertFails(F, "errors.rows[0].supplier")

    def test_tag_escapes_anyway(self):
        self.assertNotIn('"', br.tag('good" onmouseover="x', "l").split('class="', 1)[1].split('"', 1)[0])
        self.assertIn('class="tag warn"', br.tag("<b>", "l"))

    def test_html_injection_escaped(self):
        inj = '<script>alert(1)</script><img src=x onerror=alert(2)>'
        F = load(); F["summary"] = inj; F["meta"]["title"] = inj; F["claims"][0]["item"] = "`" + inj + "`**" + inj + "**"
        F["sections"].append({"title": "t", "image": {"path": "img.png", "alt": '"><script>alert(1)</script>'}})
        h, c, _ = self.build(F)
        for x in (h, c): self.assertNotIn("<script>", x); self.assertNotIn("<img src=x", x)


# ---------------- 4. 坏输入：报错，不甩 traceback ----------------
class Malformed(Case):
    def test_cases(self):
        def setp(path, val):
            def f(F):
                x = F; ks = path.split(".")
                for k in ks[:-1]: x = x[int(k)] if isinstance(x, list) else x[k]
                if val is DEL: x.pop(int(ks[-1]) if isinstance(x, list) else ks[-1])
                else: x[int(ks[-1]) if isinstance(x, list) else ks[-1]] = val
            return f
        DEL = object()
        cases = [
            ("del_gateway_items", setp("gateway", {"note": "x"}), "gateway 缺 items"),
            ("del_gateway", lambda F: F.pop("gateway"), "顶层 缺 gateway"),
            ("gateway_items_str", setp("gateway.items", "x"), "gateway.items 要是数组"),
            ("del_auth_evidence", setp("authenticity.evidence", DEL), "authenticity 缺 evidence"),
            ("evidence_no_id", lambda F: F["authenticity"]["evidence"][0].pop("id"), "authenticity.evidence[0] 缺 id"),
            ("del_cost_tiers", setp("cost.tiers", DEL), "cost 缺 tiers"),
            ("tier_official_str", lambda F: F["cost"]["tiers"][0].update(official="$3"), "cost.tiers[0].official 要是数字或 null"),
            ("ratio_str", lambda F: F["cost"]["tiers"][0].update(ratio="1.2x"), "cost.tiers[0].ratio 要是小数"),
            ("ask_no_item", setp("asks", [{"why": "x"}]), "asks[0] 缺 item"),
            ("asks_str", setp("asks", ["x"]), "asks[0] 要是对象"),
            ("errors_row_missing", setp("errors.rows", [{"official": "a", "supplier": "b"}]), "errors.rows[0] 缺 input"),
            ("errors_row_verdict", lambda F: F["errors"]["rows"][0].update(verdict="ok"), "errors.rows[0] 的 verdict"),
            ("section_no_title", setp("sections", [{"intro": "x"}]), "sections[0] 缺 title"),
            ("section_bar_value", setp("sections", [{"title": "t", "bars": {"items": [{"label": "a", "value": "1"}]}}]), "value 要是数字"),
            ("section_table_rows", setp("sections", [{"title": "t", "table": {"head": ["a"], "rows": ["x"]}}]), "table.rows 要是二维数组"),
            ("section_image_missing", setp("sections", [{"title": "t", "image": {"path": "nope.png"}}]), "找不到 nope.png"),
            ("section_image_ext", setp("sections", [{"title": "t", "image": {"path": "img.bmp"}}]), "image.path 只收"),
            ("exchanges_empty", setp("exchanges", []), "exchanges 不能为空"),
            ("exchanges_missing", lambda F: F.pop("exchanges"), "exchanges 缺"),
            ("exchange_no_title", lambda F: F["exchanges"][0].pop("title"), "exchanges[0] 缺 title"),
            ("exchange_bad_label", lambda F: F["exchanges"][0]["supplier"].update(label="nope"), "找不到记录"),
            ("exchange_bad_file", lambda F: F["exchanges"][0]["supplier"].update(jsonl="artifacts/nope.jsonl"), "找不到文件"),
            ("exchange_nth", lambda F: F["exchanges"][0]["supplier"].update(nth=9), "越界"),
            ("claims_str", setp("claims", ["just text"]), "claims[0] 要是对象"),
            ("claims_obj", setp("claims", {"a": 1}), "claims 要是数组"),
            ("existing_lines_str", setp("internal.existing_lines", ["line-a"]), "internal.existing_lines[0] 要是对象"),
            ("redact_terms_str", setp("internal.redact_terms", "x"), "redact_terms 要是文字数组"),
            ("gateway_tier_bad", setp("gateway.tier", "maybe"), "gateway.tier 只能是"),
            ("passthrough_badstatus", setp("passthrough", {"rows": [{"id": "x", "field": "f", "official": "o", "supplier": "s", "status": "weird"}]}), "status 只能是"),
            ("decision_bad", setp("internal.decision", "maybe"), "internal.decision 只能是"),
            ("meta_str", setp("meta", "x"), "meta 要是对象"),
            ("lang_bad", setp("meta.lang", "fr"), "meta.lang 只能是"),
            ("mode_bad", setp("meta.mode", "public"), "meta.mode 只能是"),
            ("method_kv", setp("method.kv", ["a"]), "method.kv 要是"),
            ("bullets_obj", setp("sections", [{"title": "t", "bullets": [{"a": 1}]}]), "bullets 要是文字数组"),
        ]
        for name, mut, needle in cases:
            F = load(); mut(F)
            with self.subTest(name): self.assertFails(F, needle)

    def test_top_level_not_object(self):
        self.assertIn("顶层要是对象", self.run_br(self.task(None, raw="[1,2]"), "--check").stderr)

    def test_bad_json_line_col(self):
        r = self.run_br(self.task(None, raw='{\n "meta": {,\n}'), "--check"); self.assertNotEqual(r.returncode, 0); self.assertIn("第 2 行第", r.stderr)

    def test_bad_jsonl_line(self):
        p = self.task(load())
        with open(os.path.join(os.path.dirname(p), "artifacts", "supplier.jsonl"), "a", encoding="utf-8") as f: f.write("{oops\n")
        r = self.run_br(p, "--check"); self.assertNotEqual(r.returncode, 0); self.assertIn("supplier.jsonl 第", r.stderr)

    def test_missing_file(self):
        r = self.run_br(os.path.join(self.tmp, "none", "findings.json"), "--check"); self.assertNotEqual(r.returncode, 0); self.assertIn("找不到", r.stderr)

    def test_tested_missing_warns(self):
        F = load(); F["cost"]["tiers"][0].pop("tested"); r = self.assertPasses(F); self.assertIn("没写 tested", r.stdout)

    def test_ratio_computed_and_mismatch(self):
        F = load(); tr = F["cost"]["tiers"][0]; tr.update(official=3, supplier=2.4); tr.pop("ratio", None)
        self.assertAlmostEqual(br.ratio_of(tr), 0.8)
        h, _, _ = self.build(F); self.assertIn("80%", h)
        F = load(); F["cost"]["tiers"][0].update(official=3, supplier=3.6, ratio=120); r = self.assertPasses(F); self.assertIn("对不上", r.stdout)

    def test_md_bool_and_mime(self):
        br.L = "zh"; self.assertEqual(br.md(True), "是"); self.assertEqual(br.md(False), "否"); self.assertEqual(br.md(3), "3")
        F = load(); F["claims"][0]["measured"] = True; h, _, _ = self.build(F); self.assertNotIn("<td>1</td>", h)
        for ext, mime in ((".webp", "image/webp"), (".svg", "image/svg+xml"), (".JPG", "image/jpeg"), (".gif", "image/gif")):
            F = load(); p = self.task(F); d = os.path.dirname(p); shutil.copy(os.path.join(d, "img.png"), os.path.join(d, "img" + ext))
            F["sections"].append({"title": "t", "image": {"path": "img" + ext}})
            with open(p, "w", encoding="utf-8") as f: json.dump(F, f, ensure_ascii=False)
            r = self.run_br(p); self.assertEqual(r.returncode, 0, r.stderr)
            with self.subTest(ext): self.assertIn(f"data:{mime};base64", text(os.path.join(d, "artifacts", "report.html")))


# ---------------- 命令行 ----------------
class Cli(Case):
    def test_help(self):
        for f in ("-h", "--help"):
            r = self.run_br(f); self.assertEqual(r.returncode, 0); self.assertIn("用法", r.stdout)

    def test_no_args_usage(self):
        r = self.run_br(); self.assertNotEqual(r.returncode, 0); self.assertIn("用法", r.stderr)

    def test_unknown_flag(self):
        r = self.run_br("--chek", os.path.join(EX, "text", "findings.json")); self.assertNotEqual(r.returncode, 0); self.assertIn("不认识的参数", r.stderr)

    def test_flag_order(self):
        r = self.run_br("--check", os.path.join(EX, "text", "findings.json")); self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_br("--check", os.path.join(EX, "text")); self.assertEqual(r.returncode, 0, r.stderr)  # 给目录也行

    def test_init(self):
        out = os.path.join(self.tmp, "a", "findings.json")
        r = self.run_br("--init", "nope", out); self.assertNotEqual(r.returncode, 0); self.assertIn("video / text", r.stderr)
        r = self.run_br("--init", "video"); self.assertNotEqual(r.returncode, 0); self.assertIn("用法", r.stderr)
        r = self.run_br(out, "--init", "text"); self.assertEqual(r.returncode, 0, r.stderr); self.assertEqual(json.loads(text(out))["meta"]["kind"], "text")
        r = self.run_br("--init", "text", out); self.assertNotEqual(r.returncode, 0); self.assertIn("不覆盖", r.stderr)
        r = self.run_br(out, "--check"); self.assertNotEqual(r.returncode, 0); self.assertIn("没通过校验", r.stderr)  # 空骨架：报缺项，不崩


# ---------------- 5. 规则 16 ----------------
def seedance(F=None, url="same", c2pa="good", bucket="good", decision="备用"):
    F = F or load("video"); m = F["meta"]; m.update(model="doubao-seedance-2-5", official="BytePlus ModelArk")
    F["authenticity"] = {"evidence": [{"id": "c2pa", "check": "C2PA", "official": "有", "supplier": "有", "verdict": c2pa, "label": "x"},
                                      {"id": "encoder", "check": "编码器", "official": "a", "supplier": "a", "verdict": "good", "label": "x"},
                                      {"id": "bucket", "check": "桶", "official": "官方桶", "supplier": "官方桶", "verdict": bucket, "label": "x"}]}
    for r in F["passthrough"]["rows"]: r["status"] = "same"
    F["passthrough"]["rows"][0]["status"] = url; F["internal"]["decision"] = decision
    return F


class Rule16(Case):
    def test_all_good_passes(self): self.assertPasses(seedance(), "video")

    def test_failures_force_reject(self):
        for kw in ({"url": "rehosted"}, {"url": "lost"}, {"url": "fake"}, {"c2pa": "warn"}, {"bucket": "bad"}):
            with self.subTest(kw):
                self.assertFails(seedance(**kw), "规则 16", "video")
                self.assertPasses(seedance(**kw, decision="不接"), "video")
                self.assertPasses(seedance(**kw, decision="reject"), "video")

    def test_skipped_not_allowed(self):
        for k in ("c2pa", "bucket"):
            F = seedance(decision="不接"); F["authenticity"]["evidence"] = [c for c in F["authenticity"]["evidence"] if c["id"] != k]
            F["authenticity"]["skipped"] = {k: "没测"}
            with self.subTest(k): self.assertFails(F, f"必须实测 {k}", "video")

    def test_trigger_by_official_or_flag(self):
        for meta in ({"model": "video-x", "official": "火山方舟"}, {"model": "video-x", "official": "Volcengine Ark"},
                     {"model": "video-x", "official": "BytePlus"}, {"model": "video-x", "official": "官方", "rule16": True}):
            F = seedance(bucket="bad"); F["meta"].update(meta)
            with self.subTest(meta): self.assertFails(F, "规则 16", "video")
        F = seedance(bucket="bad"); F["meta"].update(model="wan3.0-t2v", official="阿里云百炼"); self.assertPasses(F, "video")
        self.assertFalse(br.rule16_applies({"kind": "text", "model": "doubao-pro", "official": "火山方舟"}))
        self.assertFalse(br.rule16_applies({"kind": "video", "model": "x", "official": "dark market spark"}))

    def test_rehosted_renders_and_counts_as_lost(self):
        F = load("video"); F["passthrough"]["rows"][0]["status"] = "rehosted"
        h, _, _ = self.build(F, "video"); self.assertIn('<span class="tag bad">转存</span>', h)
        for r in F["passthrough"]["rows"]: r["status"] = "rehosted"
        F["internal"]["decision"] = "backup"; self.assertFails(F, "核心字段全被封装", "video")


# ---------------- 6. 只出外发版 ----------------
class ExternalOnly(Case):
    def strip(self, F):
        F.pop("internal"); F.pop("gateway"); return F

    def test_meta_mode(self):
        F = self.strip(load()); self.assertFails(copy.deepcopy(F), "顶层 缺 gateway")
        F["meta"]["mode"] = "external"; h, c, r = self.build(F); self.assertIsNotNone(h); self.assertIsNone(c); self.assertIn("不出内部卡", r.stdout)

    def test_flag(self):
        h, c, _ = self.build(self.strip(load()), "text", "--external-only"); self.assertIsNotNone(h); self.assertIsNone(c)

    def test_redact_terms_still_checked(self):
        F = self.strip(load()); F["meta"]["mode"] = "external"; F["internal"] = {"redact_terms": ["SecretUpstream"]}; F["summary"] += " SecretUpstream"
        self.assertFails(F, "内部才能写的名字")

    def test_rule16_warns(self):
        F = seedance(bucket="bad"); F.pop("internal"); F.pop("gateway"); F["meta"]["mode"] = "external"
        r = self.assertPasses(F, "video"); self.assertIn("规则 16 没过", r.stdout)


# ---------------- 7. 英文版 ----------------
class English(Case):
    def test_en_headings(self):
        F = load(); F["meta"]["lang"] = "en"; F["meta"].pop("pdf_name"); F["internal"]["decision"] = "fix-first"
        h, c, _ = self.build(F)
        for s in ("<h2>1 Claimed vs measured</h2>", "Bottom line: ", "Is it the real thing: authenticity evidence", "Cost ratio",
                  "Appendix · raw requests and responses", "Official request"):
            self.assertIn(s, h)
        for s in ("声称 vs", "一句话：", "附录 ·", "官方（", "官方请求", "官方响应", ">倍率<", " 项</h3>", "影响客户", "怎么测的"): self.assertNotIn(s, body(h))  # 样例数据本身是中文，只查生成器文案
        self.assertIn(">fix-first<", c); self.assertIn("Internal decision card", c); self.assertIn("ExampleRelay-audit-report.pdf", c)

    def test_en_accepts_zh_decision_and_labels(self):
        F = load("video"); F["meta"]["lang"] = "en"
        h, c, _ = self.build(F, "video"); self.assertIn("All wrapped", h); self.assertIn("Affects integration", h); self.assertIn(">fix-first<", c)
        self.assertIn("Supplier must fix", c)

    def test_zh_accepts_en_decision(self):
        F = load(); F["internal"]["decision"] = "Reject"; _, c, _ = self.build(F); self.assertIn(">不接<", c)


# ---------------- 8. PDF / 换页 ----------------
class Pdf(Case):
    def test_part_name(self):
        self.assertEqual(check_pages.part_name("/a.png/x/seams.png", 0), "/a.png/x/seams.png")
        self.assertEqual(check_pages.part_name("/a.png/x/seams.png", 1), "/a.png/x/seams-2.png")
        self.assertEqual(check_pages.part_name("seams", 2), "seams-3.png")

    def test_no_chrome_friendly(self):
        env = dict(os.environ, CHROME=os.path.join(self.tmp, "no-chrome"))
        p = self.task(load()); r = self.run_br(p, "--pdf", env=env)
        self.assertNotEqual(r.returncode, 0); self.assertIn("找不到 Chrome", r.stderr)

    @unittest.skipUnless(HAVE_CHROME, "没有 Chrome / Chromium")
    def test_pdf_written(self):
        p = self.task(load()); art = os.path.join(os.path.dirname(p), "artifacts")
        stale = os.path.join(art, "ExampleRelay-Claude-检测报告.pdf")
        with open(stale, "wb") as f: f.write(b"old")
        r = self.run_br(p, "--pdf"); self.assertEqual(r.returncode, 0, r.stderr)
        with open(stale, "rb") as f: self.assertEqual(f.read(5), b"%PDF-")
        self.assertEqual(br.pdf_pages(os.path.join(art, "ExampleRelay-内部决策卡.pdf")), 1)


if __name__ == "__main__":
    unittest.main()
