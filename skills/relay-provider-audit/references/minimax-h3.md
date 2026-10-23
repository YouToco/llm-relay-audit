# MiniMax H3 / H3-Max 官方基准

> Last verified: 2026-10-10；价格与行为以官方文档为准。

状态：官方接口与价目已从文档整理；**官方成片指纹（编码器 / 容器 / 标签）还没有**——要拿一条官方成片用 `scripts/analyze_videos.py` 取，见「成片规格（指纹）」。
官方文档：[创建任务](https://platform.minimax.io/docs/api-reference/video-generation-v2-create)、[查询任务](https://platform.minimax.io/docs/api-reference/video-generation-v2-query)、
[价目](https://platform.minimax.io/docs/guides/pricing-paygo)（价目页没写日期）。

## 官方接口与响应（2026-10-10 读文档）

- **创建**：`POST https://api.minimax.io/v2/video_generation`，`Authorization: Bearer <key>`，`Content-Type: application/json`；只有「按量付费 API」能用 H3。
  - `model`：`MiniMax-H3` / `MiniMax-H3-Max`。
  - `content[]`：必有 1 个非空 `text`（≤7000 字符）；`image_url` / `video_url` / `audio_url` 带可选 `role`：`first_frame` / `last_frame` / `reference_image` / `reference_video` / `reference_audio`。
  - `resolution`（必填）、`duration`（必填整数）、`ratio`（默认 `adaptive`）、`callback_url`、`extra`（仅 H3-Max，`prompt_expansion_mode`）。
  - H3：`768P` / `2K`，**4–15 秒**；H3-Max：`480P` / `768P`，5–15 秒（不支持 4）、无 2K。
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
- 观察到 480P 16:9 = 832×480、24fps、32kHz 音轨（非官方观察，不能当基准）；方形首帧 + adaptive → 768×768；duration=5 容器时长约 5.17 秒，仍按整数秒计。
- **校验顺序**：素材类型 / `ratio` / `extra` 先于 `duration`，`duration` 先于分辨率 → 免费探针可用 `duration:3`（对两个型号都非法）兜底（规则 5）。
- 上游接受小写 `480p` 并回显成 `480P`。H3-Max 不支持参考图 / 视频 / 音频（400）。
- 计费 usage：H3 有 `output_seconds`（计费）、`input_seconds`（仅参考视频）、`input_image_count`（含免费图）、`total_seconds`（与文档一致）；
  H3-Max 观察到拆成 `video_seconds` + `video_input_seconds` + `image_input_count`——文档没写这套名字，**非官方观察，待官方直连实测**，可能是中转改的名。
- 出片快：480P 5 秒约 10 秒。
- 官方非法参数行为矩阵只有文档、没有逐条直连实测（待补）。

## 成片规格（指纹）

- **待补**：官方成片的编码器 / 容器 / 合规标签 / 成片链接域名还没取到。拿到一条官方成片前，判真伪只能靠「规格是否符合文档 + 有没有自建管线痕迹」，无法做编码器逐项比对。
- 上节经第三方观察到的 832×480、24fps、32kHz 只是线索，**非官方观察，不能当基准（待官方直连实测）**。

## 判真伪要点

- **ComfyUI 工作流**：`scripts/extract_comfy.py` 读 mp4 元数据，有工作流 = 中转用开源 / 量化权重自建管线，不是官方 API 输出（能读出文本编码器、主模型、量化方式、LoRA、采样步数、GPU 数）。
- 分辨率是否被放大（480P→768P）、帧率 / 音频采样率是否和官方直连成片一致（官方值待实测；第三方观察到的 24fps / 32kHz 不能当基准）。分辨率不在文档档位里（如 1344×768）是强信号。
- 码率异常低、无 AI 生成合规标识、成片链接在第三方 CDN → 结合上两条判断。
- 状态体有没有官方形状的 `task` 对象和 `usage`；`task_id` 是不是纯数字。
- 价目标了的档位也要实测能不能用（规则 1）。

## 接入网关要求

- 能拿到官方任务号（纯数字字符串）和官方形状的查询结果（`status`、`content.url`、`resolution`、`duration`）。
- 状态体有 `usage`：按文档是 `output_seconds`、`input_seconds`、`input_image_count`、`total_seconds`，参考素材计费口径要和官方一致。H3-Max 经第三方见过 `video_seconds` / `video_input_seconds` / `image_input_count` 这套名字（非官方观察，待官方直连实测），网关先两种都能解析，别把它写成官方要求。
- 报错保留官方错误码（2013 / 1004 / 1008 / 1026 / 1002），不泄露插件名、源码行号等内部信息。
- 成片链接能直接拿到（不是只能另调 `/content` 接口取流）。

## 中转常见问题（匿名案例）

- **自建开源权重冒充官源**：某中转放在标着「官方」的分组、按接近官方的价卖，成片 mp4 元数据嵌着 ComfyUI 工作流（量化文本编码器 + 量化主模型 + 加速 LoRA + 少步采样），
  分辨率不是官方档位、码率很低、无合规标识、链接在第三方 CDN；同一提示词两单画质差异大。
- **没有官方原生路径**：`/v2/video_generation` 回网页 HTML；只有 new-api 的 `POST /v1/videos`（扁平 `prompt` / `resolution` / `duration` / `ratio`，素材塞 `images` / `input_reference` / `metadata.content`）。
  状态值换成 `queued / in_progress / completed / failed`，成功响应只有 id / status / progress，**没有 usage、没有链接**（要另调 `/v1/videos/{id}/content`）。
- 参数校验规则同官方但报错外壳不同，且回传插件名、版本、源码行号。
- **标了 2K 却不能用**：提交成功、先预扣，约 20 秒后后端回「只支持 768P / 720P / 480P」再退款 → 价目表标了也要测。
- 实扣按它自己的价目公式按秒线性，与官方倍率无关。
