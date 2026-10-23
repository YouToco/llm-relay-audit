# 视频线路细则（付费矩阵、成片核验、成本、网关）

> SKILL.md 流程第 2、3、5、6 步的视频部分。各厂商事实在 `ali-wan.md` / `minimax-h3.md` / `seedance.md`。
> 典型两种结局：成片是官方原片但缺 `usage`、价格曲线异常（不好接）；自建开源权重管线冒充官方（ComfyUI 元数据露馅）。

## 付费最小矩阵（报价后，规则 1）
- 最便宜档 2 秒 → 同档 4 秒（看是否按秒线性）→ 每个更高档各 2 秒（逐档看实扣，不线性外推）。
- **Seedance**：卖 2.5 就加一轮样片（规则 7，清单 `seedance.md`「样片 draft 必测清单」），报价时把「样片 480p + 正式片 1080p」单独列；只测最新系列（规则 8）。第一单出片先过规则 16。
- 固定一个短提示词、不设 seed（要判同源再做同 seed 配对，那要在官方也出片，先问用户）；Seedance 付费单用自己选的独特 seed，好在别处认出同一单。
- 记下：提交响应、轮询过程、成功响应、耗时、实扣（new-api 系看日志 `quota`，500000 = $1）。

## 成片核验（下载前先问用户）
按硬度排，findings.json 的 `authenticity.evidence` 必须有 `c2pa`、`encoder`、`bucket` 三项（没测写 `skipped` 原因）：
1. **C2PA**：`scripts/c2pa_check.py`。厂商签发 + 签名有效 + 文件哈希匹配 = 厂商原片且没被改过，比编码器指纹硬（BytePlus / 火山国内原片都有；「证书不受信任」只是本机信任列表没有它）。
2. **ComfyUI 工作流**：`scripts/extract_comfy.py` 读 mp4 元数据，有 = 供应商用开源权重自建管线（能读出模型 / 量化 / LoRA / 步数）。
3. **规格与编码器**：`scripts/analyze_videos.py` 读分辨率 / 帧率 / 帧数 / 音轨 / 编码器 / 容器与合规标签（如阿里的 `AIGC`）/ 频谱。判同源看「编码器 + 标签是否和官方成片一致」。**频谱分不出原生 480p 和超分 720p，别当证据。**
4. **成片链接域名**：官方 OSS / TOS 桶还是供应商代理、签名 AK 是不是官方的。
5. **画质**：`scripts/contact_sheet.py` 拼首中尾帧，再用眼睛看：贴不贴提示词、有没有肢体崩坏、细节。放进 findings 的 `sections[].image`。

ffmpeg 没装：`uv run --with imageio-ffmpeg python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"`，再 `FF=<路径> uv run --with numpy --with pillow python analyze_videos.py <输出目录> "标签=mp4" …`。

## 成本（findings `cost.tiers` 每档一行）
- 为什么每档都测（规则 1）：见过价目标了 2K，提交先扣钱、20 秒后后端回「只支持 768P / 720P / 480P」才退款；见过低档远低于官方价、1080P 却接近官方价，按低档线性外推会低估数倍。
- 每档每秒价 × 官方标价（各地域各档）、倍率是否合理（wan3 官方 480:720:1080 = 1:2:4）、计费时点（提交扣 / 成功扣 / 失败退）、币种与汇率。
- 价目表与实扣可能不一致：new-api 日志 `other.param_resolution_*`（实际落的计价档位）、`settlement_mode`（`unsettled_missing_tokens` = 状态里没 token 数、扣的是预估固定值）都要看。见过价目按 `metadata.resolution` 取档、原生请求的 `parameters.resolution` 读不到，所有单都落默认档 → 1080P 和 480P 同价：这是计价缺陷，不是降价，别当稳定成本。

## 网关能不能接（findings `gateway.items`）
逐条核对 `references/<厂商>.md`「接入网关要求」，每条归一档：`ready` 不改代码 / `gateway` 网关要改 / `vendor` 要对方补。如 wan3：状态要有 `usage`（`output_video_duration` / `SR`）、能拿到官方任务号（对账 / 排错要用）、「查不到任务」的外壳；Seedance：样片任务认不认官方 `cgt-` 号，还是网关要自己发句柄。
