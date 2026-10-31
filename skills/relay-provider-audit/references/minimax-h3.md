# MiniMax H3 / H3-Max 官方基准

> Last verified: 2026-10-30；价格与行为以官方文档为准。

状态：官方接口与价目从文档整理（2026-10-10，型号 2026-10-30 复读）；**官方直连实测 2026-10-30**：`MiniMax-H3` 768P / 2K × 6 个比例 + 图生共 14 单（尺寸、帧数、每秒 token、耗时）和报错矩阵 13 项；官方成片指纹（编码器 / 容器 / `AIGC` 标签）共 18 条（含 2026-09-28 的 H3-Max 系两条、10-27 的 2K 重生成两条）。成片指纹超过 30 天先取一条复核。
官方文档：[创建任务](https://platform.minimax.io/docs/api-reference/video-generation-v2-create)、[查询任务](https://platform.minimax.io/docs/api-reference/video-generation-v2-query)、
[价目](https://platform.minimax.io/docs/guides/pricing-paygo)（价目页没写日期）。

## 官方接口与响应（2026-10-10 读文档）

- **创建**：`POST https://api.minimax.io/v2/video_generation`，`Authorization: Bearer <key>`，`Content-Type: application/json`；只有「按量付费 API」能用 H3。
  - `model`：`MiniMax-H3` / `MiniMax-H3-Max`。
  - `content[]`：必有 1 个非空 `text`（≤7000 字符）；`image_url` / `video_url` / `audio_url` 带可选 `role`：`first_frame` / `last_frame` / `reference_image` / `reference_video` / `reference_audio`。
  - `resolution`（必填）、`duration`（必填整数）、`ratio`（默认 `adaptive`）、`callback_url`、`extra`（仅 H3-Max，`prompt_expansion_mode`）。
  - H3：`768P` / `2K`，**4–15 秒**；H3-Max：`480P` / `768P`，5–15 秒（不支持 4）、无 2K。
  - 2026-10-30 复读文档：型号枚举还有 `MiniMax-H3-Highspeed`（`768P`，4–15 秒）、`MiniMax-H3-Lite`（`480P` / `768P`，4–15 秒，参考生视频不支持 adaptive）；**H3 没有 480P / 1080P**。文档没有像素尺寸表（实测见下）。
  - 文生视频 `ratio` 必填且不能 `adaptive`；图生视频一律 adaptive；参考生视频可选。文档没有 `seed`。首尾帧与参考素材不能混用。
  - 素材限制：图 ≤30MB、256–5760px、宽高比 0.4–2.5，最多 1 首帧 + 1 尾帧 + 9 参考图；视频 MP4 / MOV ≤50MB、2–15 秒、总 ≤15 秒、最多 3 段；音频 WAV / MP3 ≤15MB、最多 3 段；请求体 ≤64MB。
- **创建响应**：`{"task_id": "<纯数字字符串>"}`。
- **查询**：`GET https://api.minimax.io/v2/query/video_generation/{task_id}` →
  `{"task": {id, model, status, created_at(秒), updated_at, content: {url}, resolution, duration, usage, ratio, task_type: "generation", modality: "video"}}`。
  - `status`：`queued` / `running` / `succeeded` / `failed` / `cancelled`；失败时 `error: {code, message}`、`usage: {}`。
  - `usage`：`total_seconds`、`input_seconds`、`output_seconds`、`input_image_count`、`input_audio_seconds`（无参考音频时省略）、`total_tokens` / `prompt_tokens` / `completion_tokens`（由秒数和图数折算）。
  - 视频链接有时效，过期重新查询换新链接；**只能查最近 7 天的任务**（更早回 `invalid task_id`）。
- **错误**：真实 HTTP 状态码 + `{"type":"error","error":{"type","message","http_code"},"request_id"}`：
  400 `bad_request_error`（如 `invalid params, content must include a non-empty text item (prompt is required) (2013)`）、401 `authorized_error`（1004）、
  402 余额不足（1008）、422 敏感内容（1026）、429 限流（1002）、500（1000）。
- 其他官方端点：`/v2/h3_context_ir`（只返回增强提示词，不出片）、`/v2/video_regeneration`（768P 任务升 2K）、`/v2/query/video_generation`（列表，可按 model / task_type 过滤）、取消 / 删除任务。
  - 列表接口会列出同账号的**所有**任务：官方 key 若也在跑别的业务，列表结果别落盘（规则 17 的做法：只记条数）。
  - **删了的任务查不回来**（再查回 400「This task_id does not exist (2013)」）：官方基准任务别删，后面还要用任务号重新查询换新链接。

## 官方实测（2026-10-30，`MiniMax-H3` 直连官方，14 单 + 报错 13 项）

固定请求体（中转一侧照发才能逐单比）：文生 `{"model":"MiniMax-H3","content":[{"type":"text","text":PROMPT}],"resolution":"768P"|"2K","duration":4,"ratio":<比例>}`，`PROMPT = "A red panda exploring a misty forest at dawn, soft golden light through the trees, cinematic"`，另有 768P 16:9 5 秒一单；图生 `ratio:"adaptive"` + 一张 720×1280 竖图作 `first_frame`。

**尺寸**（文档没有，全部实测）：

| 比例 | 768P | 2K |
|---|---|---|
| 21:9 | **1536×672** | **2944×1248** |
| 16:9 | 1344×768 | 2560×1440 |
| 4:3 | 1024×768 | 1920×1440 |
| 1:1 | 768×768 | 1440×1440 |
| 3:4 | 768×1024 | 1440×1920 |
| 9:16 | 768×1344 | 1440×2560 |
| 图生 adaptive（720×1280 竖图） | 768×1344 | 1440×2560 |

- 21:9 不是「高 = 768 / 1440」，而是像素数保持在同档附近（1536×672 ≈ 103 万）；中转 21:9 出 1792×768 / 3360×1440 就是它自己的尺寸规则。
- 帧数：24 fps，4 秒 = **107 帧 / 4.458 s**，5 秒 = **124 帧 / 5.167 s**（帧数网格 17n + 5，比标称多出一截是官方原样）。

**用量**（`task.usage`，计费按 `output_seconds`）：

| 档位 | 每秒 `completion_tokens` | 例 |
|---|---|---|
| 768P | **32,549** | 4 秒 130,196、5 秒 162,745（6 个比例都一样，和比例无关） |
| 2K | **52,078** | 4 秒 208,312（= 768P × 1.6） |
| 每张输入图 | `prompt_tokens` **13,020**、`input_image_count` +1 | 768P 图生 4 秒 143,216、2K 图生 4 秒 221,332 |
| 2K 重生成（2026-10-27） | — | 4 秒 `total_tokens` 78,116、`task_type: regeneration` |

中转回的 usage 按这张表核：token 数对不上 = 自己算的或换了模型。

**耗时**（服务端 `updated_at - created_at`，3 路并发）：768P 4–5 秒 117–202 秒（中位约 177 秒）；2K 4 秒 285–406 秒（中位约 335 秒）；图生比同档文生慢约 20 秒。

**报错与校验顺序**：
- **校验顺序：ratio → model → duration → resolution / content**——非法分辨率和空 content 都被 3 秒时长先挡住，探针保险要放在更靠后的检查上（规则 5）。
- `ratio=7:3` → 400「invalid params, ratio="7:3" invalid, allowed: adaptive, 16:9, 4:3, 1:1, 3:4, 9:16, 21:9 (2013)」
- `model=nope-model` → 400「invalid params, this model is not supported by /v2/video_generation (2013)」；**小写 `minimax-h3` 能过型号检查**（撞到的是时长报错）。
- `duration` 0 / 2 / 3 / 99 → 400「invalid params, model MiniMax-H3 does not support duration Xs, supported durations: 4s, 5s, … 15s (2013)」
- 不带 key / 错 key → 401 `authorized_error`「login fail: Please carry the API secret key in the 'Authorization' field of the request header (1004)」（两种文案相同）
- 查不存在的任务 → **400**（不是 404）「invalid params, This task_id does not exist (2013)」

## 价目（美元，价目页无日期，2026-10-10 读；以官方页为准）

| 项 | H3 | H3-Max |
|---|---|---|
| 输出 | 768P $0.08 / 秒、2K $0.13 / 秒 | 480P $0.05 / 秒、768P $0.08 / 秒 |
| 参考图 | 前 5 张免费，之后 $0.04 / 张 | 前 2 张免费，之后 $0.074 / 张 |
| 参考视频（按输入秒数） | 与输出同价（768P $0.08、2K $0.13） | 480P $0.0553 / 秒、768P $0.143 / 秒 |
| 参考音频 | 免费 | 免费 |

- 另：H3 升 2K 重生成 $0.05 / 秒；H3-Context-IR $0.90 / $3.60 每百万 token（输入 / 输出）。
- 官方档位倍率：H3 2K / 768P = 1.625。

## 经第三方观察到的行为（2026-09，非直连官方 key）

> **非官方观察，不能当基准（待官方直连实测）**：本节全部经第三方转发看到，可能混着中转自己的改写；对照表的「官方列」只能用上面的文档内容。
> 某中转以 `-Turbo` 后缀售卖（H3-Max-Turbo）；规格（480P / 768P、5–15 秒）与文档里的 H3-Max 一致，推断为同一型号。

- 规格：H3-Max 只有 480P / 768P；时长 5–15 整数；文生视频必须显式 `ratio`（不能 adaptive），带图可 adaptive。
- 观察到 480P 16:9 = 832×480、24fps、32kHz 音轨；方形首帧 + adaptive → 768×768；duration=5 容器时长约 5.17 秒，仍按整数秒计。**这几项已被官方成片证实**（2026-09-28 官方 key 出的 H3-Max 系两条，见下「成片规格（指纹）」）。
- **校验顺序**：素材类型 / `ratio` / `extra` 先于 `duration`，`duration` 先于分辨率 → 免费探针可用 `duration:3`（对两个型号都非法）兜底（规则 5）。H3 的顺序已由官方直连证实（上文「报错与校验顺序」）。
- 上游接受小写 `480p` 并回显成 `480P`。H3-Max 不支持参考图 / 视频 / 音频（400）。
- 计费 usage：H3 有 `output_seconds`（计费）、`input_seconds`（仅参考视频）、`input_image_count`（含免费图）、`total_seconds`（与文档一致）；
  H3-Max 观察到拆成 `video_seconds` + `video_input_seconds` + `image_input_count`——文档没写这套名字，**非官方观察，待官方直连实测**，可能是中转改的名。
- 出片快：480P 5 秒约 10 秒。
- H3-Max / -Lite / -Highspeed 的官方非法参数矩阵还没有直连实测（H3 的见上）。

## 成片规格（指纹，官方实测 2026-10-28 / 10-30，共 18 条）

| 成片 | 尺寸 | 编码 | 帧 / 时长 | 码率 |
|---|---|---|---|---|
| H3-Max 系 480P 5 秒（2026-09-28） | 832×480 | H.264 **Constrained Baseline** | 124 帧 / 5.184 s | 4.2 Mbps |
| H3-Max 系 768P 5 秒（2026-09-28） | 768×768（1:1） | H.264 Constrained Baseline | 124 帧 / 5.184 s | 4.5 Mbps |
| H3 2K 重生成 4 秒（2026-10-27，两条） | 2560×1440 | H.264 **High** | 107 帧 / 4.459 s | 4.9 Mbps |
| H3 768P 4 / 5 秒（2026-10-30，7 条） | 见上「尺寸」 | H.264 **High** | 107 / 124 帧 | 1.4–3.3 Mbps |
| H3 2K 直出 4 秒（2026-10-30，7 条） | 见上「尺寸」 | H.264 **High** | 107 帧 | 5.3–14.6 Mbps |

- **编码器**：码流 SEI `x264 - core 163 r3060 5db6aa6`，容器 `Lavf59.27.100`，24 fps，有声 AAC 32 kHz 立体声（18 条全部一致）。H3 是 High profile，H3-Max 系是 Constrained Baseline。
- **没有 C2PA**（`c2pa_check.py` 报「无 C2PA」对 MiniMax 不是负面证据）。判原片靠容器 **`AIGC` 标签**：`{"Label":"1","ContentProducer":"MiniMax","ProduceID":"<32 位十六进制>","ReservedCode1":"{\"SecurityData\":{\"Type\":\"TC260PG\",…,\"AlgID\":\"1.2.156.10197.1.501\"…,\"Signature\":\"…\"}}"}`（国标 TC260 隐式标识，签名算法 OID = SM2-with-SM3）。中转成片 `ContentProducer` 不是 MiniMax、没有这个标签，或编码器不是 x264 core 163 / Lavf59.27.100 → 转码过或自部署。
- **成片地址**：`video-product.cdn.minimax.io/h3-480p|h3-768p/<日期>/style1/<任务号>-1-<16 位十六进制>_aigc.mp4`（H3-Max 系），H3 普通出片和重生成是 `…/inference_output/rollout/<日期>/<uuid>/output_aigc.mp4`。不带签名、长期可下；H3-Max 系文件名里的任务号 = 官方 task_id。

## 判真伪要点

- **ComfyUI 工作流**：`scripts/extract_comfy.py` 读 mp4 元数据，有工作流 = 中转用开源 / 量化权重自建管线，不是官方 API 输出（能读出文本编码器、主模型、量化方式、LoRA、采样步数、GPU 数）。
- **是不是官方原片**：容器 `AIGC` 标签（`ContentProducer: MiniMax` + TC260PG 签名）+ 编码器（x264 core 163 / Lavf59.27.100）+ 成片在 `video-product.cdn.minimax.io`，三项都对上才算（上节）。
- **尺寸 + 帧数网格 + 帧率**：同型号同档同比例，尺寸要和上文实测表一致（注意 768P 16:9 官方就是 1344×768）、帧数在 17n + 5 网格上（4 秒 107、5 秒 124）、24 fps、AAC 32 kHz；分辨率是否被放大（480P→768P）。
- 码率异常低、无 AI 生成合规标识、成片链接在第三方 CDN → 结合上两条判断。
- **自部署（自己 GPU 跑开源 H3 权重）常见特征**：自有协议、成片链接要鉴权、无 `usage`、默认扩写提示词、时长 / 分辨率比官方宽（1–30 秒、480p / 1440p 直出）、16 秒以上是多段拼接；尺寸和帧数网格可能和官方一样（同一套模型），所以只看尺寸判不出，要看 `AIGC` 标签和编码器。
- `usage` 按上文「用量」表核每秒 token。
- 状态体有没有官方形状的 `task` 对象和 `usage`；`task_id` 是不是纯数字。
- 价目标了的档位也要实测能不能用（规则 1）。

## 接入网关要求

- 能拿到官方任务号（纯数字字符串）和官方形状的查询结果（`status`、`content.url`、`resolution`、`duration`）；「查不到任务」官方是 400 `(2013)`，不是 404。
- 状态体有 `usage`：按文档是 `output_seconds`、`input_seconds`、`input_image_count`、`total_seconds`，参考素材计费口径要和官方一致。H3-Max 经第三方见过 `video_seconds` / `video_input_seconds` / `image_input_count` 这套名字（非官方观察，待官方直连实测），网关先两种都能解析，别把它写成官方要求。
- 报错保留官方错误码（2013 / 1004 / 1008 / 1026 / 1002），不泄露插件名、源码行号等内部信息。
- 成片链接能直接拿到（不是只能另调 `/content` 接口取流）。

## 中转常见问题（匿名案例）

- **自建开源权重冒充官源**：某中转放在标着「官方」的分组、按接近官方的价卖，成片 mp4 元数据嵌着 ComfyUI 工作流（量化文本编码器 + 量化主模型 + 加速 LoRA + 少步采样），
  码率很低、无合规标识、链接在第三方 CDN；同一提示词两单画质差异大。成片 1344×768 / 24 fps——当时以为不是官方档位，2026-10-30 官方实测 768P 16:9 正是 1344×768，所以**尺寸对得上不代表是官方**，要看 `AIGC` 标签和编码器。
- **没有官方原生路径**：`/v2/video_generation` 回网页 HTML；只有 new-api 的 `POST /v1/videos`（扁平 `prompt` / `resolution` / `duration` / `ratio`，素材塞 `images` / `input_reference` / `metadata.content`）。
  状态值换成 `queued / in_progress / completed / failed`，成功响应只有 id / status / progress，**没有 usage、没有链接**（要另调 `/v1/videos/{id}/content`）。
- 参数校验规则同官方但报错外壳不同，且回传插件名、版本、源码行号。
- **标了 2K 却不能用**：提交成功、先预扣，约 20 秒后后端回「只支持 768P / 720P / 480P」再退款 → 价目表标了也要测。
- 实扣按它自己的价目公式按秒线性，与官方倍率无关。
- **自部署冒充官方原片**：某家自己 GPU 跑开源 H3，成片尺寸、帧数网格、24 fps 都和官方一样，但没有 MiniMax 的 `AIGC` 标签、编码器不是官方那套、链接要鉴权、没有 `usage`。
- **画质对照被提示词扩写带偏**：同一家默认扩写提示词，把画面改成全景深，第一轮被误判成「锐化痕迹」；关掉扩写、两边同一句原句、同帧数（官方 4 秒 107 帧）重测后结论作废——画质对照必须同条件（`video-checks.md`「画质」）。
