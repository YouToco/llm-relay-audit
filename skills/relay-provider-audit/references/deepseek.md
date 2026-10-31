# DeepSeek 文本线路（官方基准：DeepSeek 原厂 + 火山方舟 / 腾讯云托管）

> Last verified: 2026-10-20（原厂 / 方舟官方 key 实测）；价目与 Anthropic 入口 2026-10-29。价格与行为以官方文档为准。

## 官方接口
### DeepSeek 原厂（api.deepseek.com）
- 模型（`/models`，2026-10-20）：只有 `deepseek-flash`（= DeepSeek-V4.1-Flash-1017，文本 + 图片）和 `deepseek-v4-pro`（= V4-Pro-0813，纯文本）。旧名 `deepseek-v4-flash` / `-vision-exp` 照收、由 V4.1-Flash-1017 服务。**V4-Flash 正式版（GA）原厂已下线**，中转卖 `…flash-ga…` 只能和方舟比。
- `/models` 带 name / context_window / max_output_tokens / input_modalities / effort（`supported_levels: [low, high, max]`，默认 high）/ api_capabilities。
- 另有 `GET /user/balance`、`/beta`（前缀续写、strict 工具）、Anthropic 入口 `/anthropic`（claude-opus* → v4-pro、其它 claude* → flash，未知非 claude 名 400）。
- 回包：id 是 UUID；有 `system_fingerprint`（官方实测值：`deepseek-flash` `e72d3c7f663d3e1383b00b3884cb4501`、`deepseek-v4-pro` `a307abda487cd1b463329ccb945ce396`，流式每块也带，2026-10-20）；usage 多 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`（同时也有 `prompt_tokens_details.cached_tokens`）；思考在 `reasoning_content`，思考 token 算在 completion；工具调用 id `call_00_<大小写混合>`。
- **思考默认开、和正文共用 `max_tokens`**：小预算会被思考吃光、`content` 为空但 HTTP 200——测试小请求要么关思考、要么给足 max_tokens，别把空 content 当中转毛病。
- 流式 include_usage：usage 挂在 finish 块上、不单发。
- **Anthropic 入口**（`POST /anthropic/v1/messages`，`x-api-key` + `anthropic-version`，model `deepseek-flash`，2026-10-29 实测）：200，「Hi」`input_tokens: 31`，usage 带 `cache_creation_input_tokens` / `cache_read_input_tokens` 和 `service_tier: standard`；**id 是 UUID**（不是 `msg_…`），流式事件名和 Anthropic 一样。中转卖 Claude 却回 UUID id + 这套 usage = 可能背后是 DeepSeek 的 Anthropic 入口。
- 延迟参照（2026-10-29，OpenAI 口流式、关思考 ×10，国内）：首包 p50 0.15 s（先回空增量）、首字 p50 0.63 s（0.48–0.80 s）。
- 前缀缓存门槛 64；1.4k 的 system 第二次命中 1152–1280。

### 火山方舟托管版（ark.cn-beijing.volces.com，`/api/v3/chat/completions`）
- 现役 ID（`/api/v3/models`，2026-10-20）：`deepseek-v4-1-flash-260910`、`-261017`、`-economy-261017`、`deepseek-v4-flash-ga-260731`、`deepseek-v4-pro-ga-260813`（`deepseek-v4-pro-260425` Retiring）。**每个模型先在控制台开通**，没开通 404 `ModelNotOpen`（先于参数校验）。
- 回包：id = 方舟 Request id（`0217` + 毫秒时间戳 + …，= `x-request-id` 头）；多 `service_tier: "default"`；响应头 `server: istio-envoy`、`x-client-request-id: unknown-<北京时间>-<随机>`、`x-envoy-upstream-service-time`。
- 工具调用 id：v4.1 `call_00_<24 位小写>`、GA `call_<24 位小写>`。流式 include_usage：0910 / GA 在 finish 块挂一次 usage 后**再单发一个 `choices: []` 的 usage 块**，1017 只挂 finish 块（和原厂一样）——这也能分版本。
- 参数：文档写 thinking 只有 enabled / disabled（实测 GA 两个收 auto）；`reasoning_effort` 默认 high，映射表见[深度思考](https://www.volcengine.com/docs/82379/1449737)；logprobs / top_logprobs ≤ 20；json_schema 支持；`caching` 字段照收不生效。

### 腾讯云 TokenHub（经中转观察，推断为平台行为）
- 报错 `{code:"400002", message_zh, source:"client", request_id:<UUID>}`；回包 model 带 `-0731` 后缀；错误码表见腾讯云文档 cloud.tencent.com/document/product/1823/131595。
- V4-Flash 正式版：收 `adaptive`、拒 `auto`（和方舟 GA 相反）；无 `service_tier`。

## 计数接口
- 原厂**没有在线计数接口**。
- 方舟 `/api/v3/tokenization`（model + text[]）：三个模型同一分词器、开头加 BOS（"hi" = 2）；只切纯文本，聊天外壳另加（非思考 +3）。与原厂同分词器，可拿来对照。
- 方舟与原厂**同一套聊天模板**：同一请求输入 token 逐个相等（hi 非思考 5、hi 思考 31〔v4.1〕/ 84〔两个 GA〕）；例外：pro 的 json_object 方舟 134 vs 原厂 37（方舟注入了 JSON 指令）、tool_choice 指定函数 288 vs 295。
- 方舟官方 key 实测：两个 GA 模型带 json_schema 的输入比 3 条独立中转线路都多 11（原因不明）→ **这个差别别当中转注入证据**。json_schema 变体（方舟 flash-ga，原样 181）：去 strict / strict=false / 键重排 181，去 additionalProperties 176，去 required 166，加 description 187，name 改长 185，去 name 400 `MissingParameter`。
- **官方输入 token 基准**（同一请求体，左 = v4.1-flash 三个：方舟 0910 / 1017、原厂 flash；右 = 原厂 v4-pro、方舟 pro-ga / flash-ga；2026-10-20）：hi 默认（思考）31 / 84；thinking enabled 质数题 43 / 96；thinking disabled 17 / 17；effort low 42 / **16**（右边 low 直接不思考）、high 42 / 95、max 42 / 108；tools auto 307 / 370；1.4k system 1372 / 1371；system + 段落 + tools 422 / 431；纯段落 139；多轮 46 → 63 / 99 → 116。
- 方舟 tokenization：「hi」2（BOS 0 + 6366）、「用一句话解释什么是向量数据库」7；10,000 字 filler → 9,756。
- 缓存（1.4k 前缀第二次）：方舟 v4.1 命中 1280、原厂 flash 1152、原厂 pro 1280、**方舟 GA 两个 0**。

## 价目（元 / 百万 token，以官方页为准）
- 原厂（[价目页](https://api-docs.deepseek.com/zh-cn/quick_start/pricing)，2026-10-20，10-29 复核未变）：flash 高峰 输入 2 / 命中 0.04 / 输出 8，空闲 1 / 0.02 / 4；pro 高峰 9 / 0.30 / 27，空闲 4.5 / 0.15 / 13.5。**空闲时段半价**；高峰 = 北京时间工作日 9–12、14–18，不含法定节假日。人民币账户实扣按 ¥ 估（实测约 ¥7 / 百万输出 token，比美元价换算高）。
  - 价目页还写：并发上限 flash 2500、v4-pro 500；Search / Fetch 接口各 ¥5 / 千次成功请求；经 Claude Code / Codex 等走服务端工具的调用 2026-11-01 起开始收费。
- 方舟（[模型价格](https://www.volcengine.com/docs/82379/1544106)，页面 2026-10-19 更新）：v4.1-flash 空闲 1 / 0.02 / 4、高峰 2 / 0.04 / 8（同原厂峰谷）；**v4-flash 正式版 3 / 0.10 / 9；v4-pro 正式版 9 / 0.30 / 27**；缓存存储 0.017 / 百万 / 小时。2026-10-29 页面（10-24 更新）新增 **v4.1-flash 经济版**（`-economy-261017`）：高峰 1.60 / 0.032 / 6.40、空闲 0.80 / 0.016 / 3.20。
- 方舟页上还留着调价前老价：flash 正式版 1 / 0.2 / 2（08-21 起不适用）、pro 预览版 12 / 1 / 24（08-28 起不适用）——**中转价对上老价 = 它的价目表没跟调价**。

## 官方指纹
- 原厂参数：`thinking.type` 只认 `adaptive / enabled / disabled`（`auto` 422）；`reasoning_effort` 认 none…max 八档；`response_format: json_schema` → 400「This response_format type is unavailable now」（只有 json_object）；temperature 0 时 logprobs 被夹成 0 / -9999（不能当指纹）。
- 原厂报错：外壳 `{error:{message,type,param:null,code}}`，message 末尾 `(request_id: <uuid>)`；反序列化失败 **422**（role / thinking / effort / response_format 枚举错）；范围错 400（temperature、top_logprobs、`max_tokens` 0 或超 393216，免费）。原文：role「unknown variant `robot`, expected one of `system`, `user`, `assistant`, `tool`, `latest_reminder`」；「Invalid temperature value, the valid range of temperature is [0, 2]」；max_tokens「the valid range of max_tokens is [1, 393216]」；空 messages「Empty input messages」；错 key 401「Authentication Fails, Your api key: ****xxxx is invalid」；不存在模型「The supported API model names are deepseek-flash, deepseek-v4-pro…」。
- 原厂文档（2026-10-20）：
  - 响应 Schema required：`system_fingerprint`、`usage.prompt_cache_hit_tokens / prompt_cache_miss_tokens`、`choices[].logprobs`（可为 null）。**方舟 / TokenHub 转的线路都没有前两项**。
  - 流式 include_usage：每块都有 usage 键（末块前为 null），统计附在最后一个内容块上，**不单独下发只含 usage 的块**。
  - effort 映射：minimal → low、medium / xhigh → high、ultra → max，none 关思考；thinking.type 文档只写 enabled / disabled。
  - 写明 400：stream_options 不配 stream、思考模式 + tool_choice required / 指定函数、带 tools 的后续请求不回传 reasoning_content、max_tokens 不在 1–393216。
  - 错误码表：400 格式、401、402、422 参数、429、500 故障、503 繁忙（**没有 403 / 404**）。
- 方舟报错：`{error:{code,message,param,type}}`，message 末尾 `Request id: 0217…`；不存在模型 404 `InvalidEndpointOrModel.NotFound`；参数错 400 `InvalidParameter`（temperature ≤ 2、top_logprobs ≤ 20、role 多认 `developer`）；`max_tokens: 0` → 400「max_completion_tokens must be greater than 0」（免费，可当保险）；错 key 401「The API key format is incorrect」；Responses 空 input 400 `MissingParameter`；未知顶层字段照收 200。`ModelNotOpen` 报错原文带方舟账号号，存证前打码。
- 方舟三个 ID 的区分特征（判换模型用）：
  - v4.1-flash：思考模板 31、`thinking:auto` 400（「unknown variant auto, expected adaptive/enabled/disabled」，但 `adaptive` 也 400）、有前缀缓存。
  - **0910 还是 1017**（输入 token 三者全等，只能靠续写 / logprobs 分）：原厂 `deepseek-flash` 10-17 起由 1017 服务，temperature 0 续写和方舟 `-261017` 同一句「The rain falls soft as whispered secrets on the roof.」；方舟 `-260910` 是上一版「The rain descends in silver threads tonight,」。
  - 两个 GA：模板 84、`auto` 200、前缀缓存不命中。
  - temperature 0 续写「Write the first line of a poem about rain.」：v4.1「The rain descends in silver…」、flash-ga「Rain writes its signature…」（批次抖动会换成另一两句）、pro「The sky unspools its silver, thread by thread.」（**和原厂 V4-Pro 逐字相同**）。方舟 temperature 0 的 logprobs 是真值，可做指纹。

## 判真伪招数是否有效
- **超大 `max_tokens` 逼模型名无效**：原厂 400 只报范围不报模型名；方舟 `9999999` 不报错、照常回答扣费（对照 claude.md）。
- **`max_tokens: 0` 当免费保险**：原厂 / 方舟有效（400）；**过 new-api 的线路无效**——new-api 把 0 当没填、照常出答计费（new-api.md）。
- 有效：
  1. 回包 id：`0217…` = 方舟；UUID + `system_fingerprint` = 原厂；别的格式 = 自建 / 再转。
  2. 同一份请求比输入 token（hi 思考 31 / 84 这类模板数最灵敏）；多出固定数 = 注入。
  3. 换模型：上面「区分特征」+ temperature 0 续写 / logprobs，和方舟官方同 ID 各发 3 次比（方舟自身有批次抖动，看是否落在同一组值里，别比单次）。
  4. Schema required 字段与官方程序求差集（规则 12）。
  5. 缓存：新 nonce 开头、隔 5–120 s 重发，**连发 ≥ 5 次看稳定性**；方舟 v4-pro 正式版 / TokenHub v4-flash 的 1.4k 前缀常不命中、4k 前缀命中数 2048 / 3840 跳动甚至 0（经中转观察），单次未命中不算证据。
  6. 额度只给整数的中转：「同尺寸请求连发、数额度跳格」测单价，每个区间 ≥ 20 单才有 ±5%（规则 1：先报价）。

## 中转常见问题（匿名）
- 方舟原样转发型：计费 token 与方舟逐个相等、键集合 / 响应头 / SSE 零差异，只换 `X-Request-Id`；报错改成自家外壳（方舟原码挪到别的字段、丢 `param`）；只开放 chat，Responses / tokenization / embeddings 不通；路径和鉴权写法挑剔（缺前缀 404 / 405、小写 `bearer` 不认）。
- **每单按 max_tokens 预扣费用上界**；客户端中途断开的流式请求冻结额度不立即释放。
- 见过中转价目没跟方舟调价（还按老价收）。
- **一把 key 按模型分到多套后端**：同站不同模型分别回 `0217…`（方舟）、new-api 原文「field messages is required (request id: …)」且是 **500**（中间一层 new-api）、TokenHub 外壳——每个模型单独认后端。
- **同名不同快照**：卖 `deepseek-flash` 实为方舟 v4.1-flash-260910，而原厂同名已是 1017 → 比对要落到具体快照。
- new-api 的 `/v1/messages` 转换丢 `thinking:{type:disabled}` 和 pro 的 `max_tokens`。
- 基准选谁：**以模型厂商官方文档为准**，背后是云平台时云平台只用来解释差异从哪来（text-checks.md）。

## 接入网关要求
- 峰谷计价：同一模型按北京时间工作日时段两档价，网关计费要按请求时刻分档（节假日按空闲）；以官方价目页为准，按日期留档。
- usage 字段：原厂用 `prompt_cache_hit_tokens` / `miss_tokens`，方舟 / TokenHub 只有 `prompt_tokens_details.cached_tokens`——两种都要能解析。
- 思考在 `reasoning_content`；带 tools 的多轮要回传 reasoning_content，否则原厂 400。
- 流式统计附在最后一个内容块上、没有单独 usage 块，网关别等「纯 usage 块」；方舟 0910 / GA 会在 finish 块之后再单发一个纯 usage 块，两处都读到时别重复计费。
- `thinking` 枚举各家不一（原厂 adaptive / enabled / disabled，方舟 v4.1 拒 adaptive 和 auto，GA 收 auto，TokenHub 收 adaptive 拒 auto）：混挂多家时要归一化或透传报错。
