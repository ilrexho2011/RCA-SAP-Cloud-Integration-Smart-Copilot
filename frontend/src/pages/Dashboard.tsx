/* Dashboard — landing overview across SAP CPI, APIM and AEM.
   Order: KPIs → Quick actions → Recent iFlows (selectable) → iFlows Health → Recent failures. */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  getMonitoringOverview, getPackages, getMonitorFlows, watchFlow, unwatchFlow,
  formatTimestamp, type MonitoringOverview, type MonitorFlow,
} from "../api";

function healthy(status: string): boolean {
  const s = (status || "").toUpperCase();
  return s === "STARTED" || s === "STARTING" || s === "DEPLOYED";
}

export default function Dashboard() {
  const [ov, setOv] = useState<MonitoringOverview | null>(null);
  const [pkgCount, setPkgCount] = useState<number | null>(null);
  const [flows, setFlows] = useState<MonitorFlow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [o, p, f] = await Promise.all([
          getMonitoringOverview(),
          getPackages().catch(() => []),
          getMonitorFlows().catch(() => []),
        ]);
        setOv(o); setPkgCount(p.length); setFlows(f);
      } finally { setLoading(false); }
    })();
  }, []);

  async function toggle(f: MonitorFlow) {
    setBusy(f.id);
    try {
      if (f.watched) await unwatchFlow(f.id); else await watchFlow(f.id);
      setFlows(await getMonitorFlows());
    } finally { setBusy(null); }
  }

  const sys = ov?.systems?.[0];
  const kpi = (k: string) => ov?.kpis.find((x) => x.key === k)?.value ?? 0;
  const selected = flows.filter((f) => f.watched);

  const cards = [
    { label: "Total iFlows", value: sys?.deployed_iflows ?? "—", tone: "watched" },
    { label: "Packages", value: pkgCount ?? "—", tone: "info" },
    { label: "Watched", value: selected.length, tone: "success" },
    { label: "Failing", value: kpi("failed"), tone: "failed" },
  ];

  const actions = [
    { to: "/generate", title: "Generate iFlow", desc: "Build a new integration with AI", icon: "⚙" },
    { to: "/iflows", title: "Browse iFlows", desc: "View, explain and manage artifacts", icon: "▤" },
    { to: "/groovy", title: "Generate Groovy", desc: "Write scripts with AI assistance", icon: "</>" },
  ];

  return (
    <div className="page page--wide">
      <div className="eyebrow">AI Copilot for SAP Cloud Integration</div>
      <h2 className="page__title">Dashboard</h2>
      <p className="page__sub">Generation and management of integrations with AI Assistance — SAP CPI, API Management (APIM) and AEM.</p>

      <div className="kpi-grid">
        {cards.map((c) => (
          <div className="card kpi" key={c.label}>
            <div className="label-mono">{c.label}</div>
            <div className={`kpi-value kpi-value--${c.tone}`}>{loading ? "—" : c.value}</div>
            <div className="kpi__note">{ov?.source === "live" ? "live from tenant" : "demo data"}</div>
          </div>
        ))}
      </div>

      {/* Quick actions */}
      <div className="label-mono" style={{ margin: "26px 0 12px" }}>Quick actions</div>
      <div className="autogrid autogrid--wide">
        {actions.map((a) => (
          <Link key={a.to} to={a.to} className="card action">
            <div className="action__icon">{a.icon}</div>
            <div className="action__title">{a.title}</div>
            <div className="action__desc">{a.desc}</div>
          </Link>
        ))}
      </div>

      {/* Recent iFlows — selectable in any combination; each links to the iFlows page */}
      <div className="section-head">
        <span className="label-mono">Recent iFlows</span>
        <Link to="/iflows" className="link-btn">View all</Link>
      </div>
      <section className="card panel" style={{ marginTop: 12 }}>
        <div className="iflow-list" style={{ padding: 14, gap: 6, maxHeight: 320, overflowY: "auto" }}>
          {flows.slice(0, 12).map((f) => (
            <div className={"iflow-row" + (f.watched ? " iflow-row--sel" : "")} key={f.id}>
              <label className="pick">
                <input type="checkbox" checked={f.watched} disabled={busy === f.id} onChange={() => toggle(f)} />
                <span>
                  <span className="iflow-row__name">{f.name}</span>
                  <span className="mono" style={{ display: "block", fontSize: 11 }}>{f.status}</span>
                </span>
              </label>
              <Link to="/iflows" className="btn btn--sm">View</Link>
            </div>
          ))}
          {flows.length === 0 && <div style={{ color: "var(--text-muted)" }}>{loading ? "Loading…" : "No iFlows (connect a tenant in Settings)."}</div>}
        </div>
      </section>

      {/* iFlows Health — the selected flows, with a health indicator */}
      <div className="section-head">
        <span className="label-mono">iFlows Health {selected.length > 0 && <span style={{ color: "var(--rca-lime)" }}>({selected.length})</span>}</span>
        <Link to="/monitor" className="link-btn">Configure monitor</Link>
      </div>
      {selected.length > 0
        ? <div className="hp-note">All {selected.length} selected flow(s) {selected.every((f) => healthy(f.status)) ? "healthy" : "— check status"}</div>
        : null}
      <div className="autogrid autogrid--health" style={{ marginTop: 12 }}>
        {selected.map((f) => (
          <div className="card health-card" key={f.id}>
            <div className="health-card__head">
              <span className={"hdot " + (healthy(f.status) ? "hdot--ok" : "hdot--warn")} />
              <span className="label-mono">{healthy(f.status) ? "Healthy" : "Check"}</span>
            </div>
            <div className="health-card__name">{f.name}</div>
            <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>{f.status}</div>
          </div>
        ))}
        {selected.length === 0 && (
          <div className="card" style={{ padding: 18, color: "var(--text-muted)", gridColumn: "1 / -1" }}>
            Tick one or more iFlows above to add them here and follow their health.
          </div>
        )}
      </div>

      {/* Recent failures */}
      <div className="label-mono" style={{ margin: "26px 0 12px" }}>Recent failures</div>
      <section className="card panel">
        <table className="tbl">
          <thead><tr><th>Interface</th><th>Status</th><th>Error</th><th style={{ textAlign: "right" }}>When</th></tr></thead>
          <tbody>
            {(ov?.failed_messages ?? []).slice(0, 6).map((r, i) => (
              <tr key={i}>
                <td className="mono">{r.interface}</td>
                <td><span className="status-tag" style={{ color: "var(--status-failed)" }}>{r.status}</span></td>
                <td style={{ color: "var(--text-secondary)", maxWidth: 520 }}>{r.error || "—"}</td>
                <td className="mono" style={{ textAlign: "right", whiteSpace: "nowrap" }}>{formatTimestamp(r.timestamp)}</td>
              </tr>
            ))}
            {ov && ov.failed_messages.length === 0 && (
              <tr><td colSpan={4} style={{ color: "var(--text-muted)" }}>No failures in the current window.</td></tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
