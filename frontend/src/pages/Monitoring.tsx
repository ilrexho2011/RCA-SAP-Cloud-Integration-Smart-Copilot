/* Monitor — control room: KPIs, Ask your monitoring, watch list, JMS queues.
   Data from /api/monitoring/overview and /api/monitor/*. */
import { useEffect, useState, type ReactNode } from "react";
import {
  getMonitoringOverview, getMonitorFlows, watchFlow, unwatchFlow, getQueuesOverview, askMonitoring,
  getSystemDetail, explainTenant,
  type MonitoringOverview, type MonitorFlow, type AskAnswer,
  type SystemDetail, type ExplainResult, type ApimAnalytics, type QueuesOverview,
} from "../api";

const SUGGESTED = [
  "How many flows failed this week?",
  "Which flows are failing regularly?",
  "How many messages were processed today?",
  "How many iFlows are deployed?",
  "Which flow is slowest this week?",
  "Which flows haven't run in 30 days?",
];

/* Format a timestamp as dd-mm-yyyy hh:mm:ss. Accepts SAP OData /Date(ms)/,
   ISO strings, or epoch millis; returns "—" when empty and the raw value if
   it can't be parsed. */
function fmtDateTime(raw?: string | null): string {
  if (!raw) return "—";
  let ms: number | null = null;
  const m = /\/Date\((\d+)([+-]\d+)?\)\//.exec(raw);
  if (m) ms = parseInt(m[1], 10);
  else if (/^\d{10,}$/.test(raw)) ms = parseInt(raw, 10);
  else { const d = Date.parse(raw); if (!Number.isNaN(d)) ms = d; }
  if (ms === null) return raw;
  const d = new Date(ms);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getDate())}-${p(d.getMonth() + 1)}-${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

export default function Monitor() {
  const [data, setData] = useState<MonitoringOverview | null>(null);
  const [flows, setFlows] = useState<MonitorFlow[]>([]);
  const [queuesOv, setQueuesOv] = useState<QueuesOverview | null>(null);
  const [answer, setAnswer] = useState<AskAnswer | null>(null);
  const [question, setQuestion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [asking, setAsking] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggleSys(kind: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(kind) ? next.delete(kind) : next.add(kind);
      return next;
    });
  }

  async function load() {
    setLoading(true); setError(null);
    try {
      const [ov, fl, q] = await Promise.all([
        getMonitoringOverview(), getMonitorFlows().catch(() => []),
        getQueuesOverview().catch(() => null),
      ]);
      setData(ov); setFlows(fl); setQueuesOv(q);
    } catch (e) { setError(e instanceof Error ? e.message : "Failed to load"); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function onAsk(qtext?: string) {
    const q = qtext ?? question; if (!q) return;
    setQuestion(q); setAsking(true); setAnswer(null);
    try { setAnswer(await askMonitoring(q)); }
    catch (e) { setError(e instanceof Error ? e.message : "Ask failed"); } finally { setAsking(false); }
  }
  async function toggleWatch(f: MonitorFlow) {
    if (f.watched) await unwatchFlow(f.id); else await watchFlow(f.id);
    setFlows(await getMonitorFlows());
  }

  const source = data?.source;
  const watched = flows.filter((f) => f.watched);

  return (
    <div className="page page--wide">
      <div className="eyebrow">AI Copilot for SAP Cloud Integration</div>
      <div className="page__head">
        <div>
          <h2 className="page__title">Monitor</h2>
          <p className="page__sub">Generation and management of integrations with AI Assistance — SAP CPI, API Management (APIM) and AEM signals, live and local MPL.</p>
        </div>
        <div className="page__actions">
          <button className="btn" onClick={load} disabled={loading}>↻ Refresh sources</button>
          <span className={"pill " + (source === "live" ? "pill--ok" : "pill--warn")}>
            {loading ? "Loading…" : source === "live" ? `${data?.sources_connected} source connected` : "demo data"}
          </span>
        </div>
      </div>

      {error && <div className="card" style={{ padding: 16, marginTop: 20, color: "var(--status-failed)" }}>{error}</div>}
      {data?.error && (
        <div className="card" style={{ padding: 16, marginTop: 20, color: "var(--status-warn)", borderColor: "rgba(242,193,78,.4)" }}>
          ⚠ Live connection issue: {data.error}
        </div>
      )}

      <div className="kpi-grid">
        {(data?.kpis ?? []).map((k) => (
          <div className="card kpi" key={k.key}>
            <div className="label-mono">{k.label}</div>
            <div className={`kpi-value kpi-value--${k.tone}`}>{loading ? "—" : k.value}</div>
            <div className="kpi__note">{k.note}</div>
          </div>
        ))}
      </div>

      {/* Connected systems + recent failures */}
      <section className="card panel">
        <div className="panel__head"><span className="label-mono">Connected systems — SAP CPI · APIM · AEM</span></div>
        {(data?.systems ?? []).map((s) => {
          const open = expanded.has(s.kind);
          return (
          <div className="sys" key={s.kind}>
            <div className="sys__head sys__head--btn" onClick={() => toggleSys(s.kind)}>
              <div>
                <span className="sys__chev">{open ? "▾" : "▸"}</span>
                <span className="pill pill--info" style={{ marginRight: 10 }}>{s.kind}</span>
                <span className="sys__name">{s.name}</span>
                <span className="label-mono" style={{ marginLeft: 10 }}>sap_sid={s.sap_sid}</span>
              </div>
              <span className={"pill " + (s.live && !s.note ? "pill--ok" : "pill--warn")}>{s.live && !s.note ? "Live" : s.note ? (s.note.startsWith("Configured") ? "Disabled" : "Error") : "Demo"}</span>
            </div>
            {s.note && <div className="note-line" style={{ color: "var(--status-warn)", marginTop: 0 }}>⚠ {s.note}</div>}
            {s.metrics.length > 0 && (
              <div className="sys__kpis">
                {s.metrics.map((m) => (
                  <div className="card sys__kpi" key={m.label}>
                    <div className="label-mono">{m.label}</div>
                    <div className={`kpi-value kpi-value--${m.tone}`} style={{ fontSize: 26 }}>{m.value}</div>
                  </div>
                ))}
              </div>
            )}
            {/* SAP CPI: recent failed messages, directly below the CPI indicator gadgets */}
            {s.kind === "CPI" && (
              <div style={{ marginTop: 14 }}>
                <div className="panel__subhead label-mono" style={{ marginTop: 0 }}>Recent failed messages (24h · last errors)</div>
                <table className="tbl">
                  <thead><tr><th>Interface</th><th>Exception</th><th>Status</th><th>Error</th><th style={{ textAlign: "right" }}>Date / Time</th></tr></thead>
                  <tbody>
                    {(data?.failed_messages ?? []).map((r, i) => (
                      <tr key={i}>
                        <td className="mono">{r.interface}</td>
                        <td className="mono">{r.exception}</td>
                        <td><span className="status-tag">{r.status}</span></td>
                        <td style={{ color: "var(--text-secondary)" }}>{r.error}</td>
                        <td className="mono" style={{ textAlign: "right" }}>{fmtDateTime(r.timestamp)}</td>
                      </tr>
                    ))}
                    {data && data.failed_messages.length === 0 && (
                      <tr><td colSpan={5} style={{ color: "var(--text-muted)" }}>No failed messages in the current window.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
            {/* APIM: the six monitoring zones, always shown below the indicator gadgets */}
            {s.kind === "APIM" && s.analytics && (
              <div style={{ marginTop: 14 }}><ApimZones a={s.analytics} /></div>
            )}
            {open && (
              <div className="sys__detail">
                <SystemDrill kind={s.kind} />
              </div>
            )}
          </div>
        );})}
      </section>

      {/* Ask your monitoring — below connected systems */}
      <section className="card panel" style={{ marginTop: 22, padding: 20 }}>
        <div className="label-mono" style={{ marginBottom: 12 }}>✦ Ask your monitoring</div>
        <div className="page__actions">
          <input className="input" style={{ flex: 1 }} value={question}
            placeholder="e.g. how many flows failed this week? which flows are failing regularly?"
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") onAsk(); }} />
          <button className="btn btn--primary" onClick={() => onAsk()} disabled={asking || !question}>{asking ? "…" : "Ask"}</button>
        </div>
        <div className="pill-row" style={{ marginTop: 12 }}>
          {SUGGESTED.map((s) => (
            <button key={s} className="pill" style={{ cursor: "pointer" }} onClick={() => onAsk(s)}>{s}</button>
          ))}
        </div>
        {answer && (
          <div className="note-line" style={{ color: answer.evaluated ? "var(--text-primary)" : "var(--status-warn)", fontSize: 13 }}>
            {answer.evaluated ? "→ " : "⚠ "}{answer.answer}
          </div>
        )}
      </section>

      {/* Selected iFlows — health gadgets (mirrors the Dashboard selection / watch list) */}
      <div className="section-head">
        <span className="label-mono">Selected iFlows — health {watched.length > 0 && <span style={{ color: "var(--rca-lime)" }}>({watched.length})</span>}</span>
      </div>
      <div className="autogrid autogrid--health" style={{ marginTop: 12 }}>
        {watched.map((f) => {
          const ok = ["STARTED", "STARTING", "DEPLOYED"].includes((f.status || "").toUpperCase());
          return (
            <div className="card health-card" key={f.id}>
              <div className="health-card__head">
                <span className={"hdot " + (ok ? "hdot--ok" : "hdot--warn")} />
                <span className="label-mono">{ok ? "Healthy" : "Check"}</span>
                <span className="label-mono" style={{ marginLeft: "auto", color: "var(--text-faint)" }}>no data today</span>
              </div>
              <div className="health-card__name">{f.name}</div>
              <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>{f.status} · no traffic yet today</div>
            </div>
          );
        })}
        {watched.length === 0 && (
          <div className="card" style={{ padding: 18, color: "var(--text-muted)", gridColumn: "1 / -1" }}>
            No iFlows selected yet — tick flows in the watch list below (or on the Dashboard) to follow their health here.
          </div>
        )}
      </div>

      {/* Watch list */}
      <section className="card panel" style={{ padding: 18, marginTop: 22 }}>
        <div className="label-mono" style={{ marginBottom: 6 }}>Watch list <span style={{ color: "var(--rca-lime)" }}>({watched.length})</span></div>
        <div className="field__hint" style={{ marginBottom: 12 }}>Click a flow to watch it. Watched flows alert on failure.</div>
        <div className="iflow-list" style={{ maxHeight: 300, overflowY: "auto" }}>
          {flows.slice(0, 40).map((f) => (
            <div className="iflow-row" key={f.id}>
              <div><div className="iflow-row__name">{f.name}</div><div className="mono" style={{ fontSize: 11 }}>{f.status}</div></div>
              <button className={"btn " + (f.watched ? "btn--primary" : "btn--ghost")} onClick={() => toggleWatch(f)}>
                {f.watched ? "★ Watching" : "☆ Watch"}
              </button>
            </div>
          ))}
          {flows.length === 0 && <div style={{ color: "var(--text-muted)" }}>No flows available (connect a tenant).</div>}
        </div>
      </section>

      {/* Message Queues & Data Stores — indicators + both tables */}
      <QueuesDatastores ov={queuesOv} />
    </div>
  );
}

function QueuesDatastores({ ov }: { ov: QueuesOverview | null }) {
  const queues = ov?.queues ?? [];
  const stores = ov?.datastores ?? [];
  const tablesGrid = {
    display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 14, marginTop: 14,
  } as const;
  return (
    <section className="card panel" style={{ padding: 18, marginTop: 22 }}>
      <div className="label-mono" style={{ marginBottom: 6 }}>Message queues (JMS) &amp; data stores</div>
      <div className="field__hint" style={{ marginBottom: 12 }}>Queue depth, stuck messages, retry backlog and Data Store entries (overdue highlighted).</div>

      {(ov?.kpis?.length ?? 0) > 0 && (
        <div className="sys__kpis">
          {ov!.kpis.map((m) => (
            <div className="card sys__kpi" key={m.label}>
              <div className="label-mono">{m.label}</div>
              <div className={`kpi-value kpi-value--${m.tone}`} style={{ fontSize: 26 }}>{m.value}</div>
            </div>
          ))}
        </div>
      )}

      <div style={tablesGrid}>
        {/* Queues */}
        <div>
          <div className="label-mono" style={{ marginBottom: 8 }}>JMS queues</div>
          <table className="tbl tbl--zone">
            <thead><tr><th>Queue</th><th style={{ width: 96 }}>Access</th><th style={{ textAlign: "right", width: 70 }}>Depth</th><th style={{ textAlign: "right", width: 52 }}>Stuck</th><th style={{ textAlign: "right", width: 52 }}>Retry</th><th style={{ width: 88 }}>State</th></tr></thead>
            <tbody>
              {queues.map((q) => (
                <tr key={q.name}>
                  <td className="mono">{q.name}</td>
                  <td className="mono" style={{ color: "var(--text-secondary)" }}>{q.access || "—"}</td>
                  <td className="mono" style={{ textAlign: "right" }}>{q.depth}/{q.capacity}</td>
                  <td className="mono" style={{ textAlign: "right", color: q.stuck ? "var(--status-failed)" : undefined }}>{q.stuck}</td>
                  <td className="mono" style={{ textAlign: "right", color: q.retry ? "var(--status-warn)" : undefined }}>{q.retry}</td>
                  <td><span className={"pill " + (q.state === "OK" ? "pill--ok" : "pill--warn")}>{q.state}</span></td>
                </tr>
              ))}
              {queues.length === 0 && <tr><td colSpan={6} style={{ color: "var(--text-muted)" }}>No queues (connect a tenant).</td></tr>}
            </tbody>
          </table>
        </div>

        {/* Data stores */}
        <div>
          <div className="label-mono" style={{ marginBottom: 8 }}>Data stores</div>
          <table className="tbl tbl--zone">
            <thead><tr><th>Data store</th><th>iFlow</th><th style={{ width: 60 }}>Type</th><th style={{ textAlign: "right", width: 58 }}>Entries</th><th style={{ textAlign: "right", width: 62 }}>Overdue</th></tr></thead>
            <tbody>
              {stores.map((d) => (
                <tr key={d.name}>
                  <td className="mono">{d.name}</td>
                  <td className="mono" style={{ color: "var(--text-secondary)" }}>{d.iflow || "—"}</td>
                  <td className="mono">{d.type || "—"}</td>
                  <td className="mono" style={{ textAlign: "right" }}>{d.entries}</td>
                  <td className="mono" style={{ textAlign: "right", color: d.overdue ? "var(--status-failed)" : undefined }}>{d.overdue}</td>
                </tr>
              ))}
              {stores.length === 0 && <tr><td colSpan={5} style={{ color: "var(--text-muted)" }}>No data stores (connect a tenant).</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      {ov?.error && <div className="note-line" style={{ color: "var(--status-warn)", marginTop: 10 }}>⚠ {ov.error}</div>}
    </section>
  );
}

function SystemDrill({ kind }: { kind: string }) {
  const [detail, setDetail] = useState<SystemDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [explain, setExplain] = useState<ExplainResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getSystemDetail(kind).then(setDetail).catch(() => setDetail(null)).finally(() => setLoading(false));
  }, [kind]);

  async function doExplain(id: string) {
    setBusy(id); setExplain(null);
    try { setExplain(await explainTenant("_", id)); } catch { /* ignore */ } finally { setBusy(null); }
  }

  if (loading) return <div className="mono" style={{ color: "var(--text-muted)" }}>Loading…</div>;
  if (!detail) return <div style={{ color: "var(--status-failed)" }}>Failed to load detail.</div>;
  if (detail.error) return <div style={{ color: "var(--status-warn)" }}>⚠ {detail.error}</div>;

  return (
    <>
      <div className="label-mono" style={{ marginBottom: 8 }}>
        {kind === "APIM" ? "API proxy inventory — " : ""}{detail.items.length} item(s)
      </div>
      <table className="tbl">
        <thead><tr>{detail.columns.map((c) => <th key={c}>{c}</th>)}{kind === "CPI" && <th></th>}</tr></thead>
        <tbody>
          {detail.items.slice(0, 50).map((it, i) => (
            <tr key={i}>
              {kind === "CPI" && <>
                <td className="mono">{String(it.name ?? "")}</td>
                <td><span className="status-tag" style={{ color: "var(--status-success)" }}>{String(it.status ?? "")}</span></td>
                <td style={{ textAlign: "right" }}><button className="link-btn" onClick={() => doExplain(String(it.id ?? ""))} disabled={busy !== null}>{busy === it.id ? "…" : "Explain"}</button></td>
              </>}
              {kind === "APIM" && (detail.columns.length === 4 ? <>
                <td className="mono">{String(it.name ?? "")}</td>
                <td className="mono">{String(it.calls ?? "")}</td>
                <td className="mono" style={{ color: "var(--status-success)" }}>{String(it.success ?? "")}</td>
                <td className="mono" style={{ color: Number(it.failed) ? "var(--status-failed)" : undefined }}>{String(it.failed ?? "")}</td>
              </> : <>
                <td className="mono">{String(it.name ?? "")}</td>
                <td className="mono">{String(it.version ?? "")}</td>
                <td className="mono">{String(it.status ?? "")}</td>
              </>)}
              {kind === "AEM" && <>
                <td className="mono">{String(it.name ?? "")}</td>
                <td className="mono">{String(it.spool_mb ?? "")}</td>
                <td className="mono">{String(it.access ?? "")}</td>
              </>}
            </tr>
          ))}
          {detail.items.length === 0 && <tr><td colSpan={4} style={{ color: "var(--text-muted)" }}>No items.</td></tr>}
        </tbody>
      </table>
      {explain && (
        <div className="brief" style={{ marginTop: 12 }}>
          <div className="brief__summary">{explain.summary}</div>
          <div className="brief__meta">Sender {explain.facts.sender_adapter} → Receiver {explain.facts.receiver_adapter} · {explain.facts.step_count} steps · error handling: {explain.facts.has_error_handling ? "yes" : "no"}</div>
          {explain.risks.map((r, i) => <div key={i} className="brief__meta" style={{ color: "var(--status-warn)" }}>⚠ {r}</div>)}
        </div>
      )}
    </>
  );
}

/* APIM monitoring zones — the six panels below the APIM-RCA indicator bar
   (Integrations & APIs, Success vs Failed, Proxy Errors, Proxy Breakdown,
   API Provider, Key Value Maps). Mirrors the QDKEP APIM monitoring screen. */
/* Scrollable zone table: shows a pinned header and a vertical scrollbar once
   the body has more than 5 rows, so tall zones don't stretch the layout. */
function ZoneTable({ rows, head, children }: { rows: number; head: ReactNode; children: ReactNode }) {
  const scroll = rows > 5;
  return (
    <div className={scroll ? "zone-scroll" : undefined} style={scroll ? { maxHeight: 244 } : undefined}>
      <table className="tbl tbl--zone">
        <thead>{head}</thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function ApimZones({ a }: { a: ApimAnalytics }) {
  const ia = a.integrations_apis;
  const t = a.proxy_traffic;
  const maxSF = Math.max(t.success, t.failed, 1);
  const zoneGrid = {
    display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
    gap: 14, marginBottom: 4,
  } as const;
  return (
    <div style={zoneGrid}>
      {/* 1 — Integrations and APIs */}
      <div className="card" style={{ padding: 16 }}>
        <div className="label-mono" style={{ marginBottom: 8 }}>Integrations and APIs</div>
        <div className="kpi-value kpi-value--success" style={{ fontSize: 34, lineHeight: 1 }}>{ia.total}</div>
        <div className="field__hint" style={{ margin: "4px 0 14px" }}>Total started artifacts</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {([["Started", ia.started, "success"], ["Starting", ia.starting, "watched"],
             ["Stopping", ia.stopping, "warn"], ["Error", ia.error, "failed"]] as const).map(([l, v, tone]) => (
            <div key={l} className="iflow-row" style={{ padding: "2px 10px", minHeight: 0 }}>
              <span className="label-mono" style={{ fontSize: 10 }}>{l}</span>
              <span className={`kpi-value kpi-value--${tone} mono`} style={{ fontSize: 13, lineHeight: 1 }}>{v}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 2 — Success vs Failed (API proxy calls) — enlarged ~50%, sat lower */}
      <div className="card" style={{ padding: 16 }}>
        <div className="label-mono" style={{ marginBottom: 8 }}>Success vs Failed (API proxy calls)</div>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "center", gap: 54, height: 230, paddingTop: 28 }}>
          {([["Success", t.success, "var(--status-success)"], ["Failed", t.failed, "var(--status-failed)"]] as const).map(([l, v, col]) => (
            <div key={l} style={{ display: "flex", flexDirection: "column", alignItems: "center", height: "100%", justifyContent: "flex-end" }}>
              <div className="mono" style={{ color: col, fontWeight: 600, fontSize: 15, marginBottom: 6 }}>{v}</div>
              <div style={{ width: 78, height: `${Math.max((v / maxSF) * 165, 6)}px`, background: col, borderRadius: "5px 5px 0 0" }} />
              <div className="label-mono" style={{ marginTop: 8 }}>{l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 3 — API Proxy Errors */}
      <div className="card" style={{ padding: 16 }}>
        <div className="label-mono" style={{ marginBottom: 10 }}>API Proxy Errors</div>
        <ZoneTable rows={a.proxy_errors.rows.length}
          head={<tr><th>API proxy</th><th style={{ textAlign: "right", width: 60 }}>Errors</th></tr>}>
          {a.proxy_errors.rows.map((r) => (
            <tr key={r.name}><td className="mono">{r.name}</td>
              <td className="mono" style={{ textAlign: "right", color: "var(--status-failed)" }}>{r.count}</td></tr>
          ))}
          {a.proxy_errors.rows.length === 0 && <tr><td colSpan={2} style={{ color: "var(--text-muted)" }}>No proxy errors.</td></tr>}
        </ZoneTable>
      </div>

      {/* 4 — API Proxy Breakdown */}
      <div className="card" style={{ padding: 16 }}>
        <div className="label-mono" style={{ marginBottom: 10 }}>API Proxy Breakdown</div>
        <ZoneTable rows={a.api_proxy_breakdown.length}
          head={<tr><th>API proxy</th><th style={{ textAlign: "right", width: 62 }}>Success</th><th style={{ textAlign: "right", width: 56 }}>Failed</th></tr>}>
          {a.api_proxy_breakdown.map((b) => (
            <tr key={b.name}>
              <td className="mono">{b.name}</td>
              <td className="mono" style={{ textAlign: "right", color: "var(--status-success)" }}>{b.success}</td>
              <td className="mono" style={{ textAlign: "right", color: b.failed ? "var(--status-failed)" : undefined }}>{b.failed}</td>
            </tr>
          ))}
        </ZoneTable>
      </div>

      {/* 5 — API Provider */}
      <div className="card" style={{ padding: 16 }}>
        <div className="label-mono" style={{ marginBottom: 10 }}>API Provider</div>
        <ZoneTable rows={a.api_providers.length}
          head={<tr><th>Provider</th><th>Host</th><th style={{ textAlign: "right", width: 58 }}>Proxies</th></tr>}>
          {a.api_providers.map((p) => (
            <tr key={p.name}><td className="mono">{p.name}</td><td className="mono">{p.host}</td>
              <td className="mono" style={{ textAlign: "right" }}>{p.proxies}</td></tr>
          ))}
        </ZoneTable>
      </div>

      {/* 6 — Key Value Maps */}
      <div className="card" style={{ padding: 16 }}>
        <div className="label-mono" style={{ marginBottom: 10 }}>Key Value Maps</div>
        <ZoneTable rows={a.key_value_maps.length}
          head={<tr><th>Map</th><th style={{ width: 78 }}>Encrypted</th><th style={{ textAlign: "right", width: 58 }}>Entries</th></tr>}>
          {a.key_value_maps.map((k) => (
            <tr key={k.name}><td className="mono">{k.name}</td>
              <td className="mono" style={{ color: k.encrypted ? "var(--status-success)" : "var(--text-muted)" }}>{k.encrypted ? "Yes" : "No"}</td>
              <td className="mono" style={{ textAlign: "right" }}>{k.entries}</td></tr>
          ))}
        </ZoneTable>
      </div>
    </div>
  );
}
