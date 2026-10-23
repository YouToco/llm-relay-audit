"""成片核验脚本的测试：analyze_videos / c2pa_check / contact_sheet / extract_comfy。
跑法（仓库根目录）：python3 -m unittest discover -s tests
需要 ffmpeg 的用例：PATH 上有 ffmpeg，或有 uv（自动 uv run --with imageio-ffmpeg 取）；都没有就跳过。
需要 C2PA 的用例：uv + openssl（现场生成自签证书链并签一条小视频，不入库私钥）；没有就跳过，判定逻辑另有纯函数用例。"""
import hashlib, importlib.util, json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "relay-provider-audit", "scripts")
UV = shutil.which("uv")
OPENSSL = shutil.which("openssl")
EVIL = "a b 中文 $(touch PWNED) `touch PWNED2`"


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, name + ".py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, **kw)


_FF = None


def ffmpeg():
    global _FF
    if _FF is None:
        _FF = shutil.which("ffmpeg") or ""
        if not _FF and UV:
            r = run([UV, "run", "--quiet", "--with", "imageio-ffmpeg", "python", "-c",
                     "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"])
            _FF = r.stdout.strip() if r.returncode == 0 else ""
    return _FF


def py(*pkgs):
    """带依赖的 python：有 uv 用 uv run --with，否则用当前解释器（依赖缺了脚本自己降级 / 报错）。"""
    if UV and pkgs: return [UV, "run", "--quiet"] + [x for p in pkgs for x in ("--with", p)] + ["python", "-I"]
    return [sys.executable, "-I"]


def script(name): return os.path.join(SCRIPTS, name + ".py")


def make_clip(ff, out, *extra, rate="30000/1001", dur="0.5"):
    base = [ff, "-y", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size=160x120:rate={rate}", "-t", dur, "-pix_fmt", "yuv420p"]
    r = run(base + ["-c:v", "libx264"] + list(extra) + [out])
    if r.returncode != 0: r = run(base + ["-c:v", "mpeg4"] + list(extra) + [out])
    if r.returncode != 0: raise RuntimeError(r.stderr)
    return out


# ---------------- 不依赖外部工具 ----------------
class UsageTest(unittest.TestCase):
    def test_no_args_prints_usage(self):
        for name in ("analyze_videos", "c2pa_check", "contact_sheet", "extract_comfy"):
            r = run([sys.executable, "-I", script(name)])
            self.assertEqual(r.returncode, 2, name); self.assertIn("用法", r.stdout, name); self.assertNotIn("Traceback", r.stderr, name)

    def test_help(self):
        for name in ("analyze_videos", "c2pa_check", "contact_sheet", "extract_comfy"):
            r = run([sys.executable, "-I", script(name), "--help"])
            self.assertEqual(r.returncode, 0, name); self.assertIn("用法", r.stdout, name)

    def test_analyze_bad_pair(self):
        r = run([sys.executable, "-I", script("analyze_videos"), tempfile.gettempdir(), "没有等号"])
        self.assertEqual(r.returncode, 2); self.assertNotIn("Traceback", r.stderr)


class FfmetadataTest(unittest.TestCase):
    def test_unescape(self):
        val = {"a=b": "x;y#z\\w", "n": 1}
        esc = json.dumps(val, indent=1)  # 多行 JSON，ffmetadata 按 \ = ; # 换行 逐个加反斜杠
        for ch in ("\\", "=", ";", "#", "\n"): esc = esc.replace(ch, "\\" + ch)
        txt = f";FFMETADATA1\nmajor_brand=isom\nprompt={esc}\nencoder=Lavf\n[STREAM]\nx=1\n"
        for mod in (load("analyze_videos"), load("extract_comfy")):
            m = mod.parse_ffmetadata(txt)
            self.assertEqual(json.loads(m["prompt"]), val)
            self.assertEqual(m["encoder"], "Lavf"); self.assertNotIn("x", m)

    def test_rate(self):
        av = load("analyze_videos")
        self.assertAlmostEqual(av.rate("30000/1001"), 29.97, places=2)
        self.assertIsNone(av.rate("0/0")); self.assertIsNone(av.rate(None))


class VerdictTest(unittest.TestCase):
    """判定逻辑：签名 / 哈希 / 指纹 / 信任各种组合。"""
    @classmethod
    def setUpClass(cls): cls.m = load("c2pa_check")

    def rec(self, **kw):
        base = {"file": "x.mp4", "c2pa": True, "error": None, "signature_valid": True, "hash_match": True,
                "failures": ["signingCredential.untrusted"], "trust": "untrusted", "validation_state": "Valid",
                "signer": {"org": "Byteplus Pte. Ltd."}, "signer_sha256": "ab" * 32}
        base.update(kw); return base

    def test_self_signed_byteplus_is_not_official(self):
        r = self.m.decide(self.rec(), [])
        self.assertEqual(r["verdict"], self.m.V_UNVERIFIED)

    def test_fingerprint_match(self):
        known = [{"vendor": "BytePlus", "issuer": "Byteplus Pte. Ltd.", "sha256": "AB:" * 31 + "AB", "source": "t", "verified": "2026-10-23"}]
        known = [dict(k, sha256=self.m.norm_fp(k["sha256"])) for k in known]
        self.assertEqual(self.m.decide(self.rec(), known)["verdict"], self.m.V_OFFICIAL)
        # 指纹对上但哈希不匹配 → 仍判无效
        self.assertEqual(self.m.decide(self.rec(hash_match=False), known)["verdict"], self.m.V_INVALID)

    def test_invalid_cases(self):
        for kw in ({"signature_valid": False}, {"hash_match": False}, {"failures": ["assertion.bmffHash.mismatch"]},
                   {"validation_state": "Invalid"}):
            self.assertEqual(self.m.decide(self.rec(**kw), [])["verdict"], self.m.V_INVALID, kw)

    def test_untrusted_alone_is_not_invalid(self):
        r = self.m.decide(self.rec(failures=["signingCredential.untrusted"]), [])
        self.assertNotEqual(r["verdict"], self.m.V_INVALID)

    def test_trusted_but_unknown(self):
        r = self.m.decide(self.rec(failures=[], trust="trusted"), [])
        self.assertEqual(r["verdict"], self.m.V_UNVERIFIED); self.assertIn("信任列表", r["verdict_note"])

    def test_no_c2pa_and_error(self):
        self.assertEqual(self.m.decide({"c2pa": False, "error": None}, [])["verdict"], self.m.V_NONE)
        self.assertEqual(self.m.decide({"c2pa": False, "error": "坏了"}, [])["verdict"], self.m.V_ERROR)

    def test_load_known(self):
        d = tempfile.mkdtemp(prefix="已知 签名 ")
        p = os.path.join(d, "k.json")
        with open(p, "w", encoding="utf-8") as fh: json.dump([{"vendor": "火山", "sha256": "AA:" * 31 + "AA"}], fh, ensure_ascii=False)
        self.assertEqual(self.m.load_known(p)[0]["sha256"], "aa" * 32)
        with open(p, "w", encoding="utf-8") as fh: json.dump([{"vendor": "x", "sha256": "123"}], fh)
        with self.assertRaises(ValueError): self.m.load_known(p)
        self.assertEqual(self.m.load_known(os.path.join(d, "无.json")), [])
        shutil.rmtree(d)

    def test_shipped_known_list_is_valid(self):
        self.assertIsInstance(self.m.load_known(self.m.DEFAULT_KNOWN), list)


# ---------------- 需要 ffmpeg ----------------
class FfmpegCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ff = ffmpeg()
        if not cls.ff: raise unittest.SkipTest("没有 ffmpeg，也没法用 uv 取 imageio-ffmpeg")
        cls.d = tempfile.mkdtemp(prefix="视频 测试 ")
        cls.env = dict(os.environ, FF=cls.ff)

    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.d, ignore_errors=True)


class AnalyzeVideosTest(FfmpegCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        aigc = json.dumps({"Label": "1", "ContentProducer": "001191330106MA2CFLDG4R10001", "ProduceID": "p=1;#x"})
        cls.ntsc = make_clip(cls.ff, os.path.join(cls.d, EVIL + ".mp4"), "-metadata", f"AIGC={aigc}", "-movflags", "use_metadata_tags")
        cls.mkv = make_clip(cls.ff, os.path.join(cls.d, "无码率 流.mkv"), rate="25", dur="0.4")

    def analyze(self, out, extra_env=None):
        env = dict(self.env, **(extra_env or {}))
        return run(py("numpy", "pillow") + [script("analyze_videos"), out, f"注入 {EVIL}={self.ntsc}", f"mkv={self.mkv}"], cwd=self.d, env=env)

    def check(self, out, r):
        self.assertEqual(r.returncode, 0, r.stderr); self.assertNotIn("Traceback", r.stderr)
        for p in ("PWNED", "PWNED2"):
            self.assertFalse(os.path.exists(os.path.join(self.d, p)), "文件名里的命令被执行了")
            self.assertFalse(os.path.exists(os.path.join(out, p)))
        with open(os.path.join(out, "video_analysis.json"), encoding="utf-8") as fh: j = json.load(fh)
        a = j[f"注入 {EVIL}"]
        self.assertAlmostEqual(a["fps"], 29.97, places=2); self.assertEqual((a["w"], a["h"]), (160, 120))
        self.assertAlmostEqual(a["duration"], 0.5, delta=0.05); self.assertIn(a["frames"], (15, 16))
        self.assertEqual(a["aigc"]["ContentProducer"], "001191330106MA2CFLDG4R10001"); self.assertEqual(a["aigc"]["ProduceID"], "p=1;#x")
        for k in ("first", "mid", "last"): self.assertTrue(a["frames_png"][k] and os.path.isfile(a["frames_png"][k]), k)
        m = j["mkv"]; self.assertIsNotNone(m["vkbps"]); self.assertEqual(m["vkbps_source"], "format"); self.assertIsNotNone(m["bpp"])
        return j

    def test_ffprobe_path(self):
        if not (os.environ.get("FFPROBE") or shutil.which("ffprobe") or load("analyze_videos").find_ffprobe(self.ff)):
            self.skipTest("没有 ffprobe")
        out = os.path.join(self.d, "输出 ffprobe"); j = self.check(out, self.analyze(out))
        self.assertEqual(j["mkv"]["probe"], "ffprobe")

    def test_ffmpeg_fallback(self):
        out = os.path.join(self.d, "输出 回退"); j = self.check(out, self.analyze(out, {"FFPROBE": "none"}))
        self.assertEqual(j["mkv"]["probe"], "ffmpeg -i")

    def test_missing_file_continues(self):
        out = os.path.join(self.d, "输出 缺文件")
        r = run(py("numpy", "pillow") + [script("analyze_videos"), out, "缺=" + os.path.join(self.d, "没有.mp4"), f"好={self.mkv}"], env=self.env)
        self.assertEqual(r.returncode, 1); self.assertNotIn("Traceback", r.stderr)
        with open(os.path.join(out, "video_analysis.json"), encoding="utf-8") as fh: j = json.load(fh)
        self.assertIn("error", j["缺"]); self.assertEqual(j["好"]["w"], 160)

    def test_contact_sheet(self):
        out = os.path.join(self.d, "输出 拼图"); self.check(out, self.analyze(out))
        jpg = os.path.join(out, "对照 图.jpg")
        r = run(py("pillow") + [script("contact_sheet"), jpg, os.path.join(out, "frames"), "官方成片=mkv", "不存在=nope"])
        if "缺 pillow" in r.stderr: self.skipTest("没有 pillow")
        self.assertEqual(r.returncode, 0, r.stderr); self.assertTrue(os.path.getsize(jpg) > 0); self.assertIn("缺 3 张", r.stdout)


class ExtractComfyTest(FfmpegCase):
    def test_prompt_variants(self):
        g = {"3": {"class_type": "KSampler", "inputs": {"seed": 7, "steps": 20, "cfg": 5.5, "sampler_name": "euler", "model": ["4", 0]}},
             "4": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2 = fp8;#q.safetensors", "note": "a\\b\nc"}}}
        good = make_clip(self.ff, os.path.join(self.d, "有 工作流.mp4"), "-metadata", "prompt=" + json.dumps(g, ensure_ascii=False), "-movflags", "use_metadata_tags")
        bad = make_clip(self.ff, os.path.join(self.d, "坏 JSON.mp4"), "-metadata", "prompt={not json", "-movflags", "use_metadata_tags")
        none = make_clip(self.ff, os.path.join(self.d, f"无标签 {EVIL}.mp4"))
        r = run([sys.executable, "-I", script("extract_comfy"), good, bad, none], env=self.env, cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr); self.assertNotIn("Traceback", r.stderr)
        with open(os.path.join(self.d, "有 工作流.comfy-prompt.json"), encoding="utf-8") as fh: self.assertEqual(json.load(fh), g)
        self.assertIn("unet_name=wan2.2 = fp8;#q.safetensors", r.stdout); self.assertIn("steps=20", r.stdout)
        self.assertTrue(os.path.isfile(os.path.join(self.d, "坏 JSON.comfy-prompt.txt"))); self.assertIn("不是合法 JSON", r.stdout)
        self.assertIn("没有 prompt 标签", r.stdout); self.assertFalse(os.path.exists(os.path.join(self.d, "PWNED")))


# ---------------- 需要 uv + c2pa-python + openssl ----------------
SIGN = r'''
import c2pa, sys
src, dst, chain, key = sys.argv[1:5]
info = c2pa.C2paSignerInfo(b"es256", open(chain, encoding="utf-8").read().encode(), open(key, encoding="utf-8").read().encode(), None)
m = {"claim_generator_info": [{"name": "llm-relay-audit-test", "version": "0"}], "title": "t",
     "assertions": [{"label": "c2pa.actions", "data": {"actions": [{"action": "c2pa.created", "softwareAgent": "BytePlus_ModelArk",
       "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
       "parameters": {"model_name": "fake-seedance", "log_id": "test"}}]}}]}
with open(src, "rb") as s, open(dst, "wb") as d: c2pa.Builder(m).sign(c2pa.Signer.from_info(info), "video/mp4", s, d)
'''


def top_boxes(b):
    i, out = 0, []
    while i + 8 <= len(b):
        size = int.from_bytes(b[i:i + 4], "big"); typ = b[i + 4:i + 8]; hdr = 8
        if size == 1: size = int.from_bytes(b[i + 8:i + 16], "big"); hdr = 16
        if size == 0: size = len(b) - i
        out.append((typ, i, hdr, size)); i += size
    return out


class C2paTest(FfmpegCase):
    @classmethod
    def setUpClass(cls):
        if not (UV and OPENSSL): raise unittest.SkipTest("要 uv 和 openssl 才能现场生成 C2PA 样片")
        super().setUpClass()
        d, o = cls.d, lambda *a: run([OPENSSL] + list(a), cwd=cls.d)
        steps = [
            ("ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", "ca.key"),
            ("req", "-x509", "-new", "-key", "ca.key", "-sha256", "-days", "30", "-subj", "/O=Fake Root/CN=Fake Root CA",
             "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign", "-out", "ca.pem"),
            ("ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", "leaf.key"),
            ("pkcs8", "-topk8", "-nocrypt", "-in", "leaf.key", "-out", "leaf.pk8"),
            ("req", "-new", "-key", "leaf.key", "-subj", "/C=SG/O=Byteplus Pte. Ltd./CN=BytePlus_ModelArk", "-out", "leaf.csr"),
        ]
        with open(os.path.join(d, "ext.cnf"), "w", encoding="utf-8") as fh:
            fh.write("basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=emailProtection\n"
                     "subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\n")
        steps.append(("x509", "-req", "-in", "leaf.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial", "-days", "30",
                      "-sha256", "-extfile", "ext.cnf", "-out", "leaf.pem"))
        for s in steps:
            r = o(*s)
            if r.returncode != 0: raise unittest.SkipTest(f"openssl 失败：{r.stderr[-200:]}")
        with open(os.path.join(d, "chain.pem"), "w", encoding="utf-8") as fh:
            for p in ("leaf.pem", "ca.pem"):
                with open(os.path.join(d, p), encoding="utf-8") as f2: fh.write(f2.read())
        run([OPENSSL, "x509", "-in", "leaf.pem", "-outform", "DER", "-out", "leaf.der"], cwd=d)
        with open(os.path.join(d, "leaf.der"), "rb") as fh: cls.leaf_fp = hashlib.sha256(fh.read()).hexdigest()
        cls.plain = make_clip(cls.ff, os.path.join(d, "无 凭证.mp4"), "-movflags", "+faststart")
        cls.signed = os.path.join(d, f"签名 {EVIL}.mp4")
        helper = tempfile.mkdtemp(prefix="c2pa-helper-"); hp = os.path.join(helper, "sign.py")
        with open(hp, "w", encoding="utf-8") as fh: fh.write(SIGN)
        r = run([UV, "run", "--quiet", "--with", "c2pa-python", "python", "-I", hp, cls.plain, cls.signed,
                 os.path.join(d, "chain.pem"), os.path.join(d, "leaf.pk8")])
        shutil.rmtree(helper, ignore_errors=True)
        if r.returncode != 0: raise unittest.SkipTest(f"c2pa-python 签名失败（离线？）：{r.stderr[-300:]}")
        with open(cls.signed, "rb") as fh: b = bytearray(fh.read())
        mdat = next(x for x in top_boxes(b) if x[0] == b"mdat")
        b[mdat[1] + mdat[2] + (mdat[3] - mdat[2]) // 2] ^= 0xFF
        cls.tampered = os.path.join(d, "篡改 过.mp4")
        with open(cls.tampered, "wb") as fh: fh.write(b)

    def check(self, *args):
        r = run(py("c2pa-python") + [script("c2pa_check"), "--json"] + list(args), cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr); self.assertNotIn("Traceback", r.stderr)
        return json.loads(r.stdout)

    def test_batch_continues_and_verdicts(self):
        m = load("c2pa_check")
        out = self.check("--no-save", self.plain, self.signed, self.tampered, os.path.join(self.d, "不存在.mp4"), self.plain)
        self.assertEqual([x["verdict"] for x in out], [m.V_NONE, m.V_UNVERIFIED, m.V_INVALID, m.V_ERROR, m.V_NONE])
        s = out[1]
        self.assertTrue(s["signature_valid"]); self.assertTrue(s["hash_match"]); self.assertEqual(s["trust"], "untrusted")
        self.assertEqual(s["signer"]["org"], "Byteplus Pte. Ltd."); self.assertIn("Fake Root", s["signer"]["issuer_dn"])
        self.assertEqual(s["signer_sha256"], self.leaf_fp); self.assertEqual(len(s["chain_sha256"]), 2)
        self.assertEqual(s["actions"][0]["model_name"], "fake-seedance")
        self.assertFalse(out[2]["hash_match"])
        self.assertFalse(os.path.exists(os.path.join(self.d, "PWNED")))

    def test_known_fingerprint(self):
        m = load("c2pa_check"); k = os.path.join(self.d, "已知.json")
        with open(k, "w", encoding="utf-8") as fh:
            json.dump([{"vendor": "测试", "issuer": "Byteplus Pte. Ltd.", "sha256": self.leaf_fp.upper(), "source": "fixture", "verified": "2026-10-23"}], fh)
        out = self.check("--no-save", "--known", k, self.signed, self.tampered)
        self.assertEqual(out[0]["verdict"], m.V_OFFICIAL); self.assertEqual(out[1]["verdict"], m.V_INVALID)

    def test_trust_anchors(self):
        m = load("c2pa_check")
        out = self.check("--no-save", "--trust-anchors", os.path.join(self.d, "ca.pem"), self.signed)
        self.assertEqual(out[0]["trust"], "trusted"); self.assertEqual(out[0]["verdict"], m.V_UNVERIFIED)

    def test_saves_raw_json(self):
        self.check(self.signed)
        with open(self.signed + ".c2pa.json", encoding="utf-8") as fh: self.assertIn("active_manifest", json.load(fh))

    def test_human_output(self):
        r = run(py("c2pa-python") + [script("c2pa_check"), "--no-save", self.plain, self.signed], cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("无 C2PA", r.stdout); self.assertIn("签名有效但签发者未核实", r.stdout)


if __name__ == "__main__":
    unittest.main()
