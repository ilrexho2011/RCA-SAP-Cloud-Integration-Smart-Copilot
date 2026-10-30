/* Typed client for the RCA Smart Copilot backend. */

/* Format any tenant timestamp (OData /Date(ms)/, ISO, epoch) as dd-mm-yyyy hh:mm:ss. */
export function formatTimestamp(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined || raw === "") return "—";
  let d: Date;
  const s = String(raw);
  const odata = /\/Date\((-?\d+)([+-]\d+)?\)\//.exec(s);
  if (odata) d = new Date(Number(odata[1]));
  else if (/^\d{10,}$/.test(s)) d = new Date(Number(s) * (s.length <= 10 ? 1000 : 1));
  else d = new Date(s);
  if (isNaN(d.getTime())) return s;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getDate())}-${p(d.getMonth() + 1)}-${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/* ---- Auth token + fetch wrapper (injects Bearer, handles 401) ---- */
const TOKEN_KEY = "rca_token";
export function getToken(): string { return localStorage.getItem(TOKEN_KEY) || ""; }
export function setToken(t: string): void { localStorage.setItem(TOKEN_KEY, t); }
export function clearToken(): void { localStorage.removeItem(TOKEN_KEY); }

const _rawFetch = globalThis.fetch.bind(globalThis);
async function jfetch(url: string, opts: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string> | undefined) };
  const t = getToken();
  if (t) headers["Authorization"] = "Bearer " + t;
  const res = await _rawFetch(url, { ...opts, headers });
  if (res.status === 401) { clearToken(); window.dispatchEvent(new Event("rca-unauth")); }
  return res;
}

export interface AuthResult { token: string; email: string; role: string; tenant_id: string; }
async function authCall(path: string, email: string, password: string): Promise<AuthResult> {
  const res = await jfetch(`/api/auth/${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? `${path} failed`);
  setToken(data.token);
  return data;
}
export const login = (email: string, password: string) => authCall("login", email, password);
export const register = (email: string, password: string) => authCall("register", email, password);
export function logout(): void { clearToken(); }
export async function me(): Promise<{ email: string; role: string; tenant_id: string }> {
  const res = await jfetch("/api/auth/me");
  if (!res.ok) throw new Error("unauthorized");
  return res.json();
}

export interface KpiCard { key: string; label: string; value: number; tone: string; note: string; }
export interface SystemMetric { label: string; value: number; tone: string; }
export interface ConnectedSystem {
  name: string; sap_sid: string; kind: string; live: boolean;
  success: number; failed: number; retry: number; total: number; deployed_iflows: number;
  metrics: SystemMetric[]; note: string; analytics?: ApimAnalytics | null;
}
export interface FailedMessage {
  interface: string; exception: string; status: string; error: string; timestamp: string | null;
}
export interface MonitoringOverview {
  source: "live" | "demo";
  sources_connected: number;
  kpis: KpiCard[];
  systems: ConnectedSystem[];
  failed_messages: FailedMessage[];
  error?: string | null;
}

export async function getMonitoringOverview(): Promise<MonitoringOverview> {
  const res = await jfetch("/api/monitoring/overview");
  if (!res.ok) throw new Error(`overview failed: ${res.status}`);
  return res.json();
}

export interface ConnectionInfo {
  configured: boolean; mode: "live" | "demo";
  base_url: string; token_url: string; client_id: string; web_ide_url: string; secret_set: boolean;
  rt_base_url: string; rt_token_url: string; rt_client_id: string; rt_secret_set: boolean;
}
export interface ConnectionUpdate {
  base_url: string; token_url: string; client_id: string; web_ide_url: string;
  client_secret: string; mode: string;
  rt_base_url: string; rt_token_url: string; rt_client_id: string; rt_client_secret: string;
}

export interface EmailAlertsInfo {
  configured: boolean; method: string; smtp_host: string; smtp_port: string;
  from_address: string; smtp_user: string; recipients: string; password_set: boolean;
}
export interface EmailAlertsUpdate {
  method: string; smtp_host: string; smtp_port: string; from_address: string;
  smtp_user: string; smtp_password: string; recipients: string;
}
export interface EmailTestResult { ok: boolean; detail: string; }

export async function getEmailAlerts(): Promise<EmailAlertsInfo> {
  const res = await jfetch("/api/settings/email");
  if (!res.ok) throw new Error(`get email failed: ${res.status}`);
  return res.json();
}
export async function saveEmailAlerts(body: EmailAlertsUpdate): Promise<EmailAlertsInfo> {
  const res = await jfetch("/api/settings/email", {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`save email failed: ${res.status}`);
  return res.json();
}
export async function testEmailAlerts(): Promise<EmailTestResult> {
  const res = await jfetch("/api/settings/email/test", { method: "POST" });
  if (!res.ok) throw new Error(`test email failed: ${res.status}`);
  return res.json();
}

/* ---- APIM / AEM sources ---- */
export interface SourceInfo {
  kind: string; enabled: boolean; auth_type: string; base_url: string; token_url: string;
  client_id: string; username: string; vpn: string; analytics_base_url: string; secret_set: boolean;
}
export interface SourceUpdate {
  enabled: boolean; auth_type: string; base_url: string; token_url: string;
  client_id: string; username: string; vpn: string; analytics_base_url: string; secret: string;
}
export interface SourceTestResult { ok: boolean; kind: string; detail: string; }

export async function getSource(kind: string): Promise<SourceInfo> {
  const res = await jfetch(`/api/settings/source/${kind}`);
  if (!res.ok) throw new Error(`get source failed: ${res.status}`);
  return res.json();
}
export async function saveSource(kind: string, body: SourceUpdate): Promise<SourceInfo> {
  const res = await jfetch(`/api/settings/source/${kind}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`save source failed: ${res.status}`);
  return res.json();
}
export async function testSource(kind: string): Promise<SourceTestResult> {
  const res = await jfetch(`/api/settings/source/${kind}/test`, { method: "POST" });
  if (!res.ok) throw new Error(`test source failed: ${res.status}`);
  return res.json();
}
export interface ConnectionTestResult {
  ok: boolean; mode: string; detail: string; deployed_iflows: number | null;
}

export async function getConnection(): Promise<ConnectionInfo> {
  const res = await jfetch("/api/settings/connection");
  if (!res.ok) throw new Error(`get connection failed: ${res.status}`);
  return res.json();
}

export async function saveConnection(body: ConnectionUpdate): Promise<ConnectionInfo> {
  const res = await jfetch("/api/settings/connection", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`save failed: ${res.status}`);
  return res.json();
}

export async function testConnection(): Promise<ConnectionTestResult> {
  const res = await jfetch("/api/settings/connection/test", { method: "POST" });
  if (!res.ok) throw new Error(`test failed: ${res.status}`);
  return res.json();
}

export async function switchMode(mode: "live" | "demo"): Promise<ConnectionInfo> {
  const res = await jfetch(`/api/settings/connection/mode/${mode}`, { method: "POST" });
  if (!res.ok) throw new Error(`switch failed: ${res.status}`);
  return res.json();
}

/* ---- Monitor (watch / ask / queues) ---- */
export interface MonitorFlow { id: string; name: string; status: string; watched: boolean; }
export interface AskAnswer { question: string; answer: string; data: Record<string, unknown>; evaluated: boolean; source: string; }
export interface QueueHealth { name: string; depth: number; capacity: number; stuck: number; retry: number; state: string; access?: string; }
export interface DataStore { name: string; iflow: string; type: string; entries: number; overdue: number; }
export interface QueuesOverview {
  kpis: SystemMetric[];
  queues: QueueHealth[];
  datastores: DataStore[];
  error?: string | null;
}
export async function getQueuesOverview(): Promise<QueuesOverview> {
  const res = await jfetch("/api/monitor/queues-overview");
  if (!res.ok) throw new Error(`queues overview failed: ${res.status}`);
  return res.json();
}

export async function getMonitorFlows(): Promise<MonitorFlow[]> {
  const res = await jfetch("/api/monitor/flows");
  if (!res.ok) throw new Error(`flows failed: ${res.status}`);
  return res.json();
}
export async function watchFlow(id: string): Promise<void> {
  await jfetch(`/api/monitor/watch/${encodeURIComponent(id)}`, { method: "POST" });
}
export async function unwatchFlow(id: string): Promise<void> {
  await jfetch(`/api/monitor/watch/${encodeURIComponent(id)}`, { method: "DELETE" });
}
export async function getQueues(): Promise<QueueHealth[]> {
  const res = await jfetch("/api/monitor/queues");
  if (!res.ok) throw new Error(`queues failed: ${res.status}`);
  return res.json();
}
export async function askMonitoring(question: string): Promise<AskAnswer> {
  const res = await jfetch("/api/monitor/ask", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(`ask failed: ${res.status}`);
  return res.json();
}
export interface ApimAnalytics {
  integrations_apis: { total: number; started: number; starting: number; stopping: number; error: number };
  proxy_traffic: { total_calls: number; success: number; failed: number };
  proxy_errors: { total: number; rows: { name: string; count: number }[] };
  quality: { policy_faults: number; avg_latency_ms: number; error_rate: number };
  api_proxy_breakdown: { name: string; total: number; success: number; failed: number }[];
  api_providers: { name: string; host: string; proxies: number }[];
  key_value_maps: { name: string; encrypted: boolean; entries: number }[];
  cards?: Record<string, number>;
  _source?: string;
}
export interface SystemDetail { kind: string; columns: string[]; items: Record<string, unknown>[]; error: string | null; analytics?: ApimAnalytics; }
export async function getSystemDetail(kind: string): Promise<SystemDetail> {
  const res = await jfetch(`/api/monitor/system/${kind}`);
  if (!res.ok) throw new Error(`system detail failed: ${res.status}`);
  return res.json();
}

/* ---- AI Assistant ---- */
export interface ChatMessage { role: "user" | "assistant"; content: string; }
export async function assistantChat(messages: ChatMessage[]): Promise<{ reply: string; provider?: string }> {
  const res = await jfetch("/api/assistant/chat", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages }),
  });
  if (!res.ok) throw new Error(`assistant failed: ${res.status}`);
  return res.json();
}

/* ---- Knowledge Base generator ---- */
export interface KbDoc { filename: string; kind: string; content: string; }
export interface KbReadiness {
  score: number; status: string; note?: string;
  documents: { file_name: string; score: number; status: string; issues: number }[];
}
export interface KbResult {
  manifest: { package_id: string; run_id: string; source_system: string; generated_at: string; scope: string; counts: Record<string, number>; files: string[] };
  readiness: KbReadiness;
  docs: KbDoc[];
}
export async function kbGenerate(scope: string): Promise<KbResult> {
  const res = await jfetch("/api/kb/generate", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope }),
  });
  if (!res.ok) throw new Error(`kb generate failed: ${res.status}`);
  return res.json();
}
export async function kbDownload(): Promise<void> {
  const res = await jfetch("/api/kb/download");
  if (!res.ok) throw new Error(`download failed: ${res.status}`);
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  const name = /filename="?([^"]+)"?/.exec(cd)?.[1] || "rca_kb.zip";
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = name; a.click();
  URL.revokeObjectURL(a.href);
}

/* ---- AI engine (BYOK) ---- */
export interface AiEngineInfo { provider: string; endpoint: string; model: string; key_set: boolean; active: boolean; }
export interface AiEngineUpdate { provider: string; endpoint: string; model: string; api_key: string; }
export interface AiEngineTestResult { ok: boolean; provider: string; detail: string; }

export async function getAiEngine(): Promise<AiEngineInfo> {
  const res = await jfetch("/api/settings/ai-engine");
  if (!res.ok) throw new Error(`get ai-engine failed: ${res.status}`);
  return res.json();
}
export async function saveAiEngine(body: AiEngineUpdate): Promise<AiEngineInfo> {
  const res = await jfetch("/api/settings/ai-engine", {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`save ai-engine failed: ${res.status}`);
  return res.json();
}
export async function testAiEngine(): Promise<AiEngineTestResult> {
  const res = await jfetch("/api/settings/ai-engine/test", { method: "POST" });
  if (!res.ok) throw new Error(`test ai-engine failed: ${res.status}`);
  return res.json();
}
export interface ModelList { provider: string; models: string[]; detail: string; }
export async function listAiModels(): Promise<ModelList> {
  const res = await jfetch("/api/settings/ai-engine/models");
  if (!res.ok) throw new Error(`list models failed: ${res.status}`);
  return res.json();
}

/* ---- Groovy ---- */
export interface GroovyResult {
  steps: { state: string; label: string; status: string; detail: string }[];
  script: string;
  validation: { ok: boolean; checks: { name: string; passed: boolean; detail: string }[] };
}
export async function generateGroovy(description: string): Promise<GroovyResult> {
  const res = await jfetch("/api/groovy/generate", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ description }),
  });
  if (!res.ok) throw new Error(`groovy failed: ${res.status}`);
  return res.json();
}

/* ---- iFlows / Explain ---- */
export interface Package { id: string; name: string; vendor: string; }
export interface IflowItem { id: string; name: string; version: string; }
export interface ExplainSections {
  what_it_does: string;
  trigger: string;
  step_by_step: string[];
  error_handling: string[];
  notes: string[];
}
export interface ExplainScript { name: string; points: string[]; }
export interface ExplainResult {
  source: string;
  facts: {
    name: string; sender_adapter: string; receiver_adapter: string;
    step_count: number; steps: string[]; has_error_handling: boolean;
    participants: { name: string; type: string }[];
  };
  summary: string;
  risks: string[];
  sections?: ExplainSections | null;
  scripts?: ExplainScript[];
}

export async function getPackages(): Promise<Package[]> {
  const res = await jfetch("/api/iflows/packages");
  if (!res.ok) { const d = await res.json().catch(() => null); throw new Error(d?.detail || `packages failed: ${res.status}`); }
  return res.json();
}
export async function getPackageIflows(pkg: string): Promise<IflowItem[]> {
  const res = await jfetch(`/api/iflows/packages/${encodeURIComponent(pkg)}/iflows`);
  if (!res.ok) throw new Error(`iflows failed: ${res.status}`);
  return res.json();
}
export async function explainZip(file: File): Promise<ExplainResult> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await jfetch("/api/iflows/explain-zip", { method: "POST", body: fd });
  if (!res.ok) throw new Error(`explain failed: ${res.status}`);
  return res.json();
}
export async function explainTenant(pkg: string, iflow: string): Promise<ExplainResult> {
  const res = await jfetch(`/api/iflows/explain/${encodeURIComponent(pkg)}/${encodeURIComponent(iflow)}`, { method: "POST" });
  if (!res.ok) throw new Error(`explain failed: ${res.status}`);
  return res.json();
}
export async function getRuntimeStatus(): Promise<Record<string, string>> {
  const res = await jfetch("/api/iflows/runtime-status");
  if (!res.ok) return {};
  return res.json();
}

/* ---- Generate / orchestrator ---- */
export interface RunStep { state: string; label: string; status: string; detail: string; payload?: Record<string, unknown> | null; }
export interface RunView {
  run_id: string; status: string; state: string; steps: RunStep[];
  classification: Record<string, unknown> | null;
  citations: { doc_id: string; title: string }[];
  brief: { summary?: string; steps?: string[]; error_handling?: string; security?: string; citations?: unknown[] } | null;
  artifact: string | null;
  validation: { ok: boolean; checks: { name: string; passed: boolean; detail: string }[] } | null;
  score: { total: number; threshold: number; passed: boolean; status: string; criteria: { name: string; weight: number; passed: boolean }[] } | null;
  attempts: number;
}
export interface Attachment { name: string; kind: string; content: string; }
export interface GenerateRequest {
  description: string; iflow_id: string; iflow_name: string; package: string;
  sample_input?: string; sample_output?: string; quick?: boolean; attachments?: Attachment[];
}

export async function generateIflow(body: GenerateRequest): Promise<RunView> {
  const res = await jfetch("/api/generate/iflow", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `generate failed: ${res.status}`;
    try { const j = await res.json(); if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* keep status */ }
    throw new Error(detail);
  }
  return res.json();
}
export async function approveRun(runId: string): Promise<RunView> {
  const res = await jfetch(`/api/generate/runs/${runId}/approve`, { method: "POST" });
  if (!res.ok) throw new Error(`approve failed: ${res.status}`);
  return res.json();
}
export async function reviseRun(runId: string, feedback: string): Promise<RunView> {
  const res = await jfetch(`/api/generate/runs/${runId}/revise`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ feedback }),
  });
  if (!res.ok) throw new Error(`revise failed: ${res.status}`);
  return res.json();
}
export async function deployRun(runId: string): Promise<RunView> {
  const res = await jfetch(`/api/generate/runs/${runId}/deploy`, { method: "POST" });
  if (!res.ok) {
    let detail = `deploy failed: ${res.status}`;
    try { const j = await res.json(); if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* keep status */ }
    throw new Error(detail);
  }
  return res.json();
}
