<<<<<<< HEAD
# THẮNG MIA — Next.js + React + FastAPI

**Version 3.0.0 — web migration of the original offline studio**

THẮNG MIA is a **browser-based, locally hosted** production desk for 42 short story briefs per day, shared across three human-operated AI web sessions. It does **not** call paid AI APIs, automate AI websites, store finished stories, or publish to Facebook. UI language: Vietnamese. Story-writing prompts: English, requesting Philippine Taglish.

## Technology

- **Frontend:** React 19, Next.js 16 App Router, TypeScript, plain responsive CSS, Lucide icons.
- **Backend:** Python 3.10+, FastAPI, Uvicorn. Core planning/brief/prompt algorithms ported from the original desktop source with no Tkinter dependency.
- **Database:** local SQLite, single JSON-schema-v2 document saved atomically under a transaction. The JSON v2 export/import remains compatible with the desktop project.
- **API:** `/api/*`, routed by Next.js to FastAPI. No browser CORS setup required in standard development.

## Run on your computer (Windows / macOS / Linux)

Prerequisites: **Python 3.10+**, **Node.js 20.9+**, internet **only for initial installation** of npm/Python packages.

From the directory containing `backend` and `frontend`, open **two terminals**.

**Terminal 1 — backend**

```powershell
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — frontend**

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**. API documentation (development): **http://127.0.0.1:8000/docs**.

> For Windows, if `python` isn't recognized, use `py` to create your virtual environment; running `py -m venv .venv` works as well.

When you first select a date, the app creates 42 briefs (14 per AI) from unused starter ideas, exactly as in the desktop version. The 84 built-in briefs last up to 2 full days unless new briefs are imported. **After exhaustion, open “Bổ sung ý tưởng” and import 14 briefs per AI.**

## Docker (optional)

From the project root:

```bash
docker compose up --build
```

Then open http://localhost:3000. SQLite persists in the existing `story42_data` volume for upgrade compatibility. The application is bound to **127.0.0.1 by default**; Docker does not expose the backend's port publicly.

## Migrate existing desktop data

1. Make a copy of `~/.story42_offline/project.json` from the desktop installation, or export JSON through the desktop app.
2. Open **Lịch sử & sao lưu** in the web app.
3. Click **Chọn file** under Khôi phục bản sao and choose the copied `project.json`.
4. Confirm replacement. This restores the existing 84 seed library, any added ideas, daily assignments, and statuses.

**Warning:** restoration replaces the entire current web database. First export any web data you wish to retain.

The web app stores its own data under `~/.thangmia/thangmia.sqlite3` by default. If the legacy web database `~/.story42_web/story42.sqlite3` exists, the backend backs it up and copies it to the new path only when the new database does not exist. The legacy database and desktop JSON file are never deleted or overwritten.

To export Full prompts for a lane, set `THANGMIA_WORKSPACE_DIR` (default:
`~/.thangmia/workspace/`) to the directory shared with the Chrome Extension,
then click **Xuất 14 TXT** in Workflow. Files are written under `AI1`, `AI2`,
or `AI3` using the selected date and lane slot. Existing input or output files
are skipped and never overwritten. With Docker, mount the same host directory
as the backend workspace; a container path is not automatically visible to
Chrome on the host.

On Windows, set the persistent user variable before starting or restarting the
backend:

```powershell
[Environment]::SetEnvironmentVariable('THANGMIA_WORKSPACE_DIR', 'D:\thang\workspace', 'User')
```

Workflow also provides **Workspace** configuration, file status refresh, prompt
and output viewing/editing, download, and confirmed deletion. The backend keeps
`.thangmia_manifest.json` in the workspace to map each file to the date, lane,
slot, and brief UID. Files without a matching mapping are shown as warnings
and are not assigned automatically.

## User workflow

1. **Trang chủ:** choose date, examine 42 cards, review duplication warnings, copy next available prompt per AI, and mark each story complete manually. Edit a brief and copy the Full / Part 1 / Part 2 prompts as needed.
2. **Bổ sung ý tưởng:** select AI 1/2/3, copy the prompt that requests 14 new briefs; paste the 14 generated lines into THẮNG MIA and import. Ready-only lanes can be replaced after confirmation; a lane containing any sent / part1 / done brief is protected.
3. **Lịch sử & sao lưu:** view daily counts, download JSON backup, and restore JSON. Dashboard also shows remaining ideas and can filter them.

The web app records a copy as `sent` or `part1` **only after the browser clipboard operation succeeds**. Clipboard permissions require localhost or HTTPS on most browsers.

## Important limitations

- Running on the web **does not mean automatic cloud hosting**. This bundle runs locally in a web browser. To make it publicly accessible, first add authentication, role-based access, HTTPS, a deployment plan and proper backup policy; **do not expose this unauthenticated instance directly to the internet**.
- There is one project/database, not separate user accounts. Edits from concurrent browser clients are serialized in SQLite, but there are no per-user permissions or real-time collaboration updates.
- The near-duplicate detector uses weighted Jaccard keyword overlap. It is **not semantic similarity, copyright, or plagiarism detection**.
- THẮNG MIA does not inspect finished 3,000-word stories. Actual AI service limits, output length, and story quality are not guaranteed.
- Python 3.10+ for backend; contrary to the original desktop project, web dependencies now require `pip install` and `npm install` during setup.

## Tests

From the project root (with backend dependencies installed):

```bash
pip install -r backend/requirements-dev.txt
python -m unittest discover -s backend/tests -v
```

Frontend after `npm install`:

```bash
cd frontend
npm run typecheck
npm run build
```

Original desktop project is preserved under `legacy/Story42.py`; original SRS is under `docs/SRS_Story42_Desktop.md`. See `docs/SRS_Story42_Web.md` for the web design and API summary.

## Project layout

```text
thangmia/
├── backend/
│   ├── core.py               # Reused business rules (84 seed, 42 assignment, Taglish prompts)
│   ├── main.py               # FastAPI routes and validation
│   ├── store.py              # SQLite persistence and transactions
│   ├── requirements.txt
│   └── tests/test_api.py
├── frontend/
│   ├── app/page.tsx          # React UI: 3 AI / planner / history / modals
│   ├── app/globals.css
│   ├── app/layout.tsx
│   ├── lib/api.ts
│   ├── lib/types.ts
│   └── next.config.ts        # Forward /api/* to Python server
├── docs/
├── legacy/
├── Dockerfile.backend
├── Dockerfile.frontend
└── docker-compose.yml
```
=======
# content
>>>>>>> d15903ed345d4d681a6d747bdeb1e4a1a8cfbf92
