# Technical verification — THẮNG MIA Web v3.0.0

Tested in the delivery environment on 2026-11-07:

- `python Story42.py --self-test` (original desktop code): **5/5 pass**.
- `python -m unittest discover -s backend/tests -v` (web API): **5/5 pass**.
- TypeScript/TSX source files were parsed/transpiled with TypeScript 5.8.3: **no syntax diagnostics**.
- CSS was parsed with PostCSS: **syntax passed**.
- `npm install` could **not** complete, because access to `registry.npmjs.org` failed (`EAI_AGAIN`). This means **Next.js type-check, production build, and visual browser smoke tests have not been verified** in the delivery environment.

Recommended additional verification on the actual development machine after installing packages:

```bash
cd frontend
npm install
npm run typecheck
npm run build
npm run dev
```

Then test clipboard prompts (Full/P1/P2), 14-line import, editing, file restore/download, date changes, filters, and responsive layout in the browser.
