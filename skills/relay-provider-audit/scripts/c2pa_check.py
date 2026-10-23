"""读媒体文件（mp4 / 图片）的 C2PA 内容凭证：签名、文件哈希、签发者、签名证书指纹、信任状态，给出判定。
用法：uv run --with c2pa-python python -I c2pa_check.py [--json] [--known <json>] [--trust-anchors <pem>] <文件>…
  --json            stdout 只输出 JSON 数组（可直接引进 findings.json 的 authenticity.evidence）
  --known           已知官方签名证书指纹清单，默认同目录 c2pa_known_signers.json：
                    [{"vendor": "火山方舟", "issuer": "签名证书使用者 O", "sha256": "叶证书 DER 的 SHA-256", "source": "从哪条官方成片取的", "verified": "YYYY-MM-DD"}]
                    只收自己从官方 API 直接拿到的成片里的叶证书（厂商会换证书，见到新的就加一条）
  --trust-anchors   C2PA 信任列表 PEM（根 / 中间证书），用它校验证书链；不给就只报「本机未校验信任」
  每个文件另存 <文件>.c2pa.json（c2pa 原始 JSON）。
判定（从严到宽）：
  官方原片（指纹匹配）       签名有效 + 哈希匹配 + 签名证书 SHA-256 在已知官方清单里
  签名有效但签发者未核实     签名和哈希都对，但证书不在清单里——任何人都能自签一张写着 Byteplus 的证书，不能当原片证据
  签名无效或哈希不匹配       签名 / 哈希 / 证书校验失败：文件被改过或凭证是假的
  无 C2PA                    没有内容凭证（转码、重封装、非厂商出片都会这样；官方本来不带的厂商除外）
注意：c2pa 报的 issuer 其实是签名证书「使用者」的 O 字段（自己填的），真正的签发 CA 看 issuer_dn。"""
import argparse, hashlib, json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_KNOWN = os.path.join(HERE, "c2pa_known_signers.json")
TRUST_CODES = {"signingCredential.untrusted", "signingCredential.trusted"}
HASH_OK = {"assertion.bmffHash.match", "assertion.dataHash.match", "assertion.boxesHash.match", "assertion.collectionHash.match"}
V_OFFICIAL, V_UNVERIFIED, V_INVALID, V_NONE, V_ERROR = (
    "官方原片（指纹匹配）", "签名有效但签发者未核实", "签名无效或哈希不匹配", "无 C2PA", "读取失败")


# ---------- 从 JUMBF 里取签名证书链（c2pa-python 不导出证书本体，只能自己解析） ----------
def _cbor(b, i, depth=0):
    """最小 CBOR 解码，返回 (值, 下一个位置)。标签直接剥掉。"""
    if depth > 32: raise ValueError("cbor 嵌套过深")
    ib = b[i]; mt, ai = ib >> 5, ib & 31; i += 1
    if ai < 24: n = ai
    elif ai in (24, 25, 26, 27):
        k = 1 << (ai - 24); n = int.from_bytes(b[i:i + k], "big"); i += k
    elif ai == 31 and mt in (2, 3, 4, 5): n = None
    else: raise ValueError("cbor 不支持的长度")
    if mt == 0: return n, i
    if mt == 1: return -1 - n, i
    if mt in (2, 3):
        if n is None:
            parts = []
            while b[i] != 0xFF: v, i = _cbor(b, i, depth + 1); parts.append(v)
            v = (b"" if mt == 2 else "").join(parts); return v, i + 1
        v = bytes(b[i:i + n]); i += n
        return (v if mt == 2 else v.decode("utf-8", "replace")), i
    if mt == 4:
        out = []
        while (len(out) < n) if n is not None else (b[i] != 0xFF): v, i = _cbor(b, i, depth + 1); out.append(v)
        return out, (i if n is not None else i + 1)
    if mt == 5:
        out, c = {}, 0
        while (c < n) if n is not None else (b[i] != 0xFF):
            k, i = _cbor(b, i, depth + 1); v, i = _cbor(b, i, depth + 1)
            out[k if not isinstance(k, (list, dict)) else repr(k)] = v; c += 1
        return out, (i if n is not None else i + 1)
    if mt == 6: return _cbor(b, i, depth + 1)
    if ai == 20: return False, i
    if ai == 21: return True, i
    if ai in (22, 23): return None, i
    if ai == 25: return None, i  # 半精度浮点用不到
    if ai == 26: return struct.unpack(">f", b[i - 4:i])[0], i
    if ai == 27: return struct.unpack(">d", b[i - 8:i])[0], i
    return None, i


def _der(b, i):
    """DER TLV：返回 (tag, 内容起点, 内容终点)。"""
    tag, ln = b[i], b[i + 1]; i += 2
    if ln & 0x80: k = ln & 0x7F; ln = int.from_bytes(b[i:i + k], "big"); i += k
    return tag, i, i + ln


def cert_serial(der):
    _, s, _ = _der(der, 0); _, s, _ = _der(der, s)  # Certificate → tbsCertificate
    tag, cs, ce = _der(der, s)
    if tag == 0xA0: tag, cs, ce = _der(der, ce)  # 跳过 [0] version
    return int.from_bytes(der[cs:ce], "big")


def signature_chains(path):
    """扫描文件里每个 c2pa.signature 盒（按 jumd 结构精确定位），返回 x5chain 列表（每条是 DER 证书列表）。"""
    data = open(path, "rb").read()
    chains, pos = [], 0
    while True:
        k = data.find(b"c2pa.signature\x00", pos)
        if k < 0: return chains
        pos = k + 1; js = k - 25  # jumd：size(4) 'jumd'(4) uuid(16，csig / c2cs 开头) toggles(1) label…
        try:
            if js < 0 or data[js + 4:js + 8] != b"jumd" or data[js + 8:js + 12] not in (b"csig", b"c2cs"): continue
            jsize = int.from_bytes(data[js:js + 4], "big"); cb = js + jsize
            size = int.from_bytes(data[cb:cb + 4], "big"); hdr = 8
            if data[cb + 4:cb + 8] != b"cbor": continue
            if size == 1: size = int.from_bytes(data[cb + 8:cb + 16], "big"); hdr = 16
            cose, _ = _cbor(data[cb + hdr:cb + size], 0)
            if not isinstance(cose, list) or len(cose) < 2: continue
            prot = _cbor(cose[0], 0)[0] if isinstance(cose[0], bytes) and cose[0] else {}
            x5 = None
            for hdrs in (prot, cose[1]):
                if isinstance(hdrs, dict): x5 = x5 or hdrs.get(33) or hdrs.get("x5chain")
            if isinstance(x5, bytes): x5 = [x5]
            if isinstance(x5, list) and x5 and all(isinstance(c, bytes) for c in x5): chains.append(x5)
        except (IndexError, ValueError, UnicodeError):
            continue


def signer_fingerprint(path, serial):
    """按活动清单的证书序列号挑出签名证书。返回 (叶证书 sha256, 整条链 sha256 列表, 说明)。"""
    try: chains = signature_chains(path)
    except OSError as e: return None, [], f"读文件失败：{e}"
    if not chains: return None, [], "没在文件里找到 x5chain（可能是远程清单或少见封装），指纹未取到"
    cands = {}
    for ch in chains:
        try: s = cert_serial(ch[0])
        except (IndexError, ValueError): continue
        if serial is None or s == serial: cands.setdefault(hashlib.sha256(ch[0]).hexdigest(), ch)
    if len(cands) != 1:
        why = "没有序列号对得上的证书" if not cands else f"{len(cands)} 张不同证书序列号相同，无法确定（可疑），不做指纹比对"
        return None, [], why
    fp, ch = next(iter(cands.items()))
    return fp, [hashlib.sha256(c).hexdigest() for c in ch], ""


# ---------- 已知官方签名者清单与判定（纯函数，测试直接调） ----------
def norm_fp(s): return "".join(c for c in str(s).lower() if c in "0123456789abcdef")


def load_known(path):
    """读 [{"vendor","issuer","sha256","source","verified"}]；文件不存在当空清单。"""
    if not path or not os.path.exists(path): return []
    with open(path, encoding="utf-8") as fh: items = json.load(fh)
    if not isinstance(items, list): raise ValueError(f"{path} 应是 JSON 数组")
    out = []
    for it in items:
        fp = norm_fp(it.get("sha256", "")) if isinstance(it, dict) else ""
        if len(fp) != 64: raise ValueError(f"{path} 有条目缺 64 位 sha256：{it!r}")
        out.append(dict(it, sha256=fp))
    return out


def decide(rec, known):
    """按记录里的事实给判定，写回 rec['verdict'] / rec['verdict_note'] / rec['known_signer']。"""
    if rec.get("error"): rec["verdict"], rec["verdict_note"] = V_ERROR, rec["error"]; return rec
    if not rec.get("c2pa"): rec["verdict"], rec["verdict_note"] = V_NONE, "文件里没有 C2PA 清单"; return rec
    other_fail = [c for c in rec.get("failures", []) if c not in TRUST_CODES]
    if not rec.get("signature_valid") or not rec.get("hash_match") or other_fail or rec.get("validation_state") == "Invalid":
        rec["verdict"] = V_INVALID
        rec["verdict_note"] = "；".join(filter(None, [
            "" if rec.get("signature_valid") else "签名没通过校验",
            "" if rec.get("hash_match") else "文件哈希不匹配或没有哈希断言（字节被改过）",
            ("失败项：" + ", ".join(other_fail)) if other_fail else ""]))
        return rec
    fp = norm_fp(rec.get("signer_sha256") or "")
    hit = next((k for k in known if fp and k["sha256"] == fp), None)
    rec["known_signer"] = hit
    if hit:
        rec["verdict"], rec["verdict_note"] = V_OFFICIAL, f"签名证书指纹 = 已知 {hit.get('vendor')}（{hit.get('source')}，{hit.get('verified')} 核实）"
        return rec
    trust = rec.get("trust")
    rec["verdict"] = V_UNVERIFIED
    rec["verdict_note"] = ("证书链在给定信任列表里受信，但指纹不在已知官方清单：核对使用者 / 签发 CA 后把指纹加进清单"
                           if trust == "trusted" else
                           "证书不受信、指纹不在已知官方清单：使用者名字可以自己填，不能据此认定厂商原片"
                           if fp else "没取到签名证书指纹，无法和官方清单比对")
    return rec


# ---------- 读 C2PA ----------
def _dn(d): return ", ".join(f"{k}={v}" for k, v in d.items()) if isinstance(d, dict) else (d or None)


def read_one(c2pa, path, ctx, anchors):
    rec = {"file": path, "c2pa": False, "error": None, "trust_anchors": anchors}
    if not os.path.isfile(path): rec["error"] = "文件不存在"; return rec, None
    try:
        kw = {"context": ctx} if ctx is not None else {}
        if hasattr(c2pa.Reader, "try_create"): rd = c2pa.Reader.try_create(path, **kw)
        else: rd = c2pa.Reader(path, **kw)
        if rd is None: return rec, None
        raw = json.loads(rd.json())
        cr = {}
        try: cr = json.loads(rd.crjson()) if hasattr(rd, "crjson") else {}
        except Exception: cr = {}
    except Exception as e:  # noqa: BLE001 — 每个文件单独兜底，不让一个坏文件停掉整批
        if "ManifestNotFound" in type(e).__name__ or "ManifestNotFound" in str(e) or "no JUMBF" in str(e): return rec, None
        rec["error"] = f"{type(e).__name__}: {e}"; return rec, None
    rec["c2pa"] = True
    label = raw.get("active_manifest"); m = raw.get("manifests", {}).get(label, {})
    si = m.get("signature_info", {}) or {}
    vr = (raw.get("validation_results") or {}).get("activeManifest") or {}
    ok = [r.get("code") for r in vr.get("success", [])]
    bad = [r.get("code") for r in vr.get("failure", [])]
    if not vr:  # 旧版 c2pa 只有 validation_status（只列问题）
        bad = [r.get("code") for r in raw.get("validation_status", []) or []]
    acts = []
    for a in m.get("assertions", []):
        if str(a.get("label", "")).startswith("c2pa.actions"):
            for x in (a.get("data") or {}).get("actions", []):
                p = x.get("parameters") or {}
                acts.append({k: v for k, v in {"action": x.get("action"), "softwareAgent": x.get("softwareAgent"),
                             "model_name": p.get("model_name"), "log_id": p.get("log_id"), "when": x.get("when")}.items() if v is not None})
    ci = {}
    for mm in cr.get("manifests", []) if isinstance(cr.get("manifests"), list) else []:
        if mm.get("label") in (label, None) or len(cr["manifests"]) == 1:
            ci = ((mm.get("signature") or {}).get("certificateInfo")) or ci
    serial = si.get("cert_serial_number")
    try: serial = int(serial) if serial is not None else None
    except ValueError: serial = int(str(serial), 16)
    fp, chain, note = signer_fingerprint(path, serial)
    trust = "trusted" if "signingCredential.trusted" in ok else "untrusted" if "signingCredential.untrusted" in bad else "not_checked"
    rec.update({
        "active_manifest": label, "validation_state": raw.get("validation_state"),
        "claim_generator": [g.get("name") for g in m.get("claim_generator_info", []) if isinstance(g, dict)] or m.get("claim_generator"),
        "actions": acts,
        "signature_valid": "claimSignature.validated" in ok,
        "hash_match": bool(HASH_OK & set(ok)),
        "signer": {"org": si.get("issuer"), "common_name": si.get("common_name"), "subject_dn": _dn(ci.get("subject")),
                   "issuer_dn": _dn(ci.get("issuer")), "serial": str(serial) if serial is not None else None,
                   "alg": si.get("alg"), "time": si.get("time"), "validity": ci.get("validity")},
        "signer_sha256": fp, "chain_sha256": chain, "fingerprint_note": note or None,
        "trust": trust, "failures": bad,
    })
    return rec, raw


def make_context(c2pa, anchors):
    """关掉远程清单 / OCSP 拉取（不让被测文件触发外网请求）；给了 PEM 就作为信任锚。"""
    cfg = {"verify": {"remote_manifest_fetch": False, "ocsp_fetch": False}}
    if anchors:
        with open(anchors, encoding="utf-8") as fh: cfg["trust"] = {"trust_anchors": fh.read()}
    if not hasattr(c2pa, "Context"):
        if anchors: sys.exit("这个版本的 c2pa-python 不支持 Context，没法用 --trust-anchors；升级：uv run --with 'c2pa-python>=0.30' …")
        return None
    return c2pa.Context(c2pa.Settings.from_dict(cfg))


def line(r):
    s = r.get("signer") or {}
    parts = [r["file"], "|", r["verdict"]]
    if r.get("c2pa"):
        parts += ["| 签名", r.get("signature_valid"), "| 哈希", r.get("hash_match"), "| 信任", r.get("trust"),
                  "| 使用者", s.get("org"), "/", s.get("common_name"), "| 签发 CA", s.get("issuer_dn"),
                  "| 指纹", r.get("signer_sha256") or r.get("fingerprint_note"), "| 动作", r.get("actions")]
        if r.get("failures"): parts += ["| 失败项", r["failures"]]
    if r.get("verdict_note"): parts += ["|", r["verdict_note"]]
    return " ".join(str(p) for p in parts)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, usage=argparse.SUPPRESS)
    ap.add_argument("files", nargs="*"); ap.add_argument("--json", action="store_true")
    ap.add_argument("--known", default=DEFAULT_KNOWN); ap.add_argument("--trust-anchors")
    ap.add_argument("--no-save", action="store_true", help="不写 <文件>.c2pa.json")
    a = ap.parse_args(argv)
    if not a.files: print(__doc__); return 2
    try: known = load_known(a.known)
    except (OSError, ValueError) as e: print(f"已知签名者清单读不了：{e}", file=sys.stderr); return 2
    try: import c2pa
    except ImportError: print("缺 c2pa-python：uv run --with c2pa-python python -I c2pa_check.py …", file=sys.stderr); return 2
    ctx = make_context(c2pa, a.trust_anchors)
    out = []
    for f in a.files:
        rec, raw = read_one(c2pa, f, ctx, a.trust_anchors)
        decide(rec, known); out.append(rec)
        if raw is not None and not a.no_save:
            try:
                with open(f + ".c2pa.json", "w", encoding="utf-8") as fh: json.dump(raw, fh, ensure_ascii=False, indent=1)
            except OSError as e: print(f"{f}: 存 .c2pa.json 失败：{e}", file=sys.stderr)
        if not a.json: print(line(rec), flush=True)
    if a.json: print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
