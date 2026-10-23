# OpenAI（文本）线路基准：一方 API / Azure OpenAI / Bedrock 托管 / Codex 后端

> Last verified: 2026-10-23（官方文档部分）；价格与行为以官方文档为准。标「实测观察」的是经中转看到、文档里没有的现象，只能当线索。
> 通用判真伪见 `text-checks.md`；new-api 站点的日志 / 价目接口见 `new-api.md`；非功能项见 `nonfunctional-checks.md`。

来源（2026-10-23 读；OpenAI 文档页在 URL 后加 `.md` 可取 Markdown 版）：
[API overview](https://developers.openai.com/api/reference/overview)（认证、调试响应头、兼容性约定）、
[Responses create](https://developers.openai.com/api/reference/resources/responses/methods/create)、
[Input token counts](https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens) 与 [Counting tokens 指南](https://developers.openai.com/api/docs/guides/token-counting)、
[Chat Completions 对象](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/retrieve)、
[Error codes](https://developers.openai.com/api/docs/guides/error-codes)、[Rate limits](https://developers.openai.com/api/docs/guides/rate-limits)、[Reasoning](https://developers.openai.com/api/docs/guides/reasoning)、[Pricing](https://developers.openai.com/api/docs/pricing)；
Azure：[v1 API](https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle)（页面日期 2026-05-13）、[REST 参考](https://learn.microsoft.com/en-us/azure/foundry/openai/reference)（2026-05-19）、[内容筛选注释](https://learn.microsoft.com/en-us/azure/foundry-classic/openai/concepts/content-filter-annotations)（2026-01-15）；
Bedrock：[AWS Responses API](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-responses-api.html)、[OpenAI 的 Bedrock 指南](https://developers.openai.com/api/docs/guides/amazon-bedrock)。

## 官方接口与响应

- 地址 `https://api.openai.com/v1`，`Authorization: Bearer <key>`；多组织 / 多项目时可带 `OpenAI-Organization` / `OpenAI-Project` 头。
- **Responses**：`POST /v1/responses`。响应 `object: "response"`，id 形如 `resp_<十六进制>`（文档示例 `resp_` 后 48 位 hex），输出消息项 `msg_…`、推理项 `rs_…`。顶层字段（文档示例）：`id` `object` `created_at` `status` `completed_at` `error` `incomplete_details` `instructions` `max_output_tokens` `model` `output` `parallel_tool_calls` `previous_response_id` `reasoning` `store` `temperature` `text` `tool_choice` `tools` `top_p` `truncation` `usage` `user` `metadata` 等——字段会增加，**当天取文档程序求差集**（规则 12）。
  - `usage`：`input_tokens`、`input_tokens_details.{cached_tokens, cache_write_tokens}`、`output_tokens`、`output_tokens_details.reasoning_tokens`、`total_tokens`。
  - 推理 token 计入 `output_tokens`、**按输出价计费**（Reasoning 指南）——和 xAI 口径相反（`grok-xai.md`）。
  - `max_output_tokens` 限的是「可见输出 + 推理」总数；到上限回 `status: "incomplete"` + `incomplete_details.reason: "max_output_tokens"`，可能一个可见字都没有却已经花了输入和推理的钱。`reason` 还可能是 `content_filter` 等。
- **Chat Completions**：`POST /v1/chat/completions`。id `chatcmpl-…`，`object: "chat.completion"`，可选 `system_fingerprint`；`usage` = `prompt_tokens` / `completion_tokens` / `total_tokens` + `prompt_tokens_details.{cached_tokens, cache_write_tokens, audio_tokens}` + `completion_tokens_details.{reasoning_tokens, accepted_prediction_tokens, rejected_prediction_tokens, audio_tokens}`。
- **`service_tier`**：回包写**实际使用的**处理档位，可能和请求值不同；请求 `fast` 或 `priority`，回包都显示 `priority`。项目不允许该档位时回 400「Invalid `service_tier` argument」（`param: service_tier`）。
- **免费计数**：`POST /v1/responses/input_tokens`，请求体和 Responses 一样（文本、图片、文件、工具、会话都能算），回 `{"object":"response.input_tokens","input_tokens":N}`。指南说它返回模型实际收到的确切数（含角色 / 边界等格式 token）；**文档没写是否计费**——第一次用时看一眼官方账单确认（规则 2：拿不准当付费）。
- **输出 token 有不可见部分**（Counting tokens 指南）：GPT-5 等型号会生成格式 / 通道分隔 token，不出现在正文和 `logprobs` 里，所以 `output_tokens` 可能比可见文字多，**即使 `reasoning_tokens` 是 0**，且差值随型号和响应形状变。→ 判「输出 token 虚报」不能拿可见文字重数，要和官方同请求的 usage 比（`nonfunctional-checks.md`）。
- **响应头**（API overview）：`openai-organization`、`openai-processing-ms`、`openai-version`（当前 `2020-10-01`）、`x-request-id`；限流头 `x-ratelimit-{limit,remaining,reset}-{requests,tokens}`，有项目级 token 限额时再加 `x-ratelimit-{limit,remaining,reset}-project-tokens`。
  - 请求头 `X-Client-Request-Id`：自己给的 id，只许 ASCII、≤ 512 字符，否则 **400**——可做免费探针：发一个 513 字符的值，官方 400；中转 200 = 它没把这个头传上去。
- **错误外壳** `{"error":{"message","type","param","code"}}`。Error codes 页：401（认证无效 / key 错 / 不在组织 / IP 不在白名单）、403 地区不支持、429（限速；`credit_balance_exhausted`、`slow_down`、`organization_spend_limit_exceeded` 等用 `error.code` 区分，`error.type` 可能仍是 `insufficient_quota`）、500、503 `server_is_overloaded`；429 / 503 **有 `Retry-After` 时**按它等。
- **id 格式别当硬证据**：API overview 把「改变资源 id 等不透明字符串的长度或格式」列为向后兼容的改动，OpenAI 随时可以换。

## 价目

- 只认 [官方价目页](https://developers.openai.com/api/docs/pricing)，**以官方页为准、按当天读并记日期**；本文不抄价。2026-10-23 的页面按短 / 长上下文分档，另列缓存命中、缓存写入价，按处理档位分表——中转报价要落到具体型号 × 档位 × 上下文长度再比。
- 推理 token 按输出价；缓存命中看 `cached_tokens`，写入看 `cache_write_tokens`。[Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)（GPT-5.6 及以后）：写入默认 30 分钟 = 输入价 ×1.25，Responses 可选 12 小时 ×2.5；命中多数型号 ×0.1（个别 ×0.05）；最小可缓存 1,024 token。
- Bedrock 托管：OpenAI 指南写商业区价格**与 OpenAI 直连同类服务一致**，用 Bedrock 的单地域服务按 OpenAI API 的 Regional processing 价算（具体数以 AWS / OpenAI 价目页为准）。

## Azure OpenAI 的差异

- **v1 API**（2025-08 起可选用）：`https://<资源名>.openai.azure.com/openai/v1/`（也收 `<资源名>.services.ai.azure.com/openai/v1/`），**不再需要 `api-version`**；鉴权 `api-key: <key>` 头或 Entra `Authorization: Bearer`；请求里的 `model` 填**部署名**（不是 OpenAI 型号名）。
- **旧写法**（仍常见，中转多半模仿它）：`POST https://<资源名>.openai.azure.com/openai/deployments/<部署名>/chat/completions?api-version=YYYY-MM-DD`，头 `api-key`。看到 `api-version` 查询参数 / `deployments/` 路径的报错 = 背后是 Azure。
- **内容筛选字段**（Azure 独有，OpenAI 一方没有）：回包顶层 `prompt_filter_results[]`（每项 `prompt_index` + `content_filter_results`），`choices[].content_filter_results`；类别 `hate` / `sexual` / `violence` / `self_harm`（`filtered` + `severity`）、`jailbreak`（`detected` + `filtered`）、`protected_material_text` / `protected_material_code`（`detected` + `filtered`，code 带 `citation`）、`profanity` 等。提示词被拦 → 400，`error.code: "content_filter"`，详情在 `error.innererror.content_filter_results`；输出被拦 → `finish_reason: "content_filter"`。
  - 判后端：回包带这些字段 = Azure（或中转没剥干净）；卖「OpenAI 官方」却有它们 = 背后是 Azure。中转把它们剥掉也常见，没有不能证明不是 Azure。
  - Azure 的筛选比 OpenAI 一方严、且按部署可配：同一提示词 Azure 拒、OpenAI 不拒不算中转的毛病（`text-checks.md`「背后是云平台」）。
- **响应头**（实测观察，未见文档列明）：`apim-request-id`、`x-ms-region`、`azureai-fe-offer-type: paygo`、`x-ratelimit-remaining-tokens`（剩余 TPM 很小 = 容量紧，推断）。new-api 系通常把上游头剥光，要看 body。
- **body 特征**（实测观察，未见文档）：`usage.latency_checkpoint`（engine / service ttft、pre_inference）、流式 `obfuscation` 字段、`system_fingerprint`。

## Bedrock 托管的 OpenAI

- 两个端点：`https://bedrock-runtime.<区>.amazonaws.com/openai/v1`（AWS 推荐）和 `https://bedrock-mantle.<区>.api.aws/v1`（兼容端点，部分型号路径是 `/openai/v1`）。
- **型号 id**：闭源 GPT 在 bedrock-runtime 上必须写系统推理配置 id，如 `us.openai.<型号>` / `global.openai.<型号>`（GovCloud 是 `us-gov.`），不能写基础型号 id；mantle 上写 `openai.<型号>`。回包 `model` 是这种形状 = 背后是 Bedrock。
- bedrock-runtime 没有 `GET /models`（要用 ListFoundationModels / ListInferenceProfiles）；只同步、没有服务端工具、`previous_response_id` 继承等行为和 mantle 不同；gpt-oss 的 Responses 只在 mantle 上（AWS 文档）。
- 实测观察（经中转）：`resp_` / `chatcmpl-` 后是 52 位小写 base32（一方是十六进制）；头带 `x-amzn-requestid`；`input_tokens` 和官方 `/v1/responses/input_tokens` 相等；图片只收 `data:` / `s3://`（http URL 400）、`priority` 回 `default`；`temperature=9` 照收成交——**这里它不是免费保险**，先用一个型号试。

## 认后端（OpenAI 一方 vs Azure vs Bedrock vs ChatGPT / Codex 后端）

第一个 200 就分类，**同一分组里可能混着几种，按模型、按请求逐个看**：

| 判据 | OpenAI 一方 | Azure | Bedrock | ChatGPT / Codex 后端（实测观察） |
|---|---|---|---|---|
| id | `resp_` / `chatcmpl-` + hex | `chatcmpl-…` | 52 位 base32 | `resp_…` |
| 特有字段 | `openai-*` 头（常被剥） | `prompt_filter_results`、`content_filter_results` | `model` = `global.openai.*` / `us.openai.*` | 回显 `instructions`「You are Codex…」、`usage.attribution` |
| 非法参数 | 400 官方外壳 | 400，可能带 `api-version` / 部署名 | 原文带 Bedrock 字样 | 参数被丢、照常 200 |

- **ChatGPT / Codex 后端**（订阅转 API，全部实测观察）：回显 `instructions`「You are Codex…」并在 `usage.attribution` 里给 instructions 计 token（每次约 4,380，照收）；丢 `max_output_tokens` / `temperature` / `top_logprobs`；`store` 强制 false；`previous_response_id` 回「not available for this user」；流式带 `openai_chatgpt_moderation`。
- `resp_` 后第 35–38 位（0 起）API 账户见到 `87d1`、ChatGPT / Codex 见到 `8191`——**推断，样本有限，不要单独作为真伪证据**（OpenAI 声明 id 格式可变，见上），只和上面的 instructions / 字段特征一起用。
- **故意发非法参数也要看 id**：见过 API 拒绝后改投 Codex 池（`temperature 9` → 200 + Codex 注入照收），或回 `resp_ft_…` 这种非 OpenAI 形状的 id——「官方 400、它 200」本身就是证据。
- 推理模型的规矩不是中转 bug：Chat 口推理型号用 `max_completion_tokens`（`max_tokens` 不收），函数工具要配合 `reasoning_effort` 或改走 Responses——先在官方核对再记差异。

## 判真伪招数是否有效

- **超大 `max_output_tokens` 逼型号名：无效，而且花钱**。官方 `max_output_tokens: 9999999` / `300000` 过校验、照常成交扣费（实测）——这是 Claude 专用招数（`claude.md`），对 GPT 别用。
- 有效：
  1. id 形状 + 特有字段（上表）。
  2. **输入 token**：同一请求体，供应商 usage 的 `input_tokens` vs 官方 `/v1/responses/input_tokens`（免费）。期望逐个相等；固定小差 = 模板 / 服务栈差；差几千且固定 = 注入（Codex instructions 约 4,380）。
  3. `X-Client-Request-Id` 超长 400（文档写明）、`service_tier` / 未知顶层字段的非法值（官方 400 是实测行为，先拿官方 key 核一次）：中转 200 = 字段被吞（规则 5：只让被测项非法）。
  4. 缓存：超过最小可缓存长度（GPT-5.6 及以后 1,024 token，更早型号随设置变）的固定前缀连发，第 2 次起 `cached_tokens` > 0；同站两组首发就命中 = 同一上游账号（推断，`new-api.md`）。
  5. 推理深度：同一题 `reasoning.effort` 各档比 `reasoning_tokens`，和官方同题比分布（单次会抖，各发 3 次）。
  6. 字段集合（顶层 / usage / 头 / SSE 事件名）程序求差集（规则 12）。

## 接入网关要求

- usage 要带 `input_tokens_details.cached_tokens` / `cache_write_tokens` 和 `output_tokens_details.reasoning_tokens`（Chat 口是 `prompt_tokens_details` / `completion_tokens_details`），否则缓存和推理没法对账；推理按输出价。
- 回包 `service_tier` 要原样透传（实际档位决定价格），`priority` 被降成 `default` 却按 priority 收是计费问题。
- 报错要是官方外壳、保留 `error.code`（区分限速 / 余额 / 花费上限）和 `Retry-After`；Azure 线要能识别 `content_filter` 400 与 `finish_reason: content_filter`，别当上游故障重试。
- Azure 线：网关要能配部署名映射和（旧写法时）`api-version`；Bedrock 线：型号名映射到 `global.` / `us.` 推理配置 id，图片要转成 `data:`。
- 订阅 / Codex 后端线路（instructions 注入照收、参数被丢、`store` 强制 false）在报告里单独标来源风险（`nonfunctional-checks.md`「法务与条款」）。

## 中转常见问题（匿名案例）

- **同一分组混后端**：一方 API、Azure、Codex 池混在同组，按模型分；非法参数请求会被改投到更宽松的池子。
- **Codex 注入照收**：每单多约 4,380 输入 token 按官方价收（instructions 计费），客户的 `temperature` / `max_output_tokens` 被丢。
- **超大 `max_output_tokens` 探针真成交**：把 Claude 那招用到 GPT 上，被按输出上限预扣或真生成长文。
- 生图分组见 `new-api.md`「图片输出」（C2PA 主体与指纹、转存到中转自己的存储）。
