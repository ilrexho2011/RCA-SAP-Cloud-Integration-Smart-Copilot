/* Settings — SAP CPI connection. Secrets are encrypted server-side (AES-256-GCM)
   and never echoed back; the secret field shows a sentinel when one is stored. */
import { useEffect, useState } from "react";
import {
  getConnection, saveConnection, testConnection, switchMode,
  getAiEngine, saveAiEngine, testAiEngine, listAiModels,
  getEmailAlerts, saveEmailAlerts, testEmailAlerts,
  getSource, saveSource, testSource,
  type ConnectionInfo, type ConnectionTestResult,
  type AiEngineInfo, type AiEngineTestResult,
  type EmailAlertsInfo, type EmailTestResult,
  type SourceInfo, type SourceTestResult,
} from "../api";

const SENTINEL = "__stored__";

const PROVIDERS = [
  { id: "stub", label: "RCA Copilot AI (included)" },
  { id: "openai", label: "OpenAI" },
  { id: "perplexity", label: "Perplexity" },
  { id: "anthropic", label: "Anthropic (Claude)" },
  { id: "gemini", label: "Google (Gemini)" },
  { id: "deepseek", label: "DeepSeek" },
];

// Provider-specific model examples so the model string always matches the provider.
const MODEL_EXAMPLES: Record<string, string> = {
  openai: "gpt-4o · gpt-4o-mini",
  perplexity: "sonar-pro · sonar · sonar-reasoning",
  anthropic: "claude-sonnet-5 · claude-opus-5 · claude-haiku-4-5",
  gemini: "gemini-2.0-flash · gemini-1.5-pro",
  deepseek: "deepseek-chat · deepseek-reasoner",
};
// Key-prefix sanity per provider (best-effort mismatch warning).
const KEY_PREFIX: Record<string, string> = {
  openai: "sk-", anthropic: "sk-ant-", perplexity: "pplx-",
};

export default function Settings() {
  const [info, setInfo] = useState<ConnectionInfo | null>(null);
  const [form, setForm] = useState({
    base_url: "", token_url: "", client_id: "", web_ide_url: "", client_secret: SENTINEL,
    rt_base_url: "", rt_token_url: "", rt_client_id: "", rt_client_secret: SENTINEL,
  });
  const [test, setTest] = useState<ConnectionTestResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    const c = await getConnection();
    setInfo(c);
    setForm({
      base_url: c.base_url, token_url: c.token_url, client_id: c.client_id,
      web_ide_url: c.web_ide_url, client_secret: c.secret_set ? SENTINEL : "",
      rt_base_url: c.rt_base_url, rt_token_url: c.rt_token_url, rt_client_id: c.rt_client_id,
      rt_client_secret: c.rt_secret_set ? SENTINEL : "",
    });
  }
  useEffect(() => { refresh(); }, []);

  function set<K extends keyof typeof form>(k: K, v: string) { setForm((f) => ({ ...f, [k]: v })); }

  // Persist the current form so Test/Switch always act on the entered credentials.
  async function persist(): Promise<ConnectionInfo> {
    const saved = await saveConnection({ ...form, mode: "live" });
    setInfo(saved);
    if (!saved.configured) setMsg("Not configured yet — fill the Client Secret, then Save.");
    return saved;
  }

  async function onSave() {
    setBusy("save"); setMsg(null);
    try {
      const s = await persist();
      if (s.configured) setMsg(`Connection saved — now ${s.mode}.`);
    } catch (e) { setMsg(e instanceof Error ? e.message : "Save failed"); }
    finally { setBusy(null); }
  }
  async function onTest() {
    setBusy("test"); setMsg(null); setTest(null);
    try {
      await persist();                     // save first, so we test the real credentials (not demo)
      setTest(await testConnection());
    } catch (e) { setMsg(e instanceof Error ? e.message : "Test failed"); }
    finally { setBusy(null); }
  }
  async function onMode(mode: "live" | "demo") {
    setBusy("mode"); setMsg(null);
    try {
      if (mode === "live") setInfo(await persist());   // saving stores creds + sets live
      else setInfo(await switchMode("demo"));
    } catch (e) { setMsg(e instanceof Error ? e.message : "Switch failed"); }
    finally { setBusy(null); }
  }

  const field = (label: string, key: keyof typeof form, hint: string, type = "text") => (
    <label className="field">
      <span className="label-mono">{label}</span>
      <input className="input" type={type} value={form[key]} onChange={(e) => set(key, e.target.value)}
             onFocus={() => { if (String(key).includes("secret") && form[key] === SENTINEL) set(key, ""); }} />
      <span className="field__hint">{hint}</span>
    </label>
  );

  return (
    <div className="page page--wide">
      <div className="eyebrow">Connections · AI engine · Alerts</div>
      <div className="page__head">
        <div>
          <h2 className="page__title">Settings</h2>
          <p className="page__sub">SAP Integration Suite tenant credentials — encrypted at rest (AES-256-GCM)</p>
        </div>
        <span className={"pill " + (info?.configured ? "pill--ok" : "pill--warn")}>
          {info ? (info.configured ? `configured · ${info.mode}` : "not configured") : "…"}
        </span>
      </div>

      <section className="card panel" style={{ padding: 22 }}>
        <div className="label-mono" style={{ marginBottom: 16 }}>CPI Connection</div>
        <div className="form-grid">
          {field("Base URL *", "base_url", "Service Key → url")}
          {field("Token URL *", "token_url", "Service Key → tokenurl (append /oauth/token if missing)")}
          {field("Client ID *", "client_id", "Service Key → clientid")}
          {field("Client Secret *", "client_secret", "Encrypted at rest · never echoed back", "password")}
          {field("Web IDE URL", "web_ide_url", "Optional — enables click-to-open links")}
        </div>

        <div className="label-mono" style={{ margin: "22px 0 6px" }}>CPI Runtime <span style={{ color: "var(--text-faint)" }}>(optional)</span></div>
        <div className="field__hint" style={{ marginBottom: 14 }}>Only needed for Fix/Verify flows — leave blank to share the CPI Connection credentials.</div>
        <div className="form-grid">
          {field("RT Client ID", "rt_client_id", "Runtime Service Key → clientid")}
          {field("RT Client Secret", "rt_client_secret", "Runtime Service Key → clientsecret", "password")}
          {field("RT Token URL", "rt_token_url", "Runtime Service Key → tokenurl")}
          {field("RT Base URL", "rt_base_url", "Runtime host (not the design-time host)")}
        </div>

        <div className="page__actions" style={{ marginTop: 20 }}>
          <button className="btn btn--primary" onClick={onSave} disabled={busy !== null}>
            {busy === "save" ? "Saving…" : "Save credentials"}
          </button>
          <button className="btn" onClick={onTest} disabled={busy !== null}>
            {busy === "test" ? "Testing…" : "Test CPI connection"}
          </button>
          <button className="btn btn--ghost" onClick={() => onMode(info?.mode === "live" ? "demo" : "live")} disabled={busy !== null}>
            Switch to {info?.mode === "live" ? "demo" : "live"}
          </button>
        </div>

        {msg && <div className="note-line" style={{ color: "var(--rca-lime)" }}>{msg}</div>}
        {test && (
          <div className="note-line" style={{ color: test.ok ? "var(--status-success)" : "var(--status-failed)" }}>
            {test.ok ? "✓" : "✕"} [{test.mode}] {test.detail}
            {test.deployed_iflows != null && ` · deployed iFlows: ${test.deployed_iflows}`}
          </div>
        )}

        <div className="note-line" style={{ color: "var(--text-muted)" }}>
          Secrets are stored with AES-256-GCM using a per-install master key. They are never returned to the browser.
        </div>
      </section>

      <SourceCard kind="APIM" title="APIM — SAP API Management" defaultAuth="oauth" />
      <SourceCard kind="AEM" title="AEM — Advanced Event Mesh" defaultAuth="basic" />
      <EmailAlertsCard />
      <AiEngineCard />
    </div>
  );
}

function SourceCard({ kind, title, defaultAuth }: { kind: string; title: string; defaultAuth: string }) {
  const [info, setInfo] = useState<SourceInfo | null>(null);
  const [form, setForm] = useState({
    enabled: false, auth_type: defaultAuth, base_url: "", token_url: "",
    client_id: "", username: "", vpn: "", analytics_base_url: "", secret: SENTINEL,
  });
  const [test, setTest] = useState<SourceTestResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    const s = await getSource(kind);
    setInfo(s);
    setForm({ enabled: s.enabled, auth_type: s.auth_type, base_url: s.base_url, token_url: s.token_url,
      client_id: s.client_id, username: s.username, vpn: s.vpn, analytics_base_url: s.analytics_base_url,
      secret: s.secret_set ? SENTINEL : "" });
  }
  useEffect(() => { refresh(); }, []);
  function set<K extends keyof typeof form>(k: K, v: string | boolean) { setForm((f) => ({ ...f, [k]: v })); }

  async function onSave() {
    setBusy("save"); setMsg(null);
    try { setInfo(await saveSource(kind, form)); setMsg(form.enabled ? "Saved & enabled." : "Saved (disabled)."); }
    catch (e) { setMsg(e instanceof Error ? e.message : "Save failed"); } finally { setBusy(null); }
  }
  async function onTest() {
    setBusy("test"); setMsg(null); setTest(null);
    try {
      await saveSource(kind, form);
      const t = await testSource(kind);
      setTest(t);
      if (t.ok) {                             // connected -> auto-enable so it shows on Dashboard/Monitor
        const en = { ...form, enabled: true };
        setForm(en); setInfo(await saveSource(kind, en));
        setMsg("Connected & enabled — now shown on Dashboard and Monitor.");
      }
    } catch (e) { setMsg(e instanceof Error ? e.message : "Test failed"); } finally { setBusy(null); }
  }

  const isOauth = form.auth_type === "oauth";
  const isAem = kind === "AEM";
  return (
    <section className="card panel" style={{ padding: 22, marginTop: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <span className="label-mono">{title}</span>
        <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }} title="Include this source on Dashboard and Monitor">
          <input type="checkbox" checked={form.enabled} onChange={(e) => set("enabled", e.target.checked)} />
          <span className="label-mono" style={{ color: form.enabled ? "var(--status-success)" : "var(--text-muted)" }}>
            {form.enabled ? "enabled" : "enable"}
          </span>
        </label>
      </div>
      <div className="form-grid">
        <label className="field"><span className="label-mono">{isAem ? "SEMP Base URL" : "API Portal Base URL"}</span>
          <input className="input" value={form.base_url} placeholder={isAem ? "https://<host>.messaging.solace.cloud:943" : "https://<tenant>.apim...hana.ondemand.com"} onChange={(e) => set("base_url", e.target.value)} />
          <span className="field__hint">{isAem ? "SEMP v2 monitor host" : "API portal (apiportal-apiaccess)"}</span></label>
        <label className="field"><span className="label-mono">Auth type</span>
          <select className="input" value={form.auth_type} onChange={(e) => set("auth_type", e.target.value)}>
            <option value="oauth">OAuth (client credentials)</option>
            <option value="basic">Basic (user / password)</option>
          </select></label>
        {isAem && <label className="field"><span className="label-mono">Message VPN</span>
          <input className="input" value={form.vpn} placeholder="vpn name" onChange={(e) => set("vpn", e.target.value)} /></label>}
        {isOauth && <label className="field"><span className="label-mono">Token URL</span>
          <input className="input" value={form.token_url} placeholder="https://.../oauth/token" onChange={(e) => set("token_url", e.target.value)} /></label>}
        {isOauth && <label className="field"><span className="label-mono">Client ID</span>
          <input className="input" value={form.client_id} onChange={(e) => set("client_id", e.target.value)} /></label>}
        {!isOauth && <label className="field"><span className="label-mono">Username</span>
          <input className="input" value={form.username} onChange={(e) => set("username", e.target.value)} /></label>}
        <label className="field"><span className="label-mono">{isOauth ? "Client Secret" : "Password"}</span>
          <input className="input" type="password" value={form.secret} onFocus={() => { if (form.secret === SENTINEL) set("secret", ""); }} onChange={(e) => set("secret", e.target.value)} />
          <span className="field__hint">Encrypted at rest · never echoed back</span></label>
        {!isAem && <label className="field"><span className="label-mono">Analytics Base URL (optional)</span>
          <input className="input" value={form.analytics_base_url} placeholder="https://<tenant>.apimanagement...hana.ondemand.com" onChange={(e) => set("analytics_base_url", e.target.value)} />
          <span className="field__hint">AnalyticsService host — enables per-proxy traffic, errors &amp; latency</span></label>}
      </div>
      <div className="page__actions" style={{ marginTop: 20 }}>
        <button className="btn btn--primary" onClick={onSave} disabled={busy !== null}>{busy === "save" ? "Saving…" : "Save"}</button>
        <button className="btn" onClick={onTest} disabled={busy !== null}>{busy === "test" ? "Testing…" : `Test ${kind}`}</button>
      </div>
      {msg && <div className="note-line" style={{ color: "var(--rca-lime)" }}>{msg}</div>}
      {test && <div className="note-line" style={{ color: test.ok ? "var(--status-success)" : "var(--status-failed)" }}>{test.ok ? "✓" : "✕"} [{test.kind}] {test.detail}</div>}
      {info?.enabled && <div className="note-line" style={{ color: "var(--text-muted)" }}>When enabled, this source appears as a connected system on Dashboard and Monitor.</div>}
    </section>
  );
}

function EmailAlertsCard() {
  const [info, setInfo] = useState<EmailAlertsInfo | null>(null);
  const [form, setForm] = useState({ method: "rca", smtp_host: "", smtp_port: "", from_address: "", smtp_user: "", smtp_password: SENTINEL, recipients: "" });
  const [test, setTest] = useState<EmailTestResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    const e = await getEmailAlerts();
    setInfo(e);
    setForm({ method: e.method, smtp_host: e.smtp_host, smtp_port: e.smtp_port, from_address: e.from_address,
      smtp_user: e.smtp_user, smtp_password: e.password_set ? SENTINEL : "", recipients: e.recipients });
  }
  useEffect(() => { refresh(); }, []);
  function set<K extends keyof typeof form>(k: K, v: string) { setForm((f) => ({ ...f, [k]: v })); }

  async function onSave() {
    setBusy("save"); setMsg(null);
    try { setInfo(await saveEmailAlerts(form)); setMsg("Email alerts saved."); }
    catch (e) { setMsg(e instanceof Error ? e.message : "Save failed"); } finally { setBusy(null); }
  }
  async function onTest() {
    setBusy("test"); setMsg(null); setTest(null);
    try { setTest(await testEmailAlerts()); }
    catch (e) { setMsg(e instanceof Error ? e.message : "Test failed"); } finally { setBusy(null); }
  }

  const isSmtp = form.method === "smtp";
  return (
    <section className="card panel" style={{ padding: 22, marginTop: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <span className="label-mono">Email Alerts — monitor failure notifications</span>
        <span className={"pill " + (info?.configured ? "pill--ok" : "pill--warn")}>{info ? (info.configured ? "configured" : "not configured") : "…"}</span>
      </div>
      <div className="pill-row" style={{ marginBottom: 16 }}>
        <button className={"pill " + (form.method === "rca" ? "pill--ok" : "")} style={{ cursor: "pointer" }} onClick={() => set("method", "rca")}>RCA mail service (free)</button>
        <button className={"pill " + (isSmtp ? "pill--ok" : "")} style={{ cursor: "pointer" }} onClick={() => set("method", "smtp")}>My own SMTP server</button>
      </div>
      <div className="form-grid">
        <label className="field"><span className="label-mono">Alert recipients</span>
          <input className="input" value={form.recipients} placeholder="ops@realcore.al, ilrexho@outlook.com" onChange={(e) => set("recipients", e.target.value)} />
          <span className="field__hint">Comma-separated</span></label>
        {isSmtp && <label className="field"><span className="label-mono">SMTP Host</span><input className="input" value={form.smtp_host} placeholder="smtp.office365.com" onChange={(e) => set("smtp_host", e.target.value)} /></label>}
        {isSmtp && <label className="field"><span className="label-mono">SMTP Port</span><input className="input" value={form.smtp_port} placeholder="587" onChange={(e) => set("smtp_port", e.target.value)} /></label>}
        {isSmtp && <label className="field"><span className="label-mono">From Address</span><input className="input" value={form.from_address} placeholder="alerts@realcore.al" onChange={(e) => set("from_address", e.target.value)} /></label>}
        {isSmtp && <label className="field"><span className="label-mono">SMTP User</span><input className="input" value={form.smtp_user} onChange={(e) => set("smtp_user", e.target.value)} /></label>}
        {isSmtp && <label className="field"><span className="label-mono">SMTP Password</span><input className="input" type="password" value={form.smtp_password} onFocus={() => { if (form.smtp_password === SENTINEL) set("smtp_password", ""); }} onChange={(e) => set("smtp_password", e.target.value)} /><span className="field__hint">Encrypted at rest</span></label>}
      </div>
      <div className="page__actions" style={{ marginTop: 20 }}>
        <button className="btn btn--primary" onClick={onSave} disabled={busy !== null}>{busy === "save" ? "Saving…" : "Save email alerts"}</button>
        <button className="btn" onClick={onTest} disabled={busy !== null}>{busy === "test" ? "Testing…" : "Send test email"}</button>
      </div>
      {msg && <div className="note-line" style={{ color: "var(--rca-lime)" }}>{msg}</div>}
      {test && <div className="note-line" style={{ color: test.ok ? "var(--status-success)" : "var(--status-failed)" }}>{test.ok ? "✓" : "✕"} {test.detail}</div>}
    </section>
  );
}

function AiEngineCard() {
  const [info, setInfo] = useState<AiEngineInfo | null>(null);
  const [form, setForm] = useState({ provider: "stub", endpoint: "", model: "", api_key: SENTINEL });
  const [test, setTest] = useState<AiEngineTestResult | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    const a = await getAiEngine();
    setInfo(a);
    setForm({ provider: a.provider, endpoint: a.endpoint, model: a.model, api_key: a.key_set ? SENTINEL : "" });
  }
  useEffect(() => { refresh(); }, []);
  function set<K extends keyof typeof form>(k: K, v: string) { setForm((f) => ({ ...f, [k]: v })); }

  const needsModel = form.provider !== "stub" && !form.model.trim();
  const examples = MODEL_EXAMPLES[form.provider] ?? "";
  // best-effort: warn if the key prefix clearly belongs to another provider
  const expectedPrefix = KEY_PREFIX[form.provider];
  const keyLooksWrong = !!expectedPrefix && form.api_key !== SENTINEL && form.api_key !== "" &&
    !form.api_key.startsWith(expectedPrefix) &&
    Object.values(KEY_PREFIX).some((p) => form.api_key.startsWith(p));

  async function onSave() {
    if (needsModel) { setMsg(`Enter the Model string first — for ${form.provider} use: ${examples}.`); return; }
    setBusy("save"); setMsg(null);
    try { setInfo(await saveAiEngine(form)); setMsg("AI engine saved."); }
    catch (e) { setMsg(e instanceof Error ? e.message : "Save failed"); } finally { setBusy(null); }
  }
  async function onTest() {
    if (needsModel) { setMsg(`Enter the Model string first — for ${form.provider} use: ${examples}.`); return; }
    setBusy("test"); setMsg(null); setTest(null);
    try { setTest(await testAiEngine()); }
    catch (e) { setMsg(e instanceof Error ? e.message : "Test failed"); } finally { setBusy(null); }
  }
  async function onListModels() {
    setBusy("models"); setMsg(null); setModels([]);
    try {
      await saveAiEngine(form);              // ensure the current key/provider is stored
      const r = await listAiModels();
      setModels(r.models);
      setMsg(r.models.length ? `${r.detail} — click one to use it.` : r.detail);
    } catch (e) { setMsg(e instanceof Error ? e.message : "List failed"); } finally { setBusy(null); }
  }

  const isStub = form.provider === "stub";
  function chooseIncluded() { set("provider", "stub"); }
  function chooseByok() { if (form.provider === "stub") set("provider", "openai"); }
  return (
    <section className="card panel" style={{ padding: 22, marginTop: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <span className="label-mono">AI Engine — which AI powers Generate, Explain, Fix and Chat</span>
        <span className={"pill " + (info?.active ? "pill--ok" : "pill--warn")}>
          {info ? (info.active ? `active · ${info.provider}` : "RCA Copilot AI") : "…"}
        </span>
      </div>

      {/* Two assistance options */}
      <div className="opt-grid">
        <button type="button" className={"opt-card" + (isStub ? " opt-card--active" : "")} onClick={chooseIncluded}>
          <div className="opt-card__head">
            <span className="opt-radio">{isStub ? "◉" : "○"}</span>
            <span className="opt-card__title">RCA Copilot AI</span>
            <span className="pill pill--ok" style={{ marginLeft: 8 }}>included</span>
          </div>
          <div className="opt-card__desc">Runs on our managed AI. Zero setup — usage included with your account during beta.</div>
        </button>
        <button type="button" className={"opt-card" + (!isStub ? " opt-card--active" : "")} onClick={chooseByok}>
          <div className="opt-card__head">
            <span className="opt-radio">{!isStub ? "◉" : "○"}</span>
            <span className="opt-card__title">My own AI key (BYOK)</span>
          </div>
          <div className="opt-card__desc">Use your OpenAI, Anthropic, Perplexity, Gemini or DeepSeek account — usage billed to your key, prompts never leave your provider.</div>
        </button>
      </div>

      <div className="form-grid" style={{ marginTop: 18 }}>
        {!isStub && (
          <label className="field">
            <span className="label-mono">Provider</span>
            <select className="input" value={form.provider} onChange={(e) => set("provider", e.target.value)}>
              {PROVIDERS.filter((p) => p.id !== "stub").map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
            <span className="field__hint">BYOK — prompts never leave your provider</span>
          </label>
        )}
        {!isStub && (
          <label className="field">
            <span className="label-mono">Model *</span>
            <input className="input" value={form.model}
              style={needsModel ? { borderColor: "var(--status-warn)" } : undefined}
              placeholder={examples}
              onChange={(e) => set("model", e.target.value)} />
            <span className="field__hint">Required — a {PROVIDERS.find((p) => p.id === form.provider)?.label} model: {examples}</span>
          </label>
        )}
        {!isStub && (
          <label className="field">
            <span className="label-mono">API Key</span>
            <input className="input" type="password" value={form.api_key}
              style={keyLooksWrong ? { borderColor: "var(--status-warn)" } : undefined}
              onFocus={() => { if (form.api_key === SENTINEL) set("api_key", ""); }}
              onChange={(e) => set("api_key", e.target.value)} />
            <span className="field__hint" style={keyLooksWrong ? { color: "var(--status-warn)" } : undefined}>
              {keyLooksWrong
                ? `This key looks like it belongs to another provider — ${form.provider} keys start with "${expectedPrefix}".`
                : "Encrypted at rest · never echoed back"}
            </span>
          </label>
        )}
        {!isStub && form.provider === "perplexity" && (
          <label className="field">
            <span className="label-mono">Endpoint (optional)</span>
            <input className="input" value={form.endpoint} placeholder="https://api.perplexity.ai" onChange={(e) => set("endpoint", e.target.value)} />
            <span className="field__hint">Leave blank for the default Perplexity endpoint</span>
          </label>
        )}
      </div>
      <div className="page__actions" style={{ marginTop: 20 }}>
        <button className="btn btn--primary" onClick={onSave} disabled={busy !== null}>{busy === "save" ? "Saving…" : "Save AI engine"}</button>
        <button className="btn" onClick={onTest} disabled={busy !== null}>{busy === "test" ? "Testing…" : "Test AI engine"}</button>
        {!isStub && <button className="btn btn--ghost" onClick={onListModels} disabled={busy !== null}>{busy === "models" ? "Fetching…" : "List models"}</button>}
      </div>
      {models.length > 0 && (
        <div className="pill-row" style={{ marginTop: 14 }}>
          {models.map((m) => (
            <button key={m} className={"pill " + (m === form.model ? "pill--ok" : "")} style={{ cursor: "pointer" }} onClick={() => set("model", m)}>{m}</button>
          ))}
        </div>
      )}
      {msg && <div className="note-line" style={{ color: "var(--rca-lime)" }}>{msg}</div>}
      {test && (
        <div className="note-line" style={{ color: test.ok ? "var(--status-success)" : "var(--status-failed)" }}>
          {test.ok ? "✓" : "✕"} [{test.provider}] {test.detail}
        </div>
      )}
    </section>
  );
}
