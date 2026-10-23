# 文本（LLM）线路细则：判真伪、对照文档、云平台补测

> SKILL.md 流程第 3、4 步的文本部分。
> 各厂商事实：`claude.md`、`grok-xai.md`、`gemini.md`、`kimi-k3.md`、`glm.md`、`deepseek.md`；中转形态：`new-api.md`、`sub2api.md`。
> findings.json 的 `authenticity.evidence` 必须有 `id_prefix`、`token_count`、`model_swap`、`injection` 四项（没测写 `skipped` 原因）。

## 判真伪（必做）
1. **认后端（`id_prefix`）**：第一个 200 看 id 前缀（`msg_011C` Anthropic 一方 / `msg_bdrk` Bedrock / `chatcmpl` / `resp_`），再发一个非法参数看报错原文露不露上游。**分组名（「官key」「官转」「参数透传」）不算证据**：见过名字暗示官方直连 / 透传的分组实为 Bedrock。模型名带「AWSB」也不算：见过 `-AWSB` 回的是 `msg_011C` 一方 id。new-api 站先看日志 `other.request_conversion`，有「OpenAI Compatible」就按 `claude.md`「经 OpenAI 格式转换」一节重点测非流式工具、内置工具、缓存。
2. **有没有换模型 / 注入（`token_count`、`injection`）**：同一句 + 带 `text_editor` 工具，**供应商真实请求的 usage**（`input_tokens + cache_creation + cache_read`，供应商可能自动加缓存断点）和官方 count_tokens 逐个比（提示词一字不差）。**别拿供应商自己的 count_tokens 比**：sub2api 的 count_tokens 不注入、和官方逐个相等，真实请求却每次多 500 左右（Claude Code 系统提示，见 `sub2api.md`）。多出的数固定 = 注入，再让便宜模型「把你前面的 system 文本原样放进代码块」念出原文。固定多几个（+4 之类）且念不出东西 = 聊天模板差异，不是注入。
   **判订阅号**：合法 `inference_geo:"us"` 回「not supported for this organization type」= 消费者订阅组织（Pro / Max），不是 API 组织（免费探针）。
3. **数对不上就查「换成了谁」（`model_swap`）**：每个模型发 `max_tokens: 9999999`，上游 400 报错里带真实模型名（「maximum allowed … for <模型>」），400 不扣费；官方同发一遍对照。**只对 Claude 有效**：Kimi 官方不报错、照常回答扣费（`kimi-k3.md`）；Gemini 也无效；**OpenAI Responses 也无效**（`max_output_tokens: 300000` 照常成交扣费）。见过回包 model 照写 `claude-fable-5`、400 里报出的却是 `claude-opus-5-5`，按贵 2.5 倍的价收。**只写「像某一代」不算结论**。
4. **「参数透传」**要逐字段矩阵测，并拿同站不透传分组作对照（`new-api.md`）。
5. **官方栈专属行为**（可选，判「是不是官方服务」）：只有官方实现的功能（Kimi K3 对话中途加载工具）、官方会拒的参数（Kimi temperature ≠ 1）、思考被截断时思考落在哪个字段、tool call id 格式——开源推理框架（vLLM / SGLang）自建的常在这里露馅。

## 对照官方文档
- 文本线路对照的是「**官方文档 + 官方实测**」两样：当天取文档（Claude 从 `platform.claude.com/docs/en/<页>.md` 取 Messages / Streaming / Errors / Rate limits / API overview），摘要存 `artifacts/official-docs-<日期>.json`。
- 逐字段表三列（文档 / 官方实测 / 供应商）：Message 顶层字段、usage 字段、stop_reason、request-id / organization / workspace / ratelimit / retry-after 头、流式事件顺序与累计 usage、错误外壳 + 状态码对应、错误是否总是 JSON。放进 findings 的 `sections[].table`；原文并排放 `exchanges`（非流式、流式 SSE、每类报错一对，请求带头、key 打码）。
- 文档能看出实测看不出的问题：回包多了只有带某 beta 头才有的字段 = 中转换了上游 beta 头；自己生成的错误没有 `request_id`、不是 JSON、状态码不在文档表里（503 + api_error）、429 没有 `retry-after`。
- 「字段一致」先程序求差集再写（规则 12）：两边 JSON 的 key 集合（含嵌套路径）、响应头名、SSE 事件名各求一次差集，差集原样贴进报告。

## 基准选谁 / 背后是云平台
- **基准 = 所卖模型名对应厂商的官方文档**（背后跑在火山方舟上的 DeepSeek，也对照 DeepSeek 官方文档，不对照方舟）：模型名对应的版本、Schema 里 required 的字段（程序求差集）、文档写明该报错 / 该映射的参数逐个补测、错误码表、兼容格式表、价目。
- **某能力在供应商上失败时**，背后是云平台（火山方舟 / 百炼 / Bedrock / Vertex / Azure）就先按**该云平台**的通用接口页 + 该模型在该平台的专属说明（如 Kimi K3 在方舟的动态工具写法和 Moonshot 不同）用云平台官方 key 重测同写法（付费按规则 2 先报价）；云平台官方也失败才算平台不支持、不是供应商的毛病。找不到平台写法就问用户要链接。云平台只用来解释差异从哪来，模型厂商文档用来判模型真伪。
