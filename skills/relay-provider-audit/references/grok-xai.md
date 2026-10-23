# Grok（xAI 文本）线路基准

> Last verified: 2026-10-12；价格与行为以官方文档为准。
> 流程同 `claude.md`：免费探针 → 报价 → 付费矩阵 → 逐笔对账 → 报告。通用判真伪见 `text-checks.md`，订阅号池判法见 `sub2api.md`。

## 官方接口与响应
- 文档：`docs.x.ai`；三种协议都有：Responses（`/v1/responses`）、Chat Completions（`/v1/chat/completions`）、Anthropic 兼容 Messages。
- **格式**：响应 id 是裸 UUID；子项 `rs_<uuid>_us-east-1` / `msg_<uuid>_us-east-1`；`system_fingerprint` = `fp_` + 10 位，只在 chat 有。
- 错误是扁平 `{"code": "...", "error": "..."}`（不是 OpenAI 的 `{"error":{...}}`）。
- 推理模型传 `stop` 报错；`max_output_tokens` 只限可见文字（推理照算）；`store` 默认 true，可用 `previous_response_id` 续聊。
- **usage 口径**（docs.x.ai 示例）：`completion_tokens` / `output_tokens` **不含**推理 token，`total = 输入 + 输出 + 推理`；和 OpenAI 相反。
- 回包 `usage.cost_in_usd_ticks`（1e10 ticks = $1），可逐笔核：`(未缓存输入×输入价 + 缓存×缓存价 + 输出×输出价) × 1e4`（价按每百万 token）。
- **只在 Grok Build 订阅里有的型号**：`grok-composer-2.5-fast`、Grok 4.7 Fast——公共 API key 调不到，中转站卖它 = 订阅号池的强证据。

## 价目（2026-10-12，以 docs.x.ai 价目页为准）
- grok-4.7：输入 $2 / 缓存 $0.5 / 输出 $6（每百万 token）；grok-4.5：$2 / $0.3 / $6。
- 单次请求 ≥200K token 整单翻倍。

## token 固定范围（官方 key 实测 2026-10-03，chat/completions）
| 型号 | 空消息 | "Hi" | 缓存命中 |
|---|---|---|---|
| grok-4.7 | 1,242 | 1,243 | 1,152 |
| grok-4.5 | 494 | 495 | 384 |
| grok-4.3 | 192 | 193 | 128–192 |

- **官方 grok 自带内置提示词**，一句新话也命中 1,152 缓存——不要当成「中转拼了隐藏提示词」。
- 缓存数可用来**判路径**：1,152 vs 192 说明落在不同型号 / 不同来源上。

## 判真伪检测矩阵
| 阶段 | 测什么 | 判据 |
|---|---|---|
| 免费探针 | 首页 / 前端 JS（站点身份、管理接口）、`/v1/models`、错 key、不存在的模型、越界参数 | Grok2API 类软件先校验参数再校验模型：合法请求 + 没开的模型 = 404 不扣费 |
| tok | chat 空消息 / "Hi"、responses / messages "Hi"、随机码短句 | 对上表官方固定范围；看缓存数判路径 |
| leak | 空输入 ×2、让它复述上文、自报身份 | 看回答风格；自报身份不可信 |
| proto | responses / chat / messages × 流式 / 非流式 | 首字节 vs 首字（假流式 = 首字节很晚、整段一次到）、推理摘要事件 |
| feat | system、多轮、三协议函数调用、图片、json_schema、推理档位、stop、`previous_response_id` | 与官方文档对照 |
| native | `code_interpreter` 算随机码 SHA-256、`x_search`、`web_search` | `num_server_side_tools_used > 0` 且哈希对上才算 |
| cache | 约 1,900 token 随机前缀 + `prompt_cache_key` 连发 4 轮 | 第 2 轮起命中 |
| conc | 顺序 2 次 + 5 / 10 路流式 | 首字按路径分开看 |

## 对账与计数
- **grok-4.7 默认推理 high**：一句 "Hi" 也有 30–50 推理 token；空输入、或给它用不了的工具，能推理上千 token（一次 `x_search` 实测 3,856 token、约 $0.023）。报价按每次约 $0.01 估。
- 逐笔对账用 `cost_in_usd_ticks` 公式；但中转回包里的 `model` 和 `cost_in_usd_ticks` 可能是站点自己填的，只能辅助，不能单独当真伪证明。

## 中转常见问题（匿名）
- 订阅号池会**按内容粘账号**：同一句话总落同一条路径，想测另一条路径要换内容重发（看缓存数确认）。
- 站点会改写请求：自己填 `prompt_cache_key`、把 `store` 固定成 false（`previous_response_id` 续聊因此失效，推断）。
- 假流式：首字节很晚、内容一次性到达。

## 接入网关要求
- usage 按 xAI 口径（输出不含推理）换算成网关计费口径，别按 OpenAI 口径直接加总。
- 错误外壳是扁平格式，网关要能解析 `code` / `error`。
- 订阅号池线路（卖订阅专属型号、按内容粘账号）在报告里单独标明来源风险。
