# Kimi K3 文本线路（官方基准：Moonshot 原厂 + 云平台托管）

> Last verified: 2026-10-21（K3 官方 key 实测）；K3.1 Pro 2026-10-26 官方实测；价目 2026-10-29；方舟 K3.1 Pro 2026-10-30。价格与行为以官方文档为准。

## 官方接口
- 文档：platform.kimi.com/docs/api/chat（OpenAI 兼容 `/v1/chat/completions`，Bearer）。
- 回包：`model: kimi-k3`、id `chatcmpl-<24 位 hex>`；usage = prompt / completion / total + `completion_tokens_details.reasoning_tokens` + `prompt_tokens_details`（文档：`cached_tokens` + `cache_write_tokens`，另有顶层 `cached_tokens`；实测 0 缓存时只回 `cache_write_tokens: 0`）。
- 思考：文档写常开、`reasoning_effort` 只有 low / high / max（默认 max，测试压 low）；**实测官方也收 `effort: medium` 和 `thinking:{type:disabled}`**（关思考后 hi 输入 86 → 19，2026-10-20；`/v1/models/kimi-k3` 写 `supports_thinking_type: only`，实际能关）；`minimal` 照收 = low；`thinking:{type:"auto"}` 400。以实测为准，`medium` 照收不能当「非官方」证据。
  - 默认（max）hi 思考 98–261 token，完整句（「The user just said "hi" - a simple greeting…」）；**low 也会出电报体**（「Simple greeting.」「Need use tool. Then answer…」）。质数题 low 13、medium 12、high 129。
- 回包细节（官方实测）：顶层只有 id / object / created / model / choices / usage；并行工具调用 id `_0_` / `_1_` 带 index，65 字符函数名也照收。`logprobs` 只收布尔（`logprobs: 3` 400「expected type bool」）；开思考时 logprobs 含思考 token 和标记位。
- 响应头（官方实测）：`Msh-Request-Id`、`Msh-Gid`（账号所在的档位分组）、`Msh-Trace-Mode`，计费相关 `Msh-Usage-Cache-Write-Tokens-5m` / `-1h`（本单写缓存 token，按 TTL 分）、`Msh-Context-Cache-Token-Saved`（命中）；**没有 RPM / TPM / remaining 类限流头**。`Msh-Org-Id` / `Msh-Project-Id` / `Msh-Uid` 是账号 id，存证前打码。
- 流式指纹：每个 chunk（最后 usage 块除外）带 `system_fingerprint`，值随服务栈变（见「判换模型」）。速度参照（2026-10-20，effort low）：首 token 约 4.5 s、约 36 token / 秒。
- **官方自己也会过载**：K3.1 Pro 2026-10-26 下午 54 单里 14 次 429 `engine_overloaded_error`「The engine is currently overloaded, please try again later」（highspeed 8 次全 429），每单 3–4 秒才回、无 `retry-after`。中转回同样的 429 别直接判「中转限流」；补测隔 20 秒以上。
- 专属能力：动态加载工具（对话中途插一条 `{role:"system", tools:[…]}`，不带 content）；官方 2026-09-24 实测可用。
- 视频输入：`video_url` 只收 base64（公网 URL 回 `unsupported video url`）；一段 5 秒 360p 实扣 3176 = 计数接口 3175 + 1，首单 `cache_write_tokens` 3142。
- 缓存门槛 256 token；缓存块 1280。

## 计数接口
- `POST /v1/tokenizers/estimate-token-count`（model + messages，可带 tools / 图片），**免费**（规则 10：免费官方调用直接测）。
- 单轮纯文本与真实 usage 一个不差（hi = 86）；带工具、或多轮不回传思考时，真实 usage = 计数 + 1（2026-10-20 / 10-21 实测）。**请求带 `reasoning_effort`（任何值，含 minimal）真实 usage 也 +1**（hi 86 → 87、长文 1394 → 1395、视频 3175 → 3176）；K3.1 Pro 一律 = 计数 + 1。
- **计数接口不算 `response_format` 和 `tool_choice`**：json_schema 实扣 187（计数 95）、json_object 146（98）、tool_choice required 210（173）——这类请求的差额是官方自己的，别当注入。
- 官方计数基准（同一批 messages 三天一致）：hi 86、system + 段落 162、多轮 142、带 tools 169、长段落 400、长文（×20）1134、图片 base64 112、5 秒 360p 视频 3175。
- 纯文本对照：正文 token 数 = `count(text) − 85`（hi = 1 token）；空串 400。

## 价目（以官方页为准，[platform.moonshot.cn/docs/pricing/chat](https://platform.moonshot.cn/docs/pricing/chat) 2026-10-29 读，元 / 百万 token）
| 模型 | 输入 | 输出 | 缓存命中 | 写缓存 5 分钟 | 写缓存 1 小时 |
|---|---|---|---|---|---|
| kimi-k3.1-pro | 13 | 68 | 1.30 | 13 | 26 |
| kimi-k3.1-pro-highspeed | 26 | 136 | 1.30 | 26 | 52 |
| kimi-k3 | 20 | 100 | 2 | 20 | 40 |
- K3 系列上下文都是 1,048,576；自动前缀缓存默认 TTL 5 分钟，**写缓存按 TTL 单独计费**（5 分钟档 = 输入价、1 小时档 = 2× 输入价）——中转按 1 小时 TTL 收写缓存时按这个核。页上公告：K2 系列 2026-10-31 起不对新注册用户开放，计划 12 月底全部下线。
- 阿里百炼（北京）：`kimi-k3` ¥20 / ¥100 / 缓存 ¥2；带 `kimi/` 前缀的 `kimi/kimi-k3.1-pro` ¥13 / ¥68、`-highspeed` ¥26 / ¥136（2026-10-29）。
- 火山方舟：**kimi-k3.1-pro 已公开在售**（2026-10-30：`/api/v3/models` 列出 `kimi-k3-1-pro-261024`，文本 / 图片 / 视频输入、1M 上下文；价目页 ¥13 / 缓存 ¥1.30 / ¥68 = Moonshot 挂牌）；**仍没有 kimi-k3 的按量模型**（公开价目、模型列表、模型广场、海外 BytePlus ModelArk 都没有，只在 Coding / Agent Plan 订阅清单里）。

## 官方指纹
- 报错：401 `invalid_authentication_error`、404 `resource_not_found_error`（不存在模型）、400 `Invalid request: …`。原文（官方实测）：错 key「Invalid Authentication」；无 key「Incorrect API key provided」（`incorrect_api_key_error`）；`X-Api-Key` 头也被当成有效鉴权；不存在 / 缺 model 404「Not found the model … or Permission denied」；空 messages「Invalid request: messages must not be empty」（Responses 空 input 同句）；非法 JSON「Invalid request: unexpected EOF」；temperature ≠ 1「invalid temperature: only 1 is allowed for this model」；指定函数 / `any`「tool_choice 'specified' is incompatible with thinking enabled」；工具名带点「function name is invalid…」；回传不存在的 tool_call_id「tool_call_id  is not found」；公网图片「unsupported image url」。`tool_choice: required`、`allowed_tools`、tool 里多余键、未知顶层字段都 200。
- 官方会拒：`temperature ≠ 1` → 400；`tool_choice` 指定函数 → 400（与思考冲突，文档没写，2026-09-29）；`thinking:auto` 拒；公网图片 URL 拒。
- `logprobs`：`top_logprobs` 返回的是截断后的分布（尾部用 `logprob: -9999` 补位）；关思考时 completion 多 3 个不可见 token（截断复述 completion 24 个、logprobs 只 21 个）。
- K3 tokenizer 有三个非特殊 added token（163587–163589），**官方会滤掉**；vLLM / SGLang 类自部署不滤，logprobs 末尾露出 `<|close|>response<|sep|><|close|>message<|sep|>`（工具调用露 `<|open|>argument=…`）= 开源权重自部署指纹。
- `model: moonshotai/Kimi-K3` = HF 开源权重写法，第三方部署。
- 动态工具回 `tokenization failed` = 背后是 K2.x。
- 工具调用 id 形如 `<函数名>_<序号>_<8 位 hex>`（例 `Calculator_0_<8 位 hex>`）。

### 云平台托管版差异
- **火山方舟**：id `0217…`（53 位）+ `service_tier`；报错带 `Request id`；响应头 `x-client-request-id: unknown-<时间>-<随机>`、`x-envoy-upstream-service-time`。上游被拒时方舟常把 Moonshot 原因抹成 `A parameter specified in the request is not valid`。
  - 不存在模型 404 `InvalidEndpointOrModel.NotFound`，未开通 404 `ModelNotOpen`。`kimi-k3-<6 位日期>` 这类 ID 公开文档查不到，多半是企业定向接入点（推断），要问供应商来源。
  - 方舟《对话(Chat) API》（ark.volcengine.com/region:cn-beijing/docs/chat-api）的 system 消息只有 role / content（必选）/ name，**没有 `messages[].tools`**；工具只放请求根、整次请求可见。所以 Moonshot 写法的动态工具在方舟上 400（缺 content）、补上 content 后 200 但 tools 被**静默丢掉**——这是平台没这能力，不算中转的毛病；方舟上改用根 `tools` + `tool_choice: required` 测。
  - **方舟上的 K3.1 Pro**（`kimi-k3-1-pro-261024`，经方舟转发的线路观察，2026-10-30）：输入 token、截断指纹、首 token 前三候选都和 Moonshot 官方一致；**logprobs 能用**（不像方舟上的 K3 回 null）；`reasoning_effort` 收、关思考可用；思考普遍比 Moonshot 短；流式没有 `system_fingerprint`、不报 `cache_write_tokens`；视频 `video_url` base64 token = 官方，`file` 部件被当 PDF 400。没开通的账号调用回 404 `ModelNotOpen`（免费）。
  - 经疑似方舟原样转发的线路观察到（推断为方舟行为，方舟官方未能直接对照）：输入 token 与 Moonshot 官方逐个相等、缓存块 1280 相同、工具调用 id 同 Moonshot 格式；logprobs 回 null；temperature 0.5 照收；`reasoning_effort: minimal` = 关思考（输入 19，Moonshot 官方 minimal 仍思考、输入 87）。
- **阿里百炼**（推断，未证实）：id `chatcmpl-<UUID>`、第三段以 9 开头（百炼报错 id 同）；usage 带 `x_details` / `text_tokens`。
- **Kimi Code 会员订阅转 API**（订阅号池，经中转观察）：`/v1/responses` 报错原文「unsupported upstream request URL: kimi-coding-plan/v1/responses」；回包 / 日志里的上游型号名是 Kimi Code 的 `k3.1-pro`（开放平台是 `kimi-k3.1-pro`）；403 `access_terminated_error`「You've reached your concurrent request limit」（顺序发也撞 = 号和别人共用）；`thinking:{type:disabled}` 400「K3.1 Pro does not support disabled thinking mode」（开放平台能关）；`logprobs` 400；tool call id `tool_<24 位>`、响应 id `chatcmpl-<24 位 base62>`；**短提示重复第二单就整段命中、不报 `cache_write_tokens`**（开放平台 ≥ 256 token 才缓存）——这几条凑齐 = 订阅转 API。

## K3.1 Pro（官方 key 实测 2026-10-26）
- 输入 token：真实 usage = 计数接口 + 1。hi 87、system + 段落 163、多轮 143、带 tools 170、长段落 401、长文 1135、图片 base64 113、动态工具 207；关思考 hi 19。和 K3 一样（hi 计数 86），**输入 token 分不出 K3 和 K3.1 Pro**，要用下面「判换模型」里的指纹。
- 缓存：≥ 256 token 才缓存、首单报 `cache_write_tokens`，长文第二单命中 1024；短句不缓存。
- 回包：响应 id `chatcmpl-<24 位 hex>`；tool call id `get_weather_0_<8 位 hex>`。
- **视频两种官方传法**：① `video_url` 写 base64 data URL；② 先 `POST /v1/files`（multipart，`purpose=video`，单文件 ≤ 100 MiB，上传免费）再在 `video_url` 写 `ms://<file id>`（官方文档：大视频必须走上传）。**OpenAI 式 `{"type":"file","file":{"file_data":…}}` 部件官方回 400「contains an invalid part type: file」**——中转说「file 是官方格式」不成立。
- 视频计数：计数接口**不认 `ms://`**（400 unsupported video url），认 base64（75 MB 请求体也收、免费）。同一提问下 5 秒 360p 实扣 3,177；17 秒 1080p（36 MiB）40,589；计数接口另一句提问：23 秒和 26 秒 1080p 都是 40,579（像封顶帧数）。
- 报错原文同 K3（temperature ≠ 1、指定函数、公网图片、`file` 部件见上）。
- highspeed 没有官方对照（那天官方 8 次全 429）；长上下文（> 128K）、Responses / Anthropic 兼容口成功响应没测。

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
  7. **首 token 分布**：开放题（起名 / 动物 / 字母 / 乐器…）`max_tokens: 3` + `top_logprobs: 5`，和官方 K3、官方 K2.6 三方比重合度（重合 = 前 5 个相同 token 的概率取小求和，丢掉 -9999）。官方实测 9 题 K3 ~ K2.6 重合 0.69：名字 0.25、动物 0.50、字母 0.52 最分得开，水果、形容词 1.0 分不开；K3「名字」前 5 {K, El, E, Z, A}，K2.6 首选 V（0.67）。一次案例：中转对 K3 0.76、对 K2.6 0.59 → 判为 K3。
     **知识题**：直接问（2025 年的新教皇）两边都答对、区分不开；**给出「不知道就答 UNKNOWN」的出口时能分开**（官方 K3 4/4 答 Leo XIV、K2.6 4/4 答 UNKNOWN）。
     截断指纹参照（官方 K3，英文复述）切分 `Photos|ynthesis| converts|…| chlor|oplast|s`。
  8. **混池检测**：各类请求都带 logprobs，正文 token 数 vs `count(text) − 85`，逐单相等 = 同一 Kimi 分词器；先去掉正文后的结构 token 再比。
  9. **隐藏系统提示**：chat usage 可能不计注入部分；改发 `/v1/responses` 空 input，注入的系统提示会被当成用户消息计费，看 `usage.x_details[0].input_tokens` 才是真实输入。
  10. **工具调用质量**：同一请求连发 3–6 次，单发一次看不出编造结果（官方同请求 3/3 真调用，思考 8–31 token）。
  11. **K3.1 Pro 还是 K3**（logprobs / 关思考都不能用时）：
     - 流式每个 chunk 的 `system_fingerprint` **的值**：官方 K3.1 Pro `fpv0_3dc51bce`；官方 K3 在 10-20 是 `fpv0_98af8175`、id 24 位，10-26 同句 hi 不带这个字段、id 25 位（官方服务栈 10-21 后变过）。所以要比值、按日期比，不能只看有没有；过期了先重测官方。
     - **同档 effort 下的思考句式**：effort low 时官方 K3.1 Pro 17/17 单以「I need respond… / Should…」起句（常提 identity instructions），官方 K3 0/28（写「The user is asking… Need call…」「Simple greeting.」）。正则 `^(I need|I'll|I should|Kimi (needs|should|will))|\bShould\b`。**一定同档 effort 比**：默认（max）档 K3 也是长段完整句，拿它比会夸大差别。

## 中转常见问题（匿名）
- 撮合 / 按价路由的平台，背后是开源权重 K3：输入 = 官方 +1、动态工具 400、指定函数 / temperature 照收、`max_tokens` 超限误报 502「上游鉴权失败」类文案。
- new-api 套 new-api 的多层转发：日志里露渠道名、成功响应头透传上游 new-api 版本；文本输入 = 官方 +4、视频输入 = 官方实扣；effort 不生效（hi 思考 10–15）、思考截断进 content；传参说明写「不支持」的字段实测可用——**以实测为准，不信说明**。
- **中间层改写**（同一站点换了干净上游后仍在的）：视频只认自定义 `file` 部件（官方写法 `video_url` 400、`/v1/files` 501）、关思考 / temperature 静默丢、公网图片 URL 由中间层代下载、报错一律改写成同一句、流式丢 `system_fingerprint`；nginx 请求体上限 50 MiB → base64 后视频只能 ≤ 约 37 MiB（免费测法：模型名故意写错让应用层回不扣费的错，请求体填到 1 / 10 / 30 / 45 / 60 MB 用 curl 发，看哪档开始回 nginx 413 再二分；base64 内嵌膨胀 4/3，中转说「支持 50M」常指请求体）。上游换成开放平台后的认法：输入 token 逐单 = 官方、tool call id 变成官方 `get_weather_0_<8hex>`（开源栈是 `call_<24hex>`）、长文缓存 1024 = 官方。
- 注入隐藏系统提示：chat usage 只记 7，但模型思考里提到「system prompt 不得泄露 / identity instructions」，Responses 空 input 计 783；带工具 6 次里 3 次调用、2 次编天气（官方 3/3 调用）；token 比官方少 18–119 且不成常数、图片多 174；思考浅；动态工具被忽略。
- 方舟原样转发型：价 ≈ 官方挂牌，但缓存命中不打折；**失败请求按「输入 + max_tokens × 输出价」预扣、上游 400 不退**（别拿大 max_tokens 做 400 探针），不传 max_tokens 按约 1024 预扣并封顶。
- new-api / one-api 系余额：`/v1/quota`、`billing/usage` 向上取整，真余额看 `/v1/dashboard/billing/subscription` 的 `hard_limit_usd`（6 位小数），逐单前后各读一次。

## 接入网关要求
- usage 必须带 `reasoning_tokens` 与缓存字段（`cached_tokens` / `cache_write_tokens`），否则思考和缓存没法对账。
- 背后是方舟时动态工具不可用、工具只能放根 `tools`；要动态工具的客户只能走 Moonshot 原厂栈。
- 预扣型计费：网关侧别给 Kimi 线路默认塞超大 `max_tokens`（官方照收照扣，中转还按它预扣）。
- 报错要能区分上游原因：方舟会把 Moonshot 原因抹成通用 InvalidParameter，归因时别当参数 bug。
