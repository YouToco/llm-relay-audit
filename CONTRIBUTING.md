# Contributing

Issues and PRs welcome — English or 中文.

- **New vendor baseline:** add `skills/relay-provider-audit/references/<vendor>.md` following the sections in `ali-wan.md`; every fact needs a date and a source (official doc URL or an official-key measurement). Add a row to the tables in `SKILL.md`.
- **Never** include a real relay / reseller name, its domains, group names, account ids, prices you negotiated, or any key. Describe cases anonymously ("某中转…" / "a relay…").
- **Code:** scripts stay standard-library where possible; add a test under `tests/` (`python3 -m unittest discover -s tests`).
- **Before a PR:** run the CI steps locally — tests, `build_report.py … --check` on both examples, and `skills-ref validate skills/relay-provider-audit`.
