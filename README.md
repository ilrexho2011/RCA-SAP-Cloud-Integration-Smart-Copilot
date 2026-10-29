# RCA-SAP-Cloud-Integration-Smart-Copilot

**Analysis, generation and management of integrations with AI Assistance**, across **SAP CPI, API Management (APIM) and Advanced Event Mesh (AEM)** — built by **RealCore Albania (RCA)**. The visual theme is dark + RCA lime ("Control Room"); the AI runs an **orchestrated, RAG-grounded, quality-gated** pipeline, not a single LLM call.

> Status: research/build preview. Backend (FastAPI) + frontend (React + TypeScript). Runs fully in **demo mode** with no SAP tenant and no LLM key; add a service key and an AI provider to go live.

---

## What it does

Six modules, all functional:

| # | Module | What it does |
| --- | -------- | -------------- |
| 01 | **Dashboard** | Landing overview across SAP CPI, APIM and AEM: Total iFlows, Packages, Watched, Failing, quick actions and recent failures. |
| 02 | **Generate** | iFlow from plain language via the orchestrator: classify → RAG retrieve → plan → design brief → **human approval** → generate (BPMN2) → validate → quality gate → **deploy gate**. |
| 03 | **iFlows** | Browse packages/iFlows; **Explain** any iFlow from the tenant or an uploaded ZIP, grounded in the parsed BPMN model. |
| 04 | **Groovy** | Generate CPI Groovy scripts with analyze → generate → static validation. |
| 05 | **Monitor** | Control room: KPIs, **Ask your monitoring** (NL→answer over live signals), watch list, JMS queue health, recent failures — read-only from CPI OData (MPL + runtime artifacts) or demo data. |
| 06 | **Settings** | CPI connection (OAuth service key) + AI engine (BYOK: OpenAI / Perplexity / Anthropic / Gemini / DeepSeek). Secrets encrypted at rest (AES-256-GCM). |

## The orchestration idea

Every AI action runs through a **deterministic state machine**; the LLM is invoked only *inside* steps. Control transitions live in code, so we get grounded retrieval, typed validation, a repair loop, human-in-the-loop gates before any write, and a full run trace. This is the core improvement over a plain "prompt → XML" copilot. See `docs/ROADMAP.md` for the architecture and diagrams.

---

## Run it locally

Two terminals. The backend defaults to demo mode, so it works with zero configuration.

### Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # keep RCA_ENV=demo to run without a tenant

uvicorn app.main:app --reload      # http://localhost:8000  · docs at /docs
```

### Frontend (React + Vite)

```bash
cd frontend
npm install

npm run dev                       # http://localhost:5173  (proxies /api → :8000)
```

Open <http://localhost:5173>.

### Go live

In the app, open **Settings** (four sections):

- **CPI Connection** — paste your Integration Suite service key (url, tokenurl, clientid, clientsecret), Save, Test, then switch to live.
- **CPI Runtime** — optional runtime service key, needed only for Fix/Verify flows; leave blank to reuse the CPI Connection.
- **Email Alerts** — RCA managed mail service (free) or your own SMTP, with alert recipients.
- **AI Engine** — pick a provider (OpenAI, Perplexity, Anthropic, Gemini, DeepSeek), enter the exact model string + API key (BYOK). Until then, Generate/Explain/Groovy use a deterministic stub so everything is testable offline.

Secrets (design, runtime, SMTP, AI key) are encrypted with AES-256-GCM and never returned to the browser.

> Live APIM and AEM sources are shown in demo today; connecting them live needs their own service keys (a later increment). The CPI connector is live-ready now.

---

## Layout

```text
smart-copilot-sap-cpi/
  docs/ROADMAP.md          architecture + roadmap + diagrams
  backend/                 FastAPI service (see backend/README.md)
    app/
      api/                 routers: monitoring, monitor, generate, iflows, groovy, settings
      orchestrator/        state machine, agents, RAG, validator, quality gate
      connectors/          SAP CPI OData client + demo provider
      iflow/               BPMN parser + explain
      groovy/              generator + validator
      llm/                 provider abstraction + BYOK providers
      security/            AES-256-GCM store
  frontend/                React + TS + Vite, QDKEP theme (see frontend/README.md)
```

## Accounts & persistence

The app is **multi-tenant with JWT auth**. On first load you register an account (which creates your own workspace/tenant); everything you save — CPI connection, AI engine, email config, watch list, generation runs — is stored **per tenant** in a database and survives restarts. Secrets stay AES-256-GCM encrypted.

- Default DB is **SQLite** at `backend/instance/rca.db` (zero-install). Point `DATABASE_URL` at Postgres to switch: `postgresql+asyncpg://user:pass@host:5432/rca`.
- Tenants are isolated — one account never sees another's connections, runs or watch list.

## Notes & next steps

- Deploy-to-tenant (write) is gated pending a live connection.
- Live APIM/AEM sources are demo today; connecting them needs their own service keys.
- Not yet: SSE streaming of orchestrator steps; Alembic migrations (tables auto-create on startup for now).
