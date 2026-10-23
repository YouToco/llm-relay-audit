# 对照报告：findings.json + 统一生成器

> 所有接入测试报告都由 `scripts/build_report.py` 从 `findings.json` 生成，不要每个任务手写报告脚本（版式会反复出问题）。
> 样例（虚构数据，随 skill 一起安装）：视频 `assets/examples/video/findings.json`，文本 `assets/examples/text/findings.json`（原始记录在各自的 `artifacts/`）。照着填比读字段表快。

## 用法

```bash
G=<skill 目录>/scripts/build_report.py
python3 -I $G --init video <任务目录>/findings.json      # 骨架；text 同理（真伪证据按类型预填必查项）
python3 -I $G <任务目录>/findings.json --check            # 只校验
python3 -I $G <任务目录>/findings.json --pdf              # artifacts/report.html + internal-card.html + 外发 PDF + 内部卡 PDF（一页）+ 临时目录里的换页拼图
python3 -I $G <任务目录>/findings.json --pdf --external-only   # 只出外发版（同 meta.mode = "external"）
python3 -I $G <任务目录>/findings.json --scan             # 扫任务目录（含子目录）下所有 *.jsonl / *.sse 有没有像 key 的串，命中退出码 1
python3 -I $G -h                                          # 帮助
```

- 参数顺序随意；findings 路径也可以给目录。生成器只用标准库；路径都相对 findings.json 所在目录，引用的 jsonl / json / file / 图片必须存在。
- 默认构建、`--check`、`--pdf` 都会顺带跑同样的扫描，命中只警告（单独 `--scan` 才以退出码挡）。
- `--pdf` 找浏览器的顺序：`$CHROME` → `google-chrome` → `google-chrome-stable` → `chromium` → `chromium-browser` → macOS `/Applications`、`~/Applications` 下的 Chrome / Chromium；都没有就给出安装提示退出，HTML 保留。换页拼图要 `uv`（或本机已装 pymupdf + pillow），输出到新建的临时目录。
- 默认文件名：`<supplier>-对照报告.pdf` / `<supplier>-内部决策卡.pdf`；`meta.lang: "en"` 时 `<supplier>-audit-report.pdf` / `<supplier>-decision-card.pdf`；`meta.mode: "external"` 不出决策卡。
**发 PDF 前把拼图逐个看完**（每个换页处上一页底 + 下一页顶），只看整页缩略图会漏割裂。

## 两份产出（SKILL.md 规则 3）

| | 外发证据版（`report.html` → `pdf_name`） | 内部决策卡（`internal-card.html` → `card_pdf_name`，默认见上，一页 A4） |
|---|---|---|
| 给谁 | 商务 / 供应商 | 只给决策人，不外发 |
| 写什么 | 只有「供应商 vs 官方」两方；不写建议、不提别家 | 判定 + 建议 + 和现有同模型线路比 + 网关三档 + 要问商务 + 风险 |
| 版式 | 第 1 页：一句话 + ≤4 张结论卡 + 声称 vs 实测 + 要对方处理的事；正文：怎么测的 → 真伪证据 → 差异（按影响分级）→ 参数与报错 → 自定义节 → 成本倍率；附录（另起一页）：原始请求响应并排 | 判定大标签 + 理由 → 线路对比表 → 左「声称 vs 实测」右「网关 / 商务 / 风险 / 下一步」 |

两份都不写稳定性 / 容量（不实测）。生成器会挡：外发版里出现 `internal.existing_lines` 的线路名 / 供应商名或 `internal.redact_terms`（如上游渠道名、别家供应商、对方客户名）——不分大小写、在反转义后的文本上查、去掉 `**` / 反引号后照样命中，也查 alt / title 属性、`pdf_name`、`short_title`；任何一份里出现像 key 的串（`sk-` 系、`xai-`、JWT、GLM 的 `hex.secret`、带标签的 UUID、`x-api-key` / `?key=`、小写 `bearer`、`ghp_` / `github_pat_`、`hf_`、`gsk_`、`r8_`、`ya29.`、AWS secret、`*_live_` 等）。

## findings.json 字段

文字支持 `` `代码` ``、`**加粗**`、换行；不收 HTML。表格单元格可写 `{"tag":"good|warn|bad","label":"一致","text":"…"}`（`tag` 只能是这三个，别的值校验报错）；引用原始记录写 `{"jsonl":"artifacts/x.jsonl","label":"…"}`（报错矩阵显示「状态码 错误码 · 文案」，去掉 request id，不手抄）。同一 label 有多条时加 `"nth": N` 取第 N 条（0 起）；`"max": N` 控制单元格里引用文字的最长字符数（默认 220）；附录里的 `{"file","head","tail"}` 不给 `head` 或分块不够时，按 `max` 截前 N 个字符（默认 3000）。

| 字段 | 必填 | 内容 |
|---|---|---|
| `meta` | 是 | `title` `supplier` `official` `model` `kind`(video / text) `date`；可选 `short_title` `subtitle` `scope` `pdf_name` `card_pdf_name`（内部卡 PDF 文件名）`keep_headers`（附录保留的响应头）`out_dir`（产出目录，默认 `artifacts`，相对 findings.json）`lang`（`"zh"` 默认 / `"en"`：报告界面文字和默认文件名用英文，正文仍是你填的内容）`mode`（`"full"` 默认 / `"external"`：只出外发版，`internal` 和 `gateway` 变成可选、不出决策卡，等同 `--external-only`）`rule16`（Seedance 一票否决校验，SKILL.md 规则 16：`kind` 为 video 且 `model` / `official` 提到 seedance、方舟、Ark / ModelArk、BytePlus、火山引擎、volcengine 时自动启用；`true` 对任何 kind 强制启用。启用后要求 `c2pa` 和 `bucket` 都实测（不许 skipped）且为 good、`video_url` 为 `same` 或 `renamed`，否则 `decision` 只能是不接 / `reject`；`mode: external` 且没有 `internal` 时只警告） |
| `summary` | 是 | 一句话判定，**客观、外发可用**（不写建议） |
| `claims[]` | 是 | 供应商声称 vs 实测：`item` `claimed` `measured` `verdict`(good / warn / bad) `label` |
| `verdicts[]` | 是 | 第 1 页结论卡 ≤ 4 张：`area` `verdict` `label` `text`（视频常用 成片 / 接口 / 成本 / 样片；文本 后端 / 模型 / 质量 / 成本） |
| `asks[]` | 是 | 要对方修 / 答复的事：`item` `why`；没有写 `[]`。`gateway` 里 `vendor` 档的条目会自动并进来（标 `internal_only` 的不并） |
| `method` | 否 | 怎么测的：`kv` = [[标题, 内容]…]，`note` 写基准是什么、没做的项 |
| `authenticity` | 是 | 真伪证据 `evidence[]`：`id` `check` `official` `supplier` `verdict` `label`。**必查 id**：视频 `c2pa` `encoder` `bucket`；文本 `id_prefix` `token_count` `model_swap` `injection`；没测在 `skipped` 写 `{id: 原因}`。可加别的行（如 `usage`、`stack`） |
| `passthrough` | 视频必填 | 参数透传（规则 15）：`rows[]` = `id` `field` `official` `supplier` `status`（`same` 原样 / `renamed` 改名保留 / `lost` 丢失 / `rehosted` 链接指向供应商自己的存储——**按丢失算**（英文版标签 Rehosted；外发版默认引言会写「转存到自家存储算丢失」） / `fake` 非官方值）`note`；必查 id：`video_url` `task_id` `resolution` `duration` `usage`，可加别的行（`draft`、其余字段）。外发版单独一节，标「透传完整 / N 项没透传 / 全被封装」 |
| `diffs[]` | 是 | 和官方的差异：`item` `official` `supplier` `impact`（`customer` 影响客户 / `integration` 影响接入 / `none` 不影响使用）`note` |
| `errors` | 否 | 参数与报错矩阵：`rows[]` = `input` `official` `supplier` `verdict` `label`，两边同一批输入 |
| `sections[]` | 否 | 自定义节（样片 draft、成片规格、画质、思考深度、传参、文档三列对照、非功能项…）：`title` `intro` `bars{title, items[{label,value,hot,text}]}`（`bars.title` 图标题；`value` 只能是数字或 null；`items[].text` 替代数值显示的文字）`table{head,rows,cols,num}`（`rows` 是行的列表）`image{path,caption,alt}`（png / jpg / jpeg / webp / gif / svg，文件必须存在；`alt` 图片替代文字）`bullets` `note` `keep` |
| `cost` | 是 | `unit` `intro` `tiers[]` = `tier` `official` `supplier`（同单位数字或 null，文字放 `*_text`）`official_text` `supplier_text` `ratio`（= 供应商 ÷ 官方，写小数，0.8 = 官方价的 80%；不填时自动算，填了和两个数对不上会警告）`basis` `tested`（缺或 false 都会警告，规则 1）；`chart` false 关掉横条图 |
| `gateway` | 是（`mode: external` 时可选） | `items[]` = `item` `tier`（`ready` 不改代码 / `gateway` 网关要改 / `vendor` 要对方补）`detail`；`note` 卡片脚注；只进内部卡 |
| `exchanges[]` | 是（至少 1 条，每条要有 `title`） | 附录原文：`title` `note` `official` `supplier`；**官方一侧必填**（官方实测 jsonl > 官方文档示例 + `source:"文档示例"` > `{"note": 没有的原因}`），`source` 写在表头；左右 / 上下由生成器按宽度自动排；每侧 `{"jsonl","label","host"}` 或 `{"request": 文本或对象, "response": 文本 / 对象 / {"json","path"} / {"file","head","tail"}}`（SSE 原文按空行分块取头尾） |
| `internal` | 是（`mode: external` 时可选） | `decision`（主线 / 备用 / 先修后接 / 不接 / 待定；也收英文别名 `primary` / `backup` / `fix-first` / `reject` / `pending`）`reason` `this_line{cost,success_30d,volume_30d,note}`（本线路在对比表里的那一行；没接入时 `success_30d` 默认显示「未接入」）`existing_lines[]`（`line` `supplier` `cost` `success_30d` `volume_30d` `note`；真没有写 `[]` + `existing_note`）`ask_business[]` `risks[]` `next[]` `redact_terms[]` |

`existing_lines` 填你自己现有的同模型线路（成本比例、30 天成功率与量），数据从你的网关 / 监控导出，在 `existing_note` 写快照日期。

## 写法（生成器管不到的，要自己守）

- **数字都有出处**：实扣用供应商日志，耗时用时间戳，规格用 ffmpeg；推断标明是推断（「成片同源」的依据是编码器和标签一致，不是直接证明）。
- **完整请求与响应必须有**：生图 / 文本也要左官方右供应商并排、错误行为两边同一批输入实测；官方 key 没余额也要现测免费错误路径；成功响应拿不到实测就用官方文档字段并标「文档字段」。
- **文本线路**加一张「文档 / 官方实测 / 供应商」三列逐字段表（放 `sections`），文档当天取、摘要存 `artifacts/official-docs-<日期>.json`（`text-checks.md`）。「一致」先程序求差集（规则 12）。
- 只写「供应商 vs 官方」两方：别家供应商、上游渠道名、对方的客户只进 `internal`，并列进 `redact_terms`。
- 正文出现过的数据不在附录再贴；附录只放能证明结论的几对原文。图表只画一个量，供应商强调色、官方中性灰。
- 每节一张表 + 一两句大白话，重复行删掉。`sections` 里大节别加 `keep`（整节挪页会留半页空白），只给一屏内的小节加。

## 版式与打印（生成器已内置，改样式只改 `scripts/report_style.html` 和生成器）

- 判断标签放每行第一列（项目名上面），不单独占最右列（窄列会把标签挤成竖排）；表格 `table-layout:fixed` + 列宽。
- 打印不许割裂：表格跨页续表头、单行不断开；单张卡 / 柱状图 / 图 / 正文短代码块不断开（折行超约 58 行的才跨页，`class="long"`）；并排短代码块打印改 `inline-block`；附录另起一页。
- 也不许大片留白：打印走块流，大表在行间换页、卡片组在卡片行间换页，不整块挪；标题 + 引言粘住下一块的第一行，段尾 `note` 只粘上一块；图打印撑满正文宽、高随比例（高过一页才按页高缩）；表格换页时首末行各粘住相邻一行（不留孤行），引言段不拆；附录代码块可跨页（小标题粘住开头 4 行）。
- 内部卡 PDF 必须一页：页边距 8mm，放不下生成器从 zoom 1 逐级缩到 0.6 取第一个一页的（写回 `internal-card.html`）；缩到底还两页就删 `internal` 条目。
- 附录：key 打码、只留 `keep_headers` 里的响应头、base64 / 长文本 / 签名链接截断、紧凑 JSON（放得下一行的对象写一行）。
- PDF 一律本机 Chrome 无头转（`html_to_pdf.sh <html> <pdf> [lang]`，第 3 个参数可选）；字体只用本机字体，不联网。
- 附录打码：请求头 `authorization` / `x-api-key` / `api-key` / `x-goog-api-key` / `cookie` / `set-cookie` / `proxy-authorization` / `x-auth-token` 一律写成 `***`；URL 参数 `key=` / `api_key=` / `apikey=` / `api-key=` / `access_token=` / `token=` 的值打码。

## 含 key 的版本

只在用户要求时做：输出文件名带 `secret`（如 `…-secret.pdf`），确认被 `.gitignore` 忽略；生成器的 key 检查会拦含 key 的公开版，含 key 版另写脚本、别往 findings.json 里放 key。curl 里的 JSON 用多行缩进，PDF 里复制才不断行。
