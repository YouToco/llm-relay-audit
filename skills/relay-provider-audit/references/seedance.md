# Seedance（字节，火山方舟 / BytePlus ModelArk）官方基准

> Last verified: 2026-10-23；价格与行为以官方文档为准。

状态：骨架——官方原片指纹（C2PA / 桶 / 编码器 / 文件名）和样片 draft 行为已实测；官方完整请求响应样例、非法参数矩阵、各档价目待补。
官方基准两个：火山方舟（国内）、BytePlus ModelArk（海外）。新出官方单先报价（规则 2）。

## 必查三件事（规则 15）与一票否决（规则 16）

1. **成片是不是官方原片**：C2PA（签名有效、哈希匹配、**签发者证书指纹 = 已知官方指纹**）+ 官方桶名逐字比 + 编码器指纹。
2. **支不支持样片 draft**：D1–D5 清单（下文）；D4 真出 1080p 且画面是样片的高清版才算支持（规则 7）。
3. **返回的链接和参数是官方的还是包装过的**：官方成片直链、官方 `cgt-` 任务号、`resolution` / `duration` / `usage` 还在——换字段名可以接受（网关能映射）；全被封装成中转自己的链接、句柄、字段就无法接入。填 findings `passthrough`。

**规则 16**：拿不到方舟 / BytePlus 官方桶的原始直链，或成片不是原片（C2PA 签发者指纹对不上已知官方指纹 / 签名无效 / 哈希不匹配 / 无 C2PA），判不可接入。第一单出片先查这两条，不过就停测，样片、价格、其它档位都不用再测。
转存到中转自己的桶、云点播、CDN，或仿冒官方桶名，都算拿不到原链接。

## 官方接口与响应

- 协议：Ark `POST /api/v3/contents/generations/tasks`（创建）/ `GET /api/v3/contents/generations/tasks/{id}`（查询）；任务号形如 `cgt-YYYYMMDDHHMMSS-xxxxx`，时间是**北京时间**。
- 计费 token：`usage` = `宽 × 高 × 帧数 / 1024`（向下取整）。帧数：4 秒 97 帧、10 秒 241 帧。
  - 2.5：480p = 854×480，4 秒 38,830；720p 4 秒 87,300；1080p 4 秒 196,425；480p 10 秒 96,475。
  - 2.0 mini：480p = 864×496，4 秒 40,594。
- 计价分档按分辨率 × 是否含参考视频（只有 `reference_video` 算「含参考」）——以官方页为准。
- 方舟任务列表按**主账号**返回（不按项目 / key 隔离）：共用主账号时能列到别人的任务。**按规则 17 处理**：发现即停，只记「能列到别人的任务」和条数，不读任务内容、不下载成片，探针日志里删掉别家任务只留计数，报告给用户。
- 方舟 API key 管理（OpenAPI，AK/SK 签名）：`ListApiKeys {ProjectName}` 看 key 是否还在；`CreateApiKey` 需 `ResourceInstances:[{ResourceType:"presetendpoint",ResourceIds:[<模型>]}]`；`GetRawApiKey {Id}` 取值。key 回「API key doesn't exist」而 AK/SK 有项目权限时先查这个。建 key 会改动账号所有者的资源，先取得对方明确同意。

### 样片 draft（官方，2026-10）

- `draft:true`：**当前在售系列里只有 2.5 支持**（1.5 Pro 曾有 480p 样片模式），只能 480p，按 480p 正常价计。
- 正式片：`content` 只放 `{"type":"draft_task","draft_task":{"id":"<样片的官方 cgt 号>"}}` + `resolution:"1080p"`；提示词 / 素材 / 时长 / 比例 / seed / 有无声音从样片继承，**再传会报错**；按 1080p 计。样片号 7 天有效。
- 官方实测（2026-10-08 国内）：样片 38,830 token（480p 4 秒）→ 正式片 196,425 token（1080p 4 秒），状态体 `draft_task_id` 指回样片。
- 官方报错：样片号不存在 → 400 `InvalidParameter.DraftTaskNotFound`（国内文案「draft_task_id must be a draft task with status 'succeeded'」）；draft + 非 480p → 400「resolution must be 480p when draft…」。

## 价目

- 待补：国内 / 海外各档官方价以官方价目页为准（读时记日期）。
- 已知：样片按 480p 正常价、正式片按 1080p 计；失败 / 被审核拒的单不收费（下节）。

## 实测行为（官方）

- **探针非法值要对所有模型都非法**：`duration:1` 对所有 Seedance 模型非法；16 秒对 2.5 合法（拿 16 秒当保险会真出片）（规则 5）。
- 付费单用自己选的独特 seed，便于在别处认出同一单。
- BytePlus 有声版可能被以「output audio may be related to copyright restrictions」拒（普通提示词也会），不收费；海外测试默认 `generate_audio:false`。
- 状态体回显不可信：`generate_audio` 回 false 但成片有音轨的情况出现过，音轨以 ffprobe 为准。
- 测试素材：火山文档示例图 `https://ark-project.tos-cn-beijing.volces.com/doc_image/seepro_i2v.png` 国内可直连、无真人。

## 成片规格（官方原片指纹）

- **C2PA 内容凭证**（最硬的证据，`scripts/c2pa_check.py`）：
  - BytePlus（海外）2.5：`c2pa.created` 动作、`softwareAgent: BytePlus_ModelArk`、`parameters.model_name: dreamina-seedance-2-5`、`log_id`、生成时间（UTC），证书主体（Subject）O（c2pa 报成 issuer）`Byteplus Pte. Ltd.`，签名证书指纹待取。
  - 火山方舟（国内）：证书主体 O「北京火山引擎科技有限公司」、`c2pa.created` + `model_name`（如 `doubao-seedance-2-0-mini`）+ `log_id` + 时间。签发 CA `GlobalSign GCC R45 SMIME CA 2025` → 根 `GlobalSign Secure Mail Root R45`（证书链内嵌在文件里）；叶子证书 SHA-256 `635451f517fe5d0ad539d44bc0b7306d5f978bcd1eece031f8d6a193461fed68`，有效期 2026-04-20 至 2028-04-20（2026-10-08 官方 2.0-mini 成片和 2026-10-21 官方 2.5 成片同一张证书），已收进 `scripts/c2pa_known_signers.json`。
  - 判定：看 `scripts/c2pa_check.py --json` 的四级结论（`video-checks.md`）。只有「官方原片（指纹匹配）」= 签名有效 + 哈希匹配 + 叶子证书 SHA-256 在已知官方清单里，才算原片。`claimSignature.validated` + `assertion.bmffHash.match` 只证明完整性（重编码 / 放大 / 加水印都会让哈希不匹配或凭证消失）；**自签证书可以把主体 O 写成任何公司**，签名照样有效。`signingCredential.untrusted` 是信任链失败，不是原片证据。
  - 还没有已知官方指纹时（如上面 BytePlus）：同一次审计里用官方 key 直连出一条原片（先报价，规则 2），取它的叶子证书指纹当基准，写回用户笔记。
  - 凭证里**没有** cgt 任务号，只有 `log_id`。
- **官方桶**（逐字比，别只看 `volces.com`）：国内 `ark-acg-cn-beijing.tos-cn-beijing.volces.com`；海外 `ark-acg-ap-southeast-1.*`。签名 URL 里的 AK id 官方原片是同一个，记下官方原片的 AK id 前缀做比对。
- **文件名 / 路径**：`…/<model_name>/<主账号>/Video/…/<文件名>.mp4`。
  - 2.5（国内 2026-10-21 起、海外）：文件名 = 官方 `cgt-` 任务号——判任务号真伪的唯一可靠依据。
  - 国内 2026-10-15 前、BytePlus 2.0：文件名形如 `0217…ffff….mp4`，不是 cgt。
  - 路径里的主账号号码可用来跨中转比对同源（两家成片主账号相同 = 同一上游账号）。
- **编码**：`Lavf58.76.100` + H.264 High + `x264 - core 164`，带 `volc` 标记；**2.5 的 1080p = HEVC Main 10（volcengine x265 build 192）**，480p / 720p 仍是 H.264。1080p 是 H.265 不算转码。
- 官方原片**没有** `AIGC` 容器标签。
- 超分产物：成片在 `*.vod.cn-north-1.volcvideo.com`、任务号前缀 `amk-` = 过了火山 AI MediaKit 超分，不是方舟原生成片。

## 判真伪要点

- 顺序：C2PA（签名 + 哈希 + 签发者指纹）→ 桶名逐字比 → 文件名与任务号逐字比 → 编码器 → `usage` 是否严格等于公式 → 眼看（`video-checks.md`）。
- **任务号**：拿状态体里的 `cgt-` 号和成片文件名逐字比；状态体里任何 cgt 形状的字段都可能是自造的（格式、北京时间都能仿）。自造号用 UTC 时间是另一个破绽。
- **放大**：报的 token ÷ 官方 480p 公式值恒等于某个倍数、链接在点播 / MediaKit 域名、只剩 `Lavf…` 无 `x264 core` → 低档出片再放大。频谱 / 往返 PSNR 分不出原生和放大（AI 超分会补细节）；要坐实得拿官方同档原生成片当细节基准。
- **usage 略偏**：比公式少 1、或等于公式乘一个系数取整 = 不是官方回传值，是中转自己算的。
- **无 C2PA + `Lavf58.29` + 有 `AIGC` 标签**：先看 `AIGC` 标签的生成方——可能是经云点播重封装（如腾讯云点播会写 TC260PG 国标标识），也可能是第三方 ComfyUI 管线重出。
- **同 seed 对照**：让原片组用同 seed 出片，和可疑组逐帧 PSNR（同一次生成 > 28 dB，不同生成约 12 dB）。前提是可疑组真把 seed 传上去了，所以只能排除、不能证死。
- 判 D4 真假看画面是不是样片的高清版；状态体不回 `draft` 时 D3 本身证明不了什么。

## 样片 draft 必测清单（规则 7：卖 2.5 就每家都测）

| # | 项 | 怎么测 | 看什么 |
|---|---|---|---|
| D1 | 不存在的样片号（免费） | `draft_task.id` 填编的 `cgt-…`，`resolution:1080p` | 官方 400 `DraftTaskNotFound` = 字段到了上游；回「缺 text / prompt」= 中转不认 `draft_task` |
| D2 | draft + 非 480p（**有风险**） | `draft:true` + `720p` | 官方 400「resolution must be 480p when draft…」。中转若静默丢掉 `draft` 就是**一单真 720p**——按真单报价，或先跑 D1 / D3 确认它认 draft 再跑 |
| D3 | 出样片（付费） | 2.5 · `draft:true` · 480p · 4 秒，独特 seed | 状态体回不回 `draft:true`；`usage` = 38,830；实扣按 480p；返回的是官方 cgt 还是中转句柄 |
| D4 | 用样片出正式片（付费） | `content` 只放 `draft_task`（先填**官方 cgt**）+ 1080p | 成片 1920×1080、时长 / 比例继承、`draft_task_id` 指回样片、`usage` 196,425、实扣按 1080p；C2PA 仍是官方原片（指纹匹配）；画面是样片的高清版 |
| D5 | 换号再试 | D4 被拒就改填中转自己的句柄 / `task_` 号 | 它认哪种号——只认自己的句柄，网关就要支持「用中转句柄引用样片」；两种都不认 = 不支持样片 |

- 坑：有中转把 `draft:true` **静默忽略**、按普通 480p 收费，只有 D4 才露馅 → D3 成功不算数，D4 出了 1080p 才算支持。
- 报价：一轮 = D3（480p 4 秒）+ D4（1080p 4 秒），按中转价算；new-api 系按固定额度预扣，余额要够两次预扣。
- 「样片能出 ≠ 支持样片」：样片和正式片可能被路由到不同渠道，D4 被中转拦下（如「任务不属于你」「该渠道未开放样片」类报错）。

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
- 文档写的 API 域名和给的 baseurl 不同时先按文档试；控制台子域常只是前端（API 路径回网页 / 405）。
- 若对方直接提供云平台子账号凭证 + 项目 key（不是中转）：真伪一般没问题，要查的是 key 稳不稳、结算价、账号隔离（任务列表按主账号返回）。

## 待补

- 官方完整请求响应样例、官方非法参数矩阵、官方价目（国内 / 海外各档）、`execution_expires_after` 默认值。
- 中转对照要特别核：真实分辨率（放大）、用量倍数、任务号真伪、列表接口是否漏别家任务（规则 17：只数条数、不读内容）。
