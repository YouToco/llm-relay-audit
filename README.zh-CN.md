# llm-relay-audit

[English](README.md)

一个给 coding agent 用的 skill：**拿一家 AI API 中转站 / 代理 / 分销商和官方 API 逐项对比**，判断「这家卖的和官方一样吗、值不值得接」。new-api、one-api、sub2api 这类站卖的「便宜 Claude / GPT / Seedance」都适用。

把中转的地址和 key 交给你的 agent（Claude Code、Codex、Cursor……），它会按固定流程测完，最后出一份证据报告：

- **是不是真模型**：看响应 id 前缀（`msg_011C…` 一方、`msg_bdrk…` Bedrock、`resp_…` Codex）；把输入 token 和官方 `count_tokens` 逐个对账；查有没有偷换模型；查有没有注入隐藏系统提示（比如订阅号池把请求伪装成 Claude Code）。
- **视频是不是官方原片**：看 C2PA 内容凭证、编码器指纹、官方桶域名、ComfyUI 工作流元数据（自建开源权重冒充官方会露馅）；卖 Seedance 的还要测样片 draft。
- **行为和官方是否一致**：字段差异用程序求差集，不靠眼看；报错矩阵两边用同一批输入；查非法参数有没有被吞（`temperature: 9` 回 200）、官方字段是原样透传还是被封装。
- **真实成本**：按档位和官方价比倍率；实扣以供应商日志为准，它的 `billing/usage` 经常不准；每档都实测，不线性外推。
- **能不能接进你的网关**：每一条要求归入三档：不改代码就能接、网关要改、要对方补。

所有请求都记进 JSONL，key 自动打码。最后由一个生成器把 `findings.json` 渲染成两份产出：

| 产出 | 给谁 | 内容 |
|---|---|---|
| **外发证据版**（PDF） | 供应商 / 商务 | 只写「这家 vs 官方」：声称与实测、真伪证据、差异按影响客户与否分级、要对方修的事，附原始请求响应并排 |
| **内部决策卡**（一页 A4） | 拍板的人 | 判定（主线 / 备用 / 先修后接 / 不接）、和你现有线路比、网关接入三档、要问商务的事 |

生成器会拦截泄密：内部线路名、别家供应商名、像 key 的字符串都进不了外发版。

## 目录

```
skills/relay-provider-audit/
  SKILL.md            # 流程 + 16 条编号规则
  references/         # 免费探针 / 文本判真伪 / 视频核验 / 报告字段；各厂商官方基准与检测招数；new-api、sub2api 中转形态
  scripts/            # 报告生成器、带 jsonl 日志的探针库、视频取证脚本、PDF 与换页检查
examples/             # 虚构的文本 / 视频 findings.json 及生成的报告
```

## 安装

Claude Code 插件：

```
/plugin marketplace add YouToco/llm-relay-audit
/plugin install llm-relay-audit@llm-relay-audit
```

或者直接复制 skill 目录：

```bash
git clone https://github.com/YouToco/llm-relay-audit
cp -r llm-relay-audit/skills/relay-provider-audit ~/.claude/skills/
```

Codex、Cursor 等其他 agent：把 `skills/relay-provider-audit` 放到它读取 skills / rules 的位置，或者直接让它读 `SKILL.md`。

依赖：Python 3.10+（报告生成器和探针库只用标准库；视频脚本要 Pillow / numpy / c2pa-python，用 `uv run --with` 现拉）；出 PDF 要 Chrome / Chromium；换页检查要 [uv](https://github.com/astral-sh/uv)；视频取证要 ffmpeg（也可以用 uv 拉 `imageio-ffmpeg`）。

## 用法

直接对 agent 说「测一下这家中转：地址 `https://relay.example`，模型 `claude-sonnet-…`，key 在 `$K`」。它会：

1. 先只跑免费探针，每次调用都记进 `artifacts/*.jsonl`；
2. 任何可能花钱的请求，**先报价，等你点头**；
3. 跑覆盖全部档位的最小付费矩阵，填好 `findings.json`；
4. 用生成器出两份报告：

```bash
G=skills/relay-provider-audit/scripts/build_report.py
python3 -I $G --init text audits/2026-01-15-example/findings.json   # 出骨架
python3 -I $G audits/2026-01-15-example/findings.json --check       # 只校验
python3 -I $G audits/2026-01-15-example/findings.json --pdf         # 出 HTML + PDF
```

自带的样例也可以这样出：`python3 -I $G examples/text/findings.json --pdf`。

## 注意

- `references/` 里的官方基准（价格、指纹、id 格式）都标了 `Last verified` 日期，厂商会改，用之前对照官方文档核实；规则 10 会让 agent 发现基准过时就现测更新。
- 有些规则是偏严的默认策略，比如规则 16：Seedance 拿不到官方桶原片就判不接。你的业务能接受的话，在 `SKILL.md` 和 `build_report.py` 里放宽。
- 只测你有权测试的服务（例如供应商给了你试用 key）。转卖消费者订阅通常违反上游的服务条款。

## 协议

[MIT](LICENSE)
