# Tagado

Invoice follow-ups that run on **your Claude** (via MCP). Tagado stores plans, schedules sends into an outbox, reacts to client responses, and keeps everything editable — with **no AI inside the app**.

Product rules: [`SPEC.md`](SPEC.md)  
Build order: [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)

## Stack (assignment build)

- Frontend: React + Vite + TypeScript + Tailwind
- Backend: FastAPI + SQLAlchemy + SQLite
- MCP: official Python MCP SDK (Streamable HTTP)
- Email (assignment): in-app Outbox (no SMTP required for Phase 0–5)

## Prerequisites

- Python 3.11+
- Node.js 20+

## Local setup

```bash
# 1) Env
cp .env.example .env

# 2) Backend
cd backend
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3) Frontend (another terminal)
cd frontend
npm install
npm run dev
```

- App (Vite): http://localhost:5173  
- API: http://localhost:8000/api/health  
- MCP base: http://localhost:8000/mcp/?key=`<token from bootstrap log>`

On backend start, the demo workspace is seeded from `.env` and the MCP URL is printed in the server log. You can also run:

```bash
cd backend
python ..\scripts\print_mcp_url.py
```

## MCP smoke test (Phase 0)

1. Start the backend.
2. Copy the MCP URL from the startup log (includes `?key=`).
3. Open MCP Inspector:

```bash
npx @modelcontextprotocol/inspector
```

4. Transport: **Streamable HTTP**  
5. URL: the printed MCP URL (keep the trailing slash before `?` as shown)  
6. Call tool `ping` → should return the demo business name.

Claude.ai cannot reach `localhost`. Use a tunnel (cloudflared/ngrok) or deploy (Phase 6) before connecting Claude.

## No-AI guard

```bash
python scripts/check_no_ai.py
```

## Phase status

- [x] Phase 0 — pipe (health + MCP ping + SQLite seed + frontend shell) ✅
- [x] Phase 1 — core engine + Indian demo seed + pytest ✅
- [x] Phase 2 — MCP tools (incl. new client onboard) ✅
- [x] Phase 3 — outbox send + cron ✅
- [x] Phase 4 — owner app (dashboard / invoice / settings) ✅
- [x] Phase 5 — client payment page ✅
- [x] Phase 6 — deploy + Claude MCP connect ✅

## Live deploy (Render)

Repo already includes `Dockerfile` + `render.yaml`.

1. Push `main` to GitHub (this repo).
2. Open the Blueprint deploy link (replace with your fork if needed):  
   https://render.com/deploy?repo=https://github.com/Niranjan5712/Tagado
3. Create the **tagado** web service. After the first URL exists, set env `APP_URL` to `https://<service>.onrender.com` (no trailing slash) and redeploy.
4. Open the live site, sign in with the demo login below, go to **Settings → Connect Claude**, copy the private link.

### Demo login

- Email: `demo@tagado.app`
- Password: `tagado-demo-2026`

### Connect Tagado in Claude.ai

1. Open [Claude.ai](https://claude.ai) → **Settings** → **Connectors**.
2. **Add custom connector**.
3. Name: `Tagado`.
4. URL: paste the **Private Claude connection link** from Tagado (**Settings → Connect Claude**).  
   Keep the trailing slash before `?key=` — example shape:  
   `https://YOUR-APP.onrender.com/mcp/?key=YOUR_TOKEN`
5. Save → **Connect**.
6. In a new chat ask: `What can Tagado do?` then try:  
   `Track my invoice to Kalpataru Retail for ₹50,000 due 15 Dec.`

Claude cannot use `localhost`. The connector URL must be a public `https://` address.
