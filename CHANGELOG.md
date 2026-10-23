# Changelog

## 0.3.0 — 2026-10-24
Fixes from a three-way review (new-user dry run, content, code).

**Security / money**
- `probe_lib`: masks every key it sees (env, `key=`, auth headers incl. `x-api-key` / `x-goog-api-key`, query params, echoed bodies, SSE); never sends the supplier key to another origin; never resends POST/PUT/PATCH/DELETE after the request may have reached the server (no duplicate paid jobs); logs every attempt; keeps all response headers; new `call_stream()` (raw SSE + TTFB), official-side calls (`OK`/`OB`, `side="official"`, `Client`), `spent()` from vendor logs, `poll_task` presets for DashScope / Ark / MiniMax.
- `analyze_videos.py`: no shell — a filename can no longer run commands.
- `c2pa_check.py`: separates "signature valid" from "signer verified" (a self-signed cert claiming any issuer used to pass); signer SHA-256 checked against `c2pa_known_signers.json` (Volcengine Ark Seedance included); "no C2PA" handled per file.
- `build_report.py`: much wider key detection (+ `--scan` over artifacts); leak check no longer bypassable by case, HTML escaping, markdown, alt text or file names; tag injection blocked; rule 16 gate can't be bypassed by model naming and now requires bucket + C2PA + no rehosting.

**Usability**
- Clear validation errors instead of tracebacks; `--help`; `--external-only` / `meta.mode: "external"` for people who only want to know if a relay is genuine.
- English reports (`meta.lang: "en"`), English examples, English procedure (`references/en/SKILL.en.md`).
- PDF works on macOS / Chromium (`$CHROME`), fails loudly instead of reusing a stale PDF.

**Content**
- New `openai.md` (OpenAI / Azure / Bedrock-hosted, checked against official docs) and `nonfunctional-checks.md` (token inflation, context truncation, tampering, retention, compliance).
- Fixed contradictions (huge-`max_tokens` probe is free only on the official Claude API), relay-observed MiniMax values no longer called official, token-count tolerance per Anthropic docs, rule index, rule 17 (stop on cross-tenant data).

**Repo**
- 84 unit tests, CI (tests, example validation, `skills-ref`, `npx skills` discovery, secret scan), CONTRIBUTING, SECURITY, issue templates.

## 0.2.0 — 2026-10-23
- Follows the [Agent Skills spec](https://agentskills.io/specification): `license` / `compatibility` / `metadata` frontmatter, bilingual description; passes `skills-ref validate`.
- Installable with `npx skills add YouToco/llm-relay-audit` (Claude Code, Codex, Cursor, Gemini CLI…).
- Fictional examples moved into the skill (`assets/examples/`) so they ship with every install; sample PDFs in `docs/samples/`.
- README leads with images.

## 0.1.0 — 2026-10-23
- First public release: procedure + 16 rules, 12 vendor baselines, new-api / sub2api notes, report generator, video forensics scripts, Claude Code plugin manifests.
