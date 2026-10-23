# 免费探针细则（视频 + 文本通用）

> SKILL.md 流程第 1 步的细节。请求全部用 `scripts/probe_lib.py` 记 jsonl（key 打码），报告里用 `{"jsonl","label"}` 直接引用。

- **官方原生路径在不在**：不在会返回网页 HTML，说明供应商没实现官方协议。再看站点身份与版本（响应头 `Server`、`X-New-Api-Version`）、`/v1/models`、价目、提交 / 查询路由、鉴权、错误行为矩阵（非法参数 / 缺头 / 错 key / 不存在的模型 / 不存在的任务）。
- **先确认请求没被 CDN 拦**：返回 403 纯文本「error code: 1010」= Cloudflare 按 UA 拦（Python-urllib 会被拦），`probe_lib.py` 已默认带 UA（环境变量 `UA` 可覆盖）；顺手跑一个 UA 矩阵（空 / requests / httpx / Anthropic SDK / curl / Go）记进报告，接网关时要知道。
- **响应把原因抹掉时，去供应商自己的日志里读**：new-api 系 `GET /api/log/token`（免费；type 2 = 成功扣费，type 5 = 被拒请求，`content` 里是被抹掉的真实原因，`other.channel_name` 常露出上游渠道名，见 `new-api.md`）；视频任务详情 `GET /v1/video/generations/{id}` 常带出后端原始任务和失败原因（有的站的 `/v1/videos/{id}` 只给 `status`）。
- **`/v1/dashboard/billing/usage` 不可信**（见过一单 $0.29 读成 200 美分），实扣只看供应商日志的 `quota`（new-api 系 500000 = $1）。
- **价目表与实扣可能不一致**：日志 `other` 里的 `param_resolution_*`（实际落的计价档位）和 `settlement_mode` 要看，每个档位都要确认实际落的档位对不对（见 `video-checks.md`「成本」）。
- **探针保险**（规则 5）：非法值要对所有模型都非法（Seedance `duration:1` 对全系非法，但 16 秒对 2.5 合法，拿它当保险会真出片）；`max_tokens: 0` 在 Kimi 官方被当成不限、照常扣费，别当保险。
- **保险字段先确认会传到上游**：有的 new-api 版本的 `/v1/video/generations` 会**静默丢掉顶层 `duration`**（要放 `metadata.duration`），`duration:1` 保险失效、按上游默认 10 秒真出片。视频探针优先走供应商的官方原生路径；只能走 new-api 格式时先用 `metadata.duration:1` 试，或第一单只提交一个、立刻查状态，`in_progress` 就说明保险没生效。
- **网关会「钳制」越界值时 `duration:1` 保险也失效**（有的文档写「越界值自动映射 / 钳制 / 不传上游，不报错」）：先读文档有没有这类话；保险改用网关自己同步校验的项（如参考图数量超上限、缺 content、不存在的模型），先单独打一次确认是同步 400 再用。
