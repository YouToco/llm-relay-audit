# Qwen3.8 文本线路基准（阿里百炼）

> Last verified: 2026-10-28（百炼北京官方 key 实测）；价目 2026-10-29。价格与行为以官方文档为准。
> 通用判真伪见 `text-checks.md`；百炼托管别家模型（如 glm-5.3）的报错外壳见 `glm.md`。

## 官方接口与响应
- 百炼北京 OpenAI 兼容口 `POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`，Bearer；业务空间专属域名（`ws-<空间号>.cn-beijing.maas.aliyuncs.com`）是同一套接口。`/compatible-mode/v1/models` 免费（实测 183 个，qwen3.8 系有 flash / max / max-0902 / 27b / omni-flash 等）。
- 回包：顶层只有 `choices, created, id, model, object, usage`；id `chatcmpl-<uuid>`；tool call id `call_<24 位 hex>`，arguments 带空格 `{"city": "Shenzhen"}`。
- usage：`prompt_tokens_details{cached_tokens, text_tokens, image_tokens}`、`completion_tokens_details{reasoning_tokens, text_tokens}`。
- 响应头：`x-request-id`、`req-cost-time`、`x-envoy-upstream-service-time`、`server: istio-envoy`；无限流头。
- **默认开思考**，思考在 `message.reasoning_content`；`enable_thinking: false` 关；`enable_thinking: true` 非流式也能用。**`max_tokens` 只限正文、不限思考**（16 → completion 82、其中思考 61，`finish: length`）——和 MiniMax 相反。
- 报错外壳 `{"error":{"code":"invalid_parameter_error","param":null,"message","type":"invalid_request_error"},"id":"chatcmpl-…"}`：`temperature: 5`「Temperature should be in [0.0, 2.0)」；`role: robot`「robot is not one of ['system', 'assistant', 'user', 'tool', 'function']」；缺 messages「Role must be in ["user", "assistant", "system", "function", "plugin", "tool"] and the …」。

## 官方实测（2026-10-28，同一批请求体）
| 用例 | flash prompt / completion（思考） | max prompt / completion（思考） |
|---|---|---|
| hi（默认开思考） | **62** / 44（29） | **62** / 24（12） |
| hi + `enable_thinking: false` | **26** / 9 | **13** / 6 |
| ok + system | 64 / 38（34） | 64 / 29（26） |
| tool（get_weather） | 323 / 55 → `tool_calls` | 323 / 43 → `tool_calls` |
| json_object | 74 / 39 | 74 / 45 |
| multiturn | 89 / 45 | 89 / 115 |
| max_tokens 16 | 73 / 82（61）`length` | 73 / 55（36）`length` |
| image url（1920×1088） | 2,110（图 2,042） | 2,072（图 2,042） |

- **开思考时 prompt 多算一截**（flash「Hi」62 vs 关思考 26，max 62 vs 13）——比 token 时两边思考开关要一致。
- 首字参照（国内，flash 关思考流式 ×10）：p50 0.86 s、p90 1.2 s。
- 没测：长上下文、缓存命中、DashScope 原生接口（`/api/v1/services/aigc/text-generation`）、国际站（新加坡）。

## 价目（[百炼价目页](https://help.aliyun.com/zh/model-studio/model-pricing) 2026-10-29 读；国际站 [alibabacloud.com](https://www.alibabacloud.com/help/en/model-studio/model-pricing)）
| 模型（每百万 token，≤ 1M，思考 / 非思考同价） | 北京（元） | 新加坡（USD） |
|---|---|---|
| qwen3.8-max | 输入 12 / 输出 36 | 2 / 6 |
| qwen3.8-flash | 0.8 / 2.7 | 0.15 / 0.47 |
- 页注「本文仅展示模型调用原价」，活动价看控制台。显式缓存创建按输入价 125%、命中 10%；Batch 与缓存折扣不叠加。

## 判真伪要点
1. 同一请求体、同一思考开关比 prompt_tokens（上表）；多出固定数 = 注入，见 `text-checks.md`。
2. 报错原文对上百炼外壳（`invalid_parameter_error` + 回包 id）= 背后是百炼；响应头 `req-cost-time` 一类是网关加的，**不能单凭它认百炼**（`glm.md`「其它托管 / 自建后端」）。
3. `max_tokens` 小值时看 completion 是否超出 max_tokens（官方思考不受限、会超）；中转把思考也算进上限 = 改写了请求或不是百炼。

## 接入网关要求
- usage 要带 `reasoning_tokens`，思考按输出价；`max_tokens` 不限思考，网关按 max_tokens 估费会低估。
- 默认开思考：客户没写 `enable_thinking` 时 prompt 和输出都比关思考多，计价和客户文档要写明。
