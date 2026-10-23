# Security

This skill handles API keys and talks to third-party relays. Design rules:

- Keys come from environment variables only. `probe_lib.py` masks every key it sees (env, arguments, auth-like headers, query params, echoed bodies) before writing `artifacts/*.jsonl`.
- `build_report.py` refuses to render reports containing key-like strings and scans `artifacts/` for leaks.
- Nothing in this repo should ever contain a real key, a real relay's name, or a real customer's data. Examples are fictional.
- Paid requests are never retried automatically, and the procedure requires a price quote and user approval before any request that may be billed.

**Reporting a vulnerability:** please open a [private security advisory](https://github.com/YouToco/llm-relay-audit/security/advisories/new) instead of a public issue — e.g. a masking gap that writes keys to disk, a leak-check bypass, or shell injection in a script.

**Before installing any skill** (including this one), read it: skills run with your agent's permissions.
