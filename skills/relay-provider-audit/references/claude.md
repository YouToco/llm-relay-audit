# Claude（文本）线路基准：一方 API / Bedrock / Vertex / 经 OpenAI 格式转换

> Last verified: 2026-10-22（文档）；官方 key 实测 2026-10-19 – 10-29（见「官方实测」）；价格与行为以官方文档为准。
> 通用判真伪流程见 `text-checks.md`；new-api 站点的日志 / 价目接口见 `new-api.md`；订阅号池见 `sub2api.md`；探针技巧见 `probing-tips.md`。

## 官方接口与响应
- 文档：当天取 `platform.claude.com/docs/en/<页>.md`（Messages / Streaming / Errors / Rate limits / API overview / Token counting）；Bedrock 版见 AWS 文档「Anthropic Claude Messages API」页（`docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html`）。
- **id 前缀认后端**：一方 API 实测 = `msg_011C…`（请求 id `req_011C…`）——这是观察到的前缀，官方没承诺 id 格式，可能会变，看到别的前缀先拿官方 key 发一单核对；Bedrock = `msg_bdrk_…`；Vertex = `msg_vrtx_…`。分组名 / 模型名带「AWS」「Bedrock」「官转」都不算证据，以 id 为准。
- **一方 API 的身份证据**：非流式响应头有 `request-id`、`anthropic-organization-id`、`anthropic-ratelimit-*`；多发几单数一下出现几个不同的组织 id，多个 = 号池。注意 new-api 流式响应不透传上游头，要看非流式。
- usage：`input_tokens`、`output_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`，以及 `cache_creation.ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens`。
- 思考：4.7 及更新的型号（含 Opus 4.8 / 5、Sonnet 5、Fable 5）`display` 默认 `"omitted"`，思考块的 `thinking` 字段为空、只有 `signature`，要文字得显式发 `thinking.display:"summarized"`；思考块必须带 `signature`。检测「会不会想」用 effort `max`（adaptive + effort low 的简单题官方也不出思考块、`thinking_tokens` 0，不算中转毛病）。新型号不支持 assistant 预填，回 400 是正常行为。
- **5.x 代的限制**（官方实测）：`thinking.type: "enabled"` 400「"thinking.type.enabled" is not supported for this model. Use "thinking.type.adaptive" and "output_config.effort"…」；`tool_choice` 指定 tool / any 400「type "tool" and "any" are not supported for this model.」。中转对这两样回 200 = 参数被改写或丢了。
- 免费调用：`/v1/messages/count_tokens`、`/v1/models`、参数校验类 400。官方还有 OpenAI 兼容口 `api.anthropic.com/v1/chat/completions`（400 也免费），可拿同一输入对比报错原文。
- 报错：外壳 `{"type":"error","error":{"type":"…","message":"…"},"request_id":"req_…"}`；状态码与 `error.type` 对应关系以 Errors 页为准，429 带 `retry-after`。
- `inference_geo`、`speed`、`service_tier` 等是顶层合法字段；非法值官方必回 400。合法 `inference_geo:"us"` 回「not supported for this organization type」= 消费者订阅组织（Pro / Max），不是 API 组织（判订阅号池，免费）。

## 官方实测（Anthropic 官方 key，2026-10-19 – 10-29）
同一批请求体直接拿来比供应商；token 口径 10-29 原样重发 count_tokens 逐条一致。别家账号的限额数会不同，只当「长什么样」参照。
- **count_tokens**（裸「Reply with the single word OK.」/ 加 system「You are a helpful assistant.」+ `text_editor_20250728`）：

| 型号 | 裸 | system + text_editor |
|---|---|---|
| opus-4-5-20251101、sonnet-4-5(-20250929)、haiku-4-5-20251001 | 14 | 1,262 |
| opus-4-6、sonnet-4-6 | 14 | 1,263 |
| opus-4-7 | 21 | 1,681 |
| opus-4-8、fable-5 | 16 | 1,291 |
| opus-5 | 16 | 1,287 |
| sonnet-5 | 16 | 1,355 |
| opus-5-5、sonnet-5-5、haiku-5-5、fable-5-1 | 18 | 1,289 |

  不带 system 的工具版：5-5 代与 fable-5-1 1,278，4.5 代 1,255，4.6 1,256，4.7 1,670，4-8 / fable-5 1,280，opus-5 1,276，sonnet-5 1,344。**同一组里的型号数一样，只能判「是不是这一组」**，分不出组内是谁。
- **真实 `usage.input_tokens` = count_tokens**（逐个相等，不像 Kimi 差 1）；裸 OK 单 output 4、`stop_reason: end_turn`。
- **回包**：顶层键 `container, content, diagnostics, id, model, role, stop_details, stop_reason, stop_sequence, type, usage`；usage 带 `cache_creation{ephemeral_5m_input_tokens, ephemeral_1h_input_tokens}`、`output_tokens_details.thinking_tokens`、`service_tier: standard`、`inference_geo: global`、`speed: standard`。合法 `inference_geo: "us"` / `speed: "fast"` 会原样回在 usage 里——中转回包里这两个值不跟着变 = 字段没传上去。
- **响应头**：`request-id`、`anthropic-organization-id`、`anthropic-workspace-id`、`anthropic-ratelimit-{requests,input-tokens,output-tokens,tokens}-{limit,remaining,reset}`（reset 是 RFC 3339 UTC 时间）、`x-should-retry`、`Server: cloudflare` + `CF-RAY`；**没有** `x-new-api-version` / `via` / `x-amzn-*`。限流头只出现在 `/v1/messages` 的 200 上（count_tokens、`/v1/models`、4xx 都不带）；限额按模型族分档（实测一个组织里 fable 一档、其余一档）；`speed: "fast"` 单不回普通 token 头，改回 `anthropic-fast-{input,output}-tokens-*`。报错行带 `x-should-retry: false`。官方实测记录里没见过 `retry-after`（没打满过限额）。
- **流式**：`message_start → content_block_start → ping → content_block_delta… → content_block_stop → message_delta → message_stop`；首包 ≈ 首字（`message_start` 和第一个 delta 几乎同时到）。首字参照（国内经代理，sonnet-5-5 ×10）p50 约 2.1 s、2.0–3.1 s——网络占大头，要比就和供应商同一时段同一台机器各跑 10 次。
- **报错原文**（都是 `invalid_request_error` + `request_id`）：temperature=9「temperature: range: 0..1」；top_k=-5「top_k: range: -1..100,000,000」；geo=mars「inference_geo: must be one of ['global', 'us']」；service_tier=bogus「service_tier: Input should be 'auto' or 'standard_only'」；speed=bogus「speed: Input should be 'fast' or 'standard', got 'bogus'」；未知字段「foo_bar: Extra inputs are not permitted」；metadata.user_id=123「…Input should be a valid string」；stop_sequences 给字符串「…Input should be a valid array」；container「Container identifier can only be provided when using the code execution tool」；坏 beta 头「Unexpected value(s) `…` for the `anthropic-beta` header…」；版本 1999「anthropic-version: "1999-01-01" is not a valid version」；缺版本头「anthropic-version: header is required」；max_tokens 超限「max_tokens: 9999999 > 128000, which is the maximum allowed number of output tokens for <型号>」（4.5 代是 64000）；不存在模型 404 `not_found_error`「model: claude-opus-9-9」；错 key 401 `authentication_error`「invalid x-api-key」。
- **`/v1/models`**：4.6 及以后 `max_input_tokens` 1,000,000、`max_tokens` 128,000；4.5 代 200,000 / 64,000。
- **缓存**：system 约 8K / 10.6K token 带 `cache_control`，首单 `cache_creation_input_tokens` 全量（进 `ephemeral_5m`），第二单 `cache_read_input_tokens` 全量；`ttl: "1h"` 单独记在 `ephemeral_1h_input_tokens`。
- **官方 OpenAI 兼容口**（`POST /v1/chat/completions`，Bearer 官方 key）：200，「Hi」`prompt_tokens: 11`（包装和原生不同，不能和 count_tokens 直接比）；流式 chunk 的 id 仍是 `msg_011C…`。
- **自报型号不可信**：官方 opus-5 被问型号答「I'm Claude Sonnet 4.5」——判真伪别用自报。

## 价目
- 以 `platform.claude.com/docs/en/about-claude/pricing` 为准（取当天）。缓存：5 分钟写入 = 输入价 ×1.25，1 小时写入 ×2；命中一般 = 输入价 ×0.1，但新型号不同（下表）。
- 官方价目页快照（2026-10-29 读，USD / 百万 token，全球默认路由；对账前重读）：

| 模型 | 输入 | 5 分钟写 | 1 小时写 | 命中 | 输出 |
|---|---|---|---|---|---|
| Fable 5.1（Mythos 5.1 同价） | 10 | 12.50 | 20 | 0.25 | 50 |
| Fable 5（Mythos 5 同价） | 10 | 12.50 | 20 | 1 | 50 |
| Opus 5.5 | 4 | 5 | 8 | 0.20 | 20 |
| Opus 5 / 4.8 / 4.7 / 4.6 / 4.5 | 5 | 6.25 | 10 | 0.50 | 25 |
| Sonnet 5.5 | 2 | 2.50 | 4 | 0.10 | 10 |
| Sonnet 5 | 2 | 2.50 | 4 | 0.20 | 10 |
| Sonnet 4.6 / 4.5 | 3 | 3.75 | 6 | 0.30 | 15 |
| Haiku 5.5（提示 ≤ 100k / > 100k 整单） | 0.10 / 0.50 | 0.125 / 0.625 | 0.20 / 1 | 0.01 / 0.05 | 0.50 / 2.50 |
| Haiku 4.5 | 1 | 1.25 | 2 | 0.10 | 5 |

  命中倍率：Fable / Mythos 5.1 = 0.025×，Opus / Sonnet 5.5 = 0.05×，其余 0.1×。`inference_geo: "us"`（4.6 及以后）所有项 ×1.1；Batch 五折；Fast mode：Opus 5.5 $8 / $40，Opus 5 / 4.8 $10 / $50（可叠缓存和地域倍率，不能用 Batch）。4.6 及以后（Haiku 5.5 除外）1M 上下文同价、无长文阶梯。Bedrock / Google Cloud 区域端点比全球端点贵 10%（以云厂商价目页为准）。
- new-api 站点的公式（软件默认）：`quota = (输入 + 命中×cache_ratio + 写入×1.25 + 输出×completion_ratio) × model_ratio × group_ratio`，quota 500000 = $1；`/api/pricing` 免登录可取 `model_ratio` / `group_ratio`，和官方价相除得倍率。
- 站点美元 ↔ 人民币看充值档位，查不到汇率就别判贵贱。

## 判真伪检测矩阵
| 阶段 | 测什么 | 判据 |
|---|---|---|
| 免费探针 | `/v1/models`、`/api/pricing`、`/api/log/token`、错 key、非法参数 | 价目公式 vs 官方价；倍率 |
| avail | 每个模型 1 次 | 回包 `model` = 请求名；id 前缀；有无 429 |
| proto | `/v1/messages` 与 `/v1/chat/completions`，各非流 + 流式 | 事件序列、usage 位置、首字耗时 |
| feat | system、多轮、tool_use 往返、图片、stop_sequences、thinking（`display:summarized`）、json_object、预填 | 与官方一致 |
| auth | 短提示词查隐藏前缀 + 官方内置工具 `text_editor_20250728` | 短提示 input 应很小（约 30）；带 text_editor 应多约 700–1300（按型号不同，见「官方实测」）；**一句从没发过的新句子就命中大缓存 = 被拼了隐藏提示词**；内置工具说明官方写死、转换层伪造不了 |
| drops | 每个顶层字段给非法值 | 官方必 400；中转回 200 = 字段被网关删了 |
| cache | system 块 `cache_control` 连发 5 轮 | 第 1 轮写入、后面命中；看 `cache_creation.ephemeral_5m` |
| conc | 顺序基线 + 5 / 10 路并发 | 首字、是否 429 |
| 对账 | 站点日志逐笔 | 按上面公式逐笔核 |

- **认型号（model swap）**：发 `max_tokens: 9999999`，Claude 上游 400 报错里带真实模型名（「maximum allowed … for <模型>」），官方同发一遍对照。**直连官方 Claude API 时这个 400 免费；经中转当可能付费**（见下「400 也换渠道重试」、`new-api.md` 预扣）：先发一次、读供应商日志 `quota`，没扣再重复。**这招只对 Claude 有效**（Gemini 夹住不报错、OpenAI Responses 照常成交扣费，见 `gemini.md`、`text-checks.md`）。
- 超大 max_tokens 被中间层用 OpenAI 口吻拦（如 `max_output_tokens_exceeded`、不带型号名）时，改用自定义工具的 input_tokens 认型号：工具说明按型号注入的 token 数不同。
- 有官方 key 时并排测（同一请求体发两边）：每个型号两边 `input_tokens` **期望逐个相等**，分词器不同的新型号也要对上。容差：官方文档说 count_tokens 是估计值、实际可能「differ by a small amount」，且可能含官方自动加、不计费的 token（[Token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting)，2026-10-23 读）；实践中同一型号、一字不差的提示词是逐个相等的。固定小差（如每单都 +4）= 模板差异；差得大或不成常数 = 加了提示词或换了模型。
- 「只写像某一代」不算结论；「字段一致」要程序求差集（规则 12）。

## 对账与计数
- 比的是**中转真实请求的 usage**（`input_tokens + cache_creation + cache_read`，中转可能自动加缓存断点）对官方 `count_tokens`，提示词一字不差；别拿中转自己的 count_tokens 比（可能不注入、和官方相等，真实请求却多）。
- 分词器（[Token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting)，2026-10-23 读）：4.7 及更新的型号用新分词器，同一文本约多 30%；Fable 5 / 5.1 与 Mythos 5 / 5.1 共用 Opus 4.7 引入的分词器、同一提示词计数相同。**官方 key 实测和这句对不上**：fable-5 16 / 1,291、fable-5-1 18 / 1,289、opus-4-7 21 / 1,681，10-19 / 10-22 / 10-23 三次一致、10-29 原样重发仍一致（上表）——以实测为准，这几个型号同一提示词的计数确实不同（原因未查，可能是每个型号的固定包装不同）；拿数判型号时按上表逐型号比。count_tokens 免费，但有每分钟请求数限制。
- 先用免费的 `count_tokens` 定前缀大小再报价：「随机词 + 数字」拼 4200 词实际约 20K token，按词数估会低估约 4 倍。
- 一套官方并排测（可用性 / 参数 / 丢字段 / 缓存 / 延迟 / 并发）官方侧花费在 $1 以内量级（2026-10-12 实测）。
- 429 不计费；缺 `max_tokens` 或 `max_tokens:0` 在 new-api 会被补默认值而成交，不是免费探针。
- 没有官方 key 时，「官方错误行为」只能写文档行为，报告里要写明。

## 中转常见问题（匿名案例）
- **静默删字段**：某 new-api 中转把 `inference_geo`、`speed`、`service_tier` 和未知字段都删掉——合法值同样到不了上游，客户要求的「美国境内推理」会静默失效。
- **流式和非流式差很大**：某 Bedrock 中转非流式约 2.4 s，流式首字 3.6–34 s；两种都要测、配对测。

## 经 OpenAI 格式转换
- 请求体做成两边共享的模块，让付费请求和官方 count_tokens 用同一份请求体（差一个字就不可比）。
- new-api 日志 `other.request_conversion` = `["Claude Messages","OpenAI Compatible"]` 就是站内把 Claude 请求转成 OpenAI 格式发上游再转回来（名字带 AWS 也可能回一方 id）。这类线路必测、实测都坏过：
  1. 非流式工具参数：`tool_use.input` 成 `{}`；OpenAI 口看 `arguments` 是不是合法 JSON（上游把起始空 input 和 partial_json 拼成 `{}{"city":…}`）；流式单独测。
  2. 官方内置工具：带 text_editor 后 input_tokens 应多约 1270，没多 = 被删。
  3. `cache_control`：同前缀连发，写入 / 命中全 0 = 不生效。
  4. stop_sequence 命中却报 `end_turn`。
  5. 思考块没有 `signature`。
- **同一分组混多个后端**：每个请求都要归类，别只看第一单。按回包分：`msg_bdrk_` + model = 请求名 = 原生 Bedrock；带 `provider` / `usage.cost` / `is_byok` / `cost_details.upstream_inference_cost` 且 `model:"anthropic/claude-x.y"` = OpenRouter 格式（`provider` 写真实后端，见过 `Claude Platform on AWS` / `Anthropic` / `Amazon Bedrock`）；`msg_vrtx_` = Vertex。同一型号连发约 20 单看比例。new-api 站响应头 `x-oneapi-request-id` = 日志 `request_id`，日志 type 2 那条有渠道号（同 request_id 的 type 7 是重试）。
- **400 也换渠道重试**：new-api 日志 type 7 = 重试失败、`other.retry_count`；非法请求 10–180 秒才报错，还可能被宽松后端接下（`max_tokens:128001` 回 200）——这类站点超大 max_tokens 探针不是免费的。
- 后端轮换会让缓存反复写入（实测连写 3 次才命中），缓存测试多发几轮。
- **判两个分组是不是同一上游账号**：价不同但看不出区别时，A 组发一个带新 nonce 的长前缀写缓存，紧接着 B 组首次发同一前缀——B 组第一次就命中 A 组写下的缓存 = 同一账号（缓存按组织隔离；2026-10-22 实测有效）。
- 超大 max_tokens 被中间层拦下时，顺手拿官方 OpenAI 兼容口（400 免费）发同一输入：报错原文和中转不同 = 不是官方兼容口直连。

## 接入网关要求
- 要求透传：`inference_geo` / `service_tier` 等顶层字段、`cache_control`、官方内置工具、思考 `signature`、stop_sequence 原样的 `stop_reason`、非流式的 `request-id` 与限流头。
- 报错要是官方外壳 JSON、带 `request_id`、状态码在官方表内；中转自造的错误（非 JSON、503 + api_error、429 无 `retry-after`）要在报告列出。
- 回包多了只有带某 beta 头才有的字段 = 中转改了上游 beta 头（推断，需对照文档确认）。
