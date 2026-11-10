# Tagado — Phase-wise Implementation Plan (Assignment Build)

**Date:** 10 Nov 2026  
**Source of truth for product rules:** `Resources/Tagado — Product & Build Spec (v1).md`  
**Source of truth for how we build (this file):** assignment-adapted stack, phases, files, acceptance checks  

This plan is written for the Volopay Founder's Office assignment. Build **one phase at a time**. Do not start the next phase until the current phase’s **Done when** check passes.

---

## 0. Product understanding (locked)

### What Tagado is
Tagado tracks money a small Indian B2B business is owed and follows up with each client until a **human** confirms payment arrived.

- **Claude (via MCP)** thinks and writes: reads client history, drafts / redrafts follow-up plans, answers “who owes me / what needs attention”, records payment only when the owner explicitly confirms in chat.
- **Tagado (the app)** does everything else: store, validate, schedule, “send”, react to client responses with fixed rules, compute client payment history, keep the result live and editable.
- **Owner** approves plans, confirms payments, resolves issues, resumes paused plans.
- **Client payer** opens a public link (no account), pays offline (bank/UPI), reports payment / promise / need / problem.

### One rule that decides every design question

| Who | Does | Never does |
| --- | --- | --- |
| Claude (MCP) | Drafts text, reads data, records owner-confirmed payment | Sends anything, approves plans, resolves issues |
| Tagado backend | Stores, validates, schedules, sends (outbox), fixed client-response rules, history | Writes with AI, guesses intent, sends unapproved messages |
| Owner | Approves, confirms, resolves, resumes | Remembers dates |
| Client | Opens link, responds | Needs account or Claude |

### What v1 is
Invoice tracking · drafted follow-up plan per invoice · scheduled sending via outbox · public client response page · owner dashboard · 8 MCP tools.

### What v1 is not
Invoicing/GST tool · payment gateway · WhatsApp · bank reconciliation · partial payments · multi-user teams · **any AI inside the app**.

### Why this wins the assignment
Volopay asked for a small business that runs on Claude with **no AI inside the app**. Tagado is not a website builder or shop. One sharp loop:

> Claude creates a real invoice+plan → human edits/approves in the live app → app keeps it live (send, hold, pause, confirm) → client responds without login → history feeds the next Claude draft.

---

## 1. Assignment mapping (must all be true)

| Volopay requirement | How Tagado satisfies it |
| --- | --- |
| Work from Claude — a request creates something real | MCP `create_invoice_with_plan` writes invoice + draft messages to SQLite |
| Let a person edit it | Live app: review link, edit subject/body/dates, approve |
| Live on the internet | Deploy from GitHub to a public HTTPS URL (Render or equivalent) |
| No AI inside; no OpenAI/Anthropic keys | Only MCP protocol SDK; Claude is external |
| Not a website builder / online shop | Invoice follow-up product only |
| MCP link + connect steps | Settings shows MCP URL + 3 Claude connector steps |
| Test login | Seeded demo workspace (`DEMO_EMAIL` / `DEMO_PASSWORD`) |

**Pitch video support (2–5 min):** Acme warm vs Zenith firm drafts → edit/approve → Send now → Outbox + client page → issue raised → attention in Claude.

---

## 2. Assignment stack (deviations from original SPEC)

| Area | Original SPEC | This assignment build | Why |
| --- | --- | --- | --- |
| Database | Postgres (Neon) | **SQLite** (`tagado.db`) | Simple local + free hosting; enough for demo |
| Packaging | Docker multi-stage | **No Docker** | User preference; host builds from GitHub |
| Email | Gmail SMTP | **In-app Outbox** (composed HTML stored; no SMTP) | Avoid Gmail app-password friction; reviewers still see full send loop |
| Deploy check | Every phase on live URL first | Phases 0–5 proven **locally**; Phase 6 deploys + Claude.ai + tunnel/live MCP | Claude cannot hit localhost; tunnel or deploy needed for Claude connect |
| Hosting | Render Dockerfile | GitHub → Render (or similar) **Python** web service + build frontend in start/build command | No Docker |

**Non-negotiable product rules kept from SPEC:**  
§4 design decisions · §7 state machine · §10 eight tools (approve/send/resume stay human-only) · §14 guardrails · no AI libraries (`scripts/check_no_ai.py`).

### Outbox email model (replaces SMTP)
- `compose.py` still builds subject + HTML + plain text exactly as if sending.
- `send.py` / `send_one` **persists** an `outbound_emails` row and marks the message `sent` (same status transitions as SPEC).
- Owner UI: **Outbox** on invoice detail (and/or a panel after Send now) with rendered preview + **Open client page** button.
- Cron tick still claims due messages and “sends” into Outbox.
- Owner “notifications” on client response also go to Outbox (to reply-to address), not SMTP.
- **Optional later (P1+):** swap `send_email()` body to SMTP/Resend without changing engine.

### SQLite adaptations
- Money still integer **paise**; timestamps UTC; schedule/display via `Asia/Kolkata`.
- Atomic claim: SQLite has limited `FOR UPDATE SKIP LOCKED`. Use a single Uvicorn worker + transactional claim (`UPDATE … WHERE status='scheduled' AND id=(SELECT…)`) and `sending` state; acceptable for assignment.
- Persist DB file under `backend/data/tagado.db` (gitignored). On free hosts with ephemeral disk: **seed on startup** if empty + **Reset demo** button.
- Use SQLAlchemy 2.0; Alembic optional — for speed, Phase 1 may use `create_all` + seed; add Alembic only if schema churn hurts.

---

## 3. Architecture (unchanged idea)

One FastAPI process, four doors, one service layer:

```text
Owner's Claude          Owner browser           Client browser              Cron (optional)
 MCP HTTPS               React (same origin)     /p/:token                   POST /api/cron/tick
 /mcp/?key=TOKEN         /api/...                /api/public/...             x-cron-secret
        \                     |                        |                          /
         \                    v                        v                         /
          +------------------- FastAPI ----------------------------------------+
          |  mcp/   thin tools → services                                       |
          |  api/   owner | public | cron                                       |
          |  services/  engine.py (ALL status writes) · plans · stats ·         |
          |             attention · email/compose · email/send (outbox) · seed  |
          |  db/   SQLAlchemy models → SQLite                                   |
          +---------------------------------------------------------------------+
```

**Hard rule:** No file except `services/engine.py` (and email claim helpers that only flip `scheduled→sending→sent/failed` via defined functions) may write invoice/plan/message status fields. Every transition writes an `events` row in one transaction.

**Mount order:** `/api` router → `/mcp` mount → SPA static **last**.

---

## 4. Data model (6 tables + outbox)

```text
users          id · email · password_hash · name · workspace_id
workspaces     business settings · bank · upi · udyam · mcp_token · send_hour/minute IST · is_demo
clients        workspace_id · name · contact_name · email · cc_emails · relationship_notes
               UNIQUE(workspace_id, email)
invoices       amounts in paise · status · plan_status · public_token · promise_* · reported_* · issue_* · paid_at
               UNIQUE(workspace_id, invoice_number)
messages       kind main|promise_checkin · step · tone · subject · body · send_at · status · include_msme_note · sent_* · attempts
events         actor owner|client|claude|system · type · data jsonb/text · created_at
outbound_emails  id · workspace_id · invoice_id? · message_id? · to_addrs · cc · reply_to · subject · html · text · kind (reminder|owner_notice) · created_at
```

**Statuses (exact):**
- Invoice: `open` · `promised` · `payment_reported` · `issue_raised` · `paid` · `cancelled`
- Plan: `draft` · `active` · `paused` · `completed` · `cancelled`
- Message: `draft` · `scheduled` · `held` · `sending` · `sent` · `failed` · `cancelled`

**Send rule (only one):** send only if message=`scheduled`, `send_at`≤now, plan=`active`, invoice=`open`|`promised`.  
Send now: same state checks; skips time window; claims via `sending` first.

---

## 5. State machine (implement exactly — SPEC §7)

All in `backend/app/services/engine.py`:

| Function | Core effect |
| --- | --- |
| `create_invoice_with_plan` | invoice `open`, plan `draft`, messages `draft` |
| `approve_plan` | plan `active`; main draft → scheduled (past slots bumped) |
| `pause_plan` / `resume_plan` | scheduled ↔ held; resume re-spaces (min 2-day gaps) |
| `client_reported_payment` | → `payment_reported`; scheduled → held; outbox notice |
| `client_promised` | → `promised`; hold mains; schedule check-in date+1; outbox notice |
| `client_raised_issue` | → `issue_raised`; plan `paused`; hold all; outbox notice |
| `mark_promise_broken` | cron; → open + plan paused; promise_broken |
| `confirm_payment` | → paid; plan completed; unsent cancelled |
| `reject_payment_report` | → open; plan active; held re-spaced |
| `resolve_issue_and_resume` | → open; plan active; held re-spaced |
| `replace_remaining_messages` | unsent cancelled; new draft; plan draft |
| `update_message` (MCP) | plan → draft; needs re-approval |
| `update_message` (owner) | edit in place; plan unchanged |
| `cancel_invoice` | cancelled; unsent cancelled |
| sequence ended (cron) | plan completed if no unsent mains and still open |

**Deliberate:** client actions never resume sending; `payment_reported` never times out.

---

## 6. MCP tools (8 only)

**Server instructions:** use SPEC §10 verbatim (placeholders, Indian English, no bank/legal in Claude text, always `get_client_context` before draft, give `review_url`).

| Tool | R/W | Purpose |
| --- | --- | --- |
| `get_client_context` | R | History + notes + `today_ist` before drafting |
| `create_invoice_with_plan` | W | Atomic invoice + draft plan |
| `update_message` | W | Edit one unsent → forces plan draft |
| `replace_remaining_messages` | W | Redraft remaining → plan draft |
| `list_invoices` | R | Who owes what |
| `get_invoice` | R | Full detail |
| `get_attention_items` | R | What needs owner |
| `record_payment` | W | Owner-confirmed payment only |

**Not tools (human-only in app):** approve, pause, resume, resolve, send now.

Auth: `?key=` workspace `mcp_token` via ASGI middleware → `contextvars` workspace id.

Transport: FastMCP Streamable HTTP, stateless, JSON; mount at `/mcp/` (trailing slash).

---

## 7. REST API (owner + public + cron)

Session cookie auth for owner routes. Public token for client. Cron secret header.

Include all SPEC §11 routes needed for P0. Email send path writes Outbox instead of SMTP.  
`GET /api/messages/{id}/preview` and Outbox use the same `compose` function.  
`GET /api/invoices/{id}/outbox` (or embed outbox in invoice detail payload) for assignment UX.

---

## 8. Screens (P0)

| Route | Priority | Purpose |
| --- | --- | --- |
| `/login` | P0 | Demo login |
| `/` | P0 | Dashboard: 4 totals, Needs attention, invoices table |
| `/invoices/:id` | P0 | Plan review/edit/approve, response actions, timeline, outbox, Send now, Preview |
| `/settings` | P0 | Business/bank/UPI/Udyam, MCP URL + connect steps, Reset demo |
| `/p/:token` | P0 | Client page: pay info, 4 responses, state-aware |
| `/clients`, `/clients/:id` | P1 | Skip until P0 scenarios pass (seed notes still used by MCP) |

---

## 9. Seed data (relationship-aware demo)

Workspace: Pixelcraft Studio · `is_demo=true` · dummy bank + UPI + Udyam · MCP token generated.

| Client | History | Notes |
| --- | --- | --- |
| Acme Retail | 6 paid, mostly on time | Warm, long-term |
| Zenith Logistics | Often late, 2 broken promises | Polite but date-specific |
| Northwind Foods | On time | — |

Live invoices for non-empty dashboard: Northwind open+active · Northwind payment_reported · Zenith issue_raised · Acme paid.  
**No open Acme/Zenith invoices** so Claude can create them live in the demo.

Reset demo: wipe demo workspace rows → re-seed.

---

## 10. Acceptance scenarios (ship bar)

Run after Phase 6 on live URL (and earlier ones locally as noted):

1. Claude: “What can Tagado do?” → lists tools  
2. Claude: “Who owes me money?” → matches dashboard  
3. Track Acme → warm 3 msgs + review link  
4. Track Zenith → firmer, date-specific; mentions late history  
5. Repeat Acme create → “Already tracked”; no duplicate  
6. App: edit, MSME toggle, Preview, Approve → scheduled 10:30 IST  
7. Send now → **Outbox** shows email with client button; timeline logs send  
8. Client: need PO → held + attention + owner notice in Outbox  
9. Resolve & resume → re-spaced schedule  
10. Client: payment scheduled → promised + check-in  
11. Client: I’ve paid → Confirm → paid; thank-you page; stats update  
12. Claude: attention → options; drafts reply; sends nothing  

**Safety:** Claude cannot send; MCP edit after approve → draft; double cron → one send; random `/p/...` → 404.

---

## 11. Repo structure (target)

```text
tagado/
  IMPLEMENTATION_PLAN.md          # this file
  SPEC.md                         # copy/symlink of product spec for agents
  README.md                       # setup, demo login, MCP connect steps
  scripts/check_no_ai.py
  frontend/
    package.json
    vite.config.ts                # proxy /api → :8000 in dev
    src/main.tsx
    src/api/client.ts
    src/routes/Login.tsx Dashboard.tsx InvoiceDetail.tsx Settings.tsx PublicInvoice.tsx
    src/components/MessageCard.tsx Timeline.tsx AttentionList.tsx StatusChip.tsx EmailPreview.tsx OutboxList.tsx
  backend/
    requirements.txt
    pytest.ini
    data/                         # gitignored; tagado.db lives here
    app/
      main.py config.py
      db/models.py session.py
      api/auth.py dashboard.py invoices.py messages.py clients.py settings.py public.py cron.py
      mcp/server.py tools.py auth_middleware.py
      services/engine.py plans.py stats.py attention.py scheduler.py clients.py invoices.py
               workspaces.py seed.py time.py qr.py
      services/email/compose.py send.py templates/
    tests/test_engine.py test_plans.py test_scheduler.py test_mcp_tools.py
  .env.example                    # NO AI keys
  .gitignore
```

---

## 12. Environment variables

```text
DATABASE_URL=sqlite:///./data/tagado.db
APP_URL=http://localhost:8000          # later https://<deployed>
SESSION_SECRET=...
CRON_SECRET=...
DEMO_EMAIL=demo@tagado.app
DEMO_PASSWORD=...
# No SMTP_* required for assignment outbox mode
# No OPENAI/ANTHROPIC keys — ever
```

---

## 13. Phase-wise build plan

### Phase 0 — Prove the pipe  
**Goal:** Runnable skeleton; health; MCP auth + `ping`; SQLite opens; frontend shell builds.  
**Magnitude:** [MAJOR]

**Build**
1. Copy product spec to `SPEC.md` (or keep Resources path referenced from README).
2. Backend: FastAPI app, config, `/api/health`, session middleware stub.
3. SQLite engine + empty metadata create.
4. MCP FastMCP mount at `/mcp/`, token middleware, one tool `ping` → returns workspace name for valid key.
5. Minimal workspace seed for ping (or create workspace row on first boot).
6. Frontend Vite+React+TS+Tailwind shell with Login placeholder; Vite proxy `/api`.
7. `scripts/check_no_ai.py` + `.env.example` + `.gitignore` + README (local run steps).
8. Dev run script documented: `uvicorn` + `npm run dev` (or serve built static from FastAPI).

**Files to create**
- `SPEC.md`, `README.md`, `.gitignore`, `.env.example`
- `scripts/check_no_ai.py`
- `backend/requirements.txt`, `backend/app/main.py`, `config.py`, `db/session.py`, `db/models.py` (Workspace(+User) minimal)
- `backend/app/mcp/server.py`, `auth_middleware.py`
- `backend/app/api/health` (or in main)
- `backend/app/services/seed.py` (minimal workspace+token)
- `frontend/package.json`, Vite/TS/Tailwind config, `src/main.tsx`, `App.tsx`, `routes/Login.tsx`

**Done when**
- `GET /api/health` → ok locally  
- MCP Inspector Streamable HTTP → `http://localhost:8000/mcp/?key=<token>` → `ping` returns workspace name  
- `check_no_ai.py` passes  
- **Stop. Wait for approval before Phase 1.**

**Not in Phase 0:** full models, engine, React screens, email, deploy.

---

### Phase 1 — Core logic  
**Goal:** Full schema, seed, time/plans validation, **complete engine**, stats, attention; pytest for every §7 row.

**Build**
1. Full SQLAlchemy models (all 6 tables + `outbound_emails`).
2. `time.py` IST helpers; send-slot math Mon–Sat 09:00–19:00; Sunday→Monday; default 10:30 IST.
3. `plans.py`: message validation (placeholders, spacing ≥2 days, date windows), `send_at` computation, re-spacing.
4. `engine.py`: every transition in §7; one transaction + event each.
5. `stats.py`, `attention.py` (priority order).
6. Full demo seed (Acme/Zenith/Northwind + live invoices).
7. Pytest: one test per engine transition + key plan validations.

**Done when:** `pytest` green for full transition table.  
**Stop for approval.**

---

### Phase 2 — MCP tools (all 8)  
**Goal:** Claude (or Inspector) can create and read real invoices.

**Build**
1. Server instructions + tool descriptions (verbatim where SPEC says).
2. Wire tools → services only (no business logic in tools).
3. Duplicate invoice_number → return existing + message (idempotent).
4. Local Claude connect via **cloudflared/ngrok** tunnel to `/mcp/?key=…` (document steps).

**Done when:** Scenarios 1–5 pass via Inspector (and Claude if tunnel available).  
**Stop for approval.**

---

### Phase 3 — Compose + Outbox send + scheduler  
**Goal:** Sending path works without SMTP.

**Build**
1. Jinja2 compose: placeholders, footer with client link, optional MSME paragraph.
2. `send_one` → claim sending → write `outbound_emails` → mark sent + event (or failed/retry).
3. `POST /api/messages/{id}/send-now`, `GET .../preview`.
4. `POST /api/cron/tick` with secret: claim due, send to outbox, promise-broken check, sequence-completed check.
5. Owner notice on client responses → outbox.
6. Tests for claim/idempotency (double tick → one outbox row).

**Done when:** Approve a plan in API/tests → Send now → Outbox row with correct HTML/link; parallel tick safe.  
**Stop for approval.**

---

### Phase 4 — Owner React app  
**Goal:** Human edit/approve/act loop.

**Build**
1. Auth: login/logout/me + session cookie (`credentials: include`).
2. Dashboard: 4 numbers, attention list, invoices table + filters.
3. Invoice detail: messages edit/delete, MSME toggle, Preview, Approve/Pause/Resume/Confirm/Reject/Resolve/Cancel, Send now, timeline, **Outbox list**.
4. Settings: business fields, MCP URL copy + 3 connect steps, regenerate token, Reset demo.
5. Serve production build from FastAPI in prod mode; Vite proxy in dev.

**Done when:** Scenarios 6, 7, 9 pass locally in browser.  
**Stop for approval.**

---

### Phase 5 — Client public page  
**Goal:** `/p/:token` mobile-first responses drive engine.

**Build**
1. Public GET payload (no private fields).
2. Four actions: paid / scheduled / need / problem + share link (copy only).
3. State-aware views (reported / paid / withdrawn / issue).
4. Bank copy buttons; UPI QR only if UPI set and outstanding ≤ ₹1,00,000.
5. `client_viewed` event throttled (≤1/hour).

**Done when:** Scenarios 8, 10, 11 pass (phone width OK).  
**Stop for approval.**

---

### Phase 6 — Deploy + E2E polish  
**Goal:** Live URL for Volopay; all 12 scenarios twice from clean reset.

**Build**
1. Push to user’s GitHub repo.
2. Configure host (Render/etc.): build frontend, install Python deps, start uvicorn, set env vars, persistent disk **or** seed-on-boot.
3. Point `APP_URL` at public HTTPS.
4. Connect MCP in Claude.ai; fix trailing slash / Host header pitfalls.
5. Empty/loading/error states; README submission section (demo login, MCP steps).
6. Run all 12 scenarios + safety checks; `check_no_ai.py` in CI or pre-submit.

**Done when:** Live demo works end-to-end from Claude.ai.  
**P1 only after this:** Clients pages, SMTP, signup, due-date shift prompt.

---

## 14. Working rules for the agent (every phase)

1. **Propose file list → implement only that phase → summarize → wait for “continue”.**
2. Do not add packages/features not in this plan.
3. Never add AI SDKs or API keys.
4. Refuse shortcuts that break §4 / §7 / §14 product rules.
5. Prefer smallest change that passes the phase **Done when**.
6. If a change needs >3 files beyond the phase file list, flag **[COMPLEX CHANGE]** and ask.
7. After each phase: how to test locally (commands + expected result).

---

## 15. Local development commands (target)

```bash
# backend
cd backend
python -m venv .venv
.\.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env            # from repo root or backend as decided
uvicorn app.main:app --reload --port 8000

# frontend (dev)
cd frontend
npm install
npm run dev

# tests
cd backend
pytest

# no-AI guard
python scripts/check_no_ai.py
```

For Claude.ai against local: run a tunnel to port 8000; paste `https://<tunnel>/mcp/?key=<token>` into Claude Connectors.

---

## 16. Submission pack (produce in Phase 6)

1. Live app URL  
2. Demo username / password  
3. MCP URL + 3 connect steps (also in Settings)  
4. Pitch talking points: who · best work · why Tagado wins · live demo script · economics (Claude already paid; Tagado = execution layer; wedge = relationship-aware collections)  
5. Confirm `check_no_ai.py` clean  

---

## 17. Explicitly out of scope until P0 done

- Docker / Postgres / Neon  
- Gmail SMTP / Resend  
- WhatsApp, payment gateway, Zoho import, teams  
- Self-serve signup  
- Clients list/detail pages (MCP still uses seeded notes/stats)  
- Partial payments  

---

## 18. Current status

| Phase | Status |
| --- | --- |
| Plan document | **COMPLETE** |
| Phase 0 | **COMPLETE** — health OK, MCP `ping` OK, SQLite seed OK, frontend shell builds |
| Phase 1 | **COMPLETE** — models, engine §7, plans/stats/attention, Indian demo seed, pytest green |
| Phase 2 | **COMPLETE** — 8 MCP tools + ping; new-client onboard via create_invoice_with_plan |
| Phase 3 | **COMPLETE** — compose, Outbox send, send-now/preview, cron tick, tests green |
| Phase 4 | **COMPLETE** — owner app (dashboard, invoice detail, settings) with product-facing copy |
| Phase 5 | **COMPLETE** — public client page, 4 responses, UPI QR guard, view throttle |
| Phase 6 | Not started — awaiting approval |

---

## Checkpoint

Implementation plan written. Next action after your approval: **Phase 0 only** — list files, then create skeleton (FastAPI + SQLite + MCP `ping` + frontend shell). No Phase 1 until Phase 0 checks pass and you say continue.
