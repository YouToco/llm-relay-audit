# llm-relay-audit

[English](README.md) · 给 coding agent 用的 skill：拿 AI API 中转站 / 代理（new-api、one-api、sub2api……）和官方 API 逐项对比，文本和视频线路都能测。

![能解决的问题和产出](docs/images/hero-zh.png)

## 成品长这样

![生成的报告页面](docs/images/gallery-zh.png)

上图每一页都是 `build_report.py` 从虚构样例 [`assets/examples/`](skills/relay-provider-audit/assets/examples/) 直接生成的，完整 PDF（中英各一套）在 [`docs/samples/`](docs/samples/)。

## 安装

**任意 agent（Claude Code、Codex、Cursor、Gemini CLI……）**，用 [Agent Skills](https://agentskills.io) 命令行：

```bash
npx skills add YouToco/llm-relay-audit
```

加 `-g` 装到用户目录；加 `-a claude-code` / `-a codex` 指定 agent。

**Claude Code 插件：**

```
/plugin marketplace add YouToco/llm-relay-audit
/plugin install llm-relay-audit@llm-relay-audit
```

skill 符合 [Agent Skills 规范](https://agentskills.io/specification)，`skills-ref validate` 校验通过。

## 用法

对 agent 说：「测一下这家中转：地址 `https://relay.example`，模型 `claude-sonnet-…`，key 在 `$K`」。

自己出一份报告：

```bash
python3 -I skills/relay-provider-audit/scripts/build_report.py skills/relay-provider-audit/assets/examples/text/findings.json --pdf
```

| 覆盖 | 内容 |
|---|---|
| 文本基准 | Claude（一方 / Bedrock）、OpenAI（含 Azure / Bedrock 托管）、Grok、Gemini、Kimi、GLM、DeepSeek |
| 视频基准 | 阿里 wan3、MiniMax H3、Seedance（火山方舟 / BytePlus） |
| 中转形态 | new-api / one-api（分组、倍率、日志、参数透传）、sub2api（订阅号池） |
| 真伪之外 | 输出 token 虚报、上下文被截、输出被改、中转留存提示词、条款 / 合规风险 |

流程有英文版 [`references/en/SKILL.en.md`](skills/relay-provider-audit/references/en/SKILL.en.md)；findings 里写 `"lang": "en"` 就出英文报告（样例 [`assets/examples/text-en/`](skills/relay-provider-audit/assets/examples/text-en/)）。

依赖：Python 3.10+；出 PDF 要 Chrome / Chromium；视频脚本用 `uv run --with` 现拉 Pillow / numpy / c2pa-python。

**注意：** 基准都标了 `Last verified`，用前对照官方文档核实；部分规则是偏严的默认值，可以放宽；只测你有权测试的服务。

[MIT](LICENSE)
