# Seedance（字节，火山方舟 / BytePlus ModelArk）官方基准

> Last verified: 2026-10-28；价格与行为以官方文档为准。

状态：官方原片指纹（C2PA 国内 1 张 + 海外 2.5 / 2.0 各 1 张证书、桶、编码器、文件名）、样片 draft、参考素材计费口径、基础报错原文已实测（国内 2026-10-21 / 10-27，海外 2026-10-28）；官方非法参数矩阵还不全、各档价目待补。
官方基准两个：火山方舟（国内）、BytePlus ModelArk（海外）。新出官方单先报价（规则 2）。

## 必查三件事（规则 15）与一票否决（规则 16）

1. **成片是不是官方原片**：C2PA（签名有效、哈希匹配、**签发者证书指纹 = 已知官方指纹**）+ 官方桶名逐字比 + 编码器指纹。
2. **支不支持样片 draft**：D1–D5 清单（下文）；D4 真出 1080p 且画面是样片的高清版才算支持（规则 7）。
3. **返回的链接和参数是官方的还是包装过的**：官方成片直链、官方 `cgt-` 任务号、`resolution` / `duration` / `usage` 还在——换字段名可以接受（网关能映射）；全被封装成中转自己的链接、句柄、字段就无法接入。填 findings `passthrough`。

**规则 16**：拿不到方舟 / BytePlus 官方桶的原始直链，或成片不是原片（C2PA 签发者指纹对不上已知官方指纹 / 签名无效 / 哈希不匹配 / 无 C2PA），判不可接入。第一单出片先查这两条，不过就停测，样片、价格、其它档位都不用再测。
转存到中转自己的桶、云点播、CDN，或仿冒官方桶名，都算拿不到原链接。

## 素材库和样片 draft 都是必测项

- **每家 Seedance 都要测全素材库 + 样片**：照对方最新文档把素材接口逐个过一遍（建组 / 登记图片 / 登记视频 / 查询 / 列表 / 删除，文档有就测），并**真引用 `asset://` 出片**（图片素材至少一单）——建素材回 `ready` / `Active` 不算支持；样片按下文 D1–D5（规则 7）。
- **读文档时先找素材库和样片两份文档**：对方网站 / 文档站读不到其中任何一份 → **先停，问用户有没有素材库 / 样片 draft 的文档**（可能在对接群、另一个文档站或没公开），拿到后再跑免费探针和后续所有测试；用户确认对方确实没有，才判「不支持」。别自己猜接口路径就下结论，也别测到一半才停。
- **素材库不可用就停测**：素材接口一般免费，放在免费探针最前面测；不支持或账号没开通 → 不报价、不跑任何付费单，报告写「素材库不可用，未继续测」，问对方能否开通，开通后从头再测。
- **测完不支持也要明确写**：报告和内部卡逐项写「支持 / 不支持（附原文报错）/ 文档没写（已问用户）」，不能空着或只写测过的那几项。
- **没指定模型时接口列出的 Seedance 模型每个都测**（规则 8 的 Seedance 例外）：至少最低档 480p 4 秒一单，2.5 另加样片；测试金不够就在报价里列清哪些模型测不了、要测全还差多少（按预扣额算），问用户充值还是先测够钱的（新模型优先）。

## 官方接口与响应

- 协议：Ark `POST /api/v3/contents/generations/tasks`（创建）/ `GET /api/v3/contents/generations/tasks/{id}`（查询）；任务号形如 `cgt-YYYYMMDDHHMMSS-xxxxx`，时间是**北京时间**。
- 计费 token：`usage` = `宽 × 高 × 帧数 / 1024`（向下取整）。帧数：4 秒 97 帧、10 秒 241 帧。
  - 2.5：480p = 854×480，4 秒 38,830；720p 4 秒 87,300；1080p 4 秒 196,425；480p 10 秒 96,475。
  - 2.0 mini：480p = 864×496，4 秒 40,594（国内、海外一样）。
  - **海外 2.5 普通 480p 已换成 864×496 = 40,594**（官方实测 2026-10-28；最晚 10-27 起），**样片 480p 仍是 854×480 = 38,830**；国内两种都是 854×480。判中转 480p「尺寸 / usage 不对」前先看是海外还是国内、是不是样片。
- **参考素材的 token 口径**（官方实测，海外 2026-10-28，480p 4 秒、关音频、不传 `ratio`）：
  - 首帧 / 首尾帧跟原图比例出片，按实际宽高算：1920×1088 的图 → 850×482（`ratio: 425:241`）= 38,809。
  - 参考图不改比例、默认 16:9 = 854×480 = 38,830（同一时段纯文生 480p 是 864×496）。
  - **参考视频 = (输入帧 + 输出帧) × 宽 × 高 / 1024**：4 秒参考（按 96 帧算）+ 4 秒输出 = (96 + 97) × 854 × 480 / 1024 = 77,260。图片不计 token。
  - URL、base64（`data:` 原样转上游）、素材库 `asset://` 三种写法出片规格一样。
- 计价分档按分辨率 × 是否含参考视频：**只有带 `reference_video` 的单进 `with_ref` 档**（官方实测 2026-10-28 核过），首帧 / 首尾帧 / 参考图都算 `no_ref`。中转把参考图单算进 with_ref、或参考视频不算输入帧，都是计费错。单价以官方页为准。
- **任务对象字段**（官方原生）：`id model status content{video_url} usage{completion_tokens,total_tokens} created_at updated_at seed resolution ratio duration framespersecond service_tier execution_expires_after generate_audio draft priority output_format`；正式片多 `draft_task_id`（指回样片 cgt）。`execution_expires_after` 官方默认 172800（见过中转没传时被设成 3600）。
- **官方报错原文**（国内 2026-10-21 / 10-27、海外 2026-10-28 一致）：
  - `duration:1` → 400 `InvalidParameter`「the parameter duration … is not valid for model <名>」（报错里带模式名：纯文本 `t2v`、首帧 `i2v`、参考图 / 参考视频 `r2v`；**两张图都不写 `role` 按参考图处理（`r2v`），不是首尾帧**）。参考素材单这类错是提交 200、终态 `failed` 才看得到。
  - 首帧 / 尾帧和参考素材混用 → 400「… first/last frame content cannot be mixed with reference media content」。
  - 编造的 `asset://` 素材号：上游先报 `duration` 错（素材号存在性在参数校验之后才查）。
  - 错 key 401 `AuthenticationError`「The API key doesn't exist」；查不存在任务 404 `ResourceNotFound`；不存在的模型 404 `InvalidEndpointOrModel.NotFound`；海外 key 没开该模型 403 `AccessDenied`。
  - 样片相关见下「样片 draft」。
- 海外有声版会被音频版权审核拒（终态 `failed`、`OutputAudioSensitiveContentDetected.PolicyViolation`、不收费），普通提示词也会；官方一侧遇到也一样，中转这一单失败不算它的问题，关音频重跑。
- 方舟任务列表按**主账号**返回（不按项目 / key 隔离）：共用主账号时能列到别人的任务。**按规则 17 处理**：发现即停，只记「能列到别人的任务」和条数，不读任务内容、不下载成片，探针日志里删掉别家任务只留计数，报告给用户。
- 方舟 API key 管理（OpenAPI，AK/SK 签名）：`ListApiKeys {ProjectName}` 看 key 是否还在；`CreateApiKey` 需 `ResourceInstances:[{ResourceType:"presetendpoint",ResourceIds:[<模型>]}]`；`GetRawApiKey {Id}` 取值。key 回「API key doesn't exist」而 AK/SK 有项目权限时先查这个。建 key 会改动账号所有者的资源，先取得对方明确同意。

### 样片 draft（官方，2026-10）

- `draft:true`：**当前在售系列里只有 2.5 支持**（1.5 Pro 曾有 480p 样片模式），只能 480p，按 480p 正常价计。
- 正式片：`content` 只放 `{"type":"draft_task","draft_task":{"id":"<样片的官方 cgt 号>"}}` + `resolution:"1080p"`；提示词 / 素材 / 时长 / 比例 / seed / 有无声音从样片继承，**再传会报错**；按 1080p 计。样片号 7 天有效。
- 官方实测（2026-10-08 国内；10-21 / 10-27 国内、10-28 海外复测一致）：样片 38,830 token（480p 4 秒）→ 正式片 196,425 token（1080p 4 秒），状态体 `draft_task_id` 指回样片；正式片复用样片，20–31 秒出完，继承 seed / 时长 / 比例 / 有声。
- 官方报错：样片号不存在 → 400 `InvalidParameter`「The parameter `content[0].draft_task.id` … is not valid: the parameter 'draft_task_id' must be a draft task with status 'succeeded'」（**国内、海外官方都是这句**；`DraftTaskNotFound` 这个码官方实测没出现过，见过的都是中转中间层仿的）；draft + 非 480p → 400「resolution must be 480p when draft is true」。

## 价目

- 待补：国内 / 海外各档官方价以官方价目页为准（读时记日期）。
- 已知：样片按 480p 正常价、正式片按 1080p 计；失败 / 被审核拒的单不收费（下节）。

## 实测行为（官方）

- **探针非法值要对所有模型都非法**：`duration:1` 对所有 Seedance 模型非法；16 秒对 2.5 合法（拿 16 秒当保险会真出片）（规则 5）。
- 付费单用自己选的独特 seed，便于在别处认出同一单。
- BytePlus 有声版可能被以「output audio may be related to copyright restrictions」拒（普通提示词也会），不收费；海外测试默认 `generate_audio:false`。NSFW 开白线路也一样：成人内容能过输入审核，有声版却在生成约 9 分钟后被音频审核拒，关音频重跑成功。
- 状态体回显不可信：`generate_audio` 回 false 但成片有音轨的情况出现过，音轨以 ffprobe 为准。
- 测试素材：火山文档示例图 `https://ark-project.tos-cn-beijing.volces.com/doc_image/seepro_i2v.png` 国内可直连、无真人。

## 成片规格（官方原片指纹）

- **C2PA 内容凭证**（最硬的证据，`scripts/c2pa_check.py`）：
  - BytePlus（海外）2.5：`c2pa.created` 动作、`softwareAgent: BytePlus_ModelArk`、`parameters.model_name: dreamina-seedance-2-5`（不带版本日期）、`log_id`、生成时间（UTC），证书主体（Subject）O（c2pa 报成 issuer）`Byteplus Pte. Ltd.`；**叶子证书 SHA-256 `9d4096084640276cbef33572490778ad25dd932c56712699297e5e9f7c5786dd`**（有效期 2026-08-03 至 2028-08-03，官方实测 2026-10-28：480p / 样片 / 1080p / 参考素材各单都是这张）。
  - BytePlus（海外）**2.0 / fast / mini 是另一张证书**：主体 `O=Byteplus Pte. Ltd., CN=certificate@byteplus.com`，**叶子证书 SHA-256 `ce648397d59235fe1ba8159f72ae3c32352d6bdb2f47f696691e1428450680f9`**（有效期 2026-03-16 至 2028-03-16，官方 2.0-mini 一单 2026-10-28 取得；之前几家中转转出的海外 2.0 / fast / mini 原片也是这张）。
  - 海外两张和国内那张是同一条 GlobalSign 链（`GlobalSign GCC R45 SMIME CA 2025` → `GlobalSign Secure Mail Root R45`）。`scripts/c2pa_known_signers.json` 里没有这两条时，按上面的指纹补进去（来源写「官方 BytePlus ModelArk 成片，2026-10-28」）。
  - 国内 `softwareAgent` 是 `Volcengine_Ark_CN`，海外是 `BytePlus_ModelArk`。
  - 火山方舟（国内）：证书主体 O「北京火山引擎科技有限公司」、`c2pa.created` + `model_name`（如 `doubao-seedance-2-0-mini`）+ `log_id` + 时间。签发 CA `GlobalSign GCC R45 SMIME CA 2025` → 根 `GlobalSign Secure Mail Root R45`（证书链内嵌在文件里）；叶子证书 SHA-256 `635451f517fe5d0ad539d44bc0b7306d5f978bcd1eece031f8d6a193461fed68`，有效期 2026-04-20 至 2028-04-20（2026-10-08 官方 2.0-mini 成片和 2026-10-21 官方 2.5 成片同一张证书），已收进 `scripts/c2pa_known_signers.json`。
  - 判定：看 `scripts/c2pa_check.py --json` 的四级结论（`video-checks.md`）。只有「官方原片（指纹匹配）」= 签名有效 + 哈希匹配 + 叶子证书 SHA-256 在已知官方清单里，才算原片。`claimSignature.validated` + `assertion.bmffHash.match` 只证明完整性（重编码 / 放大 / 加水印都会让哈希不匹配或凭证消失）；**自签证书可以把主体 O 写成任何公司**，签名照样有效。`signingCredential.untrusted` 是信任链失败，不是原片证据。
  - 遇到不在清单里的新证书（厂商换证、新系列）：同一次审计里用官方 key 直连出一条原片（先报价，规则 2），取它的叶子证书指纹当基准，写回用户笔记。
  - 凭证里**没有** cgt 任务号，只有 `log_id`。
- **官方桶**（逐字比，别只看 `volces.com`）：国内 `ark-acg-cn-beijing.tos-cn-beijing.volces.com`；海外 `ark-acg-ap-southeast-1.tos-ap-southeast-1.volces.com`。签名 URL 里的 AK id（`X-Tos-Credential` 前缀）官方原片国内海外是同一个，记下官方原片的 AK id 前缀做比对；签名链接 24 小时有效。
- **文件名 / 路径**：`…/<model_name>/<主账号>/Video/…/<文件名>.mp4`。
  - 2.5（国内 2026-10-21 起、海外）：文件名 = 官方 `cgt-` 任务号（cgt 里的时间 = 北京时间提交时刻）——判任务号真伪的唯一可靠依据。
  - 国内 2026-10-15 前：文件名形如 `0217…ffff….mp4`，不是 cgt。
  - **海外 2.0 / mini：`…/dreamina-seedance-2-0-mini/0217…ffff….mp4`**——没有主账号段、没有 `Video/`，文件名不是 cgt（官方实测 2026-10-28）。只有 2.5 的文件名 = cgt。
  - 路径里的主账号号码可用来跨中转比对同源（两家成片主账号相同 = 同一上游账号）。
- **编码**：`Lavf58.76.100` + H.264 High + `x264 - core 164`，带 `volc` 标记；**2.5 的 1080p = HEVC Main 10（volcengine x265 build 192，国内海外一样）**，480p / 720p / 样片仍是 H.264。1080p 是 H.265 不算转码。有声版音频 AAC 32 kHz。
- 官方原片**没有** `AIGC` 容器标签。
- 超分产物：成片在 `*.vod.cn-north-1.volcvideo.com`、任务号前缀 `amk-` = 过了火山 AI MediaKit 超分，不是方舟原生成片。

## 判真伪要点

- 顺序：C2PA（签名 + 哈希 + 签发者指纹）→ 桶名逐字比 → 文件名与任务号逐字比 → 编码器 → `usage` 是否严格等于公式 → 眼看（`video-checks.md`）。
- **任务号**：拿状态体里的 `cgt-` 号和成片文件名逐字比；状态体里任何 cgt 形状的字段都可能是自造的（格式、北京时间都能仿；见过和真号同秒或差 1 秒、只有后缀不同）。自造号用 UTC 时间是另一个破绽。也见过正式片只认中转自造的号、填真号反而 400。
- **状态体回显不可信**：见过 `seed` 被挪进 `metadata.seed` 没传上游、状态体回显一个随机 seed（每家都比「请求 seed」和「状态体 seed」）；见过吞掉 `generate_audio:false` 照样出有声片、状态体却回 false（音轨以 ffprobe 为准）。
- **480p 尺寸先分地域**：海外 2.5 普通 480p 是 864×496、样片是 854×480，国内都是 854×480（上文「官方接口与响应」）——别把海外 864×496 当成中转改了尺寸。
- **放大**：报的 token ÷ 官方 480p 公式值恒等于某个倍数、链接在点播 / MediaKit 域名、只剩 `Lavf…` 无 `x264 core` → 低档出片再放大。频谱 / 往返 PSNR 分不出原生和放大（AI 超分会补细节）；要坐实得拿官方同档原生成片当细节基准。
- **usage 略偏**：比公式少 1、或等于公式乘一个系数取整 = 不是官方回传值，是中转自己算的。
- **无 C2PA + `Lavf58.29` + 有 `AIGC` 标签**：先看 `AIGC` 标签的生成方——可能是经云点播重封装（如腾讯云点播会写 TC260PG 国标标识），也可能是第三方 ComfyUI 管线重出。
- **同 seed 对照**：让原片组用同 seed 出片，和可疑组逐帧 PSNR（同一次生成 > 28 dB，不同生成约 12 dB）。前提是可疑组真把 seed 传上去了，所以只能排除、不能证死。
- 判 D4 真假看画面是不是样片的高清版；状态体不回 `draft` 时 D3 本身证明不了什么。

## 样片 draft 必测清单（规则 7：卖 2.5 就每家都测）

| # | 项 | 怎么测 | 看什么 |
|---|---|---|---|
| D1 | 不存在的样片号（免费） | `draft_task.id` 填编的 `cgt-…`，`resolution:1080p` | 官方 400 `InvalidParameter`「…'draft_task_id' must be a draft task with status 'succeeded'」= 字段到了上游；回「缺 text / prompt」= 中转不认 `draft_task`；回 `DraftTaskNotFound` 多半是中间层自己仿的（见下「中间层仿方舟错误码」），D3 出得来才算数 |
| D2 | draft + 非 480p（**有风险**） | `draft:true` + `720p` | 官方 400「resolution must be 480p when draft…」。中转若静默丢掉 `draft` 就是**一单真 720p**——按真单报价，或先跑 D1 / D3 确认它认 draft 再跑 |
| D3 | 出样片（付费） | 2.5 · `draft:true` · 480p · 4 秒，独特 seed | 状态体回不回 `draft:true`；`usage` = 38,830；实扣按 480p；返回的是官方 cgt 还是中转句柄 |
| D4 | 用样片出正式片（付费） | `content` 只放 `draft_task`（先填**官方 cgt**）+ 1080p | 成片 1920×1080、时长 / 比例继承、`draft_task_id` 指回样片、`usage` 196,425、实扣按 1080p；C2PA 仍是官方原片（指纹匹配）；画面是样片的高清版 |
| D5 | 换号再试 | D4 被拒就改填中转自己的句柄 / `task_` 号 | 它认哪种号——只认自己的句柄，网关就要支持「用中转句柄引用样片」；两种都不认 = 不支持样片 |

- 坑：有中转把 `draft:true` **静默忽略**、按普通 480p 收费，只有 D4 才露馅 → D3 成功不算数，D4 出了 1080p 才算支持。
- 报价：一轮 = D3（480p 4 秒）+ D4（1080p 4 秒），按中转价算；new-api 系按固定额度预扣，余额要够两次预扣。
- 「样片能出 ≠ 支持样片」：样片和正式片可能被路由到不同渠道，D4 被中转拦下（如 D3 正常按 480p 收费，D4 填官方 cgt 被拦「not owned by you」、填它的句柄回「draft functionality is disabled for this channel」）。
- **中间层仿方舟错误码**：D1 回 `DraftTaskNotFound` 不一定是字段到了官方——见过中间层自己先校验样片号、再查渠道开关，D3 回 `InvalidParameter.DraftNotSupported`「draft mode is not enabled on the selected channel」，外面包着中间层自己的 `upstream_create_failed`。看有没有中间层包装、「channel」这类方舟没有的措辞。
- **后台渠道会切换，样片随之失效**：同一中转不同后台渠道（状态体里上游任务号前缀不同）一个支持样片、一个不认只含 `draft_task` 的请求（「prompt is required」）；账号被切到后者后，旧样片回 409「绑定其他渠道」、新样片照收费却转不了 1080p。**D3 → D4 要在同一时段连测，并看状态体里的上游任务号前缀有没有变。**

## 接入网关要求

- 官方桶原始直链（规则 16）+ 官方 `cgt-` 任务号（或能映射到它的字段，且与成片文件名一致）。
- 状态体保留 `resolution` / `duration` / `usage`（`completion_tokens` / `total_tokens`）——按 token 结算、对账都靠它。
- 样片：认官方 cgt 最好；只认中转句柄时网关要能存句柄并在正式片里回填。
- 提交 200 空 body（无任务号）要识别为「结果未知」，不能当成功，也不能盲目重试（可能已建单扣费）。
- 有的中转把原生路径挂在前缀下（如 `/xxx/api/v3/…`），网关 baseUrl 要能配前缀；素材库 / 代理路径写死的要能配置。
- 失败单保留方舟原文错误（终态 `error`）。

## 中转常见问题（匿名案例）

- **经超分冒充高档**：某中转把 480p 经火山 MediaKit 超分后当 720p / 1080p 卖：链接在点播域名、任务号是 UTC 时间的自造 cgt、token = 480p 公式 × 固定倍数。
- **仿冒官方桶名**：某些「折扣组」成片放在名字只差一点的桶（少一段地域前缀、或改一个字母），无 C2PA、`Lavf58.29` / Main profile、`usage` 比公式少 1；多家中转成片的签名 AK 相同 = 同一转码上游。
- **ComfyUI 管线重出 1080p**：文件名是 ComfyUI 视频输出节点格式（`前缀_5 位计数-audio_…`）、容器有 GB 45438 `AIGC` 标签（第三方生成方编码 + 形似第三方云平台任务号的 `PropagateID`，推断）、`Lavf62` + `x264 core 165`。这些证明「被重出」，证明不了「超分」。
- **经云点播重封装**：某自称「官转」的中转只有扁平 prompt 格式接口、模型名改过，上游实为另一家云厂商的视频产品再到方舟（日志里的上游模型名、云厂商风格报错 `FileInfos` / `InvalidParameterValue`、失败单带方舟原文可证）；成片在云点播、无火山 C2PA、带 TC260PG 标识；无 cgt、无 usage、`content` 被丢 → 样片做不了。
- **不传 duration 记 0 费用**：某中转额度 = 请求秒数 × 档位每秒价，不传 `duration` 就记 0——计价漏洞，不是便宜。
- **官方号藏在别处且对不上**：顶层 `id` 是中转 `task_`，官方号只在终态以另一个字段给出，且部分与成片文件名对不上 → 只认文件名。
- **`draft_task` 被静默丢**：单放 `draft_task` 被中转校验拦「content 需提供 text」；为过校验带上提示词后，上游收到的是普通文生视频 → 出了一单与样片无关的 1080p 并收费。
- **提交 200 空 body**：上游同步拒单（服务异常、真人图审核）时 `Content-Length: 0`、无任务号；有时任务已建（控制台可见）、有时没有。没有列表接口时只能去控制台核对是否扣费再补跑。
- **参数错先 200 后异步失败**：有的中转提交即 200、预扣，终态 `failed` 里才给方舟原文并退款——`duration:1` 保险仍然有效，但要查终态才知道被拒原因，别把 200 当「保险失效」。
- **素材库越权与代理**：中转素材库把原图 URL 改写到自己的代理再给火山拉（代理出错就传不上）；用文档示例 ID 查素材能读到他人记录——**越权，按规则 17**：只记「能读到」这件事，不看、不存内容，报告给用户并列进要对方修的事。
- **余额先于参数校验**：new-api 系按固定额度预扣，余额不够时连非法分辨率都先回 403 `insufficient_quota`「预扣费额度失败…」（中转自己拦的，不是上游）——参数探针要在余额 ≥ 预扣时跑，别和付费单并发。
- **同步参数错被改写成通用文案**：有的中转把同步参数错误一律改成笼统说法、看不出是哪个参数；样片号这类上游才查的错先 200、终态才是方舟原文。
- **素材库文档过时**：网页文档可能只写旧的人物图库、照着上传回 500——先向对方要最新版接口文档。参考视频给带签名查询串的链接可能被素材自动登记判「FormatUnsupported」，换干净的 `.mp4` 链接。
- **任务列表接口漏别家任务**：透传方舟任务列表的中转可能把上游账号里别人的任务和成片链接都列出来（`filter.task_ids` 不生效）。查一次列表接口；漏了按规则 17 只记条数。
- **同一主账号 = 不算真备用**：两家成片路径里的方舟主账号号码相同，就是同一上游账号，挂了一起挂。
- new-api 系一个访问令牌可以建多把 key（一把 key 只属于一个分组），一次就能把各分组都测到。
- 文档写的 API 域名和给的 baseurl 不同时先按文档试；控制台子域常只是前端（API 路径回网页 / 405）。
- 若对方直接提供云平台子账号凭证 + 项目 key（不是中转）：真伪一般没问题，要查的是 key 稳不稳、结算价、账号隔离（任务列表按主账号返回）。

## 待补

- 官方非法参数矩阵（非法分辨率 / 比例、缺 content、审核拒绝）、官方价目（国内 / 海外各档）。
- 国内方舟的图生 / 参考视频 / 素材库官方单（参考素材只有海外 2026-10-28 的实测）；参考音频、多段参考视频、720p / 1080p 的 with_ref 档；原生 1080p（不走样片）、10 秒、其它比例；海外 2.0 / fast 官方出片（2.0-mini 只有一单 480p）。
- 中转对照要特别核：真实分辨率（放大）、用量倍数、任务号真伪、列表接口是否漏别家任务（规则 17：只数条数、不读内容）。
