/* iFlows / iFlow Manager — browse a package's iFlows in a table and act on each
   row inline: Explain · Modify · Verify · Fix. The result opens directly under
   the selected row. Or Explain any exported iFlow ZIP (no connection needed). */
import { Fragment, useEffect, useRef, useState, type ChangeEvent, type ReactNode } from "react";
import {
  getPackages, getPackageIflows, explainZip, explainTenant, generateIflow, getRuntimeStatus,
  type Package, type IflowItem, type ExplainResult, type RunView,
} from "../api";

type Mode = "explain" | "modify" | "verify" | "fix";
const MODES: Mode[] = ["explain", "modify", "verify", "fix"];
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function deployState(status: string | undefined, loaded: boolean): { label: string; tone: string } {
  const s = (status || "").toUpperCase();
  if (!loaded && !s) return { label: "…", tone: "muted" };
  if (["STARTED", "STARTING", "DEPLOYED"].includes(s)) return { label: "DEPLOYED", tone: "success" };
  if (["ERROR", "STOPPED", "FAILED"].includes(s)) return { label: s, tone: "failed" };
  return { label: "NOT_DEPLOYED", tone: "muted" };   // absent from runtime = not deployed (grey)
}

export default function Iflows() {
  const [packages, setPackages] = useState<Package[]>([]);
  const [pkg, setPkg] = useState("");
  const [iflows, setIflows] = useState<IflowItem[]>([]);
  const [status, setStatus] = useState<Record<string, string>>({});
  const [statusLoaded, setStatusLoaded] = useState(false);
  const [search, setSearch] = useState("");
  const [pkgNote, setPkgNote] = useState("");
  const [open, setOpen] = useState<{ id: string; mode: Mode } | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [zipResult, setZipResult] = useState<ExplainResult | null>(null);

  async function loadPackages() {
    setPkgNote("");
    try {
      const p = (await getPackages()).slice().sort((a, b) => (a.name || a.id).localeCompare(b.name || b.id, undefined, { numeric: true }));
      setPackages(p);
      if (p[0] && !pkg) setPkg(p[0].id);
      if (!p.length) setPkgNote("No packages — check the CPI connection in Settings.");
    } catch (e) { setPkgNote(e instanceof Error ? `Packages: ${e.message}` : "Could not load packages."); }
    getRuntimeStatus().then(setStatus).catch(() => {}).finally(() => setStatusLoaded(true));
  }
  useEffect(() => { loadPackages(); }, []);
  useEffect(() => {
    if (pkg) { setOpen(null); getPackageIflows(pkg).then(setIflows).catch(() => setIflows([])); }
  }, [pkg]);

  const shown = iflows.filter((f) =>
    !search || f.name.toLowerCase().includes(search.toLowerCase()) || f.id.toLowerCase().includes(search.toLowerCase()));

  function toggle(id: string, mode: Mode) {
    setZipResult(null);
    setOpen((o) => (o && o.id === id && o.mode === mode ? null : { id, mode }));
  }
  function refreshStatus() {
    getRuntimeStatus().then(setStatus).catch(() => {}).finally(() => setStatusLoaded(true));
  }

  async function onZip(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return;
    setBusy(true); setOpen(null); setZipResult(null);
    try { setZipResult(await explainZip(file)); }
    catch (ex) { setPkgNote(ex instanceof Error ? ex.message : "Explain failed"); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  return (
    <div className="page page--wide">
      <div className="eyebrow">Browse · Explain · Modify · Fix · Verify</div>
      <h2 className="page__title">iFlow Manager</h2>
      <p className="page__sub">Browse a package and act on each iFlow — or explain any exported iFlow ZIP, no connection needed.</p>

      {/* Controls */}
      <section className="card panel" style={{ padding: 16, marginTop: 18 }}>
        <div className="iflow-controls">
          <label className="field" style={{ flex: 2, minWidth: 260 }}>
            <span className="label-mono">Package</span>
            <select className="input" value={pkg} onChange={(e) => setPkg(e.target.value)}>
              {packages.length === 0 && <option value="">Select a package…</option>}
              {packages.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.id})</option>)}
            </select>
          </label>
          <label className="field" style={{ flex: 2, minWidth: 220 }}>
            <span className="label-mono">Search</span>
            <input className="input" value={search} placeholder="Filter by name or ID…" onChange={(e) => setSearch(e.target.value)} />
          </label>
          <button className="btn" onClick={loadPackages} disabled={busy}>↻ Refresh</button>
          <button className="btn" onClick={() => fileRef.current?.click()} disabled={busy}>{busy ? "…" : "Explain from ZIP"}</button>
          <input ref={fileRef} type="file" accept=".zip" hidden onChange={onZip} />
        </div>
        {pkgNote && <div className="note-line" style={{ color: packages.length ? "var(--text-muted)" : "var(--status-warn)" }}>{pkgNote}</div>}
      </section>

      {zipResult && (
        <section className="card panel" style={{ marginTop: 16, padding: 20 }}>
          <div className="label-mono" style={{ marginBottom: 10 }}>Explanation (from ZIP) · {zipResult.facts.name}</div>
          <ExplainView data={zipResult} />
        </section>
      )}

      <div className="unlock-note" style={{ marginTop: 16 }}>
        🔒 <b>Unlock before any action.</b> All iFlows must be closed in the SAP CPI web IDE before Modify, Fix or Verify can write to them.
      </div>

      {/* Table */}
      <section className="card panel" style={{ marginTop: 16 }}>
        <table className="tbl tbl--fixed">
          <thead><tr><th>Name / ID</th><th>Package</th><th>Status</th><th style={{ textAlign: "right" }}>Actions</th></tr></thead>
          <tbody>
            {shown.map((f) => {
              const st = deployState(status[f.id], statusLoaded);
              const isOpen = open?.id === f.id;
              return (
                <Fragment key={f.id}>
                  <tr className={isOpen ? "row--open" : ""}>
                    <td>
                      <div className="iflow-row__name">{f.name}</div>
                      <div className="mono" style={{ fontSize: 11 }}>{f.id}{f.version ? ` · v${f.version}` : ""}</div>
                    </td>
                    <td><span className="pill pill--info">{pkg}</span></td>
                    <td>
                      <button className="status-btn" style={{ color: st.tone === "muted" ? "var(--text-muted)" : `var(--status-${st.tone})` }}
                        title="Click to re-check the deployment status" onClick={refreshStatus}>
                        {st.tone === "success" ? "● " : ""}{st.label}
                      </button>
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <div className="iflow-actions">
                        {MODES.map((m) => (
                          <button key={m} className={"btn btn--sm" + (isOpen && open?.mode === m ? " btn--primary" : "")}
                            onClick={() => toggle(f.id, m)} disabled={busy}>{cap(m)}</button>
                        ))}
                      </div>
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="row--panel">
                      <td colSpan={4}>
                        <ActionPanel mode={open!.mode} iflow={f} pkg={pkg} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {shown.length === 0 && <tr><td colSpan={4} style={{ color: "var(--text-muted)" }}>{pkg ? "No iFlows in this package." : "Select a package."}</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}

/* ---- Inline panel: renders the right UI for the chosen action ---- */
function ActionPanel({ mode, iflow, pkg }: { mode: Mode; iflow: IflowItem; pkg: string }) {
  const [explain, setExplain] = useState<ExplainResult | null>(null);
  const [run, setRun] = useState<RunView | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // form fields
  const [change, setChange] = useState("");
  const [deploy, setDeploy] = useState(false);
  const [payload, setPayload] = useState("");
  const [expected, setExpected] = useState("");

  // Explain auto-runs on open
  useEffect(() => {
    if (mode !== "explain") return;
    setBusy(true); setErr(null);
    explainTenant(pkg, iflow.id).then(setExplain)
      .catch((e) => setErr(e instanceof Error ? e.message : "Explain failed"))
      .finally(() => setBusy(false));
  }, [mode, pkg, iflow.id]);

  const words = change.trim() ? change.trim().split(/\s+/).length : 0;
  const overLimit = words > 1000;

  async function submit() {
    setBusy(true); setErr(null); setRun(null);
    try {
      const desc =
        mode === "modify"
          ? `Modify existing iFlow ${iflow.name} (${iflow.id}): ${change}. Preserve current behavior and insert the new element between existing steps.${deploy ? " Deploy after applying." : ""}`
          : mode === "verify"
          ? `Verify iFlow ${iflow.name} (${iflow.id}) by deploying and running the provided test payload, then comparing to the expected output.`
          : `Fix iFlow ${iflow.name} (${iflow.id}) which is failing. Diagnose from the payload/logs and correct the root cause.`;
      setRun(await generateIflow({
        description: desc, iflow_id: iflow.id, iflow_name: iflow.name, package: pkg,
        sample_input: payload, sample_output: expected, quick: true,
      }));
    } catch (e) { setErr(e instanceof Error ? e.message : "Failed"); } finally { setBusy(false); }
  }

  const title = mode === "explain" ? "Explanation" : mode === "modify" ? "Modify" : mode === "verify" ? "Verify" : "Fix";

  return (
    <div className="act-panel">
      <div className="act-panel__title">{title} — {iflow.name}</div>

      {mode === "explain" && (
        busy ? <div className="mono" style={{ color: "var(--text-muted)" }}>Analysing the iFlow…</div>
          : err ? <div className="note-line" style={{ color: "var(--status-failed)" }}>{err}</div>
          : explain ? <ExplainView data={explain} /> : null
      )}

      {mode === "modify" && (
        <>
          <textarea className="input" rows={4} value={change} maxLength={12000}
            placeholder="Describe the change, e.g. Add a filter step to skip records where status is CLOSED, then add a JMS queue for failed rows…"
            onChange={(e) => setChange(e.target.value)} />
          <div className="act-row">
            <button className="btn btn--primary act-submit" onClick={submit} disabled={busy || !change.trim() || overLimit}>
              {busy ? "Working…" : "Apply Change"}
            </button>
            <label className="pick" style={{ flex: "none" }}>
              <input type="checkbox" checked={deploy} onChange={(e) => setDeploy(e.target.checked)} />
              <span className="label-mono">Deploy after modify</span>
            </label>
            <span className="label-mono" style={{ marginLeft: "auto", color: overLimit ? "var(--status-failed)" : "var(--text-faint)" }}>
              {words} / 1000 words
            </span>
          </div>
        </>
      )}

      {(mode === "verify" || mode === "fix") && (
        <>
          <div className="label-mono" style={{ marginBottom: 6 }}>
            Test payload {mode === "verify" ? "(optional — leave blank to just deploy)" : "(optional — if blank, uses last run logs)"}
          </div>
          <textarea className="input" rows={4} value={payload}
            placeholder={mode === "verify" ? "JSON, XML, CSV…" : "Trigger payload to reproduce the error…"}
            onChange={(e) => setPayload(e.target.value)} />
          <div className="label-mono" style={{ margin: "12px 0 6px" }}>Expected output (optional)</div>
          <textarea className="input" rows={3} value={expected}
            placeholder={mode === "verify" ? "Expected response body…" : "What the response should look like…"}
            onChange={(e) => setExpected(e.target.value)} />
          <div className="act-row">
            <button className="btn btn--primary act-submit" onClick={submit} disabled={busy}>
              {busy ? "Working…" : mode === "verify" ? "Deploy & Test" : "Diagnose & Fix"}
            </button>
          </div>
        </>
      )}

      {err && mode !== "explain" && <div className="note-line" style={{ color: "var(--status-failed)" }}>{err}</div>}
      {run && <RunResult run={run} />}
    </div>
  );
}

/* ---- Model-grade Explain rendering (What it does / Trigger / Steps / Scripts / Errors / Notes) ---- */
function ExplainView({ data }: { data: ExplainResult }) {
  const s = data.sections;
  return (
    <div className="explain">
      <div className="sys__kpis" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))" }}>
        <div className="card sys__kpi"><div className="label-mono">Sender</div><div className="mono" style={{ marginTop: 8, color: "var(--status-watched)" }}>{data.facts.sender_adapter}</div></div>
        <div className="card sys__kpi"><div className="label-mono">Receiver</div><div className="mono" style={{ marginTop: 8, color: "var(--status-watched)" }}>{data.facts.receiver_adapter}</div></div>
        <div className="card sys__kpi"><div className="label-mono">Steps</div><div className="mono" style={{ marginTop: 8 }}>{data.facts.step_count}</div></div>
        <div className="card sys__kpi"><div className="label-mono">Error handling</div><div className="mono" style={{ marginTop: 8, color: data.facts.has_error_handling ? "var(--status-success)" : "var(--status-failed)" }}>{data.facts.has_error_handling ? "yes" : "no"}</div></div>
      </div>

      {s ? (
        <>
          <Block title="What it does"><p className="explain__p">{s.what_it_does}</p></Block>
          <Block title="Trigger"><p className="explain__p">{s.trigger}</p></Block>
          <Block title="Step by step"><ol className="explain__ol">{s.step_by_step.map((x, i) => <li key={i}>{x}</li>)}</ol></Block>
          {(data.scripts ?? []).length > 0 && (
            <Block title="Groovy scripts">
              {(data.scripts ?? []).map((sc) => (
                <div key={sc.name} style={{ marginBottom: 10 }}>
                  <div className="mono" style={{ color: "var(--rca-lime)", marginBottom: 4 }}>{sc.name}</div>
                  <ul className="explain__ul">{sc.points.map((p, i) => <li key={i}>{p}</li>)}</ul>
                </div>
              ))}
            </Block>
          )}
          <Block title="Error handling"><ul className="explain__ul">{s.error_handling.map((x, i) => <li key={i}>{x}</li>)}</ul></Block>
          {s.notes.length > 0 && <Block title="Notes"><ul className="explain__ul">{s.notes.map((x, i) => <li key={i}>{x}</li>)}</ul></Block>}
        </>
      ) : (
        <>
          <p className="explain__p" style={{ marginTop: 14 }}>{data.summary}</p>
          <Block title="Steps"><ol className="explain__ol">{data.facts.steps.map((x, i) => <li key={i}>{x}</li>)}</ol></Block>
          {data.risks.length > 0 && <Block title="Risks"><ul className="explain__ul">{data.risks.map((x, i) => <li key={i} style={{ color: "var(--status-warn)" }}>{x}</li>)}</ul></Block>}
        </>
      )}
    </div>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="explain__block">
      <div className="label-mono explain__h">{title}</div>
      {children}
    </div>
  );
}

function RunResult({ run }: { run: RunView }) {
  return (
    <div style={{ marginTop: 16 }}>
      <div className="note-line" style={{ color: "var(--status-warn)", marginTop: 0 }}>🔒 Proposal only — writing to the tenant requires deploy approval (write gate).</div>
      {run.brief && <>
        <p className="explain__p">{run.brief.summary}</p>
        <ol className="explain__ol">{(run.brief.steps ?? []).map((s, i) => <li key={i}>{s}</li>)}</ol>
      </>}
      {run.score && <div className={`gate gate--${run.score.passed ? "ok" : "fail"}`}><div className="gate__score">{run.score.total}<span>/100</span></div><div className="gate__status">{run.score.status}</div></div>}
      {run.artifact && <pre className="code" style={{ marginTop: 12, maxHeight: 320 }}>{run.artifact}</pre>}
    </div>
  );
}
