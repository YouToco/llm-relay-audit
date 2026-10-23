# 视频线路细则（付费矩阵、成片核验、成本、网关）

> SKILL.md 流程第 2、3、5、6 步的视频部分。各厂商事实在 `ali-wan.md` / `minimax-h3.md` / `seedance.md`。
> 典型两种结局：成片是官方原片但缺 `usage`、价格曲线异常（不好接）；自建开源权重管线冒充官方（ComfyUI 元数据露馅）。

## 付费最小矩阵（报价后，规则 1）
- 最便宜档 × **该厂商最短合法时长**（wan3 2 秒、MiniMax H3 4 秒、H3-Max 5 秒…，以各厂商 reference 为准）→ 同档再加一档时长（看是否按秒线性）→ 每个更高档各一单最短时长（逐档看实扣，不线性外推）。
- **Seedance**：卖 2.5 就加一轮样片（规则 7，清单 `seedance.md`「样片 draft 必测清单」），报价时把「样片 480p + 正式片 1080p」单独列；只测最新系列（规则 8）。第一单出片先过规则 16。
- 固定一个短提示词、不设 seed（要判同源再做同 seed 配对，那要在官方也出片，先问用户）；Seedance 付费单用自己选的独特 seed，好在别处认出同一单。
- 记下：提交响应、轮询过程（`probe_lib.poll_task(..., preset=…)`）、成功响应、耗时、实扣（new-api 系看日志 `quota`，500000 = $1；`probe_lib.spent(since_ts)` 分页汇总）。

## 成片核验（下载前先问用户）
按硬度排，findings.json 的 `authenticity.evidence` 必须有 `c2pa`、`encoder`、`bucket` 三项（没测写 `skipped` 原因）：
1. **C2PA**：`scripts/c2pa_check.py --json`，四级结论：
   - 「官方原片（指纹匹配）」= 签名有效 + 哈希匹配 + 签名证书 SHA-256（`signer_sha256`）在 `scripts/c2pa_known_signers.json` 里——只有这一级能当原片证据（规则 16 ②），比编码器指纹硬。
   - 「签名有效但签发者未核实」= 证书不在清单里。签名有效 + 哈希匹配只证明**完整性**（签名后字节没被改过），证明不了来源：任何人都能自签一张主体（Subject）O 写成 `Byteplus Pte. Ltd.` 的证书，签名照样验证通过。`signingCredential.untrusted` 是信任链失败，不是原片证据。c2pa 报的 `issuer` 其实是证书主体的 O 字段（签名方自己填的），真正签发的 CA 脚本另行打印。
   - 「签名无效或哈希不匹配」= 字节被改过（重编码 / 放大 / 加水印）；「无 C2PA」= 没有凭证（wan3 官方原片本来就没有，见 `ali-wan.md`）。
   - 清单只收**从官方 API 直接取回的成片**里的叶子证书；厂商换证书时加一条（同一次审计里官方直连出一条原片取指纹，先报价）。`--trust-anchors <pem>` 用独立取得的 C2PA 信任列表验证书链——别拿文件里内嵌的根证书当锚（循环论证）。
2. **ComfyUI 工作流**：`scripts/extract_comfy.py` 读 mp4 元数据，有 = 供应商用开源权重自建管线（能读出模型 / 量化 / LoRA / 步数）。
3. **规格与编码器**：`scripts/analyze_videos.py` 读分辨率 / 帧率 / 帧数 / 音轨 / 编码器 / 码流里的编码器 SEI（`encoder_sei`：x264 core / x265 build，改了容器标签也还在）/ 容器与合规标签（如阿里的 `AIGC`）/ 频谱。判同源看「编码器 + SEI + 标签是否和官方成片一致」。**频谱分不出原生 480p 和超分 720p，别当证据。**
4. **成片链接域名**：官方 OSS / TOS 桶还是供应商代理、签名 AK 是不是官方的。
5. **画质**：`scripts/contact_sheet.py` 拼首中尾帧，再用眼睛看：贴不贴提示词、有没有肢体崩坏、细节。放进 findings 的 `sections[].image`。

ffmpeg 查找顺序：环境变量 `FF` > PATH 上的 ffmpeg > imageio-ffmpeg；ffprobe：`FFPROBE` > `FF` 所在目录 > PATH，都没有就解析 `ffmpeg -i` 输出。什么都没装：`uv run --with imageio-ffmpeg --with numpy --with pillow python analyze_videos.py <输出目录> "标签=mp4" …`（不带 numpy / pillow 只跳过频谱）。

## 成本（findings `cost.tiers` 每档一行）
- 为什么每档都测（规则 1）：见过价目标了 2K，提交先扣钱、20 秒后后端回「只支持 768P / 720P / 480P」才退款；见过低档远低于官方价、1080P 却接近官方价，按低档线性外推会低估数倍。
- 每档每秒价 × 官方标价（各地域各档）、倍率是否合理（wan3 官方 480:720:1080 = 1:2:4）、计费时点（提交扣 / 成功扣 / 失败退）、币种与汇率。
- 价目表与实扣可能不一致：new-api 日志 `other.param_resolution_*`（实际落的计价档位）、`settlement_mode`（`unsettled_missing_tokens` = 状态里没 token 数、扣的是预估固定值）都要看。见过价目按 `metadata.resolution` 取档、原生请求的 `parameters.resolution` 读不到，所有单都落默认档 → 1080P 和 480P 同价：这是计价缺陷，不是降价，别当稳定成本。

## 网关能不能接（findings `gateway.items`）
逐条核对 `references/<厂商>.md`「接入网关要求」，每条归一档：`ready` 不改代码 / `gateway` 网关要改 / `vendor` 要对方补。如 wan3：状态要有 `usage`（`output_video_duration` / `SR`）、能拿到官方任务号（对账 / 排错要用）、「查不到任务」的外壳；Seedance：样片任务认不认官方 `cgt-` 号，还是网关要自己发句柄。
