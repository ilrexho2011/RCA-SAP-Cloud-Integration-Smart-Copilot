# RCA Smart Copilot for SAP CPI — Backend

FastAPI service. Read-only SAP CPI / Integration Suite connector with a demo
fallback so the platform runs before a service key is configured.

## Run

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # leave RCA_ENV=demo to run without a tenant
uvicorn app.main:app --reload # http://localhost:8000  (docs at /docs)
```

## Endpoints

```text
GET /api/health                       mode: live | demo
GET /api/monitoring/overview          KPIs + connected systems + failed messages
GET /api/monitoring/connection-test   pings CPI (or demo)
```

## Going live

Set in `.env`:

```text
RCA_ENV=live
CPI_BASE_URL=...      # Service Key -> url
CPI_TOKEN_URL=...     # Service Key -> tokenurl  (append /oauth/token if missing)
CPI_CLIENT_ID=...     # Service Key -> clientid
CPI_CLIENT_SECRET=... # Service Key -> clientsecret
RCA_MASTER_KEY=...    # base64 32-byte key (see app/security/crypto.generate_master_key)
```

The connector reads `MessageProcessingLogs` and `IntegrationRuntimeArtifacts`
over the OData v2 API using an OAuth2 client-credentials token. Read-only — no
writes to the tenant.

## Layout

```text
backend/app/
  main.py                 FastAPI app + CORS + health
  config.py               env settings (demo/live)
  api/monitoring.py       routes
  services/monitoring_service.py   aggregation
  connectors/
    base.py               connector protocol
    sap_cpi.py            live OData client (token, MPL, runtime artifacts)
    demo_provider.py      bundled RCA sample data
  models/schemas.py       response contracts
  security/crypto.py      AES-256-GCM secret handling
```
