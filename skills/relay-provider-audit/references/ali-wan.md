# 阿里百炼 wan3.0 官方基准

> Last verified: 2026-10-12；价格与行为以官方文档为准。

来源：官方 [API 参考](https://help.aliyun.com/zh/model-studio/wan3-video-generation-api-reference)、
[使用指南](https://help.aliyun.com/zh/model-studio/wan3-video-generation-guide)，加上 2026-10-05 用官方 key 直连的实测（约 100 条原始请求、8 条官方成片）。
对照中转时，官方侧优先用已有的官方实测记录，要新出官方单先报价（SKILL.md「规则 2」）。官方 key 不写进任何报告。
官方实测已超过 14 天：复用前先对官方重跑一遍免费探针（参数错误只建任务、约 0.1 秒后 `FAILED`、不收费），报错原文和外壳对得上再沿用下面的结论；要核成片规格再出一单 480P 2 秒（先报价）。

## 官方接口与响应

- 提交：`POST {base}/api/v1/services/aigc/video-generation/video-synthesis`，头 `X-DashScope-Async: enable`、`Authorization: Bearer <key>`。
- 查询：`GET {base}/api/v1/tasks/{task_id}`，建议 15 秒一查；task_id 和 `video_url` 只保留 **24 小时**，过期状态 `UNKNOWN`；查询 RPS 20。
- `{base}`：百炼业务空间专属域名 `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com`（北京）/ `https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com`（新加坡）；2026-10-23 读文档时还列了日本（东京）`ap-northeast-1`。key 和地域要匹配。
  - 旧的通用域名 `https://dashscope.aliyuncs.com`（同样的 `/api/v1/…` 路径）现行文档已不写，但实测仍可用（实测观察，未见文档）；中转多半模仿的是旧域名的路径和响应，对照时两种 base 都算官方写法。
- 模型 `wan3.0-video` / `wan3.0-video-prime`（All-in-One，按 `input.media[].type` 自动路由：文生 / 首帧 / 首尾帧 / 参考图 / 参考视频 / 参考音频 / 文件 / 链接 / 编辑 / 延长）。
- `parameters`：
  - `resolution` 480P / 720P / **1080P（默认）**；`ratio` adaptive（默认）/ 21:9 / 16:9 / 4:3 / 1:1 / 3:4 / 9:16；
  - `duration` 2–30 整数或 -1（默认 5；有视频输入时输入 + 输出 ≤ 30）；`audio` 默认 true；`seed`；`prompt_extend`；`watermark`。
  - **不填分辨率 = 1080P 真出片**，做探针别靠「缺分辨率」当保险（规则 5）。
- 提交响应：`{"output":{"task_id":"<UUID>","task_status":"PENDING"},"request_id":"<UUID>"}`。
- 运行中：`output` 带 `submit_time` / `scheduled_time`（UTC+8，`YYYY-MM-DD HH:mm:ss.SSS`）。
- 成功：`output` 再加 `end_time`、`orig_prompt`、`video_url`（阿里 OSS 签名链接）；顶层 `usage`：
  `video_count`、`duration`（浮点，输入 + 输出）、`input_video_duration`、`output_video_duration`、`fps`（30）、`SR`（裸数字 480 / 720 / 1080）、
  `ratio`（如 `16:9`；adaptive 时可能是 `1632:937` 这类原始比例）。
- 失败：`output.task_status = FAILED` + `output.code` / `output.message`。

## 价目（官方标价，2026-10 读；计费秒数 = 输入视频 + 输出视频，失败不收；以官方页为准）

| | 480P | 720P | 1080P | 备注 |
|---|---|---|---|---|
| 北京（¥ / 秒） | 0.3 | 0.6 | 1.2 | 价目页曾标「限时 7 折」，期限页面看不出，实付看账单 |
| 新加坡（$ / 秒） | 0.05 | 0.10 | 0.20 | |
| prime 北京（¥ / 秒） | 0.45 | 0.9 | 1.8 | 无折扣 |
| prime 新加坡（$ / 秒） | 0.068 | 0.14 | 0.28 | |

- 档位倍率 **480 : 720 : 1080 = 1 : 2 : 4**（prime 新加坡 0.068 / 0.14 / 0.28 不是严格 1 : 2 : 4，看起来是标价取整，按 1 : 2 : 4 判时留几个百分点余量）。中转的价格曲线明显偏离这个倍率就是异常信号（见下「中转常见问题」）。

## 实测行为（官方，2026-10-05；对照表「官方列」用这些）

| 用例 | 官方表现 |
|---|---|
| 非法参数（duration 1 / 31 / 字符串、缺 prompt、非法 media.type、resolution 360P） | **提交仍 200**，约 0.1 秒后任务 `FAILED`（`InvalidParameter`），**不收费**；`duration` 最先校验 |
| 不带 `X-DashScope-Async` | 403 `AccessDenied`「current user api does not support synchronous calls」 |
| 错误 key / 不带 key | 401 `InvalidApiKey` |
| 不存在的模型 | 404 `InvalidParameter`「Model not exist.」 |
| 查不存在的任务 | **200** + `task_status: UNKNOWN` |
| 并发超 5 | 不回 429，第 6 个起排队 `PENDING`（单账号同时约 5 个任务） |
| 21:9 | 支持；字符串 `duration` 被拒 |
| key 限制 | 业务空间 key（`sk-ws-` 前缀）可设模型白名单；没开的模型 403 `Access denied by API-Key restrictions.` |

- 探针保险：`duration` 最先校验，`duration:1` 对所有 wan3 模型非法 → 让被测项非法时用它兜底（规则 5，`probing-tips.md`）。

**官方报错原文**（官方实测 2026-10-05；参数错都是提交 200 + task_id，终态 `output.code: InvalidParameter`）：
- duration 1 / 31 →「duration must be -1 or in [2,30]」（同时有别的错也先报这条）
- resolution 360P →「Input should be '1080P', '720P' or '480P': parameters.resolution」
- ratio 2:1 →「Input should be '21:9', '16:9', '4:3', '1:1', '3:4', '9:16' or 'adaptive': parameters.ratio」
- duration `"2"`（字符串）→「Input should be a valid integer: parameters.duration」（见过中转当数字收下、照样出片收钱）
- media.type foo →「Input should be 'first_frame', 'last_frame', 'reference_image', 'reference_video', 'reference_audio', 'file' or 'link': input.media.0.type」
- prompt、media 都没有 →「prompt and media cannot both be empty」；seed 2147483648 →「seed must be -1 or in [0,2147483647]」
- 两张 first_frame →「at most one first_frame is allowed」；first_frame + reference_image →「first_frame cannot be combined with other media types except last_frame」
- 同步报错（不建任务）：不存在的模型 404「Model not exist.」（错误码页写 `ModelNotFound`，实测 `code` 是 `InvalidParameter`；`content-type: text/plain` 但体是 JSON）；错 key 401「Invalid API-key provided. …」、不带 key 401「No API-key provided.」；批量查任务 `GET /api/v1/tasks` 在限定了模型的 key 上同样 403。
- 查不存在的任务：UUID 形和 `task_abc123` 形都是 200 + `UNKNOWN`（不是 404）。
- 响应头：`server: istio-envoy`、`x-request-id`（= 体里 `request_id`）、`req-cost-time`、`x-envoy-upstream-service-time`；公共域名的响应没有 `x-request-id`。中转响应头和这些对不上，说明中间至少隔了一层。
- `/compatible-mode/v1/models` 不列 wan3 视频模型（只有生图），不能拿它判 key 开没开 wan3；接口**没有余额 / 用量查询**，每单扣多少只能 `usage.duration × 单价` 推算。

**官方各用例的输出**（官方实测 2026-10-05，480P 2 秒为主）：

| 用例 | 成片 | `usage`（duration / 入 / 出 / SR / ratio） |
|---|---|---|
| 文生 adaptive | 854×480 | 2.0 / 0.0 / 2.0 / 480 / `16:9` |
| 9:16 + `audio:false` + `watermark:true` | 480×854，**无音轨**，右下「AI 生成」水印 | 2.0 / 0.0 / 2.0 / 480 / `9:16` |
| 首帧、首尾帧 | 844×484（比例跟首帧；首帧图 = 第 0 帧） | 2.0 / 0.0 / 2.0 / 480 / `1632:937` |
| 参考图 + 参考音频 | 522×784（比例跟参考图） | 2.0 / 0.0 / 2.0 / 480 / `2:3` |
| 参考视频（5 秒素材 + `duration:2`） | 554×738 | **7.0 / 5.0 / 2.0** / 480 / `415:554`（`duration` 参数 = 输出秒数；计费秒 = 入 + 出） |
| 不传 resolution / ratio | **1920×1080** | 2.0 / 0.0 / 2.0 / **1080** / `16:9` |
| `ratio:21:9` | 980×420 | 2.0 / 0.0 / 2.0 / 480 / `21:9`（API 参考列了、北京使用指南没列，实测支持） |

## 成片规格（官方原片指纹，2026-10-05 实测）

- 分辨率：480P 16:9 = 854×480，720P = 1280×720，1080P = 1920×1080；30fps；2 秒片 60 帧、容器时长约 2.02 秒。
- 封装：容器 `Lavf60.16.100`；视频 `libx264 (Lavc60.31.102)` High profile yuv420p，码流 SEI `x264 - core 164 r3108 31e19f9`；音频 AAC-LC 44.1kHz 立体声（`audio` 默认 true）。
- **加水印的成片是另一版编码器**：`watermark:true` 那条是 `x264 - core 164 r3191 4613ac3` + `Lavc61.3.100 libx264`（水印后加、重编码过，文件名带 `_watermark`）→ 中转水印片编码器不同，先看是不是这个原因，别直接判转码。
- **`AIGC` 元数据标签**（AI 生成内容合规标识）：`ContentProducer` = `001191330106MA2CFLDG4R10001`（官方生成方编码），每条有自己的 `ProduceID`，另有 `ReservedCode1/2`（约 302 字符签名）。
- 每像素码率 0.33–0.73（随内容变）；码率 480P 约 4.6–9.1 Mbps、1080P 约 20.7 Mbps。
- **官方原片没有 C2PA**（文件里没有 `jumb` 盒）。
- 成片链接在阿里 OSS：`dashscope-*.oss-*.aliyuncs.com`（签名 URL，24 小时到期）；实测是加速域名 `dashscope-*.oss-accelerate.aliyuncs.com/<2 位>/<2 位>/<YYYYMMDD>/<8 位账号段>/<32 位十六进制>-metadata_….mp4`（文档示例是 `dashscope-result-bj.oss-cn-beijing…`）。同一阿里账号出的片账号段相同，可拿来判两家中转是不是同一个上游账号。
- 耗时：480P 2 秒约 170 秒，1080P 2 秒约 252 秒（同批并发 7 单时）。

## 判真伪要点

- **wan3 官方原片没有 C2PA**：`c2pa_check.py` 报「无 C2PA」对 wan3 不是负面证据；看 `analyze_videos.py` 的 `aigc`（`ContentProducer`）、`encoder` 和 `encoder_sei`（官方 `x264 - core 164`）。
- 编码器 + 容器版本 + `AIGC` 标签（`ContentProducer` 与官方一致、有 `ProduceID` / `ReservedCode`）都对上 → 阿里原片、没被转码。只剩 `Lavf…`、标签缺失或生成方编码不同 → 被重编码或非官方生成。
- 分辨率 / 帧率 / 帧数 / 音轨要和上表一致；频谱分不出原生 480P 和超分 720P，别当证据（`video-checks.md`）。
- 链接域名：官方 OSS 还是中转自己的域名 / CDN（代理换域名本身不算造假，但要记下，并按规则 15 判是否被封装）。
- 是否原样透传：`task_id` / `request_id` 是不是 UUID、状态体有没有 `usage` 和 `submit_time` / `end_time`。

## 接入网关要求

接一家 wan 中转，网关至少需要这些；缺哪条就写进「要对方补」：

1. 状态体有 `usage.output_video_duration`、`usage.input_video_duration`、`usage.SR`：按秒 × 分辨率计费靠它们，没有 `usage` 无法计费对账。
2. 能拿到官方任务号：原样透传官方响应（`output.task_id` 就是官方 UUID）最好；中转改写响应、只给自家句柄时，要另给一个官方号字段（对账、排错、跨线路追单都要）。
3. 「查不到任务」的外壳可识别：官方是 200 + `UNKNOWN`；new-api 系常见 400 `task_not_exist`；别的（如 404）网关要额外识别。
4. 失败任务带 `output.code` / `output.message`；`SUCCEEDED` 但 `video_url` 为空应判失败。
5. 报错不泄露内部信息（计价公式、插件栈、余额、key 片段）。
6. 实测时顺带看 `callback_url` 会不会被拒、`Idempotency-Key` 认不认（接入方网关做回调 / 防重提交时要知道）。

## 中转常见问题（匿名案例）

- **成片是原片但接口被改写**：某中转成片 = 阿里原片（编码器、`AIGC` 标签、规格全对），但状态体无 `usage` / 时间字段、`task_id` 是自家 `task_…` 句柄、非法参数提交即 400 且原因被抹成笼统文案（真实原因只在它的令牌日志 `GET /api/log/token` 里）、查不存在任务回 404 → 网关要求 1、2、3 都不满足。原片 ≠ 能接入。
- **价格曲线不线性**：见过低档远低于官方价、1080P 却接近官方价，按低档线性外推会低估数倍 → 每档都要实测（规则 1）。
- **计价落默认档**：某 new-api 中转按 `metadata.resolution` 取计价档位，原生请求的 `parameters.resolution` 读不到，所有单都落默认档、每单固定价，日志里 `param_resolution_*` 恒为同一档、`settlement_mode = unsettled_missing_tokens`。这是计价缺陷，不是降价，不能当稳定成本（`video-checks.md`「成本」）。
- 对方在后台改配置时站点版本号可能不变：复测前重跑免费探针，比对 `/v1/models` 和 `/api/pricing` 的差异。
- **复用一套请求**：换目标只换 base / key / 模型名，同一批一致性请求跑官方和中转；中转专属的请求（查已出片任务、它的日志、可改规格的出片）单独放一组。已出片的任务号存下来——查任务免费，别为了复查重新出片花钱。
- 下载成片网速可能骤降：用 `curl -C -` 断点续传；有的代理 HEAD 回 404 JSON，读长度改用 1 字节 Range 请求看 `Content-Range`。
