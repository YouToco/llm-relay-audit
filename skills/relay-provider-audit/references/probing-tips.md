# 免费探针细则（视频 + 文本通用）

> SKILL.md 流程第 1 步的细节。请求全部用 `scripts/probe_lib.py` 记 jsonl（key 打码），报告里用 `{"jsonl","label"}` 直接引用。

**`probe_lib` 速查**（`python3 probe_lib.py` 打印完整用法）：
- 环境变量：`K` 供应商 key（空或太短直接报错）、`B` 地址、`LOG` 日志（默认 `artifacts/probes.jsonl`）、`AUTH` 鉴权写法；官方侧 `OK` / `OB` / `OLOG`（默认 `artifacts/official.jsonl`）/ `OAUTH`。
- `call(method, path, body, label=…, auth=…, side=…)`：`auth` = `"bearer"`（默认）/ `"raw"`（new-api 访问令牌，不加 Bearer）/ `"x-api-key"` / `"x-goog-api-key"` / `"api-key"`（Azure）/ `None`；`side="official"` 走官方 key、地址和日志；也可 `Client(base, key, log, auth=…)` 自建一侧。
- 安全：key 只发给本侧地址（显式传 `key=` 才例外），跨域跳转会去掉鉴权头；`register_secret(s)` 把新出现的密钥（如刚建的 key）也加进打码；全部响应头都留、其中的密钥打码。
- 重试：POST / PUT / PATCH / DELETE 一旦可能已到服务器就**不再重发**（防重复扣费）；每次尝试都落盘（失败的记 `status: null` + `error` + `phase`）。
- `call_stream(…)` 返回 `(status, events, headers)`，SSE 原文写 `<LOG 目录>/<label>.sse`，jsonl 记 `ttfb_ms` / `first_event_ms` / `first_content_ms` / `event_seq`（判假流式、配对测流式与非流式）。
- `spent(since_ts, pages)`：汇总某时刻后的 type 2 日志 `quota / 500000` = 美元实扣——付费动作前后对账用这个；`used()`（`billing/usage`）只作参考。
- `vendor_log(pages, page_size, key_param=False)`：读供应商日志原文（type 2 / 5 / 7、`content`、`other.*`）；默认 key 放头里，`key_param=True` 才用 `?key=` 写法（会把 key 写进 URL，尽量别用）。
- `poll_task(status_path=…, preset="dashscope|ark|minimax")`：按厂商形状轮询视频任务到终态；两个都不给时自动试常见路径。
- 默认 UA 仿 Anthropic SDK：Cloudflare 会按 UA 拦 Python-urllib（1010）。

- **官方原生路径在不在**：不在会返回网页 HTML，说明供应商没实现官方协议。再看站点身份与版本（响应头 `Server`、`X-New-Api-Version`）、`/v1/models`、价目、提交 / 查询路由、鉴权、错误行为矩阵（非法参数 / 缺头 / 错 key / 不存在的模型 / 不存在的任务）。
- **先确认请求没被 CDN 拦**：返回 403 纯文本「error code: 1010」= Cloudflare 按 UA 拦（Python-urllib 会被拦），`probe_lib.py` 已默认带 UA（环境变量 `UA` 可覆盖）；顺手跑一个 UA 矩阵（空 / requests / httpx / Anthropic SDK / curl / Go）记进报告，接网关时要知道。
- **响应把原因抹掉时，去供应商自己的日志里读**：new-api 系 `GET /api/log/token`，头 `Authorization: Bearer <sk>`（免费；别用 `?key=<sk>` 查询参数写法，key 会进 URL 和各层日志；type 2 = 成功扣费，type 5 = 被拒请求，`content` 里是被抹掉的真实原因，`other.channel_name` 常露出上游渠道名，见 `new-api.md`）；视频任务详情 `GET /v1/video/generations/{id}` 常带出后端原始任务和失败原因（有的站的 `/v1/videos/{id}` 只给 `status`）。
- **`/v1/dashboard/billing/usage` 不可信**（见过一单 $0.29 读成 200 美分），实扣优先看供应商日志的 `quota`（new-api 系 500000 = $1，`spent()`），其次测试 key 的已用额度；billing/usage 只作参考（规则 5）。
- **价目表与实扣可能不一致**：日志 `other` 里的 `param_resolution_*`（实际落的计价档位）和 `settlement_mode` 要看，每个档位都要确认实际落的档位对不对（见 `video-checks.md`「成本」）。
- **探针保险**（规则 5）：非法值要对所有模型都非法（Seedance `duration:1` 对全系非法，但 16 秒对 2.5 合法，拿它当保险会真出片）；`max_tokens: 0` 在 Kimi 官方被当成不限、照常扣费，别当保险；超大 `max_tokens` 的 400 只在直连官方 Claude 时免费，经中转先发一次查 `quota`（规则 2）。
- **保险字段先确认会传到上游**：有的 new-api 版本的 `/v1/video/generations` 会**静默丢掉顶层 `duration`**（要放 `metadata.duration`），`duration:1` 保险失效、按上游默认 10 秒真出片。视频探针优先走供应商的官方原生路径；只能走 new-api 格式时先用 `metadata.duration:1` 试，或第一单只提交一个、立刻查状态，`in_progress` 就说明保险没生效。
- **网关会「钳制」越界值时 `duration:1` 保险也失效**（有的文档写「越界值自动映射 / 钳制 / 不传上游，不报错」）：先读文档有没有这类话；保险改用网关自己同步校验的项（如参考图数量超上限、缺 content、不存在的模型），先单独打一次确认是同步 400 再用。
- **并发只当协议检查**（规则 3）：5 / 10 路并发看 429 外壳、`retry-after`、排队还是拒绝、首字是否被拖慢；不写容量 / 稳定性结论。
- **别发真实数据、越权即停**（规则 17）：探针只用自造文本和文档示例素材；列表 / 素材 / 任务接口露出别人的数据，只记「能看到」和条数，不读内容。
- **成功响应头漏出 `X-New-Api-Version` 或 new-api 格式的 `X-Request-Id`**：说明后面还套着一层 new-api，不是直连官方。
- **请求体大小上限免费测**：模型名故意写错（应用层回 `model_not_found`、不扣费），把请求体填充到 1 / 10 / 30 / 45 / 60 MB 用 curl 发，看哪档开始回 nginx 413，再二分到字节（见过上限正好 52,428,800 = 50 MiB）。视频 / 图片 base64 内嵌会膨胀 4/3，对方说「支持 50M」常指请求体。用 curl 不用 urllib：上传中被断时 urllib 只抛 SSLEOF，还会被当连接失败重试。

## 公网测试素材（2026-10-29 核过：HEAD 200、分段下载 206、ffprobe 能读）

测「公网 URL 传视频」和「大文件上限」时直接用；用前 `curl -sIL` 看一眼还在不在。archive.org 的链接会 302 跳一次到 `dn*.ca.archive.org`（节点名会变，传给上游要用原链接），偶尔回 500，重试即可。

| 大小 | 内容 | 链接 |
|---|---|---|
| 59.0 MiB（61,878,609 B） | Big Buck Bunny 640×360 H.264+AAC 9:56 | `https://archive.org/download/BigBuckBunny_124/Content/big_buck_bunny_720p_surround.mp4` |
| 64.7 MiB（67,801,890 B） | Elephants Dream 640×360 H.264+AAC 10:54 | `https://archive.org/download/ElephantsDream/ed_hd.mp4` |
| 44.9 MiB（47,065,346 B） | Elephants Dream 低码率 | `https://archive.org/download/ElephantsDream/ed_1024_512kb.mp4` |
| 41.3 MiB（43,315,070 B） | Big Buck Bunny 低码率 | `https://archive.org/download/BigBuckBunny_328/BigBuckBunny_512kb.mp4` |
| 29.3 MiB（30,704,510 B） | Big Buck Bunny 1080p 10 秒（同站还有 1 / 2 / 5 / 10 / 20MB 档，改文件名末尾） | `https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/1080/Big_Buck_Bunny_1080_10s_30MB.mp4` |

- 已失效（别再试）：`download.blender.org/peach/bigbuckbunny_movies/*.mp4`（只剩 .zip）、`commondatastorage.googleapis.com/gtv-videos-bucket/*`（403）。
- 有的官方接口不收公网视频 URL（如 Kimi K3 只收 base64，见 `kimi-k3.md`），这类先用小片 base64 测，公网 URL 只用来看中转会不会代下载。
- 图片素材：火山文档示例图 `https://ark-project.tos-cn-beijing.volces.com/doc_image/seepro_i2v.png`（1920×1088、无真人，国内可直连）。
- 要精确卡请求体大小、画面带可核对暗号的测试片，自己生成更好：固定时长分辨率、只靠码率撑体积（ffmpeg 加噪点），在 mp4 末尾补合法 `free` 盒子补齐到字节。
