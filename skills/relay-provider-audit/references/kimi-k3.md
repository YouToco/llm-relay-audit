# Kimi K3 文本线路（官方基准：Moonshot 原厂 + 云平台托管）

> Last verified: 2026-10-21；价格与行为以官方文档为准。

## 官方接口
- 文档：platform.kimi.com/docs/api/chat（OpenAI 兼容 `/v1/chat/completions`，Bearer）。
- 回包：`model: kimi-k3`、id `chatcmpl-<24 位 hex>`；usage = prompt / completion / total + `completion_tokens_details.reasoning_tokens` + `prompt_tokens_details`（文档：`cached_tokens` + `cache_write_tokens`，另有顶层 `cached_tokens`；实测 0 缓存时只回 `cache_write_tokens: 0`）。
- 思考：文档写常开、`reasoning_effort` 只有 low / high / max（默认 max，测试压 low）；**实测官方也收 `effort: medium` 和 `thinking:{type:disabled}`**（关思考后 hi 输入 86 → 19，2026-10-20）。以实测为准，`medium` 照收不能当「非官方」证据。
- 专属能力：动态加载工具（对话中途插一条 `{role:"system", tools:[…]}`，不带 content）；官方 2026-09-24 实测可用。
- 视频输入：`video_url` 只收 base64（公网 URL 回 `unsupported video url`）；一段 5 秒 360p 实扣 3176 = 计数接口 3175 + 1，首单 `cache_write_tokens` 3142。
- 缓存门槛 256 token；缓存块 1280。

## 计数接口
- `POST /v1/tokenizers/estimate-token-count`（model + messages，可带 tools / 图片），**免费**（规则 10：免费官方调用直接测）。
- 单轮纯文本与真实 usage 一个不差（hi = 86）；带工具、或多轮不回传思考时，真实 usage = 计数 + 1（2026-10-20 / 10-21 实测）。
- 纯文本对照：正文 token 数 = `count(text) − 85`（hi = 1 token）；空串 400。

## 价目（2026-10-19 取，以官方页为准）
- Moonshot：输入 ¥20 / 百万，缓存命中 ¥2，输出 ¥100。
- 阿里百炼（北京）kimi-k3 挂牌同价：¥20 / ¥100 / 缓存 ¥2（2026-10-21）。
- 火山方舟：公开按量价目（10-19）、模型列表（10-20）、模型广场都**没有 kimi-k3**，海外 BytePlus ModelArk 也没有，只出现在 Coding / Agent Plan 订阅清单里。

## 官方指纹
- 报错：401 `invalid_authentication_error`、404 `resource_not_found_error`（不存在模型）、400 `Invalid request: …`。
- 官方会拒：`temperature ≠ 1` → 400；`tool_choice` 指定函数 → 400（与思考冲突，文档没写，2026-09-29）；`thinking:auto` 拒；公网图片 URL 拒。
- `logprobs`：返回的是截断后的分布（尾部 0.0）；关思考时 completion 多 3 个不可见 token。
- K3 tokenizer 有三个非特殊 added token（163587–163589），**官方会滤掉**；vLLM / SGLang 类自部署不滤，logprobs 末尾露出 `<|close|>response<|sep|><|close|>message<|sep|>`（工具调用露 `<|open|>argument=…`）= 开源权重自部署指纹。
- `model: moonshotai/Kimi-K3` = HF 开源权重写法，第三方部署。
- 动态工具回 `tokenization failed` = 背后是 K2.x。
- 工具调用 id 形如 `<函数名>_<序号>_<8 位 hex>`（例 `Calculator_0_<8 位 hex>`）。

### 云平台托管版差异
- **火山方舟**：id `0217…`（53 位）+ `service_tier`；报错带 `Request id`；响应头 `x-client-request-id: unknown-<时间>-<随机>`、`x-envoy-upstream-service-time`。上游被拒时方舟常把 Moonshot 原因抹成 `A parameter specified in the request is not valid`。
  - 不存在模型 404 `InvalidEndpointOrModel.NotFound`，未开通 404 `ModelNotOpen`。`kimi-k3-<6 位日期>` 这类 ID 公开文档查不到，多半是企业定向接入点（推断），要问供应商来源。
  - 方舟《对话(Chat) API》（ark.volcengine.com/region:cn-beijing/docs/chat-api）的 system 消息只有 role / content（必选）/ name，**没有 `messages[].tools`**；工具只放请求根、整次请求可见。所以 Moonshot 写法的动态工具在方舟上 400（缺 content）、补上 content 后 200 但 tools 被**静默丢掉**——这是平台没这能力，不算中转的毛病；方舟上改用根 `tools` + `tool_choice: required` 测。
  - 经疑似方舟原样转发的线路观察到（推断为方舟行为，方舟官方未能直接对照）：输入 token 与 Moonshot 官方逐个相等、缓存块 1280 相同、工具调用 id 同 Moonshot 格式；logprobs 回 null；temperature 0.5 照收；`reasoning_effort: minimal` = 关思考（输入 19，Moonshot 官方 minimal 仍思考、输入 87）。
- **阿里百炼**（推断，未证实）：id `chatcmpl-<UUID>`、第三段以 9 开头（百炼报错 id 同）；usage 带 `x_details` / `text_tokens`。

## 判真伪招数是否有效
- **超大 `max_tokens`（Claude 逼真实模型名那招）无效**：`max_tokens: 9999999` 官方不报错、照常回答并扣费（文档上限 1048576），见 claude.md。
- **`max_tokens: 0` 不是免费保险**：官方当「不限」照常回答扣费；官方免费探针只用空 messages / 错 key / 不存在模型（规则 5）。
- 有效：
  1. 回包 `model` 是不是 `kimi-k3`。
  2. 同一份 messages：中转真实 usage vs 官方计数接口；常数差（+1 ~ +4）= 同分词器不同服务栈 / 聊天模板差；差几百或不成常数 = 注入或换模型（规则 12：差集程序算）。
  3. 动态加载工具一单：400 = 不是 Moonshot 官方栈（或中间层丢字段）；**先认后端**，背后是方舟就按方舟写法重测（见上）。
  4. 新短句连发两次看缓存（门槛 256）。
  5. 官方会拒的参数当探针：temperature 0.5、指定函数照收 = 不是官方栈；同一句 hi 比思考 token（effort 不生效 / 思考偏浅）；`max_tokens` 小到截断思考，看思考有没有跑进 content（开源框架解析器的毛病）。
  6. **截断指纹**：让模型原样复述固定文字、`thinking:{type:disabled}`、`max_tokens: 24`、`logprobs: true`，两边逐 token 比切分（模型自己的分词器决定停在哪）。
  7. **首 token 分布**：开放题（起名 / 动物 / 字母 / 乐器…）`max_tokens: 3` + `top_logprobs: 5`，和官方 K3、官方 K2.6 三方比重合度（一次案例：K3 0.76、K2.6 0.59，可区分）；知识题区分不开。
  8. **混池检测**：各类请求都带 logprobs，正文 token 数 vs `count(text) − 85`，逐单相等 = 同一 Kimi 分词器；先去掉正文后的结构 token 再比。
  9. **隐藏系统提示**：chat usage 可能不计注入部分；改发 `/v1/responses` 空 input，注入的系统提示会被当成用户消息计费，看 `usage.x_details[0].input_tokens` 才是真实输入。
  10. **工具调用质量**：同一请求连发 3–6 次，单发一次看不出编造结果。

## 中转常见问题（匿名）
- 撮合 / 按价路由的平台，背后是开源权重 K3：输入 = 官方 +1、动态工具 400、指定函数 / temperature 照收、`max_tokens` 超限误报 502「上游鉴权失败」类文案。
- new-api 套 new-api 的多层转发：日志里露渠道名、成功响应头透传上游 new-api 版本；文本输入 = 官方 +4、视频输入 = 官方实扣；effort 不生效（hi 思考 10–15）、思考截断进 content；传参说明写「不支持」的字段实测可用——**以实测为准，不信说明**。
- 注入隐藏系统提示：chat usage 只记 7，但模型思考里提到「system prompt 不得泄露 / identity instructions」，Responses 空 input 计 783；带工具 6 次里 3 次调用、2 次编天气（官方 3/3 调用）；token 比官方少 18–119 且不成常数、图片多 174；思考浅；动态工具被忽略。
- 方舟原样转发型：价 ≈ 官方挂牌，但缓存命中不打折；**失败请求按「输入 + max_tokens × 输出价」预扣、上游 400 不退**（别拿大 max_tokens 做 400 探针），不传 max_tokens 按约 1024 预扣并封顶。
- new-api / one-api 系余额：`/v1/quota`、`billing/usage` 向上取整，真余额看 `/v1/dashboard/billing/subscription` 的 `hard_limit_usd`（6 位小数），逐单前后各读一次。

## 接入网关要求
- usage 必须带 `reasoning_tokens` 与缓存字段（`cached_tokens` / `cache_write_tokens`），否则思考和缓存没法对账。
- 背后是方舟时动态工具不可用、工具只能放根 `tools`；要动态工具的客户只能走 Moonshot 原厂栈。
- 预扣型计费：网关侧别给 Kimi 线路默认塞超大 `max_tokens`（官方照收照扣，中转还按它预扣）。
- 报错要能区分上游原因：方舟会把 Moonshot 原因抹成通用 InvalidParameter，归因时别当参数 bug。
