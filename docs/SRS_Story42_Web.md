# SRS Update — THẮNG MIA

**Edition:** 3.0.0 — 2026-11-07  
**Base specification:** `SRS_Story42_Desktop.md` (desktop 2.0.0).  
**Migration policy:** preserve the existing brief selection, 14×3 assignment, prompt content, manual AI operation, no-finished-story storage, statuses, and JSON schema.

## 1. Changes of platform

| Area | Desktop 2.0.0 | Web 3.0.0 |
|---|---|---|
| UI | Python Tkinter desktop | React/Next.js + TypeScript in browser |
| Business logic | Python in same process | Python `backend/core.py`, called through FastAPI |
| Persistence | `~/.story42_offline/project.json` | SQLite `~/.thangmia/thangmia.sqlite3` |
| Backup | JSON schema version 2 | JSON schema version 2 (bidirectional compatibility) |
| Clipboard | OS Tkinter clipboard | browser clipboard API with fallback |
| Deployment | Python desktop | local web app, optionally Docker |
| Third-party packages | Python standard library only | FastAPI/Uvicorn + Next.js/React |

## 2. Functional mapping

- **FR-01/02:** GET overview and POST days; 84 seeds and 42/day allocation remain in reused core.
- **FR-03:** 3 browser columns, 14 briefs per AI, progress metrics and copy next button.
- **FR-04:** Full, Part 1, Part 2 prompt text is rendered on backend only from user-saved templates.
- **FR-05:** `ready`, `sent`, `part1`, `done`, toggling completion and autosaving are preserved. Frontend posts copy status after successful clipboard access, not before.
- **FR-06:** Edit seven brief fields with a minimum length; IDs, themes, slots and AI cannot be edited.
- **FR-07:** weighted Jaccard same as desktop; scan day and compare individual brief with archived days; warning is explicitly lexical-only.
- **FR-08/09:** planning prompt, strict 14-line parser, seed-independent `CUSTOM-` IDs, single-AI lane replacement, and warning/confirmation before replacing ready-only lane or accepting similar briefs.
- **FR-10:** daily history, JSON download/restore, UTF-8-BOM CSV, local persistent database.
- **FR-11:** no full story body ingestion or storage.

## 3. API endpoints

| Method | Endpoint | Function |
|---|---|---|
| GET | `/api/health` | Availability |
| GET | `/api/overview?date=YYYY-MM-DD` | Briefs, stats, library count |
| POST | `/api/days` | Create complete 42-brief day |
| GET | `/api/history` | Historical day totals |
| GET | `/api/days/{date}/items/{uid}/prompt?mode=full` | Generate Full, Part 1, Part 2 |
| POST | `/api/days/{date}/items/{uid}/copied` | Record a successfully copied prompt |
| POST | `/api/days/{date}/items/{uid}/toggle-done` | Toggle done / sent |
| PATCH | `/api/days/{date}/items/{uid}/brief` | Update seven fields |
| GET | `/api/days/{date}/scan` | Scan similarity in day |
| POST | `/api/days/{date}/items/{uid}/scan` | Scan individual brief, including proposed edits |
| GET | `/api/planning-prompt?date=...&ai=1` | Get batch creation prompt |
| POST | `/api/days/{date}/plan` | Import 14-line batch |
| GET | `/api/backup` | Export JSON v2 |
| POST | `/api/restore` | Validate and replace database from JSON v2 |
| GET | `/api/days/{date}/export.csv` | Export daily CSV with BOM |

API field contracts are visible at `/docs` when FastAPI is running.

## 4. Safety, data, and access

- One project on a local machine. Data stored inside SQLite and serialized in a transaction to prevent lost updates from parallel HTTP writes.
- On first startup, an existing `~/.story42_web/story42.sqlite3` is backed up and copied to the new path only when `~/.thangmia/thangmia.sqlite3` does not exist. Migration never deletes the legacy database or overwrites an existing new database.
- The backend is bound to loopback by default in local run instructions; the standard Next.js `/api` rewrite proxies to it.
- JSON restoration checks file version and content schema before replacement; restore is destructive and requires explicit browser confirmation.
- Browser Clipboard access requires user gesture and may be blocked outside localhost or HTTPS. Failed copy must **not** change an item's status.
- Web version has **no authentication**: it must not be directly exposed to the public internet without adding authentication, permissions, HTTPS, CSRF protection (as relevant to the chosen auth strategy), monitoring, and backups.

## 5. Acceptance tests

1. Two consecutive days generate 42 distinct briefs; the third day will not recycle original seeds.
2. Each day has 14 briefs per AI and 3 per category.
3. Full/P1/P2 templates are empty for new or legacy databases, validate only the seven supported brief variables, and copy only updates status if browser copy succeeds.
4. Editing updates the next generated prompt and persists after restart.
5. Import refuses 13 lines, blocks replacing already-assigned lanes, preserves other AI lanes, and allows an explicitly confirmed lexical warning.
6. Backup/restore roundtrip preserves statuses and days, and CSV starts with a UTF-8 BOM.
7. Importing `~/.story42_offline/project.json` restores a valid desktop v2 file without altering the source file.
8. Browser smoke testing of all 3 views, copy, modals and file downloads is required on target computer.

## 6. Deferred

Per-user accounts, public production hosting, semantic duplicate detection, direct AI website integration, publishing to Facebook, full-story ingest, and collaborative realtime synchronization are **not** implemented in v3.0.0.
