# Gemini 文本线路基准（AI Studio / Vertex）

> Last verified: 2026-10-19；价格与行为以官方文档为准。
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
- token 口径小差：flash 同一句 Vertex 少 1、64×64 图少 29；argon 文本逐个相等。差值固定且各组一致就不算注入。
- **argon 长文（无工具）Vertex 回 `toolUsePromptTokenCount` ≈ 输入**；若中转把它计入输入，约两倍计费——报价时长上下文按 ×2 估。

## 价目（2026-10-15，以 ai.google.dev 价目页为准）
- gemini-4-argon 标准：输入 $2 / 输出 $10 / 缓存 $0.10（每百万 token）；**2026-12-01 起翻倍**为 $4 / $20 / $0.20。
- Batch / Flex 半价、Priority 1.8×；无 >200k 阶梯；只有隐式缓存。

## 判真伪检测矩阵
| 检测 | 做法 | 判据 |
|---|---|---|
| token 外壳 | 官方 `countTokens` 与中转 `usageMetadata.promptTokenCount` 逐个比 | 见下方基准数；多出固定数 = 注入（或 Vertex 小差，见上） |
| 专属工具 | `codeExecution`、`googleSearch` | 前者回 `executableCode` + `codeExecutionResult`，后者回 `groundingMetadata` |
| thoughtSignature | 两轮函数调用回传 | Gemini 3+ 必须；开头区分 Vertex / AI Studio |
| 报错原文 | 上面那组免费 400 | 原文和外壳对官方；露 Vertex 原文 = 背后是 Vertex |
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
