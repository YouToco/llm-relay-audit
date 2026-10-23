# Claude（文本）线路基准：一方 API / Bedrock / Vertex / 经 OpenAI 格式转换

> Last verified: 2026-10-22；价格与行为以官方文档为准。
> 通用判真伪流程见 `text-checks.md`；new-api 站点的日志 / 价目接口见 `new-api.md`；订阅号池见 `sub2api.md`；探针技巧见 `probing-tips.md`。

## 官方接口与响应
- 文档：当天取 `platform.claude.com/docs/en/<页>.md`（Messages / Streaming / Errors / Rate limits / API overview / Token counting）；Bedrock 版见 AWS 文档「Anthropic Claude Messages API」页（`docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html`）。
- **id 前缀认后端**：一方 API = `msg_011C…`（请求 id `req_011C…`）；Bedrock = `msg_bdrk_…`；Vertex = `msg_vrtx_…`。分组名 / 模型名带「AWS」「Bedrock」「官转」都不算证据，以 id 为准。
- **一方 API 的身份证据**：非流式响应头有 `request-id`、`anthropic-organization-id`、`anthropic-ratelimit-*`；多发几单数一下出现几个不同的组织 id，多个 = 号池。注意 new-api 流式响应不透传上游头，要看非流式。
- usage：`input_tokens`、`output_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`，以及 `cache_creation.ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens`。
- 思考：4.7 及更新的型号默认不回思考摘要，要 `thinking.display:"summarized"` 才有；思考块必须带 `signature`。新型号不支持 assistant 预填，回 400 是正常行为。
- 免费调用：`/v1/messages/count_tokens`、`/v1/models`、参数校验类 400。官方还有 OpenAI 兼容口 `api.anthropic.com/v1/chat/completions`（400 也免费），可拿同一输入对比报错原文。
- 报错：外壳 `{"type":"error","error":{"type":"…","message":"…"},"request_id":"req_…"}`；状态码与 `error.type` 对应关系以 Errors 页为准，429 带 `retry-after`。
- `inference_geo`、`speed`、`service_tier` 等是顶层合法字段；非法值官方必回 400。合法 `inference_geo:"us"` 回「not supported for this organization type」= 消费者订阅组织（Pro / Max），不是 API 组织（判订阅号池，免费）。

## 价目
- 以 `platform.claude.com/docs/en/about-claude/pricing` 为准（取当天）。缓存：5 分钟写入 = 输入价 ×1.25，1 小时写入 ×2，命中 = 输入价 ×0.1。
- new-api 站点的公式（软件默认）：`quota = (输入 + 命中×cache_ratio + 写入×1.25 + 输出×completion_ratio) × model_ratio × group_ratio`，quota 500000 = $1；`/api/pricing` 免登录可取 `model_ratio` / `group_ratio`，和官方价相除得倍率。
- 站点美元 ↔ 人民币看充值档位，查不到汇率就别判贵贱。

## 判真伪检测矩阵
| 阶段 | 测什么 | 判据 |
|---|---|---|
| 免费探针 | `/v1/models`、`/api/pricing`、`/api/log/token`、错 key、非法参数 | 价目公式 vs 官方价；倍率 |
| avail | 每个模型 1 次 | 回包 `model` = 请求名；id 前缀；有无 429 |
| proto | `/v1/messages` 与 `/v1/chat/completions`，各非流 + 流式 | 事件序列、usage 位置、首字耗时 |
| feat | system、多轮、tool_use 往返、图片、stop_sequences、thinking（`display:summarized`）、json_object、预填 | 与官方一致 |
| auth | 短提示词查隐藏前缀 + 官方内置工具 `text_editor_20250728` | 短提示 input 应很小（约 30）；带 text_editor 应多约 700–1300（按型号不同） |
| drops | 每个顶层字段给非法值 | 官方必 400；中转回 200 = 字段被网关删了 |
| cache | system 块 `cache_control` 连发 5 轮 | 第 1 轮写入、后面命中；看 `cache_creation.ephemeral_5m` |
| conc | 顺序基线 + 5 / 10 路并发 | 首字、是否 429 |
| 对账 | 站点日志逐笔 | 按上面公式逐笔核 |

- **认型号（model swap）**：发 `max_tokens: 9999999`，Claude 上游 400 报错里带真实模型名（「maximum allowed … for <模型>」），400 不扣费，官方同发一遍对照。**这招只对 Claude 有效**（Gemini 夹住不报错、OpenAI Responses 照常成交扣费，见 `gemini.md`、`text-checks.md`）。
- 超大 max_tokens 被中间层用 OpenAI 口吻拦（如 `max_output_tokens_exceeded`、不带型号名）时，改用自定义工具的 input_tokens 认型号：工具说明按型号注入的 token 数不同。
- 有官方 key 时并排测（同一请求体发两边）：每个型号两边 `input_tokens` 必须逐个相等，分词器不同的新型号也要对上；不等 = 加了提示词或换了模型。
- 「只写像某一代」不算结论；「字段一致」要程序求差集（规则 12）。

## 对账与计数
- 比的是**中转真实请求的 usage**（`input_tokens + cache_creation + cache_read`，中转可能自动加缓存断点）对官方 `count_tokens`，提示词一字不差；别拿中转自己的 count_tokens 比（可能不注入、和官方相等，真实请求却多）。
- 先用免费的 `count_tokens` 定前缀大小再报价：「随机词 + 数字」拼 4200 词实际约 20K token，按词数估会低估约 4 倍。
- 一套官方并排测（可用性 / 参数 / 丢字段 / 缓存 / 延迟 / 并发）官方侧花费在 $1 以内量级（2026-10-12 实测）。
- 429 不计费；缺 `max_tokens` 或 `max_tokens:0` 在 new-api 会被补默认值而成交，不是免费探针。
- 没有官方 key 时，「官方错误行为」只能写文档行为，报告里要写明。

## 中转常见问题（匿名案例）
- **静默删字段**：某 new-api 中转把 `inference_geo`、`speed`、`service_tier` 和未知字段都删掉——合法值同样到不了上游，客户要求的「美国境内推理」会静默失效。
- **流式和非流式差很大**：某 Bedrock 中转非流式约 2.4 s，流式首字 3.6–34 s；两种都要测、配对测。

## 经 OpenAI 格式转换
- new-api 日志 `other.request_conversion` = `["Claude Messages","OpenAI Compatible"]` 就是站内把 Claude 请求转成 OpenAI 格式发上游再转回来（名字带 AWS 也可能回一方 id）。这类线路必测、实测都坏过：
  1. 非流式工具参数：`tool_use.input` 成 `{}`；OpenAI 口看 `arguments` 是不是合法 JSON（上游把起始空 input 和 partial_json 拼成 `{}{"city":…}`）；流式单独测。
  2. 官方内置工具：带 text_editor 后 input_tokens 应多约 1270，没多 = 被删。
  3. `cache_control`：同前缀连发，写入 / 命中全 0 = 不生效。
  4. stop_sequence 命中却报 `end_turn`。
  5. 思考块没有 `signature`。
- **同一分组混多个后端**：每个请求都要归类，别只看第一单。按回包分：`msg_bdrk_` + model = 请求名 = 原生 Bedrock；带 `provider` / `usage.cost` / `is_byok` / `cost_details.upstream_inference_cost` 且 `model:"anthropic/claude-x.y"` = OpenRouter 格式（`provider` 写真实后端）；`msg_vrtx_` = Vertex。同一型号连发约 20 单看比例。new-api 站响应头 `x-oneapi-request-id` = 日志 `request_id`，日志 type 2 那条有渠道号（同 request_id 的 type 7 是重试）。
- **400 也换渠道重试**：new-api 日志 type 7 = 重试失败、`other.retry_count`；非法请求 10–180 秒才报错，还可能被宽松后端接下（`max_tokens:128001` 回 200）——这类站点超大 max_tokens 探针不是免费的。
- 后端轮换会让缓存反复写入（实测连写 3 次才命中），缓存测试多发几轮。

## 接入网关要求
- 要求透传：`inference_geo` / `service_tier` 等顶层字段、`cache_control`、官方内置工具、思考 `signature`、stop_sequence 原样的 `stop_reason`、非流式的 `request-id` 与限流头。
- 报错要是官方外壳 JSON、带 `request_id`、状态码在官方表内；中转自造的错误（非 JSON、503 + api_error、429 无 `retry-after`）要在报告列出。
- 回包多了只有带某 beta 头才有的字段 = 中转改了上游 beta 头（推断，需对照文档确认）。
