# Gemini 文本线路基准（AI Studio / Vertex）

> Last verified: 2026-10-19（AI Studio 计数 / 报错 10-15）；**Vertex 官方实测 2026-10-28 / 10-29**；价目 2026-10-29。价格与行为以官方文档为准。
> 通用判真伪见 `text-checks.md`；new-api 站点日志见 `new-api.md`；探针技巧见 `probing-tips.md`。

## 官方接口与响应
- 文档：`ai.google.dev`（接口说明 `ai.google.dev/api/generate-content.md.txt`）。响应顶层字段 = `candidates`、`promptFeedback`、`usageMetadata`、`modelVersion`、`responseId`、`modelStatus`。
- 免费调用：`countTokens`、`/v1beta/models`、参数校验类 400。官方 key 免费层可以生成 flash 系列（3.5 / 3.8-flash），argon 生成回 429 quota——用 flash 拿官方原样响应做并排、对 usage，免费。
- `models/gemini-4-argon`（2026-10-15）：输入上限 1,048,576、输出 32,768、`thinking: true`、temperature 默认 1（最大 2）、topP 0.95、topK 64。
- 报错（免费）：temperature=5 / topP=1.5 / thinkingLevel=bogus / 未知顶层字段 / 非法 responseMimeType / 空 contents 都回 400；非法 `role` 能过校验（会真跑、扣费）。
- **`maxOutputTokens: 9999999` 不报错（被夹住）**→「超大 max_tokens 逼出真实模型名」那招（见 `claude.md`）对 Gemini 无效。
- Gemini 3+ 两轮函数调用必须回传 `thoughtSignature`。

## AI Studio 与 Vertex 的差别
- Vertex 响应多 `createTime` 和 `usageMetadata.trafficType`（ON_DEMAND / PROVISIONED），没有 `serviceTier`。
- `thoughtSignature` 开头：Vertex `AY89a1…`，AI Studio `E…`。
- Vertex 报错原文形如「Unable to submit request because it has a temperature value of 5…」。
- token 口径小差：flash 同一句 Vertex 少 1、64×64 图少 29；argon 文本逐个相等。差值固定且各组一致就不算注入。**AI Studio countTokens 对 3.1-pro / 3.8-flash 的「Reply with the single word OK.」回 8，Vertex 真单 `promptTokenCount` 是 7**（2026-10-28，原因未查）——拿 AI Studio 计数去对走 Vertex 的中转，差 1 不能直接判注入，以下面 Vertex 实测数为准。
- **Vertex 报错原文和 AI Studio 不一样**（判中转走哪条渠道，三个型号一样）：

| 用例 | Vertex | AI Studio |
|---|---|---|
| temperature=5 | 「Unable to submit request because it has a temperature value of 5 but the supported range is from 0 (inclusive) to 2.0001 (exclusive)…」 | `400 INVALID_ARGUMENT`「…temperature: temperature must be in the range [0.0, 2.0].」 |
| topP=1.5 | 「…supported range is from 0 (inclusive) to 1 (inclusive)…」 | 「…top_p: top_p must be in the range [0.0, 1.0].」 |
| responseMimeType=text/bogus | 「Found unsupported response mime type: 'text/bogus' for a multi-modal generation request」 | 「…allowed mimetypes are text/plain, application/json, application/xml, application/yaml and text/x.enum.」 |
| 空 contents | 「Unable to submit request because at least one contents field is required.」 | 「* GenerateContentRequest.contents: contents is not specified」 |
| 未知顶层字段 | 两边一字不差：「Invalid JSON payload received. Unknown name "bogusField": Cannot find field.」（带 `fieldViolations`） | 同左 |
| thinkingLevel=bogus | 基本相同，Vertex 的类型路径带 `.cloud..v1` | 「Invalid value at 'generation_config.thinking_config.thinking_level' …」 |

- AI Studio 报错外壳 `{"error": {"code", "message", "status", "details"?}}`；非法 `role` 在免费层回 429（说明过了参数校验、会真跑）。
- **argon 长文（无工具）Vertex 回 `toolUsePromptTokenCount` ≈ 输入**；若中转把它计入输入，约两倍计费——报价时长上下文按 ×2 估。

## 价目（以官方价目页为准，2026-10-29 读，USD / 百万 token）
AI Studio：[ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing)；Vertex：[cloud.google.com/vertex-ai/generative-ai/pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)（Global 价，**Non-global 一律 +10%**）。

| 模型 | 输入 | 输出（含思考） | 缓存 | 备注 |
|---|---|---|---|---|
| gemini-4-argon | 2 | 10 | 0.10 | 到 2026-11-30；**2026-12-01 起 4 / 20 / 0.20**；免费层不可用；只有隐式缓存；无 200k 阶梯 |
| gemini-3.8-flash（3.6-flash 同价） | 0.75 | 3.75 | 0.075 | 到 2026-12-31；2027-01-01 起 1.50 / 7.50 / 0.15 |
| gemini-3.1-pro-preview | 2（> 200k：4） | 12（> 200k：18） | 0.20（> 200k：0.40） | Vertex 只有 Global |
| gemini-nano-banana-2.1 | 1.50 | 文本 7.50；图片 30 | — | 每张 1K $0.0336、2K $0.0504、4K $0.113 |
| gemini-3.1-flash-image | 0.50 | 文本 3；图片 60 | — | 每张 0.5K $0.045、1K $0.067、2K $0.101、4K $0.151 |
| gemini-3-pro-image | 2 | 文本 12；图片 120 | — | 每张 1K / 2K $0.134、4K $0.24 |

- Batch / Flex 半价、Priority 1.8×；搜索接地：Gemini 3 及以后每月 5,000 次免费，之后 $14 / 千次。
- **argon 的促销价在 Vertex 上是「50% credits back on net spend」实现的**，不是标价；Vertex 页注：只对 200 响应收费；2026-11-13 起超过 32K 的输出即使请求超时失败也按已产出 token 收费。
- 生图每张价不含思考 token；实测出图时思考另算（见下），核中转按张收费时别拿含思考的总额当挂牌价。

## Vertex 官方实测（2026-10-28 / 10-29）
| 用例（`maxOutputTokens` 512） | gemini-3.1-pro-preview | gemini-4-argon | gemini-3.8-flash |
|---|---|---|---|
| ok「Reply with the single word OK.」 | prompt **7** · 思考 84 | prompt **38** · 思考 81 | prompt **7** · 思考 62 |
| hi「Hi」 | prompt **1** · 思考 175 | prompt **32** · 不思考 | prompt **1** · 思考 33 |
| ok + systemInstruction | 11 | 47 | 11 |
| ok + get_weather 函数 | 29 | 89 | 29 |
| 强制函数调用（`mode: ANY`） | 30 · 输出 17 | 90 · 输出 23 | 30 · 输出 17 |

- argon 的 prompt = AI Studio countTokens（38 / 32 / 47 / 89）逐个相等；3.1-pro / 3.8-flash 没有 argon 那约 31 token 的外壳。
- 思考默认开：`thoughtsTokenCount` 按输出价计；`usageMetadata` 带 `trafficType: ON_DEMAND`、`promptTokensDetails` / `candidatesTokensDetails` 按模态拆。
- **图片输入**（1920×1088 PNG）：3.8-flash / 3.1-pro 都计 **1,100** token（+ 文本 7）；`inlineData` base64 和 `fileData` 直接给 https URL 都能用，计数一样。
- **隐式缓存不保证命中**：约 5,500 token 的同一 `systemInstruction`，3.1-pro 第二单 `cachedContentTokenCount: 2037`（部分命中）；3.8-flash 连发 3 次都没命中。判中转「缓存不透传」要多发几次、和官方同一时段比。
- **生图**（同一提示词、不给尺寸）：nano-banana-2.1 1376×768、3-pro-image 1408×768、3.1-flash-image 1408×768（**默认不是 1:1**），图片输出都是 **1120 token**；nano-banana 思考 880、3-pro-image 思考 269、3.1-flash-image 不思考。C2PA：签发者 Google LLC（CN Google Media Processing Services），中间 CA Google C2PA Media Services 1P ICA G3，claim generator「Google C2PA Core Generator Library」，动作 created + edited；叶证书指纹已在 `scripts/c2pa_known_signers.json`。这是 Google 通用媒体签名服务，**能证明是 Google 原图，分不出 Vertex 还是 AI Studio**。
- 官方自己也会限流：Vertex 3-pro-image 第一次回 429 `RESOURCE_EXHAUSTED`「Resource has been exhausted (e.g. check quota).」，隔几秒重试成功；3.8-flash 首字长尾重（10 次里 p50 2.8 s、p90 20 s、最慢 33 s，开思考时首字要等思考完）。中转偶发 429 / 503、十几秒首字不一定是中转的问题。
- **AI Studio 免费层（2026-10-28）**：只有 3.5-flash、3.1-flash-lite 能出字；3.1-pro / argon / 三个生图型号 429，gemini-2.5-flash 404「no longer available to new users」。免费层 429 原文是 `RESOURCE_EXHAUSTED` + `google.rpc.QuotaFailure`（quotaId 如 `GenerateRequestsPerDayPerProjectPerModel-FreeTier`，`limit: 0` = 该型号免费层不可用），等待时间在体里的 `RetryInfo.retryDelay`，不在头里；AI Studio 唯一相关响应头是 `X-Gemini-Service-Tier`。
- **AI Studio OpenAI 兼容口**（`/v1beta/openai/chat/completions`，免费层 gemini-3.5-flash）：200，「Hi」`prompt_tokens: 2`、`total_tokens` 含思考、`completion_tokens` 只算正文。

## 判真伪检测矩阵
| 检测 | 做法 | 判据 |
|---|---|---|
| token 外壳 | 官方 `countTokens` 与中转 `usageMetadata.promptTokenCount` 逐个比 | 见下方基准数；多出固定数 = 注入（或 Vertex 小差，见上） |
| 专属工具 | `codeExecution`、`googleSearch` | 前者回 `executableCode` + `codeExecutionResult`，后者回 `groundingMetadata` |
| thoughtSignature | 两轮函数调用回传 | Gemini 3+ 必须；开头区分 Vertex / AI Studio |
| 报错原文 | 上面那组免费 400 | 原文和外壳对官方；露 Vertex 原文（「Unable to submit request because…」）= 背后是 Vertex |
| 字段 | 顶层 / usage 字段程序求差集（规则 12） | 多 `createTime` / `trafficType` = Vertex |

- 换模型只能靠 token 外壳数 + 专属工具 + thoughtSignature 认，不能靠超大 maxOutputTokens。

## 对账与计数（countTokens 基准，gemini-4-argon，2026-10-15）
- countTokens 按整个请求算，可和 `usageMetadata.promptTokenCount` 逐个比。
- 「Reply with the single word OK.」**38**；「Hi」**32**（argon 有约 30 token 固定外壳，flash 的「Hi」只有 2）。
- + systemInstruction「You are terse.」= 47；+ get_weather 函数 = 89；+ codeExecution = 208；+ googleSearch = 223。

## 中转常见问题（匿名）
- new-api 原生 `/v1beta/models/{m}:generateContent` 和 OpenAI 兼容口都转；但 `/v1beta/models` 只回名字（limit 等字段全 null），不是官方原样。
- 号池空：503 `{"type":"upstream_error","code":503,"message":"No available Gemini accounts: no available accounts"}`，new-api 日志 type 5、quota 0——按规则 9 归「上游偶发」类；持续出现 = 号池没额度，要问对方。
- 某中转「Vertex」分组：长文把 `toolUsePromptTokenCount` 计入输入，实际约两倍计费。
- 国内网络到 Google 可能时通时断（握手 EOF），官方对照调用要加重试。

## 接入网关要求
- 原生 `generateContent` 要透传 `thoughtSignature`、`groundingMetadata`、`executableCode` / `codeExecutionResult`。
- 计费口径要说清 `toolUsePromptTokenCount`、`thoughtsTokenCount` 是否计入输入 / 输出。
- `/v1beta/models` 不是官方原样时，型号上限要以官方文档为准，别信中转的列表。
