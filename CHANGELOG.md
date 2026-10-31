# Changelog

## 0.4.0 — 2026-10-31
Catch-up with a week of field use since 0.3.0.

**Rules**
- New rule 18: a supplier whose endpoints / fields / response structure aren't the model's official API format is rejected outright (or "fix first" if they agree to switch); flagged on the report's first line.
- Rule 15: the Seedance asset library is mandatory and a gate — exercise every documented asset endpoint and generate with `asset://`; if the library is unsupported or not enabled, stop before any paid job.
- Set-up step: for Seedance, find the asset-library and draft docs first; if either is missing, ask the user for them before probing.

**Scripts**
- `probe_lib`: large `data:` base64 in logged request bodies is replaced by length + sha256 (requests unchanged).
- `build_report`: the external "what the supplier must fix" list uses only `asks` (gateway `vendor` items are no longer merged in; warns if they exist and `asks` is empty); appendix URLs with any leading `{placeholder}` get the exchange's `host`.
- `c2pa_known_signers.json`: BytePlus Seedance 2.5 and 2.0-series certs, Google media signing (Gemini images) added.
- 4 new tests (88 total).

**References** (official measurements folded in, all relay cases anonymized)
- Seedance: corrected official D1 error text (`DraftTaskNotFound` is a middle-layer imitation), overseas 480p size change, reference-media token formula and billing tiers, full task-object fields, more relay pitfalls.
- New `qwen.md`, `minimax-text.md`; Kimi K3.1 Pro section; official measurement sections for Claude, OpenAI / Azure, Gemini, GLM-5.3, DeepSeek; official prices snapshotted 2026-10-29.
- MiniMax H3 official specs (sizes, frame grid, tokens per second, encoder fingerprints) replacing relay-observed values; wan3 official error table and output sizes.
- `text-checks.md`: long-input comparison (catch fixed-multiplier usage inflation), official rate-limit headers and latency references.
- `video-checks.md`: compare every tested resolution with the official same tier, same-condition quality comparisons; `probing-tips.md`: free request-size limit probe, public test media.
- `sub2api.md`: short-probe diversion (single-turn "OK / hi" routed to a fake backend), `speed: fast` can take a pool down; `new-api.md`: passthrough header fork, `/api/log/self`.

## 0.3.1 — 2026-10-31
- Rule 8 gets a Seedance exception: when no model is named, test every Seedance model the supplier lists (2.5 / 2.0 / fast / mini…), one cheapest-tier job each plus the 2.5 draft round; if the balance can't cover them all, list what won't fit and the shortfall (pre-deduction included) before starting, and ask whether to top up or test newest-first.

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
