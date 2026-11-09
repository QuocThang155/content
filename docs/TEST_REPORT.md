# Technical verification — THẮNG MIA Web v3.3.0

Verified in the development environment on 2026-11-09:

- `python -m unittest backend.tests.test_api -q`: **29/29 pass**.
- `npm run lint`: **pass**.
- `npm run typecheck`: **pass**.
- `npm run build`: **pass**.
- `git diff --check`: **pass**.

The frontend and backend were stopped after verification as requested; a live
browser smoke test was not rerun in this verification pass.
