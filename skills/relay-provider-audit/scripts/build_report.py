"""统一报告生成器：读任务目录的 findings.json，出两份——外发证据版（HTML → PDF）+ 一页内部决策卡（HTML）。
报告拆内外两份的规矩见 SKILL.md 规则 3。

用法（只用标准库；在哪个目录跑都行，路径都相对 findings.json 所在目录；参数顺序随意）：
    python3 -I build_report.py <任务目录>/findings.json          # 校验 + 出 artifacts/report.html、artifacts/internal-card.html
    python3 -I build_report.py <findings.json> --pdf               # 再调 html_to_pdf.sh 出外发 PDF（并在临时目录出换页拼图，每个换页处上下各一条）
                                                                   # + 一页 A4 的内部卡 PDF（<supplier>-内部决策卡.pdf，meta.card_pdf_name 可改；放不下自动缩 zoom）
    python3 -I build_report.py <findings.json> --check             # 只校验，不写文件
    python3 -I build_report.py <findings.json> --scan              # 只扫任务目录里的 *.jsonl / *.sse 原文有没有没打码的 key（有就退出码 1）
    python3 -I build_report.py <findings.json> --external-only     # 只出外发版（= meta.mode "external"）：internal / gateway 可不填，不出内部卡
    python3 -I build_report.py --init video|text <findings.json>   # 写一份骨架（真伪证据按类型预填必查项）
    python3 -I build_report.py -h                                  # 本说明

字段说明见 references/report-template.md；样例（虚构数据，路径相对 skill 目录）：
    assets/examples/video/findings.json（视频）
    assets/examples/text/findings.json（文本）
meta.lang "en" 出英文版（标题、标签、默认文件名）；internal.decision 中英都收：主线/primary 备用/backup 先修后接/fix-first 不接/reject 待定/pending。

文字里的小标记：`代码`、**加粗**、换行 = 换行；不收 HTML。表格单元格可以写 {"tag":"good|warn|bad","label":"一致","text":"…"}。
校验会挡下：缺必填项 / 类型不对、真伪证据缺必查项、外发版出现内部字段里的线路 / 供应商名、两份产出里出现像 key 的串；
--check / --pdf / 默认生成时顺带扫 artifacts 原文里的 key（只提醒）。"""
import base64, html, json, os, re, shutil, subprocess, sys, tempfile

SKILL = os.path.dirname(os.path.abspath(__file__))
USAGE = __doc__


def e(s): return html.escape("" if s is None else str(s))


def rd(p):
    with open(p, encoding="utf-8") as f: return f.read()  # 所有文本一律 utf-8


VERDICT = {"good", "warn", "bad"}
IMPACT_TAG = {"customer": "bad", "integration": "warn", "none": "good"}
GW_TAG = {"ready": "good", "gateway": "warn", "vendor": "bad"}
# 判定：内部 id → (中文, 英文, 标签色)；输入中英都收
DECISION = {"primary": ("主线", "primary", "good"), "backup": ("备用", "backup", "warn"), "fix-first": ("先修后接", "fix-first", "warn"),
            "reject": ("不接", "reject", "bad"), "pending": ("待定", "pending", "warn")}
DEC_IN = {n.casefold(): k for k, v in DECISION.items() for n in (k, v[0], v[1])}
# 真伪证据必查项（references/video-checks.md「成片核验」、text-checks.md「判真伪」）；没测要写 skipped 原因
REQUIRED_EVIDENCE = {
    "video": {"c2pa": "C2PA 内容凭证", "encoder": "编码器 / 封装指纹", "bucket": "成片存储桶 / 链接域名"},
    "text": {"id_prefix": "响应 id 前缀 / 形式", "token_count": "输入 token 和官方逐个比", "model_swap": "有没有换模型",
             "injection": "有没有注入提示词"},
}
REQUIRED_EVIDENCE_EN = {"c2pa": "C2PA content credentials", "encoder": "Encoder / container fingerprint", "bucket": "Output bucket / link domain",
                        "id_prefix": "Response id prefix / format", "token_count": "Input tokens vs official", "model_swap": "Model swapped?",
                        "injection": "Prompt injected?"}
# 视频线路必查的透传字段（规则 15：官方成片链接、任务号、清晰度、时长等没丢、只是换了字段名可以接受；全被封装就接不了）
PASS_CORE = {"video_url": "成片链接（官方桶直链）", "task_id": "官方任务号", "resolution": "清晰度 / 分辨率", "duration": "时长", "usage": "用量（token / 秒）"}
PASS_STATUS = {"same": "good", "renamed": "good", "lost": "bad", "fake": "bad", "rehosted": "bad"}
PASS_BAD = {"lost", "fake", "rehosted"}  # rehosted = 链接指向供应商自己的存储（转存），规则 15 / 16 都算丢
# 像 key 的串：各家前缀 + 带「key / token / secret」字样的长串 + 鉴权头 / 查询参数；打码过的（*** 开头）不算
_V = r"[A-Za-z0-9/+_\-]"  # key 值常见字符
_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_SEP = r"[\"']?\s*[:=]?\s*[\"']?"
_SECRET_PARTS = [
    r"(?<![A-Za-z0-9])sk-(?:[A-Za-z0-9_\-]{16,}|(?=[A-Za-z0-9_\-]{0,30}\d)[A-Za-z0-9_\-]{12,})",  # OpenAI / Anthropic / DeepSeek / Kimi…；短的要带数字
    r"(?<![A-Za-z0-9])xai-[A-Za-z0-9]{20,}",
    r"ark-[0-9a-f]{8}-[0-9a-f-]{20,}",
    r"(?<![A-Za-z0-9])(?i:bearer)\s+(?!\*)[A-Za-z0-9._~+/\-]{16,}=*",
    r"(?<![A-Za-z0-9])eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}(?:\.[A-Za-z0-9_\-]*)?",  # JWT（MiniMax 等）
    r"(?<![0-9A-Za-z])[0-9a-f]{32}\.[A-Za-z0-9]{16,}",  # 智谱 GLM：<32hex>.<secret>
    r"AKLT[A-Za-z0-9]{24,}", r"(?<![A-Za-z0-9])AKIA[0-9A-Z]{16}", r"AIza[0-9A-Za-z_\-]{30,}",
    r"(?<![A-Za-z0-9])(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})",
    r"(?<![A-Za-z0-9])(?:hf|r8)_[A-Za-z0-9]{30,}", r"(?<![A-Za-z0-9])gsk_[A-Za-z0-9]{30,}", r"(?<![A-Za-z0-9])ya29\.[A-Za-z0-9_\-]{20,}",
    r"(?<![A-Za-z0-9])[a-z]{2,6}_live_[A-Za-z0-9]{8,}",  # sk_live_ / dk_live_ / rk_live_…
    r"(?i:x-goog-api-key|x-api-key|api-key|apikey)[\"']?\s*[:=]\s*[\"']?(?!\*)[A-Za-z0-9._\-]{16,}",
    r"[?&](?i:key|api_key|apikey|api-key|access_token|token)=(?!\*)[A-Za-z0-9._\-]{16,}",
    r"(?i:aws_secret_access_key|secret_access_key|aws_secret|secretaccesskey)" + _SEP + r"[A-Za-z0-9/+]{40}(?![A-Za-z0-9/+])",
    # 明确是凭证的字段名（api_key / secret / password / access_token …）：后面 20 位以上带数字的值，或 UUID
    r"(?<![A-Za-z0-9])(?i:api[_-]?key|secret(?:[_-]?key)?|client[_-]?secret|password|passwd|access[_-]?key|(?:access|refresh|auth|session)[_-]?token)"
    + _SEP + r"(?:(?i:bearer)\s+)?(?:" + _UUID + r"|(?=[A-Za-z0-9/+_.\-]*\d)[A-Za-z0-9/+_.\-]{20,})",
    # 只写着 key / token 的（前面不是 _ 之类的词，免得 next_token / object_key 误报）：UUID（方舟等），或 32 位以上大小写 + 数字混合的串
    r"(?<![A-Za-z0-9_])(?i:key|token)" + _SEP + r"(?:(?i:bearer)\s+)?(?:" + _UUID + r"|(?=" + _V + r"*\d)(?=" + _V + r"*[a-z])(?=" + _V + r"*[A-Z])" + _V + r"{32,}={0,2})",
]
SECRET_RE = re.compile("|".join(f"(?:{p})" for p in _SECRET_PARTS))
AUTH_HEADERS = {"authorization", "proxy-authorization", "x-api-key", "api-key", "x-goog-api-key", "cookie", "set-cookie", "x-auth-token"}


def find_secrets(text):
    """HTML / 原文里像 key 的串（先反转义，data: 内嵌图不扫）。"""
    t = html.unescape(re.sub(r"data:[\w/+.\-]+;base64,[A-Za-z0-9+/=]+", "data:", str(text)))
    return [m.group(0) for m in SECRET_RE.finditer(t)]


def mask_hit(x): return f"{x[:6]}…（{len(x)} 字符）"


def mask_auth(v):
    """鉴权头的值只留 Bearer / Basic 前缀。"""
    m = re.match(r"(?i)(bearer|basic|token)\s+", str(v)); return (m.group(0) if m else "") + "***"


def mask_url(u): return re.sub(r"(?i)([?&](?:key|api_key|apikey|api-key|access_token|token)=)[^&\s#]+", r"\1***", str(u))


# ---------------- 中英文案 ----------------
L = "zh"  # 当前语言，main 按 meta.lang 设
TXT = {
    "zh": {"vs": "{sup} 对照 {off}", "tldr": "一句话：", "item": "项", "claimed": "{sup} 声称", "measured": "实测（对照官方）", "claims": "声称 vs 实测",
           "asks": "需要 {sup} 处理的事", "colon": "：", "method": "怎么测的", "not_tested": "没测", "auth": "是不是官方的东西：真伪证据", "evidence": "证据",
           "official_of": "官方（{off}）", "official": "官方", "pt_full": "透传完整", "pt_all": "全被封装", "pt_n": "{n} 项没透传",
           "pt_h": "参数透传：官方字段还在不在", "pt_intro": "官方成片链接、任务号、清晰度、时长、用量是否原样返回；换了字段名但值还在算保留，被替换成供应商自己的值、转存到自家存储或没有算丢失。",
           "field": "字段", "n_items": "{n} 项", "diffs": "和官方的差异（按影响分级）", "errors": "参数与报错", "input": "输入", "untested": "没实测",
           "tier": "档位", "unit_of": "{who}（{unit}）", "ratio": "倍率", "basis": "依据", "cost": "成本倍率", "appendix": "附录 · 原始请求与响应",
           "appendix_sub": "key 打码；只留 {h} 响应头；长文本、base64、签名链接截断。全部原始记录在任务目录 artifacts/。", "src": "（{s}）",
           "req": "请求", "resp": "响应", "side": "{who}{kind}", "side_sup": "{who} {kind}", "b64": "…（base64 省略）", "omit": "…（中间 %d 块省略）…",
           "yes": "是", "no": "否", "card": "内部决策卡", "card_meta": "不外发 · 外发证据版：", "gw_h": "网关接入：", "this_test": "本次测",
           "not_live": "未接入", "line": "线路", "cost_col": "成本", "succ": "30 天成功率", "vol": "30 天量", "note": "备注", "lines_h": "和现有同模型线路比",
           "ask_biz": "要问商务 / 对方", "risks": "风险", "next": "下一步", "card_title": " · 内部卡", "pdf": "{sup}-对照报告.pdf", "card_pdf": "{sup}-内部决策卡.pdf",
           "html_lang": "zh-CN",
           "impact": {"customer": "影响客户", "integration": "影响接入", "none": "不影响使用"},
           "gw": {"ready": "不改代码就能接", "gateway": "网关要改", "vendor": "要对方补"},
           "pass": {"same": "原样", "renamed": "改名保留", "lost": "丢失", "fake": "非官方值", "rehosted": "转存"}},
    "en": {"vs": "{sup} vs {off}", "tldr": "Bottom line: ", "item": "Item", "claimed": "{sup} claims", "measured": "Measured (vs official)", "claims": "Claimed vs measured",
           "asks": "For {sup} to address", "colon": ": ", "method": "How we tested", "not_tested": "Not tested", "auth": "Is it the real thing: authenticity evidence",
           "evidence": "Evidence", "official_of": "Official ({off})", "official": "Official", "pt_full": "Fully passed through", "pt_all": "All wrapped",
           "pt_n": "{n} not passed through", "pt_h": "Passthrough: are the official fields kept",
           "pt_intro": "Whether the official output link, task id, resolution, duration and usage come back as-is. A renamed field with the original value counts as kept; replaced by the supplier's own value, rehosted on its own storage, or missing counts as lost.",
           "field": "Field", "n_items": "{n} item(s)", "diffs": "Differences from official (by impact)", "errors": "Parameters and errors", "input": "Input",
           "untested": "Not tested", "tier": "Tier", "unit_of": "{who} ({unit})", "ratio": "Ratio", "basis": "Basis", "cost": "Cost ratio",
           "appendix": "Appendix · raw requests and responses",
           "appendix_sub": "Keys masked; only the {h} response headers kept; long text, base64 and signed links truncated. All raw records are in the task's artifacts/ folder.",
           "src": " ({s})", "req": "request", "resp": "response", "side": "{who} {kind}", "side_sup": "{who} {kind}", "b64": "… (base64 omitted)",
           "omit": "… (%d blocks omitted) …", "yes": "yes", "no": "no", "card": "Internal decision card", "card_meta": "internal only · external report: ",
           "gw_h": "Gateway: ", "this_test": "tested now", "not_live": "not connected", "line": "Line", "cost_col": "Cost", "succ": "30-day success",
           "vol": "30-day volume", "note": "Note", "lines_h": "Compared with existing lines for this model", "ask_biz": "Ask business / supplier",
           "risks": "Risks", "next": "Next steps", "card_title": " · internal card", "pdf": "{sup}-audit-report.pdf", "card_pdf": "{sup}-decision-card.pdf",
           "html_lang": "en",
           "impact": {"customer": "Affects customers", "integration": "Affects integration", "none": "No impact on use"},
           "gw": {"ready": "Works without code changes", "gateway": "Gateway change needed", "vendor": "Supplier must fix"},
           "pass": {"same": "Same", "renamed": "Renamed, kept", "lost": "Lost", "fake": "Not official", "rehosted": "Rehosted"}},
}


def t(k, **kw):
    s = TXT[L][k]; return s.format(**kw) if kw and isinstance(s, str) else s


def ev_name(k): return REQUIRED_EVIDENCE_EN.get(k, k) if L == "en" else next((d[k] for d in REQUIRED_EVIDENCE.values() if k in d), k)


def dec_id(x): return DEC_IN.get(str(x).casefold()) if isinstance(x, str) else None


def dec_label(k): return DECISION[k][1 if L == "en" else 0]


# ---------------- 小工具 ----------------
def md(s):
    """`代码`、**加粗**、换行；其余一律转义。"""
    if s is None: return "—"
    if isinstance(s, bool): return t("yes") if s else t("no")
    if isinstance(s, (int, float)): return f"{s:,}" if isinstance(s, int) else f"{s:g}"
    s = e(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return s.replace("\n", "<br>")


def tag(k, txt): return f'<span class="tag {e(k if hv(k) in VERDICT else "warn")}">{e(txt)}</span>'


CTX = None  # 当前 findings 的上下文，cell() 里引用 jsonl 记录要用


def ref_text(src):
    """{"jsonl":…, "label":…} → 「状态码 错误码 · 文案」（去掉 Request id），报错矩阵直接引原始记录，不手抄。"""
    r = CTX.record(src); b = r.get("resp")
    if isinstance(b, dict) and isinstance(b.get("error"), dict):
        er = b["error"]; msg = re.sub(r"\s*(\(request id: [^)]*\)|Request id: \w+\.?)", "", str(er.get("message", "")), flags=re.I)
        s = f'{r.get("status")} {er.get("code") or er.get("type") or ""} · {msg}'
    else:
        s = f'{r.get("status")} ' + (json.dumps(b, ensure_ascii=False) if not isinstance(b, str) else b)
    n = src.get("max", 220); return s if len(s) <= n else s[:n] + "…"


def cell(x):
    if isinstance(x, dict) and "jsonl" in x: return md(ref_text(x))
    if isinstance(x, dict) and "tag" in x:
        return tag(x["tag"], x.get("label", "")) + (f'<br>{md(x["text"])}' if x.get("text") else "")
    if isinstance(x, list): return "<br>".join(md(i) for i in x)
    return md(x)


def tbl(head, rows, cols=None, num=()):
    cg = "<colgroup>" + "".join(f'<col style="width:{w:g}%">' for w in cols) + "</colgroup>" if cols else ""
    h = "".join(f'<th class="{"n" if i in num else ""}">{e(x)}</th>' for i, x in enumerate(head))
    b = "".join("<tr>" + "".join(f'<td class="{"n" if i in num else ""}">{x}</td>' for i, x in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="scroll"><table style="table-layout:fixed">{cg}<thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


def first(tg, lbl, item):
    """判断标签放第一列（项目名下面），不单独占最右列（report-template「版式与打印」）。"""
    return f"{tag(tg, lbl)}<br>{md(item)}"


def jdump(x, ind=0, w=72):
    """紧凑 JSON：放得下一行的对象 / 数组写一行。"""
    one = json.dumps(x, ensure_ascii=False)
    if len(one) + ind <= w or not isinstance(x, (dict, list)) or not x: return one
    pad = " " * (ind + 1)
    if isinstance(x, dict):
        return "{\n" + ",\n".join(f"{pad}{json.dumps(k, ensure_ascii=False)}: {jdump(v, ind + 1, w)}" for k, v in x.items()) + "\n" + " " * ind + "}"
    return "[\n" + ",\n".join(pad + jdump(i, ind + 1, w) for i in x) + "\n" + " " * ind + "]"


def slim(x, n=100):
    """附录用：base64 省略、长文本截断、签名链接去掉 query、对象里的鉴权字段打码。"""
    if isinstance(x, dict): return {k: (mask_auth(v) if str(k).lower() in AUTH_HEADERS and isinstance(v, str) else slim_str(v, n, k) if isinstance(v, str) else slim(v, n)) for k, v in x.items()}
    if isinstance(x, list): return [slim(i, n) for i in x]
    return slim_str(x, n, "") if isinstance(x, str) else x


def slim_str(v, n, k):
    if v.startswith("data:"): return v[:30] + t("b64")
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
        self.path = os.path.abspath(path); self.dir = os.path.dirname(self.path); self._cache = {}
        if not os.path.isfile(self.path): raise SystemExit(f"找不到 {path}（先 --init 写骨架）")
        try: self.F = json.loads(rd(self.path))
        except json.JSONDecodeError as x: raise SystemExit(f"{path} 不是合法 JSON：第 {x.lineno} 行第 {x.colno} 列 {x.msg}")
        except UnicodeDecodeError: raise SystemExit(f"{path} 不是 UTF-8 文本")

    def p(self, rel): return rel if os.path.isabs(rel) else os.path.join(self.dir, rel)

    def jsonl(self, rel):
        if rel not in self._cache:
            rows = []
            for i, l in enumerate(rd(self.p(rel)).splitlines(), 1):
                if not l.strip(): continue
                try: rows.append(json.loads(l))
                except json.JSONDecodeError as x: raise ValueError(f"{rel} 第 {i} 行不是合法 JSON（{x.msg}）")
            self._cache[rel] = [r for r in rows if isinstance(r, dict)]
        return self._cache[rel]

    def record(self, src):
        rows = [r for r in self.jsonl(src["jsonl"]) if r.get("label") == src.get("label")]
        if not rows: raise SystemExit(f"找不到记录：{src['jsonl']} label={src.get('label')!r}")
        n = src.get("nth", 0)
        if not isinstance(n, int) or not -len(rows) <= n < len(rows): raise SystemExit(f"{src['jsonl']} label={src.get('label')!r} 只有 {len(rows)} 条，nth={n!r} 越界")
        return rows[n]

    def jpath(self, src):
        x = json.loads(rd(self.p(src["json"])))
        for k in (src.get("path") or "").split("."):
            if k: x = x[int(k)] if isinstance(x, list) else x[k]
        return x


def side_text(ctx, s, keep_h):
    """一侧（官方或供应商）的请求 / 响应文本。s 可以是 {jsonl,label} / {request,response}。鉴权头、URL 里的 key 参数打码。"""
    if not isinstance(s, dict): return None, None
    if "jsonl" not in s and "request" not in s and "response" not in s: return None, None  # 只有 note：没有可并排的官方原文
    if "jsonl" in s:
        r = ctx.record(s); host = s.get("host", "{base}")
        hd = "\n".join(f"{k}: {mask_auth(v) if k.lower() in AUTH_HEADERS else v}" for k, v in (r.get("req_headers") or {}).items() if k.lower() != "user-agent")
        req = f'{r.get("method", "")} {mask_url(str(r.get("url", "")).replace("{base}", str(host)))}\n{hd}'
        if r.get("body") is not None: req += "\n\n" + jdump(slim(r["body"]))
        h = {k: (mask_auth(v) if k.lower() in AUTH_HEADERS else v) for k, v in (r.get("resp_headers") or {}).items() if k.lower() in keep_h}
        rs = r.get("resp"); resp = "".join(f"{k}: {v}\n" for k, v in h.items()) + f'HTTP {r.get("status")}\n' + (jdump(slim(rs)) if not isinstance(rs, str) else rs[:1500])
        return req, resp
    out = []
    for k in ("request", "response"):
        v = s.get(k)
        if isinstance(v, dict) and "json" in v: v = ctx.jpath(v)
        if isinstance(v, dict) and "file" in v:  # 文本文件（如 SSE 原文）：head / tail 按空行分块取头尾，中间省略
            raw = rd(ctx.p(v["file"])); blocks = [b for b in raw.split("\n\n") if b.strip()]
            if "head" in v and len(blocks) > v["head"] + v.get("tail", 0):
                v = "\n\n".join(blocks[: v["head"]] + [t("omit") % (len(blocks) - v["head"] - v.get("tail", 0))] + (blocks[-v["tail"]:] if v.get("tail") else []))
            else: v = raw[: v.get("max", 3000)]
        out.append(v if isinstance(v, str) or v is None else jdump(slim(v)))
    return out[0], out[1]


def scan_artifacts(d):
    """任务目录（含子目录）里的 *.jsonl / *.sse 原文逐行扫 key（规则 4 / 13：原文落盘也要打码）。返回「相对路径:行号 片段」。"""
    hits = []
    for root, dirs, files in os.walk(d):
        dirs[:] = sorted(x for x in dirs if not x.startswith(".") and x not in ("node_modules", "__pycache__"))
        for f in sorted(files):
            if not f.endswith((".jsonl", ".sse")): continue
            p = os.path.join(root, f)
            with open(p, encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh, 1):
                    hits += [f"{os.path.relpath(p, d)}:{i} {mask_hit(x)}" for x in find_secrets(line)]
    return hits


# ---------------- 校验 ----------------
def hv(v): return v if isinstance(v, (str, int, float, type(None))) else repr(v)  # 用户填的值做集合 / 字典查找前先变成可哈希的


def is_num(x): return isinstance(x, (int, float)) and not isinstance(x, bool)


def is_external(F, flag=False):
    m = F.get("meta") if isinstance(F.get("meta"), dict) else {}
    return flag or m.get("mode") == "external"


def rule16_applies(m):
    """规则 16：Seedance（含 doubao-seedance、火山方舟 / Ark、BytePlus 视频）或 meta.rule16 true；只管视频线路。"""
    if m.get("rule16") is True: return True
    s = f'{m.get("model", "")} {m.get("official", "")}'.casefold()
    return m.get("kind") == "video" and bool(re.search(r"seedance|方舟|\bark\b|modelark|byteplus|火山引擎|volcengine", s))


def ratio_of(tr):
    """倍率 = 供应商 / 官方（小数，0.8 = 八折）；没写且两边都是数字就算出来。"""
    r = tr.get("ratio")
    if r is None and is_num(tr.get("official")) and is_num(tr.get("supplier")) and tr["official"]: r = tr["supplier"] / tr["official"]
    return r


def validate(F, ctx=None, external_only=False):
    err, warn = [], []
    if not isinstance(F, dict): return ["findings.json 顶层要是对象 {…}"], warn

    def need(obj, keys, where): [err.append(f"{where} 缺 {k}") for k in keys if obj.get(k) in (None, "", [], {})]

    def objs(x, where, req=True):
        """x 要是对象数组；返回其中的对象，非对象的条目报错。"""
        if x is None: (err.append(f"{where} 缺（没有就写 []）") if req else None); return []
        if not isinstance(x, list): err.append(f"{where} 要是数组 [...]（现在是 {type(x).__name__}）"); return []
        for i, v in enumerate(x):
            if not isinstance(v, dict): err.append(f"{where}[{i}] 要是对象 {{…}}（现在是 {json.dumps(v, ensure_ascii=False)[:40]}）")
        return [(i, v) for i, v in enumerate(x) if isinstance(v, dict)]

    def obj(x, where, req=True):
        if x is None: (err.append(f"{where} 缺") if req else None); return {}
        if not isinstance(x, dict): err.append(f"{where} 要是对象 {{…}}"); return {}
        return x

    def strs(x, where):
        if x is None: return []
        if not isinstance(x, list) or not all(isinstance(i, (str, int, float)) for i in x): err.append(f"{where} 要是文字数组 [\"…\"]"); return []
        return x

    chk = lambda v, where: hv(v) in VERDICT or err.append(f"{where} 的 verdict / tag 只能是 good / warn / bad（现在是 {v!r}）")

    def ref(src, where):
        """引用的原始记录 / 文件要找得到。"""
        if ctx is None: return
        try:
            if "jsonl" in src: ctx.record(src)
            elif "json" in src: ctx.jpath(src)
            elif "file" in src: rd(ctx.p(src["file"]))
        except SystemExit as x: err.append(f"{where}：{x}")
        except FileNotFoundError as x: err.append(f"{where}：找不到文件 {x.filename}")
        except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as x: err.append(f"{where}：引用读不出来（{type(x).__name__}: {x}）")

    def cell_ok(x, where):
        if isinstance(x, dict):
            if "jsonl" in x: ref(x, where)
            elif "tag" in x: chk(x["tag"], where)
            else: err.append(f"{where} 单元格对象只能是 {{\"tag\",\"label\",\"text\"}} 或 {{\"jsonl\",\"label\"}}")
        elif isinstance(x, list): [cell_ok(i, f"{where}[{j}]") for j, i in enumerate(x) if isinstance(i, (dict, list))]

    ext = is_external(F, external_only)
    m = obj(F.get("meta"), "meta"); need(m, ["title", "supplier", "official", "kind", "date", "model"], "meta")
    if hv(m.get("kind")) not in REQUIRED_EVIDENCE: err.append("meta.kind 只能是 video / text")
    if hv(m.get("lang", "zh")) not in TXT: err.append("meta.lang 只能是 zh / en")
    if hv(m.get("mode", "full")) not in ("full", "external"): err.append("meta.mode 只能是 full / external")
    if "keep_headers" in m: strs(m["keep_headers"], "meta.keep_headers")
    for k in ("pdf_name", "card_pdf_name", "out_dir"):
        if k in m and m[k] is not None and not isinstance(m[k], str): err.append(f"meta.{k} 要是文字")
    need(F, ["summary", "claims", "verdicts", "authenticity", "cost"] + ([] if ext else ["gateway", "internal"]), "顶层")
    for k in ("asks", "diffs"):
        if F.get(k) is None: err.append(f"顶层缺 {k}（没有就写 []）")
    for i, c in objs(F.get("claims"), "claims"): need(c, ["item", "claimed", "measured", "verdict", "label"], f"claims[{i}]"); chk(c.get("verdict"), f"claims[{i}]")
    vs = objs(F.get("verdicts"), "verdicts")
    for i, c in vs: need(c, ["area", "verdict", "label", "text"], f"verdicts[{i}]"); chk(c.get("verdict"), f"verdicts[{i}]")
    if len(vs) > 4: warn.append("结论卡超过 4 张，第 1 页可能放不下")
    for i, a in objs(F.get("asks"), "asks", req=False): need(a, ["item"], f"asks[{i}]")
    mt = obj(F.get("method"), "method", req=False)
    if "kv" in mt and (not isinstance(mt["kv"], list) or not all(isinstance(p, list) and len(p) == 2 for p in mt["kv"])): err.append("method.kv 要是 [[标题, 内容], …]")
    au = obj(F.get("authenticity"), "authenticity", req=False)  # 缺整块由上面「顶层缺」报
    if au and "evidence" not in au: err.append("authenticity 缺 evidence（数组）")
    ev = [c for _, c in objs(au.get("evidence"), "authenticity.evidence", req=False)]
    for i, c in enumerate(ev):
        need(c, ["id", "check", "official", "supplier", "verdict", "label"], f"authenticity.evidence[{i}]"); chk(c.get("verdict"), f"authenticity.evidence[{i}]")
    sk = obj(au.get("skipped"), "authenticity.skipped", req=False)
    have = {hv(c.get("id")) for c in ev} | set(sk.keys())
    for k, name in REQUIRED_EVIDENCE.get(hv(m.get("kind")), {}).items():
        if k not in have: err.append(f"真伪证据缺必查项 {k}（{name}）：补一行 evidence（id={k}），没测就在 authenticity.skipped 写原因")
    co = obj(F.get("cost"), "cost", req=False)
    if co and co.get("tiers") is None: err.append("cost 缺 tiers（数组，每档一行）")
    for i, tr in objs(co.get("tiers"), "cost.tiers", req=False):
        need(tr, ["tier"], f"cost.tiers[{i}]")
        for k in ("official", "supplier", "ratio"):
            if tr.get(k) is not None and not is_num(tr[k]): err.append(f"cost.tiers[{i}].{k} 要是数字或 null（现在是 {tr[k]!r}；带单位的文字写 {k}_text）" if k != "ratio" else f"cost.tiers[{i}].ratio 要是小数（供应商 / 官方，0.8 = 八折）或 null（现在是 {tr[k]!r}）")
        if "tested" not in tr: warn.append(f"成本档位「{tr.get('tier')}」没写 tested（规则 1：每档都要实测，测了写 true）")
        elif not tr["tested"]: warn.append(f"成本档位「{tr.get('tier')}」没实测（规则 1：每档都要实测，别线性外推）")
        r, o, s = tr.get("ratio"), tr.get("official"), tr.get("supplier")
        if is_num(r) and is_num(o) and is_num(s) and o and abs(r - s / o) > max(0.02, 0.05 * abs(s / o)):
            warn.append(f"成本档位「{tr.get('tier')}」ratio {r:g} 和 supplier / official = {s / o:.3g} 对不上（ratio 是小数，0.8 = 八折，不是百分数）")
    gw = obj(F.get("gateway"), "gateway", req=False)
    if gw:
        if gw.get("items") is None: err.append("gateway 缺 items（数组；没有要改的就写一条 ready）")
        for i, g in objs(gw.get("items"), "gateway.items", req=False):
            need(g, ["item"], f"gateway.items[{i}]")
            if hv(g.get("tier")) not in GW_TAG: err.append(f"gateway.items[{i}].tier 只能是 ready / gateway / vendor")
        if gw.get("tier") is not None and hv(gw["tier"]) not in GW_TAG: err.append("gateway.tier 只能是 ready / gateway / vendor（或不写，取 items 里最高的）")
    for i, d in objs(F.get("diffs"), "diffs", req=False):
        need(d, ["item", "official", "supplier", "impact"], f"diffs[{i}]")
        if hv(d.get("impact")) not in IMPACT_TAG: err.append(f"diffs[{i}].impact 只能是 customer / integration / none")
    er = obj(F.get("errors"), "errors", req=False)
    for i, r in objs(er.get("rows"), "errors.rows", req=False):
        need(r, ["input", "official", "supplier", "verdict", "label"], f"errors.rows[{i}]"); chk(r.get("verdict"), f"errors.rows[{i}]")
        cell_ok(r.get("official"), f"errors.rows[{i}].official"); cell_ok(r.get("supplier"), f"errors.rows[{i}].supplier")
    for i, s in objs(F.get("sections"), "sections", req=False):
        w = f"sections[{i}]"; need(s, ["title"], w)
        b = obj(s.get("bars"), f"{w}.bars", req=False)
        if b:
            for j, it in objs(b.get("items"), f"{w}.bars.items"):
                if it.get("value") is not None and not is_num(it["value"]): err.append(f"{w}.bars.items[{j}].value 要是数字或 null")
        tb = obj(s.get("table"), f"{w}.table", req=False)
        if tb:
            if not isinstance(tb.get("head"), list): err.append(f"{w}.table.head 要是数组")
            rows = tb.get("rows")
            if not isinstance(rows, list) or not all(isinstance(r, list) for r in rows): err.append(f"{w}.table.rows 要是二维数组 [[…], …]")
            else: [cell_ok(c, f"{w}.table.rows[{j}][{k}]") for j, r in enumerate(rows) for k, c in enumerate(r)]
            if tb.get("cols") is not None and (not isinstance(tb["cols"], list) or not all(is_num(c) for c in tb["cols"])): err.append(f"{w}.table.cols 要是数字数组（列宽 %）")
            if tb.get("num") is not None and (not isinstance(tb["num"], list) or not all(isinstance(c, int) for c in tb["num"])): err.append(f"{w}.table.num 要是列号数组")
        im = obj(s.get("image"), f"{w}.image", req=False)
        if im:
            if not isinstance(im.get("path"), str): err.append(f"{w}.image 缺 path")
            elif os.path.splitext(im["path"])[1].lower() not in MIME: err.append(f"{w}.image.path 只收 {' / '.join(sorted(MIME))}")
            elif ctx is not None and not os.path.isfile(ctx.p(im["path"])): err.append(f"{w}.image：找不到 {im['path']}")
        strs(s.get("bullets"), f"{w}.bullets")
    exs = objs(F.get("exchanges"), "exchanges")
    if isinstance(F.get("exchanges"), list) and not F["exchanges"]: err.append("exchanges 不能为空：附录至少放一对官方 / 供应商原始请求响应（规则 13 / 14）")
    for i, x in exs:
        if not x.get("title"): err.append(f"exchanges[{i}] 缺 title")
        o = x.get("official")
        if not o: err.append(f"exchanges[{i}]「{x.get('title')}」缺官方一侧：放官方实测 jsonl 或官方文档示例（source 写「文档示例」）；确实没有就写 official.note 说明原因")
        elif not isinstance(o, dict): err.append(f"exchanges[{i}].official 要是对象")
        elif not any(k in o for k in ("jsonl", "request", "response", "note")): err.append(f"exchanges[{i}].official 要有 jsonl / request / response / note 之一")
        sp = x.get("supplier") or {}
        if not isinstance(sp, dict): err.append(f"exchanges[{i}].supplier 要是对象"); sp = {}
        for side, sd in (("official", o if isinstance(o, dict) else {}), ("supplier", sp)):
            if "jsonl" in sd: ref(sd, f"exchanges[{i}].{side}")
            for k in ("request", "response"):
                if isinstance(sd.get(k), dict) and ("json" in sd[k] or "file" in sd[k]): ref(sd[k], f"exchanges[{i}].{side}.{k}")
        if sp and "jsonl" not in sp and not any(isinstance(sp.get(k), dict) and ("json" in sp[k] or "file" in sp[k]) for k in ("request", "response")):
            warn.append(f"exchanges[{i}]「{x.get('title')}」供应商一侧不是从原始记录（jsonl / artifacts 文件）引用的，规则 13 要求原文落盘")
    it = obj(F.get("internal"), "internal", req=False)
    dec = dec_id(it.get("decision"))
    pt = obj(F.get("passthrough"), "passthrough", req=False)
    prow = [r for _, r in objs(pt.get("rows"), "passthrough.rows", req=False)]
    for i, r in enumerate(prow):
        need(r, ["field", "official", "supplier", "status"], f"passthrough.rows[{i}]")
        if hv(r.get("status")) not in PASS_STATUS: err.append(f"passthrough.rows[{i}].status 只能是 {' / '.join(PASS_STATUS)}")
    if m.get("kind") == "video":
        have_f = {hv(r.get("id")) for r in prow}
        for k, name in PASS_CORE.items():
            if k not in have_f: err.append(f"passthrough 缺必查字段 {k}（{name}）：写官方字段 / 供应商字段 / status（{' / '.join(PASS_STATUS)}）")
        lost = [r["id"] for r in prow if hv(r.get("id")) in PASS_CORE and hv(r.get("status")) in PASS_BAD]
        if lost and len(set(lost)) == len(PASS_CORE) and dec in ("primary", "backup"):
            err.append("passthrough 核心字段全被封装（没法按官方接入），internal.decision 不能是主线 / 备用（primary / backup）")
    if rule16_applies(m):
        # 规则 16：拿不到官方原链接（链接字段丢 / 非官方 / 转存、桶不是官方）或不是原片（C2PA 不是 good）→ 只能判不接
        byid = lambda k: [c for c in ev if c.get("id") == k]
        for k, name in (("c2pa", "C2PA"), ("bucket", "成片存储桶")):
            if not byid(k): err.append(f"规则 16（Seedance / 方舟 / BytePlus 视频）必须实测 {k}（{name}），不能写进 authenticity.skipped")
        url_ok = any(r.get("id") == "video_url" and r.get("status") in ("same", "renamed") for r in prow)
        bucket_ok = bool(byid("bucket")) and all(c.get("verdict") == "good" for c in byid("bucket"))
        orig_ok = bool(byid("c2pa")) and all(c.get("verdict") == "good" for c in byid("c2pa"))
        why = [w for ok, w in ((url_ok, "video_url 不是原样 / 改名保留"), (bucket_ok, "成片桶不是官方（bucket 不是 good）"), (orig_ok, "不是原片（C2PA 不是 good）")) if not ok]
        if why and ext and not it: warn.append("规则 16 没过：" + "、".join(why) + " → 这条线不能接（外发版不写建议）")
        elif why and dec != "reject": err.append("规则 16：" + "、".join(why) + " → internal.decision 只能是「不接」（reject）")
    if not ext:
        if dec is None: err.append(f"internal.decision 只能是 {' / '.join(v[0] for v in DECISION.values())}（或 {' / '.join(DECISION)}）")
        need(it, ["reason"], "internal")
        if it.get("existing_lines") is None: err.append("internal 缺 existing_lines（和你现有的同模型线路比；确实没有就写 [] 并在 existing_note 说明）")
        elif not it["existing_lines"] and not it.get("existing_note"): err.append("internal.existing_lines 为空时要写 existing_note")
        obj(it.get("this_line"), "internal.this_line", req=False)
        for k in ("ask_business", "risks", "next"): strs(it.get(k), f"internal.{k}")
    objs(it.get("existing_lines"), "internal.existing_lines", req=False)
    if it.get("redact_terms") is not None and (not isinstance(it["redact_terms"], list) or not all(isinstance(x, str) for x in it["redact_terms"])):
        err.append("internal.redact_terms 要是文字数组")
    return err, warn


def leak_check(ext_html, F):
    """外发版不许出现内部字段里的线路 / 供应商名、内部专用词。比对前：反转义、不分大小写、去掉标签和 ** ` 标记，
    属性值（alt / title …）和外发文件名也查。"""
    it = F.get("internal") if isinstance(F.get("internal"), dict) else {}; m = F["meta"]
    own = {str(m.get("supplier", "")).casefold(), str(m.get("official", "")).casefold()}
    terms = {x for x in (it.get("redact_terms") or []) if isinstance(x, str)}
    for l in it.get("existing_lines") or []:
        for k in ("line", "supplier"):
            v = l.get(k) if isinstance(l, dict) else None
            if isinstance(v, str) and v.casefold() not in own: terms.add(v)
    body = re.sub(r"<style.*?</style>", " ", ext_html, flags=re.S)
    attrs = " ".join(v for k, v in re.findall(r'\s([\w-]+)="([^"]*)"', body) if k.lower() not in ("src", "style", "class"))
    extra = " ".join(str(m.get(k) or "") for k in ("pdf_name", "short_title"))
    zw = re.compile(r"[​-‏⁠﻿­]")
    norm = lambda s: re.sub(r"\s+", " ", zw.sub("", html.unescape(s))).casefold()
    hay = [norm(re.sub(r"<[^>]+>", sep, body) + " " + attrs + " " + extra) for sep in (" ", "")]
    hay += [re.sub(r"[*`]", "", h) for h in hay]
    return sorted(x for x in terms if x.strip() and any(norm(x).strip() in h for h in hay))


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
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif", ".svg": "image/svg+xml"}


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
                   + "".join(bar(i.get("label"), i.get("value"), mx, i.get("hot"), i.get("text")) for i in b["items"]) + "</div>")
    if s.get("table"):
        tb = s["table"]; out.append(tbl(tb["head"], [[cell(c) for c in r] for r in tb["rows"]], tb.get("cols"), tuple(tb.get("num") or [])))
    if s.get("image"):
        im = s["image"]; raw = rb(ctx.p(im["path"])); mime = MIME[os.path.splitext(im["path"])[1].lower()]
        out.append(f'<figure><img src="data:{mime};base64,{base64.b64encode(raw).decode()}" alt="{e(im.get("alt", ""))}"><figcaption>{md(im.get("caption", ""))}</figcaption></figure>')
    if s.get("bullets"): out.append("<ul>" + "".join(f"<li>{md(b)}</li>" for b in s["bullets"]) + "</ul>")
    if s.get("note"): out.append(f'<p class="sub note">{md(s["note"])}</p>')
    return "".join(out) + "</section>"


def external(ctx):
    F = ctx.F; m = F["meta"]; css = rd(os.path.join(SKILL, "report_style.html")) + EXTRA_CSS
    sup, off = m["supplier"], m["official"]; n = [0]; c_ = t("colon")

    def h2(x): n[0] += 1; return f"<h2>{n[0]} {e(x)}</h2>"
    head = f'''<header><h1>{md(m["title"])}</h1><div class="meta">{md(m.get("subtitle") or t("vs", sup=sup, off=off))} · {e(m["date"])}{(" · " + md(m["scope"])) if m.get("scope") else ""}</div></header>'''
    cards = "".join(f'<div class="v">{tag(v["verdict"], v["label"])}<b>{md(v["area"])}</b><span class="d">{md(v["text"])}</span></div>' for v in F["verdicts"])
    page1 = f'<section><div class="tldr"><p><b>{e(t("tldr"))}</b>{md(F["summary"])}</p></div><div class="verdicts">{cards}</div></section>'
    claims = tbl([t("item"), t("claimed", sup=sup), t("measured")],
                 [[first(c["verdict"], c["label"], c["item"]), md(c["claimed"]), md(c["measured"])] for c in F["claims"]], cols=[22, 32, 46])
    parts = [head, page1, f"<section>{h2(t('claims'))}{claims}</section>"]
    gw_items = (F.get("gateway") or {}).get("items") or []
    asks = list(F.get("asks") or []) + [{"item": g["item"], "why": g.get("detail", "")} for g in gw_items if g["tier"] == "vendor" and not g.get("internal_only")]
    if asks:
        li = "".join(f'<li><b>{md(a["item"])}</b>{(c_ + md(a["why"])) if a.get("why") else ""}</li>' for a in asks)
        parts.append(f'<section>{h2(t("asks", sup=sup))}<ol class="asks">{li}</ol></section>')
    mt = F.get("method") or {}
    if mt:
        kv = "".join(f"<div><b>{md(k)}</b><span>{md(v)}</span></div>" for k, v in mt.get("kv", []))
        parts.append(f'<section>{h2(t("method"))}<div class="kv">{kv}</div>' + (f'<p class="sub note">{md(mt["note"])}</p>' if mt.get("note") else "") + "</section>")
    au = F["authenticity"]
    rows = [[first(c["verdict"], c["label"], c["check"]), md(c["official"]), md(c["supplier"])] for c in au["evidence"]]
    rows += [[first("warn", t("not_tested"), ev_name(k)), "—", md(why)] for k, why in (au.get("skipped") or {}).items()]
    parts.append(f'<section>{h2(t("auth"))}' + (f'<p class="sub">{md(au["intro"])}</p>' if au.get("intro") else "")
                 + tbl([t("evidence"), t("official_of", off=off), sup], rows, cols=[22, 36, 42]) + (f'<p class="sub note">{md(au["note"])}</p>' if au.get("note") else "") + "</section>")
    pt = F.get("passthrough")
    if pt and pt.get("rows"):
        core = [r for r in pt["rows"] if r.get("id") in PASS_CORE]; bad = [r for r in core if r["status"] in PASS_BAD]
        vt = ("good", t("pt_full")) if not bad else (("bad", t("pt_all")) if len(bad) == len(core) else ("warn", t("pt_n", n=len(bad))))
        rows = [[first(PASS_STATUS[r["status"]], t("pass")[r["status"]], r["field"]) + (f'<br><span class="muted">{md(r["note"])}</span>' if r.get("note") else ""),
                 md(r["official"]), md(r["supplier"])] for r in pt["rows"]]
        parts.append(f'<section>{h2(t("pt_h"))}<p class="sub">{tag(*vt)} '
                     + md(pt.get("intro") or t("pt_intro")) + "</p>"
                     + tbl([t("field"), t("official_of", off=off), sup], rows, cols=[24, 34, 42]) + (f'<p class="sub note">{md(pt["note"])}</p>' if pt.get("note") else "") + "</section>")
    groups = []
    for imp in ("customer", "integration", "none"):
        ds = [d for d in F["diffs"] if d["impact"] == imp]
        if ds:
            groups.append(f'<h3>{tag(IMPACT_TAG[imp], t("impact")[imp])} {e(t("n_items", n=len(ds)))}</h3>' + tbl([t("item"), t("official"), sup],
                          [[md(d["item"]) + (f'<br><span class="muted">{md(d["note"])}</span>' if d.get("note") else ""), md(d["official"]), md(d["supplier"])] for d in ds], cols=[24, 34, 42]))
    if groups: parts.append(f"<section>{h2(t('diffs'))}" + "".join(groups) + "</section>")
    er = F.get("errors")
    if er and er.get("rows"):
        parts.append(f'<section>{h2(t("errors"))}' + (f'<p class="sub">{md(er["intro"])}</p>' if er.get("intro") else "")
                     + tbl([t("input"), t("official"), sup], [[first(r["verdict"], r["label"], r["input"]), cell(r["official"]), f'<span class="muted small" style="font-family:var(--font-mono)">{cell(r["supplier"])}</span>'] for r in er["rows"]], cols=[24, 30, 46])
                     + (f'<p class="sub note">{md(er["note"])}</p>' if er.get("note") else "") + "</section>")
    for s in F.get("sections") or []: parts.append(section_extra(ctx, s).replace("<h2>", "<h2>" + str(n[0] + 1) + " ", 1)); n[0] += 1
    co = F["cost"]; unit = co.get("unit", "")
    crow = [[md(tr["tier"]) + ("" if tr.get("tested", True) else "<br>" + tag("warn", t("untested"))), md(tr.get("official_text") or tr.get("official")),
             md(tr.get("supplier_text") or tr.get("supplier")), fmt_ratio(ratio_of(tr)), md(tr.get("basis", ""))] for tr in co["tiers"]]
    cost_html = tbl([t("tier"), t("unit_of", who=t("official"), unit=unit), t("unit_of", who=sup, unit=unit), t("ratio"), t("basis")], crow, cols=[18, 20, 20, 10, 32], num=(3,))
    pairs = [tr for tr in co["tiers"] if tr.get("official") is not None and tr.get("supplier") is not None and co.get("chart", True)]
    if pairs:
        mx = max(max(tr["official"], tr["supplier"]) for tr in pairs)
        cost_html += '<div class="chart">' + "".join(bar(f'{tr["tier"]} · {t("official")}', tr["official"], mx) + bar(f'{tr["tier"]} · {sup}', tr["supplier"], mx, True) for tr in pairs) + "</div>"
    parts.append(f'<section>{h2(t("cost"))}' + (f'<p class="sub">{md(co["intro"])}</p>' if co.get("intro") else "") + cost_html
                 + (f'<p class="sub note">{md(co["note"])}</p>' if co.get("note") else "") + "</section>")
    ex = F.get("exchanges") or []
    if ex:
        keep_h = {str(h).lower() for h in m.get("keep_headers", ["server", "x-new-api-version", "x-request-id"])}
        out = [f'<section class="appendix"><h2>{e(t("appendix"))}</h2><p class="sub">{e(t("appendix_sub", h=" / ".join(sorted(keep_h))))}</p>']
        for x in ex:
            o = x.get("official") or {}; o_req, o_resp = side_text(ctx, o, keep_h); s_req, s_resp = side_text(ctx, x.get("supplier"), keep_h)
            on = e(t("official")) + (e(t("src", s=o["source"])) if o.get("source") else "")
            out.append(f'<h3>{md(x["title"])}</h3>' + (f'<p class="sub">{md(x["note"])}</p>' if x.get("note") else "")
                       + (f'<p class="sub">{on}{c_}{md(o["note"])}</p>' if o.get("note") and not (o_req or o_resp) else ""))
            for kind, a, b in ((t("req"), o_req, s_req), (t("resp"), o_resp, s_resp)):
                oh, sh = t("side", who=on, kind=kind), t("side_sup", who=e(sup), kind=kind)
                if a and b and fits_side(a, b): out.append(f'<div class="pair"><div><h4>{oh}</h4>{code(a)}</div><div><h4>{sh}</h4>{code(b)}</div></div>')
                elif a and b: out.append(f'<div><h4>{oh}</h4>{code(a, wide=True)}</div><div><h4>{sh}</h4>{code(b, wide=True)}</div>')
                elif a or b: out.append(f'<div><h4>{t("side_sup", who=on if a else e(sup), kind=kind)}</h4>{code(a or b, wide=True)}</div>')
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
    F = ctx.F; m = F["meta"]; it = F["internal"]; sup = m["supplier"]; c_ = t("colon"); G = t("gw")
    css = rd(os.path.join(SKILL, "report_style.html")) + CARD_CSS.replace("__ZOOM__", f"{zoom:g}")
    gw_items = F["gateway"]["items"]; order = ["ready", "gateway", "vendor"]
    gw = F["gateway"].get("tier") or max((g["tier"] for g in gw_items), key=order.index, default="ready")
    d = dec_id(it["decision"])
    dec = f'''<div class="dec"><span class="big {DECISION[d][2]}">{e(dec_label(d))}</span><div><p style="max-width:none"><b>{md(F["summary"])}</b></p><p style="max-width:none;margin-top:6px">{md(it["reason"])}</p></div></div>'''
    head = f'<header><h1 style="font-size:24px">{md(m["title"])} · {e(t("card"))}</h1><div class="meta">{e(m["date"])} · {e(t("card_meta"))}{e(pdf_rel)}</div></header>'
    claims = "".join(f'<tr><td>{tag(c["verdict"], c["label"])}</td><td>{md(c["item"])}</td><td>{md(c["measured"])}</td></tr>' for c in F["claims"])
    claims = f'<div class="card"><h3>{e(t("claims"))}</h3><div class="scroll"><table style="table-layout:fixed"><colgroup><col style="width:22%"><col style="width:22%"><col style="width:56%"></colgroup><tbody>{claims}</tbody></table></div></div>'
    gwl = "".join(f'<li>{(tag(GW_TAG[g["tier"]], G[g["tier"]]) + " ") if g["tier"] != gw else ""}<b>{md(g["item"])}</b>{(c_ + md(g["detail"])) if g.get("detail") else ""}</li>' for g in gw_items)
    gwc = f'<div class="card"><h3>{e(t("gw_h"))}{tag(GW_TAG[gw], G[gw])}</h3><ul>{gwl}</ul>' + (f'<p class="foot">{md(F["gateway"]["note"])}</p>' if F["gateway"].get("note") else "") + "</div>"
    this = it.get("this_line") or {}
    rows = [[f'<b>{md(sup)}</b><br>{tag("warn", t("this_test"))}', md(this.get("cost", "—")), md(this.get("success_30d", t("not_live"))), md(this.get("volume_30d", "—")), md(this.get("note", ""))]]
    rows += [[md(l.get("line")) + (f'<br><span class="muted">{md(l["supplier"])}</span>' if l.get("supplier") and l["supplier"] != l.get("line") else ""), md(l.get("cost")), md(l.get("success_30d")), md(l.get("volume_30d")), md(l.get("note", ""))] for l in it["existing_lines"]]
    lines = tbl([t("line"), t("cost_col"), t("succ"), t("vol"), t("note")], rows, cols=[20, 24, 14, 14, 28])
    lines = f'<div class="card"><h3>{e(t("lines_h"))}</h3>{lines if it["existing_lines"] else ""}' + (f'<p class="foot">{md(it.get("existing_note"))}</p>' if it.get("existing_note") else "") + "</div>"
    ask = it.get("ask_business") or []; risks = it.get("risks") or []; nxt = it.get("next") or []
    lst = lambda h, xs: f'<div class="card"><h3>{e(h)}</h3><ul>' + "".join(f"<li>{md(x)}</li>" for x in xs) + "</ul></div>" if xs else ""
    body = f'{head}{dec}{lines}<div class="two"><div>{claims}</div><div>{gwc}{lst(t("ask_biz"), ask)}{lst(t("risks"), risks)}{lst(t("next"), nxt)}</div></div>'
    return f'<title>{e(m.get("short_title") or m["title"])}{e(t("card_title"))}</title>{css}<main>{body}</main>'


# ---------------- PDF ----------------
def rb(p):
    with open(p, "rb") as f: return f.read()


def pdf_pages(pdf): return len(re.findall(rb"/Type\s*/Page(?!s)", rb(pdf)))


def to_pdf(html_path, pdf):
    """调 html_to_pdf.sh（用 sh 调，不依赖可执行位）；先删旧 PDF，写不出来就报清楚原因。"""
    if os.path.exists(pdf): os.remove(pdf)
    r = subprocess.run(["sh", os.path.join(SKILL, "html_to_pdf.sh"), html_path, pdf, t("html_lang")], capture_output=True, text=True)
    if r.returncode == 127: raise SystemExit(r.stderr.strip() or "找不到 Chrome / Chromium：装 Google Chrome 或 Chromium，或设环境变量 CHROME=<可执行文件路径>")
    if r.returncode: raise SystemExit(f"转 PDF 失败（退出码 {r.returncode}）：\n{r.stderr.strip()[-1500:]}")
    if not os.path.isfile(pdf) or os.path.getsize(pdf) == 0: raise SystemExit(f"Chrome 没写出 PDF：{pdf}\n{r.stderr.strip()[-800:]}")


def seams(pdf):
    """换页拼图（检查用，不入库）：放进新建的临时目录；要 uv（自动拉 pymupdf / pillow），没有 uv 但本机有这两个包就直接跑。"""
    out = os.path.join(tempfile.mkdtemp(prefix="report-seams-"), os.path.splitext(os.path.basename(pdf))[0] + ("-page-breaks.png" if L == "en" else "-换页.png"))
    cp = os.path.join(SKILL, "check_pages.py")
    if shutil.which("uv"): cmd = ["uv", "run", "-q", "--with", "pymupdf", "--with", "pillow", "python", "-I", cp, pdf, out]
    elif subprocess.run([sys.executable, "-c", "import pymupdf, PIL"], capture_output=True).returncode == 0: cmd = [sys.executable, "-I", cp, pdf, out]
    else:
        print("提醒：换页拼图没出（要 uv：https://docs.astral.sh/uv/ ，或 pip install pymupdf pillow），发 PDF 前手动跑 scripts/check_pages.py"); return
    if subprocess.run(cmd).returncode: print("提醒：换页拼图没出成：手动跑 scripts/check_pages.py")


def card_pdf(ctx, pdf_rel, html_path, pdf):
    """内部卡必须一页 A4：从 zoom 1 起逐级缩小，取第一个只出一页的；internal-card.html 也改写成这个 zoom（浏览器里打印同样一页）。"""
    for z in (1.0, 0.92, 0.85, 0.78, 0.72, 0.66, 0.6):
        with open(html_path, "w", encoding="utf-8") as f: f.write(card(ctx, pdf_rel, z))
        to_pdf(html_path, pdf); n = pdf_pages(pdf)
        if n == 1: return z
    print(f"提醒：内部卡缩到 zoom {z} 还是 {n} 页，内容太多，删减 internal 里的条目"); return z


# ---------------- 入口 ----------------
def skeleton(kind):
    ev = [{"id": k, "check": v, "official": "", "supplier": "", "verdict": "good", "label": "一致"} for k, v in REQUIRED_EVIDENCE[kind].items()]
    return {"meta": {"title": "", "short_title": "", "supplier": "", "official": "", "model": "", "kind": kind, "date": "", "scope": "", "pdf_name": "", "lang": "zh"},
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


FLAGS = {"--check", "--pdf", "--scan", "--external-only", "--init", "-h", "--help"}


def write(p, s):
    with open(p, "w", encoding="utf-8") as f: f.write(s)


def main(a):
    global CTX, L
    flags = {x for x in a if x.startswith("-")}; pos = [x for x in a if not x.startswith("-")]
    if flags & {"-h", "--help"}: print(USAGE); return
    if flags - FLAGS: raise SystemExit(f"不认识的参数：{' '.join(sorted(flags - FLAGS))}（-h 看用法）")
    if "--init" in flags:
        kinds = [x for x in pos if x in REQUIRED_EVIDENCE]; rest = [x for x in pos if x not in REQUIRED_EVIDENCE]
        if len(pos) != 2 or len(kinds) != 1: raise SystemExit("用法：build_report.py --init video|text <findings.json>（类型只能是 video / text）")
        out = rest[0]
        if os.path.isdir(out): out = os.path.join(out, "findings.json")
        if os.path.exists(out): raise SystemExit(f"{out} 已存在，不覆盖")
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f: json.dump(skeleton(kinds[0]), f, ensure_ascii=False, indent=1)
        print("写好骨架", out); return
    if len(pos) != 1: raise SystemExit(USAGE if not a else "要且只要一个 findings.json 路径（-h 看用法）")
    path = os.path.join(pos[0], "findings.json") if os.path.isdir(pos[0]) else pos[0]
    if "--scan" in flags:
        hits = scan_artifacts(os.path.dirname(os.path.abspath(path)))
        if hits: raise SystemExit("原始记录里有像 key 的串（先打码再给别人看任务目录）：\n  " + "\n  ".join(hits))
        print("原始记录里没扫到像 key 的串"); return
    ctx = CTX = Ctx(path); xo = "--external-only" in flags
    errs, warns = validate(ctx.F, ctx, xo)
    for w in warns: print("提醒：", w)
    if errs: raise SystemExit("findings.json 没通过校验：\n  " + "\n  ".join(errs))
    for h in scan_artifacts(ctx.dir): print("提醒：原始记录里像 key 的串（规则 4，先打码）：", h)
    m = ctx.F["meta"]; L = m.get("lang") or "zh"; ext_only = is_external(ctx.F, xo); sup = m["supplier"]
    od = m.get("out_dir") or "artifacts"; art = os.path.join(ctx.dir, od); pdf_name = m.get("pdf_name") or t("pdf", sup=sup)
    try:
        ext = external(ctx); crd = None if ext_only else card(ctx, os.path.join(od, pdf_name))
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as x:  # 校验没覆盖到的结构问题：报清楚，不甩 traceback
        raise SystemExit(f"findings.json 结构不对，生成失败（{type(x).__name__}: {x}）")
    leaks = leak_check(ext, ctx.F)
    if leaks: raise SystemExit("外发版出现了内部才能写的名字（别家线路 / 供应商 / redact_terms）：" + "、".join(leaks))
    for name, h in (("外发版", ext), ("内部卡", crd)):
        hit = find_secrets(h) if h else []
        if hit: raise SystemExit(f"{name}里有像 key 的串，先打码：" + "、".join(mask_hit(x) for x in hit))
    if "--check" in flags: print("校验通过" + ("（只出外发版）" if ext_only else "")); return
    os.makedirs(art, exist_ok=True)
    write(os.path.join(art, "report.html"), ext)
    if crd: write(os.path.join(art, "internal-card.html"), crd)
    print(f"外发版 {os.path.join(art, 'report.html')}（{len(ext)//1024} KB）" + (f" · 内部卡 {os.path.join(art, 'internal-card.html')}" if crd else " · 只出外发版，不出内部卡"))
    if "--pdf" in flags:
        pdf = os.path.join(art, pdf_name)
        to_pdf(os.path.join(art, "report.html"), pdf)
        print(f"PDF {pdf}（{pdf_pages(pdf)} 页）"); seams(pdf)
        if crd:
            cpdf = os.path.join(art, m.get("card_pdf_name") or t("card_pdf", sup=sup))
            z = card_pdf(ctx, os.path.join(od, pdf_name), os.path.join(art, "internal-card.html"), cpdf)
            print(f"内部卡 PDF {cpdf}（{pdf_pages(cpdf)} 页，zoom {z:g}）")


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)  # 和子进程（Chrome / uv）的输出按先后顺序显示
    main(sys.argv[1:])
