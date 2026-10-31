# MiniMax 文本线路基准（MiniMax-M3.1-Flash / MiniMax-M3）

> Last verified: 2026-10-28（MiniMax 国际站官方 key 实测）；价目 2026-10-29。价格与行为以官方文档为准。
> 通用判真伪见 `text-checks.md`；MiniMax 视频见 `minimax-h3.md`。

## 官方接口与响应
- 国际站 `https://api.minimax.io`，OpenAI 兼容 `POST /v1/chat/completions`，`Authorization: Bearer`；`/v1/models` 列出 MiniMax-M3.1-Flash、MiniMax-M3、MiniMax-M2.7、M2.7-highspeed 等。
- **一句「Hi」就是 186–203 prompt token**：官方在前面加了约 200 token 的固定系统提示（M3.1-Flash 比 M3 多约 17）。中转的 prompt 少了这一截 = 不是官方直出。
- **思考写法两个型号不同**：M3.1-Flash 放 `message.reasoning_content`（`content` 干净）；**M3 把思考写在 `content` 开头的 `<think>…</think>` 里**。两者 `completion_tokens_details.reasoning_tokens` 都有，**思考计入 `max_tokens`**（16 全用在思考上 → 正文空，`finish: length`）——和 Qwen 相反。
- 响应字段：顶层多 `base_resp`、`input_sensitive(_type)`、`output_sensitive(_int/_type)`（M3 多 `service_tier: "standard"`）；message 有 `name: "MiniMax AI"`、`audio_content: ""`（M3.1-Flash）。id 32 位 hex；usage 带 `total_characters: 0`。tool call id：M3.1-Flash `call_<24 位 hex>`，M3 `call_<24 位大小写混排>`。
- 响应头：`Minimax-Request-Id`、`Trace-Id`、`X-Mm-Request-Id`、`X-Session-Id`、`alb_request_id`；无限流头。
- **自动缓存**：同前缀第二次 `cached_tokens` 128–256。
- **参数校验很松**：`temperature: 5` **不报错、照常出字并计费**——不能当免费探针。报错外壳 `{"type":"error","error":{"type":"bad_request_error","message":"invalid params, … (2013)","http_code":"400"},"request_id"}`：`role: robot`「invalid role: robot (2013)」；缺 messages「binding: expr_path=messages, cause=missing required parameter (2013)」；不存在的模型「unknown model '<名>' (2013)」（模型名被转成小写）。

## 官方实测（2026-10-28，同一批请求体，和 `qwen.md` 共用）
| 用例 | M3.1-Flash prompt / completion（思考） | M3 prompt / completion（思考） |
|---|---|---|
| hi | **203** / 31（19） | **186** / 53（43） |
| ok + system | 208 / 3（0） | 204 / 12（8） |
| tool（get_weather） | 436 / 36（0）→ `tool_calls` | 432 / 40（0）→ `tool_calls` |
| json_object | 213 / 7 | 196 / 58（52） |
| multiturn | 227 / 33（29） | 210 / 40（38） |
| max_tokens 16 | 213 / 16（15）`length`，正文空 | 209 / 16（15）`length` |
| image url（1920×1088） | 2,902 / 84 | 2,896 / 107 |

- 没测：长上下文（> 512K 档）、缓存命中计费、Anthropic 兼容口、M2.7 系列。

## 价目（[platform.minimax.io 价目页](https://platform.minimax.io/docs/guides/pricing-paygo) 2026-10-29 读，USD / 百万 token，Standard；页面没写更新日期）
| 模型 | 输入 | 输出 | 缓存读 |
|---|---|---|---|
| MiniMax-M3.1-Flash | 0.15 | 0.60 | 0.015 |
| MiniMax-M3（≤ 512k 输入），标「Permanent 50% off」 | ~~0.60~~ **0.30** | ~~2.40~~ **1.20** | ~~0.12~~ **0.06** |
| MiniMax-M3（> 512k 输入），同上 | ~~1.20~~ **0.60** | ~~4.80~~ **2.40** | ~~0.24~~ **0.12** |

## 判真伪要点
1. 「Hi」prompt 少了约 200 token 的固定系统提示 = 不是官方直出；多出固定数 = 中转又加了注入。
2. M3 思考在 `content` 的 `<think>` 里：中转把它挪到 `reasoning_content` 或剥掉 = 改写了输出（不一定是坏事，但要写进报告）；M3.1-Flash 的 `content` 出现 `<think>` = 不是官方 M3.1-Flash。
3. 顶层 `base_resp` / `input_sensitive` / `output_sensitive` 字段、32 位 hex id 是官方特征，字段集合程序求差集（规则 12）。

## 接入网关要求
- 思考计入 `max_tokens`：客户给小 max_tokens 会拿到空正文、仍按思考计费，文档要写明。
- M3 的 `<think>` 在 `content` 里，网关要么透传、要么统一拆到 `reasoning_content`，别让客户看到时有时无。
- 官方挂牌价有「Permanent 50% off」划线价：核供应商倍率时用折后实付价。
