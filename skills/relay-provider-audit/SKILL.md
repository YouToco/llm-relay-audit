---
name: relay-provider-audit
description: >-
  Audit a third-party AI API relay / reseller (new-api, one-api, sub2api) against the official API, for text (LLM) and video lines — real model or swapped, injected system prompt, original video (C2PA), params and errors, token accounting, cost ratio, gateway readiness; logs every request to JSONL and renders an evidence PDF plus an internal decision card. 中转站 / 代理接入检测：用户说「测这家中转 / 测这个令牌 / 测这个分组」「和官方对比」「是不是真模型 / 掺了假模型」「有没有注入提示词」「视频是不是原片」「订阅号池」「参数透传」「出供应商对照报告」时用。Baselines: Claude (incl. Bedrock), Grok, Gemini, Kimi, GLM, DeepSeek, Alibaba wan3, MiniMax H3, Seedance.
license: MIT
compatibility: Needs Python 3.10+ and network access to the relay and official APIs. PDF output needs Chrome or Chromium; video forensics need ffmpeg and uv (pulls Pillow, numpy, c2pa-python). Works in any agent that loads Agent Skills (Claude Code, Codex, Cursor, Gemini CLI…).
metadata:
  author: YouToco
  version: "0.2.0"
  repository: https://github.com/YouToco/llm-relay-audit
---

# 中转供应商接入检测规范（视频 + 文本线路）

目标：判断「这家卖的和官方一样吗、值不值得接」，给用户证据；**接不接由用户定**（例外：规则 16 一票否决的直接判不接）。
流程：立项 → 免费探针 → 报价 → 付费最小矩阵 → 核验（成片 / 判真伪 / 逐字段对照）→ 填 `findings.json` → 生成器出两份报告 → 收尾。
视频细则 `references/video-checks.md`，文本细则 `references/text-checks.md`，报告字段 `references/report-template.md`，填好的样例 `assets/examples/`。
本文件里的路径都相对本 skill 目录（`SKILL.md` 所在目录）；运行脚本时写全路径，任务产出放在用户自己的工作目录，不要写进 skill 目录。

## 规则（编号固定供引用，按阶段排）

**立项**
- **规则 2 官方基准**：只用官方文档 + 已有的官方实测记录；要新花官方 key 的钱先问用户。官方 key 若还用于其他业务，只小并发、不写进任何报告。
  **「付费」按会不会扣费判，不按请求大小判**：补全、出片、云平台同写法重测都算；`max_tokens: 0` / 超大 max_tokens 在部分厂商照常扣费（`kimi-k3.md`），拿不准就当付费。供应商给的「官方账号」是被测对象，不当基准。
- **规则 10 基准缺或过时就现测**：要官方基准（`count_tokens`、`/v1/models`、价目）时 `references/` 没有、或离 `Last verified` 太久，就用官方 key 现取并写回 `references/<厂商>.md` 或任务目录，别在报告里留「无基准」。**免费官方调用（count_tokens、/v1/models、价目接口）直接测不用问**；花钱的按规则 2。
- **规则 4 key 不入库**：脚本只从环境变量读 key；含 key 的版本只在用户要求时做，文件名带 `secret` 并加进 `.gitignore`，只留本机。

**免费探针**
- **规则 5 只让被测项非法**：保险放在更靠后才查的字段；读代码 / 文档确认对方不会补默认值（wan3 不填分辨率 = 默认 1080P，会真出片）；探针非法值要对所有模型都非法。每个付费或疑似付费的动作前后各读一次已用额度。
- **规则 9 503 / 429 至少再测 2 遍**：同一 (分组, 模型) 共 3 次，**按 body 的 `error.code` 分两类**：`model_not_found`「No available channel for model X under group Y」= 配置没挂（永久，报错常漏内部组名）；`unknown_error` / `get_channel_failed` /「上游暂时不可用」= 偶发、常能恢复。**状态码不可信**（没渠道有的报 503 有的报 429，上游挂了 502 也会报 503）。报告里「偶发已恢复」和「配置缺」分开写。
- **规则 11 管理后台不代输密码**：要看号池 / 倍率请用户自己在浏览器登录，agent 只读调 GET（接口见 `sub2api.md`），**只取非凭证字段**（类型 / 状态 / 报错 / 分组 / 并发 / 限流原因 / 倍率），token、邮箱、uuid 不读不记，不点任何改动按钮，用完关标签页。

**付费**
- **规则 1 先报价后花钱**：写清每单多少、共几单、上限，等用户点头。**每个档位都实测，不线性外推；价目表标了的也要测**（见过标了 2K、先扣钱再回「只支持 768P 以下」退款；见过低档便宜、1080P 接近官方价，线性外推低估数倍）。没测过的档按最坏 8 倍估，从最便宜档逐档往上，看实扣再决定下一档。
- **规则 7 Seedance 必测样片 draft**：卖 Seedance 2.5（官方只有 2.5 支持样片）就在免费探针 + 付费矩阵都带样片，报价单列「样片 480p + 正式片 1080p」；没测成也写原因。清单见 `references/seedance.md`「样片 draft 必测清单」。
- **规则 8 只测最新一代**：付费单先花在这家卖的最新版本上（文本测最新旗舰、生图 / 视频测最新版），免费探针确认更新的版本真不在、报告写明「没有 X」。旧版本只做免费探针，除非用户点名。
- **规则 13 原始请求响应全部落 jsonl**：免费、付费、官方对照的每个请求都经 `probe_lib.call()` 记进 `artifacts/*.jsonl`（key 打码），不用不落盘的 curl / 临时脚本；报告和附录只从 jsonl（或由 jsonl 生成的 artifacts 文件）引用，不手抄。

**核验**
- **规则 12「一致」要程序比出来**：写「字段完全一致 / body 结构一样」前，先把两边 key 集合（顶层、usage、响应头、SSE 事件名）程序求差集——凭眼看很容易漏掉供应商多出来的 `input_transformations` / `context_management` 之类字段。
- **规则 15 视频线路必查三件事**：① 成片是不是官方原片（C2PA / 编码器 / 桶）；② 支不支持样片 draft（规则 7）；③ 返回的链接和参数是官方的还是包装过的——官方成片链接、任务号、清晰度、时长、用量**值还在、只是换了字段名可以接受**，**全被封装（换成自己的链接 / 句柄、没有这些字段）就没法按官方接入**。③ 填 findings 的 `passthrough`（生成器必查 5 个核心字段，全丢时内部卡不许写主线 / 备用）。
- **规则 16 Seedance 一票否决：拿不到官方原链接或不是原片，就接不了**：两条都要过——① 返回的成片链接是**火山方舟 / BytePlus 官方桶的原始直链**（桶名逐字比，见 `seedance.md`；换了字段名可以，转存到自己的桶 / 点播 / CDN 不行）；② 文件是**官方原片**（C2PA 有效且哈希匹配）。任一不过 → `internal.decision` 写「不接」（生成器强制），也**不再加测**：第一单出片就查这两条，不过就停。只有这两条过了，规则 15 ②③ 和价格才有意义。（这是一条偏严的默认策略；你的业务能接受转存，就改生成器里这段校验。）
- **规则 6 结论后置于证据**；推断标明是推断。

**报告**
- **规则 3 报告拆内外两份**，都由 `scripts/build_report.py` 从 `findings.json` 生成：
  - **外发证据版**（PDF，可给商务 / 供应商）：只写「这家 vs 官方」两方，不出现其他第三方供应商、不写接不接建议；声称 vs 实测、真伪证据、差异清单（按是否影响客户分级）、要对方修什么，附录原始请求响应并排。
  - **内部决策卡**（一页 A4，只给决策人）：一句话判定 + 建议（主线 / 备用 / 先修后接 / 不接 / 待定）+ **和你现有的同模型线路比**（成本、近 30 天成功率，没有就写说明）+ 网关接入三档 + 要问商务的事。
  - 稳定性 / 容量**不实测**（接了再看线上监控），报告里也不写「待测」。
- **规则 14 官方放在旁边**：附录每段原始请求 / 响应都要有官方一侧（官方实测 jsonl 优先，没有就放官方文档示例并标 `source: 文档示例`，都没有写 `official.note` 原因）；生成器自动排：两侧每行 ≤ 66 字符、不超过一页就左右并排，否则上下排（官方在上）。

## 流程

0. **立项**：建任务目录（如 `audits/<YYYY-MM-DD>-<供应商>-<模型>/`，里面 `artifacts/` 放 jsonl 和产出）；key / 地址放环境变量；读 `references/<厂商>.md`。
1. **免费探针**（0 元，全用 `scripts/probe_lib.py` 记 jsonl）：官方原生路径在不在（回网页 HTML = 没实现官方协议）；身份与版本（响应头）、`/v1/models`、价目、提交 / 查询路由、鉴权、错误矩阵（非法参数 / 缺头 / 错 key / 不存在的模型 / 不存在的任务）。
   必看 `references/probing-tips.md`：先确认没被 CDN 按 UA 拦（1010）、原因被抹掉就读供应商日志、**`billing/usage` 不可信，实扣只看日志**、每档确认实际落的计价档位。
2. **报价 → 付费最小矩阵**（规则 1 / 7 / 8）：视频按 `video-checks.md`；文本按厂商 reference 的检测矩阵，判真伪的请求要和官方逐个可比。
3. **核验**：视频 → 成片核验（C2PA → ComfyUI → 编码器 / 规格 → 链接域名 → 眼看，`video-checks.md`）；文本 → 判真伪四项（id 前缀、token 逐个比、换模型、注入，`text-checks.md`）。
4. **逐字段对照官方**：**基准 = 所卖模型名对应厂商的官方文档**；某能力失败时，背后是云平台就先用该平台写法复测，平台官方也失败才算平台不支持（`text-checks.md`）。三段完整请求响应并排、字段差异、错误矩阵两边同一批输入；文本加「文档 / 官方实测 / 供应商」三列表。
5. **成本**：每档供应商价 ÷ 官方价、计费时点、币种汇率；网关能不能接逐条对 `references/<厂商>.md`「接入网关要求」，归入三档（不改代码 / 网关要改 / 要对方补）。
6. **出报告**：`python3 -I scripts/build_report.py --init video|text <任务>/findings.json` 出骨架 → 填（原始记录用 `{"jsonl","label"}` 引用，不手抄）→ `python3 -I scripts/build_report.py <任务>/findings.json --pdf`。校验会挡缺必填项 / 真伪必查项、外发版漏内部线路名、像 key 的串。**发之前看生成器出的换页拼图**（每个换页处上下各一条，只看整页缩略图会漏割裂）。测的是官方本身（如官方新开的业务区）也照出，对照已有官方基准。
7. **收尾**：把这次新测到的官方事实写回 `references/<厂商>.md`（标日期和出处）；任务目录留 jsonl、findings.json 和两份产出。

## 脚本（scripts/）

| 脚本 | 用途 |
|---|---|
| `build_report.py` | **统一报告生成器**：`findings.json` → `artifacts/report.html`（外发）+ `internal-card.html`（内部）；`--pdf` 出 PDF + 换页拼图；`--check` 只校验；`--init` 出骨架 |
| `check_pages.py` | PDF 每个换页处上下各截一条拼图（`build_report.py --pdf` 自动调） |
| `probe_lib.py` | `call()` 带 jsonl 日志（key 打码）、`used()` 读已用额度、`vendor_log()` 读 new-api 系供应商日志、`poll_task()` 轮询 |
| `analyze_videos.py` / `contact_sheet.py` / `c2pa_check.py` / `extract_comfy.py` | 成片规格与编码器 / 首中尾帧 / C2PA 凭证 / ComfyUI 工作流（用法见 `video-checks.md`） |
| `html_to_pdf.sh` / `report_style.html` | Chrome 无头转 A4 PDF / 报告样式（生成器自动用） |

`assets/examples/{text,video}/` 是虚构的完整样例（findings.json + 原始 jsonl），`--pdf` 跑一遍就能看到两份产出长什么样。

## 各厂商基准（references/）

| 文件 | 内容 |
|---|---|
| `report-template.md` | findings.json 字段、两份报告、写法、转 PDF |
| `probing-tips.md` · `video-checks.md` · `text-checks.md` | 免费探针 / 视频付费矩阵与成片核验 / 文本判真伪、对照文档、云平台补测 |
| `ali-wan.md` · `minimax-h3.md` · `seedance.md` | 视频：阿里百炼 wan3、MiniMax H3、火山方舟 / BytePlus Seedance（官方接口、价格、成片指纹、样片、接入要求） |
| `claude.md` · `grok-xai.md` · `gemini.md` | 文本：Claude（一方 / Bedrock / 经 OpenAI 格式转换）、Grok、Gemini |
| `kimi-k3.md` · `glm.md` · `deepseek.md` | 文本：Kimi、智谱 GLM、DeepSeek（计数接口、指纹、价目、哪些判真伪招数有效） |
| `new-api.md` · `sub2api.md` | 中转形态：new-api / one-api 多分组、倍率、参数透传、日志对账；订阅号池识别、后台只读 |

**新增一个厂商**：照 `ali-wan.md` 的小节写 `references/<厂商>.md`（官方接口与响应、价目、实测行为、成片规格 / token 口径、接入网关要求），每个事实标日期和出处；再在上表加一行。
