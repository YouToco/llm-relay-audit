# GLM 文本线路（官方基准：智谱原厂 + 火山方舟托管）

> Last verified: 2026-10-20（方舟 / 智谱官方 key 实测）；**glm-5.3 与 glm-5.3-flash 补测 2026-10-30**（智谱官方 key）；价目 2026-10-29。价格与行为以官方文档为准。

## 官方接口
- 智谱：`POST https://open.bigmodel.cn/api/paas/v4/chat/completions`，模型名 `glm-5.2` / `glm-5.3-flash`（`/models` 还有 glm-5.3、glm-5.3-flashx）。
- 方舟：`POST https://ark.cn-beijing.volces.com/api/v3/chat/completions`，Bearer；模型填接入点 ID `glm-5-2-260617` / `glm-5-3-flash-260828`。
  - `GET /api/v3/models` 免费，回 features / token_limits（两个都标 text-only、json_schema false、prefix_cache true、最大输出 131072）。
  - **每个模型要先在方舟控制台开通**，没开通 404 `ModelNotOpen`，且报错里带账号号——存证 / 报告前打码。

- 智谱 `/models` 列 11 个（glm-4.5 … glm-5.3、glm-5.3-flash、glm-5.3-flashx）；方舟 `/api/v3/models` 是全平台基础模型。
- 方舟流式：chunk 键序 `choices, created, id, model, service_tier, object, usage`，每块 `usage: null`，**usage 单独一块 `choices: []`**；智谱流式 `id, created, object, model, choices`，usage 跟在最后一个带 `finish_reason` 的块里；都以 `data: [DONE]` 结尾。

## 计数接口
- 智谱 tokenizer 对 glm-5 系返回 0（2026-10-13）；方舟 `/api/v3/tokenization` 只切纯文本、不含聊天外壳。→ 判真伪直接用两家真实 usage 比（小请求，费用极低）。
- 两家 prompt_tokens **逐个相等**（关思考：hi 7、system + 段落 76、三轮 35、2k 长文 2177、`Say OK.` 9）；关思考比默认少 6（模板差异）。智谱 `thinking: auto` 回 12（自己决定不思考），方舟 auto 回 18 照样思考。
- **例外：`json_object` 智谱 73、方舟 20**——智谱往提示里注入了约 53 token 的 JSON 指令；中转按智谱卖时多出这截不是中转注入。
- glm-5.3 / glm-5.3-flash（智谱，始终思考，effort=low）：hi 13、system + 段落 82、多轮 41、带 tools 162、默认 18、质数题 25、json_object 26、`Say OK.` 15；长输入 3,261 / 5,961 / 9,741（flash 各 +1）。flash 图片 40。
- 带工具 156；**工具 JSON 键按字母排序后变 155**（去 description 150、去 required 149）——中转把请求重新序列化时会露出这个 −1，别当注入。
- 思考 token 计入 completion_tokens，按输出价。

## 价目（元 / 百万 token，2026-10-20 取，以官方页为准）
| 模型 | 输入 | 缓存命中 | 输出 | 出处 |
|---|---|---|---|---|
| glm-5.2（方舟 glm-5-2-260617） | 8 | 2 | 28 | 方舟「模型价格」volcengine.com/docs/82379/1544106、docs.bigmodel.cn/cn/guide/start/pricing |
| glm-5.3-flash | 0.8 | 0.23 | 2.8 | 同上；两家同价、不分档；智谱价目页 2026-10-29 已没有折扣字样 |
| glm-5.3（智谱） | 8 | 2 | 28 | docs.bigmodel.cn 价目页（2026-10-29 / 10-30）；同 glm-5.2 |
| glm-5.3-flashx（智谱） | 2 | 0.57 | 7 | 同上 |
- 方舟缓存存储 ¥0.017 / 百万 / 小时（隐式缓存不收存储）；**智谱缓存存储「限时免费」**（页上没写截止日）。方舟文档缓存最少 token：glm-5-2 2048、glm-5-3-flash 8960。智谱 1M 上下文；支持 Batch 的模型五折。

## 官方指纹（两家「脾气」差异，认后端用，2026-10-20 实测）
| 判据 | 方舟 | 智谱 |
|---|---|---|
| 回包 id | `021` + 13 位毫秒时间戳 + hex，53 位；无 request_id | 30 位时间串，= `request_id` |
| model | 接入点 ID | glm-5.2 |
| temperature 上限 | 2（1.5 照收） | 1（1.5 → 400 code 1210） |
| max_tokens | **不含思考**（64 照样输出 1000+ token）；≥ 0；`9999999` 不报错、照常回答扣费 | 含思考（到上限 finish=length）；范围 [1, 131072] |
| thinking | enabled / disabled / auto；`bogus` → 400 InvalidParameter | `bogus` 照常回答（200）；glm-5.3-flash 关思考 / auto → 400「该模型始终思考」 |
| reasoning_effort | 7 档都收，glm-5-2 low / medium 映射为 high | none…max 7 档 |
| logprobs | 回 `logprobs.content`（文档说思考模型不支持，实测能用） | 不回 |
| 工具调用 id | `call_` + 24 位小写字母数字 | `call_-<数字>`（负数）+ `index` |
| 报错外壳 | `{error:{code:"InvalidParameter",message:"… Request id: 021…",param,type:"BadRequest"}}`；不存在模型 404 `InvalidEndpointOrModel.NotFound`；无 key / 错 key 401 `AuthenticationError` | `{error:{code:"1210",message}}`；不存在模型 400 `1211`；无 key 401 `1001` |
| 响应头 | `server: istio-envoy`、`x-request-id`（= id）、`x-client-request-id`、`x-envoy-upstream-service-time` | `x-log-id`、`ga-traceid` 等 |
| 图片输入（glm-5.2） | 收（82 token）但答错颜色 = 不看图 | 400「messages.content.type 参数非法，取值范围 ['text']」 |
| 图片输入（glm-5.3-flash） | 没测（账号未开通） | **不关思考时 200、答对颜色**（40 token）；带 `thinking: disabled` 才 400「始终思考」 |
| json_schema | glm-5-2 照收不强制（输出带 ```json 围栏） | glm-5.2 同样照收不强制 |

- 缓存：方舟同前缀第 2 次有时命中有时不中（`caching: enabled` 那组第 2 次反而 0、复测 3 次全 0），不能拿单次未命中判中转丢缓存。智谱 glm-5.2 `caching: enabled` 第 2 次 2176、默认 0；glm-5.3（开思考，约 3.3k 前缀）默认第 2 / 3 次命中 3,200，flash 默认第 2 次 0、第 3 次 3,200（官方也会有一次不中）。
- **报错原文**（官方实测）：
  - 无 key：方舟 401「the API key or AK/SK in the request is missing or invalid」；智谱 401 `1001`「Header中未收到Authorization参数，无法进行身份验证。」。错 key：方舟「The API key format is incorrect.」；智谱 401「令牌已过期或验证不正确」。
  - 不存在模型：智谱 400 `1211`「模型不存在，请检查模型代码。」。空 messages：方舟「…an array with minimum length 1…」；智谱 `1214`「输入不能为空」。
  - temperature 9 / top_p 5 / max_tokens -1：方舟「expected a value <= 2 / <= 1 / >= 0」；智谱 glm-5.2 `1210`「限制数值范围[0,1]」/「[1,131072]」。
  - reasoning_effort=bogus：方舟「value `bogus` is invalid」；智谱 1210 列出 none、minimal、low、medium、high、xhigh、max。role=bogus：方舟列出 system / assistant / user / tool / developer；智谱 1214「角色信息不正确」。tool_choice 指定不存在函数：方舟「Specified function 'nope' not found in available tools」；智谱 1210「API 调用参数有误，请检查文档。」
- 工具调用 arguments：方舟和智谱 glm-5.2 带空格 `{"city": "Shenzhen"}`，glm-5.3 / flash 紧凑 `{"city":"Shenzhen"}`。

## glm-5.3（智谱官方 key 实测 + 当天文档，2026-10-30）
- 文档（docs.bigmodel.cn 模型页）：**始终思考**，`thinking.type` 只收 `enabled`（关思考 / auto → 400 `1210`「该模型始终思考，不支持关闭思考；请使用 low、high 或 max。」）；`reasoning_effort` low / high / max，默认 max（medium 400）；仅文本（图片 400）；1M 上下文，最大输出 128K。实测与文档一致。
- **和 glm-5.2 不同：参数越界现在照收**——temperature 9、top_p 5、temperature 1.5 都 200（文档写 [0,1]，实际自动收敛），glm-5.3-flash 同；flash 指定不存在的函数也 200。中转回 400「越界」不等于官方行为。max_tokens 仍是 [1,131072]（131073 400）。
- max_tokens 含思考（512 → finish=length，completion 512、reasoning 509）；`logprobs: true` 不返回 logprobs；id 30 位时间串 = `request_id` = 响应头 `X-LOG-ID`；tool call id `call_-<19 位负整数>` + `index: 0`。
- **判后端的新判据**：多轮把上一轮 `reasoning_content` 原样回传时，智谱第 2 轮输入**不计入**上一轮思考（第 1 轮 28 → 第 2 轮 46）；回 170 多的说明后端模板保留了历史思考（不是智谱）。`clear_thinking` 不传 = true（多轮带历史思考输入 75），false = 159。
- 官方参数逐项：`do_sample: false` 两次输出相同；top_p 0 也照收；`stop` 对思考也生效（思考里碰到就停、`content` 空），5 个 stop 400「A maximum of 4 stop words is allowed.」；`tool_stream` 把工具参数分块流出；内置 `web_search` 真搜索（输入约 4,200–4,400、回包带 `web_search`）；客户自带 `request_id` 原样回显；只有 system 消息 400「messages 参数非法」。

## 其它托管 / 自建后端的认法
- **阿里百炼托管 glm-5.3**（百炼官方 key，同一批非法参数，2026-10-30）：百炼文档里 `glm-5.3` 由百炼自己推理，另有 `ZHIPU/GLM-5.3` = 智谱原厂直供（北京价同为 8 / 2 / 28）。
  - 回包 id `chatcmpl-<uuid>`（第三段 9 开头）= 响应头 `x-request-id`；没有 `request_id`。经一家中转看到百炼格式回包的流式 usage 单独一块（`choices: []`）、会回 `logprobs`（智谱不回）——这两条没直接打百炼验证。
  - 报错 OpenAI 风格外壳 + `code: invalid_parameter_error`：关思考「The value of the enable_thinking parameter is restricted to True.」、top_p「'top_p' must be in (0.0, 1.0]」、thinking.type「'type' must be in ["enabled", "disabled", "auto", "adaptive"]」、reasoning_effort「'reasoning_effort' must be one of: 'low', 'high', 'max'」、tool_choice「The tool specified in `tool_choice` does not match any of the specified `tools`」、temperature 9「<400> InternalError.Algo.InvalidParameter: Temperature should be in [0.0, 2.0)」。百炼文档写 glm-5.3 有「非思考和思考模式」，实测关思考 400（同智谱）。
- **自建推理集群的痕迹**：SGLang 回 32 位 hex id、`choices[].matched_stop`、`metadata.weight_version`，经 SGLang Model Gateway 时响应头带 `x-smg-routed-worker-id`；vLLM 在每个流式 chunk 和非流式回包带 `system_fingerprint: vllm-<版本>-tp…`；Rust 网关的报错「Failed to deserialize the JSON body into the target type」「Validation error … Number(5.0)」。响应头 `req-arrive-time` / `req-cost-time` / `resp-start-time` 是 Higress 类网关加的，百炼和自建集群前面都可能有，**不能单凭它认百炼**。

## 判真伪招数是否有效
- **超大 `max_tokens` 逼模型名无效**：方舟 `9999999` 照常回答扣费；智谱报范围不报模型名（对照 claude.md）。
- 有效：
  1. 第一个 200 看 id：`021…` 53 位 = 方舟；30 位时间串 + request_id = 智谱。
  2. temperature 1.5 一单：200 = 方舟系，400 1210 = 智谱 glm-5.2（**glm-5.3 系智谱也 200**，这招只对 5.2 有效）。
  3. 非法参数看报错原文：方舟原文带 `Request id: 021…`（规则 5：只让被测项非法）。
  4. 同一份 messages 关思考比 prompt_tokens；带工具差 −1 先查是不是键名被重排。
  5. 字段集合（顶层 / usage / 响应头 / SSE）与官方程序求差集（规则 12）。
  6. 计费：方舟上 max_tokens 不含思考，中转若按「max_tokens 预留」结算会少收 / 400 时多收——逐单余额要 6 位小数精度去量。

## 中转常见问题（匿名）
- 方舟官方接入点原样转发型：id / 报错原文 / `x-client-request-id` 透传，字段集合与方舟差集为空、token 与方舟逐个相等；但请求 JSON 键名被重排（工具 −1）、`Server` / `X-Request-Id` 换成自己的、报错外壳改成自家格式（方舟原码挪到另一个字段）。
- **小模型按大模型价收**：flash 按 glm-5.2 价结算（约 10 倍）→ 每个模型单独测单价，别外推。
- 预留结算：先按「max_tokens × 输出价 + 请求体长度估输入」预留，结算不超过预留（思考超 max_tokens 时少收）；**上游 400 照扣整笔预留**，平台自拦的错不扣；不传 max_tokens 按约 1024 预留；超大 max_tokens 直接被拒。
- 只实现 chat/completions，Responses / tokenization / embeddings 不通——接入前逐个路径探。
- 额度接口取整读不出单笔费用，用 `billing/subscription` 的 `hard_limit_usd`（6 位小数）。

## 接入网关要求
- 方舟线 max_tokens 不含思考：网关按 max_tokens 估费 / 限额会低估，要以 usage 实结。
- glm-5.3 / glm-5.3-flash 始终思考：客户传关思考会 400（智谱、百炼）或被忽略，网关要么透传报错、要么文档写明。
- 智谱 temperature 上限 1、方舟 2：同一模型名混挂两家时要统一裁剪，否则客户随机碰 400。
- 报错归因要保留上游原码（方舟 `InvalidParameter` / 智谱 `1210` 等）。
