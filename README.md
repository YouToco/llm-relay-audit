# llm-relay-audit

[中文](README.zh-CN.md) · An agent skill that audits third-party AI API relays / resellers (new-api, one-api, sub2api…) against the official API, for both text and video.

![What it checks and what you get](docs/images/hero-en.png)

## What the output looks like

![Generated report pages](docs/images/gallery-en.png)

Every page above is rendered by `build_report.py` from the fictional [`examples/`](examples/). Open the PDFs there to see the full reports.

## Install

```
/plugin marketplace add YouToco/llm-relay-audit
/plugin install llm-relay-audit@llm-relay-audit
```

Or copy the folder: `cp -r skills/relay-provider-audit ~/.claude/skills/`. For other agents, point them at [`SKILL.md`](skills/relay-provider-audit/SKILL.md).

## Use

Tell your agent: *"audit this relay: base URL `https://relay.example`, model `claude-sonnet-…`, key in `$K`"*.

To render a report yourself:

```bash
python3 -I skills/relay-provider-audit/scripts/build_report.py examples/text/findings.json --pdf
```

| Covers | Files |
|---|---|
| Text baselines | Claude (first-party / Bedrock), Grok, Gemini, Kimi, GLM, DeepSeek |
| Video baselines | Alibaba wan3, MiniMax H3, Seedance (Volcengine / BytePlus) |
| Relay stacks | new-api / one-api (groups, ratios, logs, passthrough), sub2api (subscription pools) |

Requirements: Python 3.10+ and Chrome / Chromium for PDFs. The video scripts pull Pillow / numpy / c2pa-python via `uv run --with`.

**Notes:** baselines carry a `Last verified` date, so re-check them against the official docs. Some rules are strict defaults you can relax. Only audit services you're authorized to test.

[MIT](LICENSE)
