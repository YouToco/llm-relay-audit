# GLM 文本线路（官方基准：智谱原厂 + 火山方舟托管）

> Last verified: 2026-10-20；价格与行为以官方文档为准。

## 官方接口
- 智谱：`POST https://open.bigmodel.cn/api/paas/v4/chat/completions`，模型名 `glm-5.2` / `glm-5.3-flash`（`/models` 还有 glm-5.3、glm-5.3-flashx）。
- 方舟：`POST https://ark.cn-beijing.volces.com/api/v3/chat/completions`，Bearer；模型填接入点 ID `glm-5-2-260617` / `glm-5-3-flash-260828`。
  - `GET /api/v3/models` 免费，回 features / token_limits（两个都标 text-only、json_schema false、prefix_cache true、最大输出 131072）。
  - **每个模型要先在方舟控制台开通**，没开通 404 `ModelNotOpen`，且报错里带账号号——存证 / 报告前打码。

## 计数接口
- 智谱 tokenizer 对 glm-5 系返回 0（2026-10-13）；方舟 `/api/v3/tokenization` 只切纯文本、不含聊天外壳。→ 判真伪直接用两家真实 usage 比（小请求，费用极低）。
- 两家 prompt_tokens **逐个相等**（关思考：hi 7、system + 段落 76、三轮 35、2k 长文 2177）；关思考比默认少 6（模板差异）。
- 带工具 156；**工具 JSON 键按字母排序后变 155**——中转把请求重新序列化时会露出这个 −1，别当注入。
- 思考 token 计入 completion_tokens，按输出价。

## 价目（元 / 百万 token，2026-10-20 取，以官方页为准）
| 模型 | 输入 | 缓存命中 | 输出 | 出处 |
|---|---|---|---|---|
| glm-5.2（方舟 glm-5-2-260617） | 8 | 2 | 28 | 方舟「模型价格」volcengine.com/docs/82379/1544106、docs.bigmodel.cn/cn/guide/start/pricing |
| glm-5.3-flash | 0.8 | 0.23 | 2.8 | 同上；两家同价、不分档、无折扣（智谱 flash 模型页仍有「限时折扣」字样，未核实） |
- 方舟缓存存储 ¥0.017 / 百万 / 小时（隐式缓存不收存储）；方舟文档缓存最少 token：glm-5-2 2048、glm-5-3-flash 8960。

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
| 图片输入（glm-5.2） | 收（82 token）但答错颜色 = 不看图 | 400 只许 text |
| json_schema | glm-5-2 照收不强制；glm-5-3-flash 400「not supported by this model」 | — |

- 缓存：方舟同前缀第 2 次有时命中有时不中，不能拿单次未命中判中转丢缓存。

## 判真伪招数是否有效
- **超大 `max_tokens` 逼模型名无效**：方舟 `9999999` 照常回答扣费；智谱报范围不报模型名（对照 claude.md）。
- 有效：
  1. 第一个 200 看 id：`021…` 53 位 = 方舟；30 位时间串 + request_id = 智谱。
  2. temperature 1.5 一单：200 = 方舟系，400 1210 = 智谱。
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
- glm-5.3-flash 始终思考：客户传关思考会 400（智谱）或被忽略，网关要么透传报错、要么文档写明。
- 智谱 temperature 上限 1、方舟 2：同一模型名混挂两家时要统一裁剪，否则客户随机碰 400。
- 报错归因要保留上游原码（方舟 `InvalidParameter` / 智谱 `1210` 等）。
