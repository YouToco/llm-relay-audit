"""统一报告生成器：读任务目录的 findings.json，出两份——外发证据版（HTML → PDF）+ 一页内部决策卡（HTML）。
报告拆内外两份的规矩见 SKILL.md 规则 3。

用法（只用标准库；在哪个目录跑都行，路径都相对 findings.json 所在目录）：
    python3 -I build_report.py <任务目录>/findings.json          # 校验 + 出 artifacts/report.html、artifacts/internal-card.html
    python3 -I build_report.py <findings.json> --pdf               # 再调 html_to_pdf.sh 出外发 PDF（并在临时目录出换页拼图，每个换页处上下各一条）
                                                                   # + 一页 A4 的内部卡 PDF（<supplier>-内部决策卡.pdf，meta.card_pdf_name 可改；放不下自动缩 zoom）
    python3 -I build_report.py <findings.json> --check             # 只校验，不写文件
    python3 -I build_report.py --init video|text <findings.json>   # 写一份骨架（真伪证据按类型预填必查项）

字段说明见 references/report-template.md；样例（虚构数据，在仓库根目录，复制安装 skill 时不含）：
    examples/video/findings.json（视频）
    examples/text/findings.json（文本）

文字里的小标记：`代码`、**加粗**、换行 = 换行；不收 HTML。表格单元格可以写 {"tag":"good|warn|bad","label":"一致","text":"…"}。
校验会挡下：缺必填项、真伪证据缺必查项、外发版出现内部字段里的线路 / 供应商名、两份产出里出现像 key 的串。"""
import base64, html, json, os, re, subprocess, sys, tempfile

SKILL = os.path.dirname(os.path.abspath(__file__))
e = html.escape
VERDICT = {"good", "warn", "bad"}
IMPACT = {"customer": "影响客户", "integration": "影响接入", "none": "不影响使用"}
IMPACT_TAG = {"customer": "bad", "integration": "warn", "none": "good"}
GW = {"ready": "不改代码就能接", "gateway": "网关要改", "vendor": "要对方补"}
GW_TAG = {"ready": "good", "gateway": "warn", "vendor": "bad"}
DECISION = {"主线": "good", "备用": "warn", "先修后接": "warn", "不接": "bad", "待定": "warn"}
# 真伪证据必查项（references/video-checks.md「成片核验」、text-checks.md「判真伪」）；没测要写 skipped 原因
REQUIRED_EVIDENCE = {
    "video": {"c2pa": "C2PA 内容凭证", "encoder": "编码器 / 封装指纹", "bucket": "成片存储桶 / 链接域名"},
    "text": {"id_prefix": "响应 id 前缀 / 形式", "token_count": "输入 token 和官方逐个比", "model_swap": "有没有换模型",
             "injection": "有没有注入提示词"},
}
# 视频线路必查的透传字段（规则 15：官方成片链接、任务号、清晰度、时长等没丢、只是换了字段名可以接受；全被封装就接不了）
PASS_CORE = {"video_url": "成片链接（官方桶直链）", "task_id": "官方任务号", "resolution": "清晰度 / 分辨率", "duration": "时长", "usage": "用量（token / 秒）"}
PASS_STATUS = {"same": ("good", "原样"), "renamed": ("good", "改名保留"), "lost": ("bad", "丢失"), "fake": ("bad", "非官方值")}
SECRET_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{16,}|ark-[0-9a-f]{8}-[0-9a-f-]{20,}|Bearer\s+(?!\*)[A-Za-z0-9._\-]{16,}"
                       r"|AKLT[A-Za-z0-9]{24,}|AKIA[0-9A-Z]{16}|\b[a-z]{2,6}_live_[A-Za-z0-9]{8,}|AIza[0-9A-Za-z_\-]{30,})")


# ---------------- 小工具 ----------------
def md(s):
    """`代码`、**加粗**、换行；其余一律转义。"""
    if s is None: return "—"
    if isinstance(s, (int, float)): return f"{s:,}" if isinstance(s, int) else f"{s:g}"
    s = e(str(s))
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return s.replace("\n", "<br>")


def tag(k, t): return f'<span class="tag {k}">{e(t)}</span>'


CTX = None  # 当前 findings 的上下文，cell() 里引用 jsonl 记录要用


def ref_text(src):
    """{"jsonl":…, "label":…} → 「状态码 错误码 · 文案」（去掉 Request id），报错矩阵直接引原始记录，不手抄。"""
    r = CTX.record(src); b = r["resp"]
    if isinstance(b, dict) and isinstance(b.get("error"), dict):
        er = b["error"]; msg = re.sub(r"\s*(\(request id: [^)]*\)|Request id: \w+\.?)", "", str(er.get("message", "")), flags=re.I)
        s = f'{r["status"]} {er.get("code") or er.get("type") or ""} · {msg}'
    else:
        s = f'{r["status"]} ' + (json.dumps(b, ensure_ascii=False) if not isinstance(b, str) else b)
    n = src.get("max", 220); return s if len(s) <= n else s[:n] + "…"


def cell(x):
    if isinstance(x, dict) and "jsonl" in x: return md(ref_text(x))
    if isinstance(x, dict) and "tag" in x:
        return tag(x["tag"], x.get("label", "")) + (f'<br>{md(x["text"])}' if x.get("text") else "")
    if isinstance(x, list): return "<br>".join(md(i) for i in x)
    return md(x)


def tbl(head, rows, cols=None, num=()):
    cg = "<colgroup>" + "".join(f'<col style="width:{w}%">' for w in cols) + "</colgroup>" if cols else ""
    h = "".join(f'<th class="{"n" if i in num else ""}">{e(x)}</th>' for i, x in enumerate(head))
    b = "".join("<tr>" + "".join(f'<td class="{"n" if i in num else ""}">{x}</td>' for i, x in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="scroll"><table style="table-layout:fixed">{cg}<thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


def first(t, lbl, item):
    """判断标签放第一列（项目名下面），不单独占最右列（report-template「版式与打印」）。"""
    return f"{tag(t, lbl)}<br>{md(item)}"


def jdump(x, ind=0, w=72):
    """紧凑 JSON：放得下一行的对象 / 数组写一行。"""
    one = json.dumps(x, ensure_ascii=False)
    if len(one) + ind <= w or not isinstance(x, (dict, list)) or not x: return one
    pad = " " * (ind + 1)
    if isinstance(x, dict):
        return "{\n" + ",\n".join(f"{pad}{json.dumps(k, ensure_ascii=False)}: {jdump(v, ind + 1, w)}" for k, v in x.items()) + "\n" + " " * ind + "}"
    return "[\n" + ",\n".join(pad + jdump(i, ind + 1, w) for i in x) + "\n" + " " * ind + "]"


def slim(x, n=100):
    """附录用：base64 省略、长文本截断、签名链接去掉 query。"""
    if isinstance(x, dict): return {k: (slim_str(v, n, k) if isinstance(v, str) else slim(v, n)) for k, v in x.items()}
    if isinstance(x, list): return [slim(i, n) for i in x]
    return slim_str(x, n, "") if isinstance(x, str) else x


def slim_str(v, n, k):
    if v.startswith("data:"): return v[:30] + "…（base64 省略）"
    if v.startswith("http") and "?" in v: return v.split("?")[0][:120] + "?…"
    if len(v) > n and k in ("content", "reasoning_content", "text", "message", "prompt", "input"): return v[:n] + "…"
    return v if len(v) <= 400 else v[:400] + "…"


def fits_side(*ts):
    """左右并排放得下：每侧每行不超过半栏宽（约 66 字符，不折行）且不超过约一页；否则上下排。"""
    return all(t and max((len(l) for l in t.strip().splitlines()), default=0) <= 66 and len(t.strip().splitlines()) <= 58 for t in ts)


def code(s, wide=False):
    s = s.strip(); per = 120 if wide else 68
    vis = sum(max(1, -(-len(l) // per)) for l in s.splitlines())  # 按栏宽估折行后的可见行数
    cls = ' class="long"' if vis > 58 else ""  # 超过约一页的才允许跨页，其余整块挪页不割裂
    return f"<pre{cls}><code>{e(s)}</code></pre>"


# ---------------- 读数据 ----------------
class Ctx:
    def __init__(self, path):
        self.path = os.path.abspath(path); self.dir = os.path.dirname(self.path)
        self.F = json.load(open(self.path)); self._cache = {}

    def p(self, rel): return rel if os.path.isabs(rel) else os.path.join(self.dir, rel)

    def jsonl(self, rel):
        if rel not in self._cache: self._cache[rel] = [json.loads(l) for l in open(self.p(rel)) if l.strip()]
        return self._cache[rel]

    def record(self, src):
        rows = [r for r in self.jsonl(src["jsonl"]) if r.get("label") == src["label"]]
        if not rows: raise SystemExit(f"找不到记录：{src['jsonl']} label={src['label']!r}")
        return rows[src.get("nth", 0)]

    def jpath(self, src):
        x = json.load(open(self.p(src["json"])))
        for k in (src.get("path") or "").split("."):
            if k: x = x[int(k)] if isinstance(x, list) else x[k]
        return x


def side_text(ctx, s, keep_h):
    """一侧（官方或供应商）的请求 / 响应文本。s 可以是 {jsonl,label} / {request,response}。"""
    if s is None: return None, None
    if "jsonl" not in s and "request" not in s and "response" not in s: return None, None  # 只有 note：没有可并排的官方原文
    if "jsonl" in s:
        r = ctx.record(s); host = s.get("host", "{base}")
        hd = "\n".join(f"{k}: {v}" for k, v in (r.get("req_headers") or {}).items() if k.lower() != "user-agent")
        req = f'{r["method"]} {r["url"].replace("{base}", host)}\n{hd}'
        if r.get("body") is not None: req += "\n\n" + jdump(slim(r["body"]))
        h = {k: v for k, v in (r.get("resp_headers") or {}).items() if k.lower() in keep_h}
        resp = "".join(f"{k}: {v}\n" for k, v in h.items()) + f'HTTP {r["status"]}\n' + (jdump(slim(r["resp"])) if not isinstance(r["resp"], str) else r["resp"][:1500])
        return req, resp
    out = []
    for k in ("request", "response"):
        v = s.get(k)
        if isinstance(v, dict) and "json" in v: v = ctx.jpath(v)
        if isinstance(v, dict) and "file" in v:  # 文本文件（如 SSE 原文）：head / tail 按空行分块取头尾，中间省略
            raw = open(ctx.p(v["file"])).read(); blocks = [b for b in raw.split("\n\n") if b.strip()]
            if "head" in v and len(blocks) > v["head"] + v.get("tail", 0):
                v = "\n\n".join(blocks[: v["head"]] + ["…（中间 %d 块省略）…" % (len(blocks) - v["head"] - v.get("tail", 0))] + (blocks[-v["tail"]:] if v.get("tail") else []))
            else: v = raw[: v.get("max", 3000)]
        out.append(v if isinstance(v, str) or v is None else jdump(slim(v)))
    return out[0], out[1]


# ---------------- 校验 ----------------
def it_decision(F):
    return (F.get("internal") or {}).get("decision")


def validate(F):
    err, warn = [], []
    need = lambda obj, keys, where: [err.append(f"{where} 缺 {k}") for k in keys if obj.get(k) in (None, "", [])]
    m = F.get("meta", {}); need(m, ["title", "supplier", "official", "kind", "date", "model"], "meta")
    if m.get("kind") not in REQUIRED_EVIDENCE: err.append("meta.kind 只能是 video / text")
    need(F, ["summary", "claims", "verdicts", "authenticity", "cost", "gateway", "internal"], "顶层")
    for k in ("asks", "diffs"):
        if k not in F: err.append(f"顶层缺 {k}（没有就写 []）")
    chk = lambda v, where: v in VERDICT or err.append(f"{where} 的 verdict 只能是 good / warn / bad（现在是 {v!r}）")
    for i, c in enumerate(F.get("claims", [])): need(c, ["item", "claimed", "measured", "verdict", "label"], f"claims[{i}]"); chk(c.get("verdict"), f"claims[{i}]")
    for i, c in enumerate(F.get("verdicts", [])): need(c, ["area", "verdict", "label", "text"], f"verdicts[{i}]"); chk(c.get("verdict"), f"verdicts[{i}]")
    if len(F.get("verdicts", [])) > 4: warn.append("结论卡超过 4 张，第 1 页可能放不下")
    ev = (F.get("authenticity") or {}).get("evidence", [])
    for i, c in enumerate(ev):
        need(c, ["check", "official", "supplier", "verdict", "label"], f"authenticity.evidence[{i}]"); chk(c.get("verdict"), f"authenticity.evidence[{i}]")
    have = {c.get("id") for c in ev} | set(((F.get("authenticity") or {}).get("skipped") or {}).keys())
    for k, name in REQUIRED_EVIDENCE.get(m.get("kind"), {}).items():
        if k not in have: err.append(f"真伪证据缺必查项 {k}（{name}）：补一行 evidence（id={k}），没测就在 authenticity.skipped 写原因")
    for i, t in enumerate((F.get("cost") or {}).get("tiers", [])):
        need(t, ["tier"], f"cost.tiers[{i}]")
        if not t.get("tested", True): warn.append(f"成本档位「{t.get('tier')}」没实测（规则 1：每档都要实测，别线性外推）")
    for i, g in enumerate((F.get("gateway") or {}).get("items", [])):
        if g.get("tier") not in GW: err.append(f"gateway.items[{i}].tier 只能是 ready / gateway / vendor")
    for i, d in enumerate(F.get("diffs", [])):
        need(d, ["item", "official", "supplier", "impact"], f"diffs[{i}]")
        if d.get("impact") not in IMPACT: err.append(f"diffs[{i}].impact 只能是 customer / integration / none")
    for i, x in enumerate(F.get("exchanges", [])):
        o = x.get("official")
        if not o: err.append(f"exchanges[{i}]「{x.get('title')}」缺官方一侧：放官方实测 jsonl 或官方文档示例（source 写「文档示例」）；确实没有就写 official.note 说明原因")
        elif not any(k in o for k in ("jsonl", "request", "response", "note")): err.append(f"exchanges[{i}].official 要有 jsonl / request / response / note 之一")
        sp = x.get("supplier") or {}
        if sp and "jsonl" not in sp and not any(isinstance(sp.get(k), dict) and ("json" in sp[k] or "file" in sp[k]) for k in ("request", "response")):
            warn.append(f"exchanges[{i}]「{x.get('title')}」供应商一侧不是从原始记录（jsonl / artifacts 文件）引用的，规则 13 要求原文落盘")
    if m.get("kind") == "video":
        pt = F.get("passthrough") or {}
        have_f = {r.get("id") for r in pt.get("rows", [])}
        for k, name in PASS_CORE.items():
            if k not in have_f: err.append(f"passthrough 缺必查字段 {k}（{name}）：写官方字段 / 供应商字段 / status（same / renamed / lost / fake）")
        for i, r in enumerate(pt.get("rows", [])):
            need(r, ["field", "official", "supplier", "status"], f"passthrough.rows[{i}]")
            if r.get("status") not in PASS_STATUS: err.append(f"passthrough.rows[{i}].status 只能是 {' / '.join(PASS_STATUS)}")
        lost = [r["id"] for r in pt.get("rows", []) if r.get("id") in PASS_CORE and r.get("status") in ("lost", "fake")]
        if lost and len(lost) == len(PASS_CORE) and F.get("internal", {}).get("decision") in ("主线", "备用"):
            err.append("passthrough 核心字段全被封装（没法按官方接入），internal.decision 不能是主线 / 备用")
        # 规则 16：Seedance 拿不到官方原链接或不是原片 → 只能判不接
        if "seedance" in str(m.get("model", "")).lower():
            # 缺 video_url 行由上面的「缺必查字段」报；这里只认明确写了 lost / fake 的
            url_ok = not any(r.get("id") == "video_url" and r.get("status") in ("lost", "fake") for r in pt.get("rows", []))
            c2pa = [c for c in ev if c.get("id") == "c2pa"]
            if not c2pa: err.append("Seedance 必须实测 C2PA（规则 16），不能写进 authenticity.skipped")
            orig_ok = bool(c2pa) and all(c.get("verdict") == "good" for c in c2pa)
            if not (url_ok and orig_ok) and it_decision(F) != "不接":
                err.append("规则 16：Seedance " + ("拿不到官方原链接" if not url_ok else "") + ("、" if not url_ok and not orig_ok else "")
                           + ("不是原片（C2PA 不是 good）" if not orig_ok else "") + " → internal.decision 只能是「不接」")
    it = F.get("internal", {})
    if it.get("decision") not in DECISION: err.append(f"internal.decision 只能是 {' / '.join(DECISION)}")
    need(it, ["reason"], "internal")
    if "existing_lines" not in it: err.append("internal 缺 existing_lines（和你现有的同模型线路比；确实没有就写 [] 并在 existing_note 说明）")
    elif not it["existing_lines"] and not it.get("existing_note"): err.append("internal.existing_lines 为空时要写 existing_note")
    return err, warn


def leak_check(ext_html, F):
    """外发版不许出现内部字段里的线路 / 供应商名、内部专用词。"""
    it = F["internal"]; terms = set(it.get("redact_terms", []))
    for l in it.get("existing_lines", []):
        for k in ("line", "supplier"):
            if l.get(k) and l[k] not in (F["meta"]["supplier"], F["meta"]["official"]): terms.add(l[k])
    text = re.sub(r"<[^>]+>", " ", ext_html)
    return sorted(t for t in terms if t and t in text)


# ---------------- 外发证据版 ----------------
EXTRA_CSS = """<style>
.tldr { background:var(--surface); border:1px solid var(--line); border-left:4px solid var(--accent); border-radius:6px; padding:14px 18px; }
.tldr p { max-width:none; font-size:15px; }
td,td span,td code { overflow-wrap:anywhere; } td .muted { font-size:12px; }
ol.asks { margin:0; padding-left:1.4em; display:flex; flex-direction:column; gap:6px; max-width:none; }
.appendix h3 { margin-top:6px; }
@media print {
  main > * + * { margin-top:16px; } section > * + * { margin-top:8px; } .appendix h3 { margin-top:14px; }
  pre.long, .pair > div:has(pre.long) { break-inside:auto; }
  .pair:not(:has(pre.long)) { display:block; } .pair:not(:has(pre.long)) > div { display:inline-block; width:49%; vertical-align:top; margin-right:1%; }
  .tldr, .keep, ol.asks li { break-inside:avoid; } .kv { grid-template-columns:repeat(4,1fr); }
  /* 附录另起一页；里面的代码块可以跨页（标题 / 小标题粘住代码块开头至少 4 行），不然每段请求响应整块跳页留大片空白 */
  .appendix { break-before:page; } .appendix pre { break-inside:auto; orphans:4; widows:3; }
  .appendix .pair { display:grid !important; } .appendix .pair > div { display:block !important; width:auto !important; margin:0 !important; break-inside:auto; }
}
</style>"""


def bar(lbl, val, mx, hot=False, txt=None):
    w = 0 if not mx or val is None else val / mx * 100
    return f'<div class="bar"><span class="bn">{md(lbl)}</span><span class="bt"><i class="{"hot" if hot else ""}" style="width:{w:.1f}%"></i></span><span class="bv">{e(txt if txt is not None else ("—" if val is None else f"{val:g}"))}</span></div>'


def fmt_ratio(r): return "—" if r is None else f"{r*100:.0f}%"


def section_extra(ctx, s):
    out = [f'<section{" class=keep" if s.get("keep") else ""}><h2>{md(s["title"])}</h2>']
    if s.get("intro"): out.append(f'<p class="sub">{md(s["intro"])}</p>')
    if s.get("bars"):
        b = s["bars"]; mx = max((i["value"] for i in b["items"] if i.get("value") is not None), default=0)
        out.append('<div class="chart">' + (f'<h4>{md(b["title"])}</h4>' if b.get("title") else "")
                   + "".join(bar(i["label"], i.get("value"), mx, i.get("hot"), i.get("text")) for i in b["items"]) + "</div>")
    if s.get("table"):
        t = s["table"]; out.append(tbl(t["head"], [[cell(c) for c in r] for r in t["rows"]], t.get("cols"), tuple(t.get("num", []))))
    if s.get("image"):
        im = s["image"]; raw = open(ctx.p(im["path"]), "rb").read(); mime = "image/png" if im["path"].endswith(".png") else "image/jpeg"
        out.append(f'<figure><img src="data:{mime};base64,{base64.b64encode(raw).decode()}" alt="{e(im.get("alt", ""))}"><figcaption>{md(im.get("caption", ""))}</figcaption></figure>')
    if s.get("bullets"): out.append("<ul>" + "".join(f"<li>{md(b)}</li>" for b in s["bullets"]) + "</ul>")
    if s.get("note"): out.append(f'<p class="sub note">{md(s["note"])}</p>')
    return "".join(out) + "</section>"


def external(ctx):
    F = ctx.F; m = F["meta"]; css = open(os.path.join(SKILL, "report_style.html")).read() + EXTRA_CSS
    sup, off = m["supplier"], m["official"]; n = [0]

    def h2(t): n[0] += 1; return f"<h2>{n[0]} {e(t)}</h2>"
    head = f'''<header><h1>{md(m["title"])}</h1><div class="meta">{md(m.get("subtitle") or f"{sup} 对照 {off}")} · {e(m["date"])}{(" · " + md(m["scope"])) if m.get("scope") else ""}</div></header>'''
    cards = "".join(f'<div class="v">{tag(v["verdict"], v["label"])}<b>{md(v["area"])}</b><span class="d">{md(v["text"])}</span></div>' for v in F["verdicts"])
    page1 = f'<section><div class="tldr"><p><b>一句话：</b>{md(F["summary"])}</p></div><div class="verdicts">{cards}</div></section>'
    claims = tbl(["项", f"{sup} 声称", "实测（对照官方）"],
                 [[first(c["verdict"], c["label"], c["item"]), md(c["claimed"]), md(c["measured"])] for c in F["claims"]], cols=[22, 32, 46])
    parts = [head, page1, f"<section>{h2('声称 vs 实测')}{claims}</section>"]
    asks = list(F["asks"]) + [{"item": g["item"], "why": g.get("detail", "")} for g in F["gateway"]["items"] if g["tier"] == "vendor" and not g.get("internal_only")]
    if asks:
        li = "".join(f'<li><b>{md(a["item"])}</b>{("：" + md(a["why"])) if a.get("why") else ""}</li>' for a in asks)
        parts.append(f'<section>{h2(f"需要 {sup} 处理的事")}<ol class="asks">{li}</ol></section>')
    mt = F.get("method") or {}
    if mt:
        kv = "".join(f"<div><b>{md(k)}</b><span>{md(v)}</span></div>" for k, v in mt.get("kv", []))
        parts.append(f'<section>{h2("怎么测的")}<div class="kv">{kv}</div>' + (f'<p class="sub note">{md(mt["note"])}</p>' if mt.get("note") else "") + "</section>")
    au = F["authenticity"]
    rows = [[first(c["verdict"], c["label"], c["check"]), md(c["official"]), md(c["supplier"])] for c in au["evidence"]]
    rows += [[first("warn", "没测", REQUIRED_EVIDENCE[m["kind"]].get(k, k)), "—", md(why)] for k, why in (au.get("skipped") or {}).items()]
    parts.append(f'<section>{h2("是不是官方的东西：真伪证据")}' + (f'<p class="sub">{md(au["intro"])}</p>' if au.get("intro") else "")
                 + tbl(["证据", f"官方（{off}）", sup], rows, cols=[22, 36, 42]) + (f'<p class="sub note">{md(au["note"])}</p>' if au.get("note") else "") + "</section>")
    pt = F.get("passthrough")
    if pt and pt.get("rows"):
        core = [r for r in pt["rows"] if r.get("id") in PASS_CORE]; bad = [r for r in core if r["status"] in ("lost", "fake")]
        vt = ("good", "透传完整") if not bad else (("bad", "全被封装") if len(bad) == len(core) else ("warn", f"{len(bad)} 项没透传"))
        rows = [[first(PASS_STATUS[r["status"]][0], PASS_STATUS[r["status"]][1], r["field"]) + (f'<br><span class="muted">{md(r["note"])}</span>' if r.get("note") else ""),
                 md(r["official"]), md(r["supplier"])] for r in pt["rows"]]
        parts.append(f'<section>{h2("参数透传：官方字段还在不在")}<p class="sub">{tag(*vt)} '
                     + md(pt.get("intro") or "官方成片链接、任务号、清晰度、时长、用量是否原样返回；换了字段名但值还在算保留，被替换成供应商自己的值或没有算丢失。") + "</p>"
                     + tbl(["字段", f"官方（{off}）", sup], rows, cols=[24, 34, 42]) + (f'<p class="sub note">{md(pt["note"])}</p>' if pt.get("note") else "") + "</section>")
    groups = []
    for imp in ("customer", "integration", "none"):
        ds = [d for d in F["diffs"] if d["impact"] == imp]
        if ds:
            groups.append(f'<h3>{tag(IMPACT_TAG[imp], IMPACT[imp])} {len(ds)} 项</h3>' + tbl(["项", "官方", sup],
                          [[md(d["item"]) + (f'<br><span class="muted">{md(d["note"])}</span>' if d.get("note") else ""), md(d["official"]), md(d["supplier"])] for d in ds], cols=[24, 34, 42]))
    if groups: parts.append(f"<section>{h2('和官方的差异（按影响分级）')}" + "".join(groups) + "</section>")
    er = F.get("errors")
    if er:
        parts.append(f'<section>{h2("参数与报错")}' + (f'<p class="sub">{md(er["intro"])}</p>' if er.get("intro") else "")
                     + tbl(["输入", "官方", sup], [[first(r["verdict"], r["label"], r["input"]), cell(r["official"]), f'<span class="muted small" style="font-family:var(--font-mono)">{cell(r["supplier"])}</span>'] for r in er["rows"]], cols=[24, 30, 46])
                     + (f'<p class="sub note">{md(er["note"])}</p>' if er.get("note") else "") + "</section>")
    for s in F.get("sections", []): parts.append(section_extra(ctx, s).replace("<h2>", "<h2>" + str(n[0] + 1) + " ", 1)); n[0] += 1
    co = F["cost"]; unit = co.get("unit", "")
    crow = [[md(t["tier"]) + ("" if t.get("tested", True) else "<br>" + tag("warn", "没实测")), md(t.get("official_text") or t.get("official")),
             md(t.get("supplier_text") or t.get("supplier")), fmt_ratio(t.get("ratio")), md(t.get("basis", ""))] for t in co["tiers"]]
    cost_html = tbl(["档位", f"官方（{unit}）", f"{sup}（{unit}）", "倍率", "依据"], crow, cols=[18, 20, 20, 10, 32], num=(3,))
    pairs = [t for t in co["tiers"] if t.get("official") is not None and t.get("supplier") is not None and co.get("chart", True)]
    if pairs:
        mx = max(max(t["official"], t["supplier"]) for t in pairs)
        cost_html += '<div class="chart">' + "".join(bar(f'{t["tier"]} · 官方', t["official"], mx) + bar(f'{t["tier"]} · {sup}', t["supplier"], mx, True) for t in pairs) + "</div>"
    parts.append(f'<section>{h2("成本倍率")}' + (f'<p class="sub">{md(co["intro"])}</p>' if co.get("intro") else "") + cost_html
                 + (f'<p class="sub note">{md(co["note"])}</p>' if co.get("note") else "") + "</section>")
    ex = F.get("exchanges", [])
    if ex:
        keep_h = {h.lower() for h in m.get("keep_headers", ["server", "x-new-api-version", "x-request-id"])}
        out = [f'<section class="appendix"><h2>附录 · 原始请求与响应</h2><p class="sub">key 打码；只留 {e(" / ".join(sorted(keep_h)))} 响应头；长文本、base64、签名链接截断。全部原始记录在任务目录 artifacts/。</p>']
        for x in ex:
            o = x.get("official") or {}; o_req, o_resp = side_text(ctx, o, keep_h); s_req, s_resp = side_text(ctx, x.get("supplier"), keep_h)
            on = "官方" + (f'（{e(o["source"])}）' if o.get("source") else "")
            out.append(f'<h3>{md(x["title"])}</h3>' + (f'<p class="sub">{md(x["note"])}</p>' if x.get("note") else "")
                       + (f'<p class="sub">{on}：{md(o["note"])}</p>' if o.get("note") and not (o_req or o_resp) else ""))
            for kind, a, b in (("请求", o_req, s_req), ("响应", o_resp, s_resp)):
                if a and b and fits_side(a, b): out.append(f'<div class="pair"><div><h4>{on}{kind}</h4>{code(a)}</div><div><h4>{e(sup)} {kind}</h4>{code(b)}</div></div>')
                elif a and b: out.append(f'<div><h4>{on}{kind}</h4>{code(a, wide=True)}</div><div><h4>{e(sup)} {kind}</h4>{code(b, wide=True)}</div>')
                elif a or b: out.append(f'<div><h4>{on if a else e(sup)} {kind}</h4>{code(a or b, wide=True)}</div>')
        parts.append("".join(out) + "</section>")
    return f'<title>{e(m.get("short_title") or m["title"])}</title>{css}<main>{"".join(parts)}</main>'


# ---------------- 内部决策卡 ----------------
CARD_CSS = """<style>
main { max-width:900px; gap:16px; } body { font-size:14px; }
.dec { display:flex; gap:16px; align-items:flex-start; background:var(--surface); border:1px solid var(--line); border-left:5px solid var(--accent); border-radius:6px; padding:14px 18px; }
.dec .big { font-size:22px; font-weight:700; white-space:nowrap; padding:4px 12px; border-radius:4px; }
.big.good { background:var(--good-bg); color:var(--good); } .big.warn { background:var(--warn-bg); color:var(--warn); } .big.bad { background:var(--bad-bg); color:var(--bad); }
.two { display:grid; grid-template-columns:1fr 1fr; gap:14px; } .two > div { min-width:0; display:flex; flex-direction:column; gap:8px; }
.card { background:var(--surface); border:1px solid var(--line); border-radius:6px; padding:12px 14px; display:flex; flex-direction:column; gap:8px; }
.card h3 { font-size:14px; } table { min-width:0; font-size:12.5px; } th,td { padding:6px 9px; }
.foot { color:var(--muted); font-size:12px; } p code, td code, li code { font-size:.9em !important; }
@media (max-width:640px) { .two { grid-template-columns:1fr; } .dec { flex-direction:column; } }
@media print { body { font-size:10.5px; line-height:1.45; } main { gap:8px; } h1 { font-size:18px !important; } .dec .big { font-size:16px; } .dec { padding:8px 12px; }
  .two { grid-template-columns:1fr 1fr; gap:8px; } table { font-size:9.5px; } th,td { padding:3px 6px; } .card { padding:6px 9px; gap:4px; } .card h3 { font-size:12px; }
  ul { gap:2px; } .two,.card { break-inside:auto; } .dec,li,tr { break-inside:avoid; }  /* 一页 A4：卡片不整块挪页，否则右栏会被推到第 2 页 */
  main > * + * { margin-top:8px; } .two > div > * + * { margin-top:0; } .card > * + * { margin-top:0; } main { zoom:__ZOOM__; } }
@page { size:A4; margin:8mm 9mm; }  /* 内部卡只出一页：页边距收窄，放不下时生成器逐级缩小 zoom（见 card_pdf） */
</style>"""


def card(ctx, pdf_rel, zoom=1.0):
    F = ctx.F; m = F["meta"]; it = F["internal"]; sup = m["supplier"]
    css = open(os.path.join(SKILL, "report_style.html")).read() + CARD_CSS.replace("__ZOOM__", f"{zoom:g}")
    gw_items = F["gateway"]["items"]; order = ["ready", "gateway", "vendor"]
    gw = F["gateway"].get("tier") or max((g["tier"] for g in gw_items), key=order.index, default="ready")
    dec = f'''<div class="dec"><span class="big {DECISION[it["decision"]]}">{e(it["decision"])}</span><div><p style="max-width:none"><b>{md(F["summary"])}</b></p><p style="max-width:none;margin-top:6px">{md(it["reason"])}</p></div></div>'''
    head = f'<header><h1 style="font-size:24px">{md(m["title"])} · 内部决策卡</h1><div class="meta">{e(m["date"])} · 不外发 · 外发证据版：{e(pdf_rel)}</div></header>'
    claims = "".join(f'<tr><td>{tag(c["verdict"], c["label"])}</td><td>{md(c["item"])}</td><td>{md(c["measured"])}</td></tr>' for c in F["claims"])
    claims = f'<div class="card"><h3>声称 vs 实测</h3><div class="scroll"><table style="table-layout:fixed"><colgroup><col style="width:22%"><col style="width:22%"><col style="width:56%"></colgroup><tbody>{claims}</tbody></table></div></div>'
    gwl = "".join(f'<li>{(tag(GW_TAG[g["tier"]], GW[g["tier"]]) + " ") if g["tier"] != gw else ""}<b>{md(g["item"])}</b>{("：" + md(g["detail"])) if g.get("detail") else ""}</li>' for g in gw_items)
    gwc = f'<div class="card"><h3>网关接入：{tag(GW_TAG[gw], GW[gw])}</h3><ul>{gwl}</ul>' + (f'<p class="foot">{md(F["gateway"]["note"])}</p>' if F["gateway"].get("note") else "") + "</div>"
    this = it.get("this_line") or {}
    rows = [[f'<b>{md(sup)}</b><br>{tag("warn", "本次测")}', md(this.get("cost", "—")), md(this.get("success_30d", "未接入")), md(this.get("volume_30d", "—")), md(this.get("note", ""))]]
    rows += [[md(l.get("line")) + (f'<br><span class="muted">{md(l["supplier"])}</span>' if l.get("supplier") and l["supplier"] != l.get("line") else ""), md(l.get("cost")), md(l.get("success_30d")), md(l.get("volume_30d")), md(l.get("note", ""))] for l in it["existing_lines"]]
    lines = tbl(["线路", "成本", "30 天成功率", "30 天量", "备注"], rows, cols=[20, 24, 14, 14, 28])
    lines = f'<div class="card"><h3>和现有同模型线路比</h3>{lines if it["existing_lines"] else ""}' + (f'<p class="foot">{md(it.get("existing_note"))}</p>' if it.get("existing_note") else "") + "</div>"
    ask = it.get("ask_business") or []; risks = it.get("risks") or []; nxt = it.get("next") or []
    lst = lambda t, xs: f'<div class="card"><h3>{t}</h3><ul>' + "".join(f"<li>{md(x)}</li>" for x in xs) + "</ul></div>" if xs else ""
    body = f'{head}{dec}{lines}<div class="two"><div>{claims}</div><div>{gwc}{lst("要问商务 / 对方", ask)}{lst("风险", risks)}{lst("下一步", nxt)}</div></div>'
    return f'<title>{e(m.get("short_title") or m["title"])} · 内部卡</title>{css}<main>{body}</main>'


def pdf_pages(pdf): return len(re.findall(rb"/Type\s*/Page(?!s)", open(pdf, "rb").read()))


def to_pdf(html_path, pdf): subprocess.run([os.path.join(SKILL, "html_to_pdf.sh"), html_path, pdf], check=True, stdout=subprocess.DEVNULL)


def card_pdf(ctx, pdf_rel, html_path, pdf):
    """内部卡必须一页 A4：从 zoom 1 起逐级缩小，取第一个只出一页的；internal-card.html 也改写成这个 zoom（浏览器里打印同样一页）。"""
    for z in (1.0, 0.92, 0.85, 0.78, 0.72, 0.66, 0.6):
        open(html_path, "w").write(card(ctx, pdf_rel, z)); to_pdf(html_path, pdf); n = pdf_pages(pdf)
        if n == 1: return z
    print(f"提醒：内部卡缩到 zoom {z} 还是 {n} 页，内容太多，删减 internal 里的条目"); return z


# ---------------- 入口 ----------------
def skeleton(kind):
    ev = [{"id": k, "check": v, "official": "", "supplier": "", "verdict": "good", "label": "一致"} for k, v in REQUIRED_EVIDENCE[kind].items()]
    return {"meta": {"title": "", "short_title": "", "supplier": "", "official": "", "model": "", "kind": kind, "date": "", "scope": "", "pdf_name": ""},
            "summary": "", "claims": [{"item": "", "claimed": "", "measured": "", "verdict": "good", "label": "一致"}],
            "verdicts": [{"area": a, "verdict": "good", "label": "一致", "text": ""} for a in (["成片", "接口", "成本", "样片 / 参数"] if kind == "video" else ["后端", "模型", "接口", "成本"])],
            "method": {"kv": [["对象", ""], ["测了多少", ""], ["花了多少", ""], ["官方基准", ""]], "note": ""},
            "authenticity": {"intro": "", "evidence": ev, "skipped": {}, "note": ""},
            **({"passthrough": {"intro": "", "rows": [{"id": k, "field": v, "official": "", "supplier": "", "status": "same", "note": ""} for k, v in PASS_CORE.items()], "note": ""}} if kind == "video" else {}),
            "diffs": [], "asks": [], "errors": {"rows": []}, "sections": [],
            "cost": {"unit": "", "tiers": [{"tier": "", "official": None, "supplier": None, "ratio": None, "tested": True, "basis": ""}], "note": ""},
            "gateway": {"items": [{"item": "", "tier": "ready", "detail": ""}]},
            "exchanges": [{"title": "", "official": {"jsonl": "artifacts/official.jsonl", "label": ""}, "supplier": {"jsonl": "artifacts/paid.jsonl", "label": ""}}],
            "internal": {"decision": "待定", "reason": "", "this_line": {"cost": "", "note": ""}, "existing_lines": [], "existing_note": "",
                         "ask_business": [], "risks": [], "next": [], "redact_terms": []}}


def main(a):
    if a[:1] == ["--init"]:
        kind, out = a[1], a[2]
        if os.path.exists(out): raise SystemExit(f"{out} 已存在，不覆盖")
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        json.dump(skeleton(kind), open(out, "w"), ensure_ascii=False, indent=1); print("写好骨架", out); return
    if not a: raise SystemExit(__doc__)
    global CTX
    ctx = CTX = Ctx(a[0]); errs, warns = validate(ctx.F)
    for w in warns: print("提醒：", w)
    if errs: raise SystemExit("findings.json 没通过校验：\n  " + "\n  ".join(errs))
    m = ctx.F["meta"]; art = os.path.join(ctx.dir, m.get("out_dir", "artifacts")); pdf_name = m.get("pdf_name") or f'{m["supplier"]}-对照报告.pdf'
    ext = external(ctx); crd = card(ctx, os.path.join(m.get("out_dir", "artifacts"), pdf_name))
    leaks = leak_check(ext, ctx.F)
    if leaks: raise SystemExit("外发版出现了内部才能写的名字（别家线路 / 供应商 / redact_terms）：" + "、".join(leaks))
    for name, h in (("外发版", ext), ("内部卡", crd)):
        hit = SECRET_RE.findall(h)
        if hit: raise SystemExit(f"{name}里有像 key 的串，先打码：" + "、".join(x[:12] + "…" for x in hit))
    if "--check" in a: print("校验通过"); return
    os.makedirs(art, exist_ok=True)
    open(os.path.join(art, "report.html"), "w").write(ext); open(os.path.join(art, "internal-card.html"), "w").write(crd)
    print(f"外发版 {os.path.join(art, 'report.html')}（{len(ext)//1024} KB）· 内部卡 {os.path.join(art, 'internal-card.html')}")
    if "--pdf" in a:
        pdf = os.path.join(art, pdf_name)
        to_pdf(os.path.join(art, "report.html"), pdf)
        print(f"PDF {pdf}（{pdf_pages(pdf)} 页）"); seams = os.path.join(tempfile.gettempdir(), os.path.basename(pdf)[:-4] + "-换页.png")  # 检查用，不入库
        r = subprocess.run(["uv", "run", "-q", "--with", "pymupdf", "--with", "pillow", "python", "-I", os.path.join(SKILL, "check_pages.py"), pdf, seams])
        if r.returncode: print("换页拼图没出成（要 uv）：手动跑 scripts/check_pages.py")
        cpdf = os.path.join(art, m.get("card_pdf_name") or f'{m["supplier"]}-内部决策卡.pdf')
        z = card_pdf(ctx, os.path.join(m.get("out_dir", "artifacts"), pdf_name), os.path.join(art, "internal-card.html"), cpdf)
        print(f"内部卡 PDF {cpdf}（{pdf_pages(cpdf)} 页，zoom {z:g}）")

if __name__ == "__main__":
    main(sys.argv[1:])
