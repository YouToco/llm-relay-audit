# new-api / one-api 系中转：多分组、倍率、参数透传、日志对账

> Last verified: 2026-10-23；new-api 各分叉行为不同，以实测为准。
> 判真伪通用步骤见 `text-checks.md`，免费探针通用坑见 `probing-tips.md`，Claude 官方基准与对账见 `claude.md`，订阅号池见 `sub2api.md`。

## 认出 new-api 系
- 响应头带 `X-New-Api-Version`、`X-Oneapi-Request-Id`；上游响应头通常被剥光（没有 `request-id` / `anthropic-organization-id` / `Apim-Request-Id` / 限流头）。少数分叉版本会透传上游头，看到就多一份证据。
- `/api/status`、`/api/pricing` 免登录可读；`/v1/messages/count_tokens` 多半 404，官方 token 基准只能用官方 key 现取（免费，规则 10）。
- 一个站点常挂多个分组，每组背后可能是完全不同的后端（Azure、逆向 Codex、Bedrock、厂商一方 API 混在同一站）。**按组测，别把一组的结论套到另一组**。

## 管理接口：访问令牌 vs sk key
- 供应商给的可能是**访问令牌**（不是 `sk-` key）：`/api/*` 管理接口用 `Authorization: <访问令牌>`（直接放，不加 Bearer）；老分叉还要头 `New-Api-User: <数字用户 id>`，缺了报 `New-Api-User header not provided`，新版已去掉。
- 数字用户 id：`GET /api/user/self` 的 `id`，或站点的账户设置页；也可在使用者已登录的浏览器里只读 `JSON.parse(localStorage.user).id`（只取 id / username / group，别读别的）。
- **建 key**：`POST /api/token/`，body `{name, group, unlimited_quota, remain_quota, expired_time:-1}`。创建响应 `data=null`，列表 / 详情里 key 全打码；完整 key 要再 `POST /api/token/:id/key` 取。
- 测试账户若和线上业务共用：新建测试 key 一律 `unlimited_quota:false` + `remain_quota` 限额，名字带 `eval-<日期>`，已有 key 只读不碰。
- 可选分组清单：`GET /api/user/self/groups`（带 ratio / desc）。各组能用哪些模型：用该组 sk key 打 `/v1/models`（免费）。
- 余额：`GET /api/user/self`；先看余额再跑——**余额不足时请求回 403「预扣费额度失败」**，预扣额 = `max_tokens` × 单价，超大 `max_tokens` 探针会要几百上千额度。

## 价目：`/api/pricing`、`group_ratio`、`billing_expr`
- `/api/pricing` 给每模型的 `billing_expr`（如 `p*4 + c*20` = 输入 $4 / 输出 $20 每百万 token）和各组 `group_ratio`。
- 实测 base 系数大多 = 官方 list 价，此时 **`group_ratio` 就是官方价的倍数**。但**要逐个模型和官方价比**：见过某站把个别模型的 `billing_expr` 底价写得比官方高，倍率之外再多收。日志 `other.expr_b64` 解码 = 该笔实际用的公式。
- 倍率 < 1 常见于逆向 / 订阅资源（推断）；> 1 也不代表更真，真伪另判。
- **真实贵贱要看充值汇率**：站点 `usd_exchange_rate` 常为 1、`top_up_link` 常为空；灰产常见「¥X 买 $1 额度」。报告写「显示价 = 官方 × 倍率」，贵贱注明需供应商提供充值档。

## 日志对账：`/api/log/token`
- `GET /api/log/token?key=<sk>`（用 **sk key**，不是访问令牌），免费。逐笔字段：`quota`、`usage_usd`、`model_cost_usd`、`pricing_accuracy`、`other.group_ratio`、`other.cache_ratio`、`other.expr_b64`、渠道号。
- `type 2` = 成功扣费；`type 5` = 被拒请求，`content` 里是响应里被抹掉的真实原因；`other.channel_name` 常露出上游渠道名；`other.request_conversion` 出现「OpenAI Compatible」= 中间做了格式转换，按 `claude.md`「经 OpenAI 格式转换」一节重点测非流式工具、内置工具、缓存。
- 额度单位：**500000 quota = $1**。微型调用 `quota` 会取整成 0，看 `usage_usd`。
- `/v1/dashboard/billing/usage` **默认不可信**（见过一单读错几百倍）；个别站的 `total_usage`（美分）可信，先拿日志核对一次再当总额用。
- 账户 `used_quota` 混着其它流量，不能当本次花费；本次花费用测试 key 的 `GET /api/token/:id` `used_quota` 求和，按预估拦。
- `/api/log/self?token_name=` 是**模糊匹配**，要按 request id 去重。部分站 `/api/log/token` 有限流（`Retry-After` 约 1 分钟，连续重试会一直被顶住），拉开间隔。

## 错误外壳
- **一锅端**：越组 / 跨厂 / 假模型常报同一个 `get_channel_failed`；状态码不可信（没渠道有的报 503、有的报 429）。
- 503 / 429 按 `error.code` 分两类（规则 9，同一组 × 模型共测 3 次）：`model_not_found`「No available channel for model X under group <组名>」= 配置没挂（报错常漏内部组名）；`unknown_error` / `get_channel_failed` /「上游暂时不可用」= 上游偶发、常能恢复。**`model_not_found` 也见过 20 分钟后自己恢复**，「永久」要复测后再下。
- 后面接 Bedrock 时：透传的 400 外壳是 `{"type":"error","error":{"type":"<nil>","message":"operation error Bedrock Runtime: InvokeModel … ValidationException: …"}}`（`error.type` 是 Go 空值、无 request_id），型号 id 区域前缀被打码成 `***.claude-…`；「负载饱和」429 / 503 会在中转内部重试 1–5 分钟才回，客户端超时设短、复测间隔拉开。

## 参数被吞 / 透传矩阵
- **非法参数被吞**是常态：`temperature=9`、`top_k=-5`、`service_tier=bogus`、`inference_geo=mars` 官方 400，new-api 常返 200（值被丢）。合法值也可能被静默剥掉：`inference_geo:"us"` 回包仍 `global`。
- 缺 `max_tokens` 会补默认值成交（不是免费探针）；`max_tokens=0` 会被改写成交，**也不免费**。
- 同站不同组行为不一样：有的组由上游（Bedrock）回 400，有的组吞掉。**按组测**。
- **「参数透传」分组名不可信，逐字段矩阵测**：同一模型，每次只让一个字段非法（官方都 400），看中转 400（原样透传校验）还是 200（被吞 / 被删）：
  `temperature=9`、`top_k=-5`、`service_tier=bogus`、`inference_geo=mars`、`speed=bogus`、未知顶层字段、`anthropic-beta: bogus`、`anthropic-version: 1999-01-01`、`max_tokens=0`（付费）、旧 `thinking.enabled`（只认 adaptive 的型号）。
  再测合法值是否生效：`inference_geo:"us"`（回包 `usage.inference_geo` 应为 `us`，官方价 ×1.1）、`stop_sequences`、`output_config.effort`、`metadata.user_id`。
- **对照组**：同站「不透传」分组跑同一矩阵，才能说清「透传」多透了什么。见过标透传的组只透一部分（丢 `inference_geo` / beta / version 头），标不透传的组反而让合法 `inference_geo:"us"` 生效（且没加价）。
- 模型规矩不是中转 bug：OpenAI 推理模型 chat 口要 `max_completion_tokens`，函数工具要 `reasoning_effort=none` 或走 `/v1/responses`。

## 认后端：response id 与 body
- 第一个 200 就看 id 前缀：`msg_011C…` = Anthropic 一方；`msg_bdrk…` = AWS Bedrock；`chatcmpl…` = OpenAI / Azure chat；`resp_…` = OpenAI Responses（逆向 Codex 也走这个）。再故意发一个非法参数，看报错原文露不露上游（`Bedrock Runtime` / Vertex / Azure）。报告第一张卡写「分组名说的」vs「实测后端」。
- **Azure 看 body 不看头**（头已被剥）：`usage.latency_checkpoint`（engine / service ttft、pre_inference）、流式 `obfuscation`、`system_fingerprint`。Codex 这些都没有。透传头的分叉还能看到 `azureai-fe-offer-type: paygo`、`x-ratelimit-key`、`x-ratelimit-remaining-tokens`（剩余 TPM 很小 = 容量紧）。
- **OpenAI API 账户 vs ChatGPT / Codex 后端**：`resp_` 后第 35–38 位（0 起）API 账户见到 `87d1`、ChatGPT / Codex 见到 `8191`（样本有限，推断规律）。Codex 还会：回显 `instructions`「You are Codex…」并在 `usage.attribution` 里给 instructions 计 token（每次约 4,380，照收）；丢 `max_output_tokens` / `temperature` / `top_logprobs`；`store` 强制 false；`previous_response_id`「not available for this user」；流式带 `openai_chatgpt_moderation`。**同一分组里可能混着两种，按模型逐个看**。
- **故意发非法参数也要看 id**：见过 API 拒绝后改投 Codex 池（`temperature 9` → 200 + Codex 注入照收），或回 `resp_ft_…` 这种非 OpenAI 的 id——「官方 400、它 200」本身就是证据。
- **Bedrock 上的 OpenAI**：回包 model = `global.openai.<型号>` / `us.openai.…`（Bedrock 跨区推理 id）；`resp_` / `chatcmpl-` 后是 52 位小写 base32（官方是十六进制）；头带 `x-amzn-requestid`；`input_tokens` 照样 = 官方 `/v1/responses/input_tokens`。Bedrock 限制原样传给客户：图片只收 `data:` / `s3://`（http URL 400）、没有 Priority（`priority` 回 `default`）、gpt-oss 不支持 Responses。价按 OpenAI 指南 = 官方直连价（单区域 +10%）。**这里 `temperature=9` 不是保险**：见过全型号照收成交，先用一个型号试。
- **超大 `max_tokens` 招数对 GPT 无效**：官方 `max_output_tokens: 9999999` 过校验，中转会真成交扣钱；GPT 认后端靠上面的 id 段 + instructions。

## 换模型识别
- **第一步（便宜，判「是不是」）**：同一句（裸「Reply with the single word OK.」）+ 带厂商专属工具（Claude 用 `text_editor_20250728`，放大到上千 token 更灵敏），各组真实请求的 `input_tokens` 逐个和官方 count_tokens 比。**提示词和建基准时一字不差**，换短提示词会造成假性不符。多出来 = 注入隐藏系统提示或换了模型。
- 不同代分词器不同（例：Claude 5 代 18 / 带工具 1289，fable-5 16 / 1291），数对不上 = 换了模型；**同一代几个型号数一样，分不出是谁**，不能写「像某一代」就停。
- **第二步（免费，判「是谁」，只对 Claude 有效）**：其他字段合法，发 `max_tokens: 9999999`，上游 400「`max_tokens: 9999999 > 128000, which is the maximum allowed number of output tokens for <真实模型名>`」。400 不扣费（日志 type 5、quota 0）。每个模型都发，并在官方同发对照：正常型号报自己的名字，被换的报替身名字。
- 案例（匿名）：某组 `claude-fable-5` 实际跑 `claude-opus-5-5`，回包 `model` 照写 fable-5、按贵模型价收，只有报错说了实话。
- 中转改写 / 抹掉上游报错时退回看：默认思考块（官方 fable-5 回 OK 也出 `thinking` 块，opus-5-5 没有）、输出 token 数、耗时（真 fable-5 约 4–6 秒、替身约 2 秒），拿替身型号并排比这几项是否完全一样。
- 报告分开写「是不是」（token）和「是谁」（报错模型名）两条证据，附原文。

### Claude 官方 count_tokens 基准（2026-10-14，裸「Reply with the single word OK.」）
opus-5-5=18 / opus-5=16 / opus-4-8=16 / opus-4-7=21 / opus-4-6=14 / sonnet-5-5=18 / sonnet-5=16 / sonnet-4-6=14 / sonnet-4-5=14 / haiku-5-5=18 / haiku-4-5=14 / fable-5=16 / fable-5-1=18；带 `text_editor` 工具 opus-5-5=1289。过期按规则 10 现取。

## 多分组一次测完
- 拿到访问令牌后：列分组 → 每组建一把限额 key → 每组 `/v1/models` → 同一批免费探针（id 前缀、非法参数、`max_tokens` 招数）逐组跑 → 同一句真实请求逐组比 token → 日志读实扣与 `group_ratio`。报告做「分组一览 + 真伪 token 表 + 成本倍率表」三张表。
- **同站不同倍率可能是同一上游**：上游版本头、限流额度一样时，先在 A 组写一段约 6,700 token 的固定前缀，再到 B 组发同一前缀，`cached_tokens` 首次就命中 = 同一上游账号（推断依据：缓存按账号隔离）。
- **分组标签观测不到**：「可否蒸馏」「官 key」「参数透传」这类用途 / 营销标签是供应商的用途政策或营销名。见过两个这样标签的组都是真 Bedrock、同倍率、`input_tokens` 都和官方相等、无注入——请求响应里没有可观测的差异，报告别据此下结论。
- 模型名带后端字样（如带 AWS / Bedrock 字样的后缀）也不算证据，见过回一方 id 的。

## 图片输出
- 生图模型常在单独的生图分组。出图可能是真 OpenAI（C2PA 签发方 `OpenAI OpCo, LLC`、签名有效），但**被转存到中转自己的对象存储**，url 域名非官方；有的转存后文件哈希与签名不匹配（字节被重处理），有的匹配。
- 同组可能混 url 型和 b64 型；见过另一种 b64 后端无 C2PA、输入 token 多 13、medium 质量 515 token——**看回包形状 + token 就能分后端**，不必每张跑 C2PA。
