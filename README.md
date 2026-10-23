# llm-relay-audit

[中文说明](README.zh-CN.md)

An agent skill for **auditing third-party AI API relays / resellers against the official API**: the "cheap Claude / GPT / Seedance" endpoints sold through new-api, one-api, sub2api and similar stacks.

Point your coding agent (Claude Code, Codex, Cursor…) at a relay's base URL and key. The skill walks it through a fixed procedure and ends with an evidence report:

- **Is it the real model?** Response-id forensics (`msg_011C…` first-party vs `msg_bdrk…` Bedrock vs `resp_…` Codex), token-by-token reconciliation against the official `count_tokens`, model-swap detection, and hidden system-prompt injection detection (e.g. subscription pools that disguise traffic as Claude Code).
- **Is the video an original?** C2PA credentials, encoder fingerprints, official bucket domains, ComfyUI workflow metadata (a self-hosted open-weights pipeline posing as the official API), and Seedance draft (sample) mode.
- **Does it behave like the official API?** Field-by-field diffs computed by a program, not by eye; an error matrix with the same inputs on both sides; and checks for silently swallowed parameters (`temperature: 9` → 200) and fields that pass through vs. get wrapped.
- **What does it really cost?** The price per tier compared with the official list price, using the relay's own billing logs rather than its `billing/usage` figure, which is often wrong. Every tier is tested; nothing is extrapolated.
- **Can you plug it into your gateway?** Each requirement is sorted into one of three bins: works as-is, needs gateway changes, or needs the vendor to fix something.

Every request is logged to JSONL with keys masked. A single generator turns `findings.json` into two outputs:

| Output | Audience | Content |
|---|---|---|
| **Evidence report** (PDF) | the vendor / your BD team | relay vs. official only: claims vs. measured, authenticity evidence, diffs ranked by customer impact, the list of fixes asked for, and raw request/response pairs side by side |
| **Internal decision card** (one A4 page) | the person deciding | verdict (primary / backup / fix-first / reject), comparison with your existing lines, gateway readiness, open questions |

The generator also blocks leaks: internal line names, other vendors, and anything that looks like an API key cannot reach the external report.

## What's inside

```
skills/relay-provider-audit/
  SKILL.md                 # the procedure and 16 numbered rules (Chinese)
  references/
    probing-tips.md        # free probes: CDN/UA blocks, safe "illegal value" probes, reading vendor logs
    text-checks.md         # LLM authenticity: id prefix, token reconciliation, model swap, injection
    video-checks.md        # paid matrix, original-video verification, per-tier cost
    report-template.md     # findings.json schema
    claude.md grok-xai.md gemini.md kimi-k3.md glm.md deepseek.md   # official baselines + detection tricks per vendor
    ali-wan.md minimax-h3.md seedance.md                            # video baselines + official file fingerprints
    new-api.md sub2api.md  # how relay stacks behave: groups, ratios, logs, passthrough, subscription pools
  scripts/
    build_report.py        # findings.json -> evidence report + decision card (+ PDF)
    probe_lib.py           # call() with JSONL logging and key masking; vendor log / usage helpers
    c2pa_check.py analyze_videos.py contact_sheet.py extract_comfy.py   # video forensics
    html_to_pdf.sh check_pages.py report_style.html                     # PDF + page-break check
examples/                  # fictional text + video findings.json with the generated reports
```

## Install

**Claude Code (plugin):**

```
/plugin marketplace add YouToco/llm-relay-audit
/plugin install llm-relay-audit@llm-relay-audit
```

**Any agent (copy the skill folder):**

```bash
git clone https://github.com/YouToco/llm-relay-audit
cp -r llm-relay-audit/skills/relay-provider-audit ~/.claude/skills/
```

For Codex, Cursor and other agents, put `skills/relay-provider-audit` wherever that agent loads skills or rules from, or point it at `SKILL.md` directly.

Requirements: Python 3.10+ (the report generator and probe library use only the standard library; video scripts need Pillow / numpy / c2pa-python, all pulled via `uv run --with`), and Chrome / Chromium for PDF output. [uv](https://github.com/astral-sh/uv) is needed for the page-break check, and ffmpeg (or `imageio-ffmpeg` via uv) for video forensics.

## Quick start

Tell your agent something like *"audit this relay: base URL `https://relay.example`, model `claude-sonnet-…`, key in `$K`"*. The skill then:

1. runs free probes only, with every call logged to `artifacts/*.jsonl`;
2. **quotes a price and waits for your OK** before any request that could cost money;
3. runs the smallest paid matrix that still covers every tier and fills in `findings.json`;
4. builds both reports:

```bash
G=skills/relay-provider-audit/scripts/build_report.py
python3 -I $G --init text audits/2026-01-15-example/findings.json   # skeleton
python3 -I $G audits/2026-01-15-example/findings.json --check       # validate
python3 -I $G audits/2026-01-15-example/findings.json --pdf         # HTML + PDF
```

You can render the bundled examples the same way: `python3 -I $G examples/text/findings.json --pdf`.

## Ground rules baked into the skill

- Keys come from environment variables only and are never written to disk unmasked.
- **No money is spent without a quote first.** Free probes are designed so that only the field under test is invalid. The skill knows which "safe" probes are actually billed by which vendor, e.g. `max_tokens: 0` on Kimi.
- Conclusions come after evidence, and inferences are labeled as inferences.
- Admin consoles are read-only: the agent never types passwords and reads only non-credential fields.

## Caveats

- The vendor baselines in `references/` (prices, fingerprints, id formats) carry a `Last verified` date. Vendors change things, so re-check against the official docs; rule 10 tells the agent to refresh stale baselines.
- Some rules are deliberately strict defaults. For example, rule 16 rejects any Seedance relay that doesn't return the official bucket's original file. Relax them in `SKILL.md` and `build_report.py` if your use case allows.
- Use this only on services you are authorized to test, such as a vendor that gave you a trial key. Reselling consumer subscriptions usually violates upstream terms of service.

## License

[MIT](LICENSE)
