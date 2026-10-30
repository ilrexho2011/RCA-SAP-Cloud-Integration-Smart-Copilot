/* Generate — drive the orchestrator. Analyse & Plan pauses at the design brief
   (HITL); Approve runs generate → validate → quality gate → await deploy.
   Quick Generate skips the approval gate. Accepts sample I/O and file uploads
   (groovy, xml/json, xslt, xsd, iflw, zip, images) that ground the build. */
import { useEffect, useRef, useState } from "react";
import { generateIflow, approveRun, reviseRun, deployRun, getPackages, type RunView, type Package, type Attachment } from "../api";

const STAGE_LABELS: Record<string, string> = {
  classify: "Classify", retrieve: "Retrieve (RAG)", plan: "Plan", draft_brief: "Draft brief",
  await_approval: "Human approval", generate: "Generate", validate: "Validate",
  quality_gate: "Quality gate", repair: "Repair", await_deploy: "Await deploy",
  blocked: "Blocked", done: "Done",
};

const TEXT_EXT = ["groovy", "xml", "json", "csv", "xsl", "xslt", "xsd", "iflw", "wsdl", "txt", "md", "properties"];
const ACCEPT = ".groovy,.xml,.json,.csv,.xsl,.xslt,.xsd,.iflw,.wsdl,.txt,.md,.properties,.zip,image/*";

function kindFor(name: string, type: string): string {
  if (type.startsWith("image/")) return "image";
  const ext = name.split(".").pop()?.toLowerCase() || "";
  if (ext === "zip") return "zip";
  if (["xsl", "xslt"].includes(ext)) return "xslt";
  if (TEXT_EXT.includes(ext)) return ext === "iflw" ? "iflw" : (["xml", "json", "csv", "xsd", "groovy"].includes(ext) ? ext : "text");
  return "text";
}

export default function Generate() {
  const [form, setForm] = useState({
    description: "", iflow_id: "", iflow_name: "", package: "",
    sample_input: "", sample_output: "",
  });
  const [packages, setPackages] = useState<Package[]>([]);
  const [pkgNote, setPkgNote] = useState<string>("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [showSamples, setShowSamples] = useState(false);
  const [run, setRun] = useState<RunView | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function loadPackages() {
    setPkgNote("");
    try {
      const p = (await getPackages()).slice().sort((a, b) =>
        (a.name || a.id).localeCompare(b.name || b.id, undefined, { numeric: true }));
      setPackages(p);
      if (p[0]) setForm((f) => ({ ...f, package: f.package || p[0].id }));
      setPkgNote(p.length ? `${p.length} package(s) from your tenant` : "No packages found — check the CPI connection in Settings.");
    } catch (e) { setPkgNote(e instanceof Error ? `Packages: ${e.message}` : "Could not load packages — check the CPI connection."); }
  }
  useEffect(() => { loadPackages(); }, []);

  function set<K extends keyof typeof form>(k: K, v: string) { setForm((f) => ({ ...f, [k]: v })); }

  async function onFiles(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    const next: Attachment[] = [];
    for (const f of files) {
      const kind = kindFor(f.name, f.type);
      if (kind === "image") {
        next.push({ name: f.name, kind, content: "" });   // vision provider required to read pixels
      } else if (kind === "zip" || kind === "iflw") {
        next.push({ name: f.name, kind, content: "" });   // binary — referenced by name
      } else {
        const text = await f.text();
        next.push({ name: f.name, kind, content: text.slice(0, 20000) });
      }
    }
    setAttachments((a) => [...a, ...next]);
    if (fileRef.current) fileRef.current.value = "";
  }
  function removeAtt(i: number) { setAttachments((a) => a.filter((_, idx) => idx !== i)); }

  async function run_(quick: boolean) {
    setBusy(quick ? "quick" : "plan"); setErr(null); setRun(null);
    try {
      setRun(await generateIflow({
        ...form,
        iflow_id: form.iflow_id || "iFlow",
        iflow_name: form.iflow_name || form.iflow_id || "iFlow",
        attachments, quick,
      }));
    } catch (e) { setErr(e instanceof Error ? e.message : "Failed"); } finally { setBusy(null); }
  }
  async function onApprove() {
    if (!run) return; setBusy("approve"); setErr(null);
    try { setRun(await approveRun(run.run_id)); }
    catch (e) { setErr(e instanceof Error ? e.message : "Failed"); } finally { setBusy(null); }
  }
  async function onRevise() {
    if (!run) return;
    const fb = prompt("What should change in the design?"); if (!fb) return;
    setBusy("revise"); setErr(null);
    try { setRun(await reviseRun(run.run_id, fb)); }
    catch (e) { setErr(e instanceof Error ? e.message : "Failed"); } finally { setBusy(null); }
  }
  async function onDeploy() {
    if (!run) return; setBusy("deploy"); setErr(null);
    try { setRun(await deployRun(run.run_id)); }
    catch (e) { setErr(e instanceof Error ? e.message : "Failed"); } finally { setBusy(null); }
  }

  const stTone = (s: string) => (s === "fail" ? "fail" : s === "info" ? "info" : "ok");
  const words = form.description.trim() ? form.description.trim().split(/\s+/).length : 0;
  const overLimit = words > 4000;

  return (
    <div className="page page--wide">
      <div className="eyebrow">AI iFlow &amp; Groovy generation</div>
      <h2 className="page__title">Generate</h2>
      <p className="page__sub">Describe the integration in plain language — attach files if useful — the orchestrator plans, grounds it in patterns, then generates under review.</p>

      <div className="gen-grid gen-grid--wide">
        <section className="card panel" style={{ padding: 20 }}>
          <div className="label-mono" style={{ marginBottom: 14 }}>New iFlow</div>
          <label className="field">
            <span className="label-mono">Description *</span>
            <textarea className="input" rows={9} value={form.description}
              placeholder="Describe what this iFlow should do, including source system, target system, and key logic…"
              onChange={(e) => set("description", e.target.value)} />
            <span className="field__hint" style={overLimit ? { color: "var(--status-failed)" } : undefined}>
              {words} / 4000 words{overLimit ? " — please shorten" : ""}
            </span>
          </label>
          <div className="form-grid" style={{ marginTop: 16 }}>
            <label className="field"><span className="label-mono">iFlow ID *</span>
              <input className="input" value={form.iflow_id} placeholder="SF_OrderToS4" onChange={(e) => set("iflow_id", e.target.value)} /></label>
            <label className="field"><span className="label-mono">iFlow Name *</span>
              <input className="input" value={form.iflow_name} placeholder="Orders to S/4HANA" onChange={(e) => set("iflow_name", e.target.value)} /></label>
          </div>
          <label className="field" style={{ marginTop: 16 }}>
            <span className="label-mono">Package <button className="link-btn" style={{ marginLeft: 8 }} onClick={(e) => { e.preventDefault(); loadPackages(); }}>refresh</button></span>
            <select className="input" value={form.package} onChange={(e) => set("package", e.target.value)}>
              {packages.length === 0 && <option value="">CPICopilot</option>}
              {packages.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.id})</option>)}
            </select>
            {pkgNote && <span className="field__hint" style={{ color: packages.length ? "var(--text-muted)" : "var(--status-warn)" }}>{pkgNote}</span>}
          </label>

          {/* Attachments */}
          <div className="samples-toggle" style={{ cursor: "default", marginTop: 16 }} onClick={() => fileRef.current?.click()}>
            📎 Attach files <span style={{ color: "var(--text-muted)" }}>(groovy, xml/json, xslt, xsd, iflw, zip, images — ground the build)</span>
          </div>
          <input ref={fileRef} type="file" multiple hidden accept={ACCEPT} onChange={onFiles} />
          {attachments.length > 0 && (
            <div className="att-list">
              {attachments.map((a, i) => (
                <div className="att-row" key={i}>
                  <span className="pill pill--info">{a.kind}</span>
                  <span className="att-row__name">{a.name}</span>
                  {!a.content && a.kind !== "text" && <span className="field__hint">by reference</span>}
                  <button className="link-btn" onClick={() => removeAtt(i)}>remove</button>
                </div>
              ))}
            </div>
          )}

          <button className="samples-toggle" onClick={() => setShowSamples((s) => !s)}>
            {showSamples ? "−" : "+"} Sample Input / Output <span style={{ color: "var(--text-muted)" }}>(optional — improves accuracy)</span>
          </button>
          {showSamples && (
            <div className="form-grid" style={{ marginTop: 12, gridTemplateColumns: "1fr" }}>
              <label className="field"><span className="label-mono">Sample Input</span>
                <textarea className="input" rows={4} value={form.sample_input} placeholder="JSON, XML, CSV payload…" onChange={(e) => set("sample_input", e.target.value)} /></label>
              <label className="field"><span className="label-mono">Sample Output</span>
                <textarea className="input" rows={4} value={form.sample_output} placeholder="Expected response…" onChange={(e) => set("sample_output", e.target.value)} /></label>
            </div>
          )}

          <div className="unlock-note">
            🔒 <b>Unlock before generating.</b> If this iFlow ID already exists in CPI, it must be closed in the web IDE before Generate can overwrite it.
          </div>

          <div className="page__actions" style={{ marginTop: 16 }}>
            <button className="btn btn--primary" onClick={() => run_(false)} disabled={busy !== null || !form.description || overLimit}>
              {busy === "plan" ? "Analysing…" : "Analyse and Plan"}
            </button>
            <button className="btn" onClick={() => run_(true)} disabled={busy !== null || !form.description || overLimit}>
              {busy === "quick" ? "Generating…" : "Quick Generate"}
            </button>
          </div>
          {err && <div className="note-line" style={{ color: "var(--status-failed)" }}>{err}</div>}
        </section>

        <section className="card panel" style={{ padding: 20 }}>
          <div className="label-mono" style={{ marginBottom: 14 }}>Orchestrator</div>
          {!run && <div style={{ color: "var(--text-muted)" }}>Run a plan to see the state machine, design brief and generated iFlow.</div>}

          {run && (
            <>
              <div className="stepline">
                {run.steps.map((s, i) => (
                  <div key={i} className={`step step--${stTone(s.status)}`}>
                    <span className="step__dot" />
                    <span className="step__label">{STAGE_LABELS[s.state] ?? s.state}</span>
                    <span className="step__detail">{s.detail}</span>
                  </div>
                ))}
              </div>

              {run.brief && (
                <div className="brief">
                  <div className="label-mono">Design brief</div>
                  <div className="brief__summary">{run.brief.summary}</div>
                  <ol className="brief__steps">{(run.brief.steps ?? []).map((s, i) => <li key={i}>{s}</li>)}</ol>
                  <div className="brief__meta"><b>Error handling:</b> {run.brief.error_handling}</div>
                  <div className="brief__meta"><b>Security:</b> {run.brief.security}</div>
                  <div className="cites">{run.citations.map((c) => <span key={c.doc_id} className="pill pill--info" title={c.title}>{c.doc_id}</span>)}</div>
                </div>
              )}

              {run.status === "awaiting_approval" && (
                <div className="page__actions" style={{ marginTop: 16 }}>
                  <button className="btn btn--primary" onClick={onApprove} disabled={busy !== null}>{busy === "approve" ? "Generating…" : "Approve & generate"}</button>
                  <button className="btn" onClick={onRevise} disabled={busy !== null}>Revise</button>
                </div>
              )}

              {run.score && (
                <div className={`gate gate--${run.score.passed ? "ok" : "fail"}`}>
                  <div className="gate__score">{run.score.total}<span>/100</span></div>
                  <div>
                    <div className="gate__status">{run.score.status}</div>
                    <div className="gate__crit">{run.score.criteria.map((c) => (
                      <span key={c.name} className={c.passed ? "ok" : "fail"}>{c.passed ? "✓" : "✕"} {c.name}</span>
                    ))}</div>
                  </div>
                </div>
              )}

              {run.status === "awaiting_deploy" && (
                <div style={{ marginTop: 12 }}>
                  <div className="note-line" style={{ color: "var(--status-warn)", marginBottom: 10 }}>
                    🔒 Passed the gate. Deploy will create the iFlow in package <b>{form.package}</b> on your tenant and attempt activation.
                  </div>
                  <button className="btn btn--primary" onClick={onDeploy} disabled={busy !== null}>
                    {busy === "deploy" ? "Deploying…" : "🚀 Deploy to tenant"}
                  </button>
                  <span className="field__hint" style={{ marginLeft: 12 }}>
                    Requires a live CPI connection (Settings). The skeleton’s adapters may still need configuration in the Web IDE.
                  </span>
                </div>
              )}

              {run.status === "done" && (
                <div className="note-line" style={{ color: "var(--status-success)", marginTop: 12 }}>
                  ✓ Written to tenant. See the run steps above for the create/deploy result.
                </div>
              )}

              {run.artifact && (
                <div style={{ marginTop: 16 }}>
                  <div className="label-mono" style={{ marginBottom: 8 }}>Generated iFlow (BPMN2)</div>
                  <pre className="code" style={{ maxHeight: 420 }}>{run.artifact}</pre>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
