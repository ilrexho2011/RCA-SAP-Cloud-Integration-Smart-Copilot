# Connecting a live SAP CPI tenant

The backend runs on **your machine**, so the live connection is made there (not in any sandbox). Follow these steps.

## 1. Start the app

```bash
# Terminal 1
cd backend
python -m venv .venv && .venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload                          # http://localhost:8000

# Terminal 2
cd frontend
npm install
npm run dev                                            # http://localhost:5173
```

## 2. Enter your service key (Settings → CPI Connection)

From your trial tenant (values from the BTP service key):

| Field | Value (example, ap21 trial) |
|-------|------------------------------|
| Base URL | `https://47f506eatrial.it-cpitrial03.cfapps.ap21.hana.ondemand.com` |
| Token URL | `https://47f506eatrial.authentication.ap21.hana.ondemand.com/oauth/token` |
| Client ID | `sb-30ffb28a-…!b130557|it!b196` |
| Client Secret | *(from the service key)* |
| Web IDE URL | *(leave blank — optional)* |

Then: **Save credentials** → **Test CPI connection** → **Switch to live**.

## 3. Required OAuth roles on the service key

This is the most common blocker. The connection reads **MessageProcessingLogs** and **IntegrationPackages / design-time artifacts** over the OData API, which need read roles on the key.

When you create the service key (BTP Cockpit → Instances → Integration Suite / *Process Integration Runtime* → plan `api` → **Create Service Key**), include at least:

- `MonitoringDataRead` — required for MPL (failed/completed messages)
- `WorkspacePackagesRead` — required for packages and iFlow list
- `IntegrationContentRead` — deployed runtime artifacts

If your existing key was created without roles, recreate it with these (or add the role collection), then paste the new `clientid`/`clientsecret`.

## 4. Read the result

- **Success** → the badge flips to `live`, and Monitor/Dashboard show real numbers (deployed iFlows, real MPL failures).
- **Failure** → the app now shows the **real reason** instead of a generic error, e.g.:
  - `HTTP 401/403 … check the service key OAuth scopes` → roles missing (step 3).
  - `HTTP 404` → Base URL wrong (must be the API host `…/api/v1` base, not the Web IDE URL).
  - `Connection failed / timeout` → Base or Token URL host is wrong, or no network to the tenant.

## Notes

- Secrets are encrypted at rest (AES-256-GCM) and never returned to the browser.
- Testing in-session may have reset `backend/instance/` — just re-enter and save the key.
- Live **APIM** and **AEM** sources are shown in demo today; connecting them live needs their own service keys (a later increment). The **CPI** connector is live-ready now.

