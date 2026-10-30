/* Groovy — generate CPI Groovy scripts with lightweight orchestration. */
import { useState } from "react";
import { generateGroovy, type GroovyResult } from "../api";

export default function Groovy() {
  const [description, setDescription] = useState("");
  const [result, setResult] = useState<GroovyResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function onGenerate() {
    setBusy(true); setErr(null); setResult(null); setCopied(false);
    try { setResult(await generateGroovy(description)); }
    catch (e) { setErr(e instanceof Error ? e.message : "Failed"); } finally { setBusy(false); }
  }
  function onCopy() {
    if (result) { navigator.clipboard.writeText(result.script); setCopied(true); setTimeout(() => setCopied(false), 1500); }
  }

  return (
    <div className="page page--wide">
      <div className="eyebrow">Script generation with AI assistance</div>
      <h2 className="page__title">Groovy</h2>
      <p className="page__sub">Describe the logic — the script is generated, then statically validated.</p>

      <div className="gen-grid gen-grid--wide">
        <section className="card panel groovy-form" style={{ padding: 20 }}>
          <div>
            <div className="label-mono" style={{ marginBottom: 12 }}>What should the script do?</div>
            <textarea className="input" rows={10} value={description}
              placeholder="Parse the body as JSON, count the Orders array, set property RCA_Status to the count, and add a log attachment."
              onChange={(e) => setDescription(e.target.value)} />
            {err && <div className="note-line" style={{ color: "var(--status-failed)" }}>{err}</div>}
          </div>
          <button className="btn btn--primary groovy-form__go" onClick={onGenerate} disabled={busy || !description}>
            {busy ? "Generating…" : "Generate script"}
          </button>
        </section>

        <section className="card panel" style={{ padding: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <span className="label-mono">Generated script</span>
            {result && <button className="btn btn--ghost" onClick={onCopy}>{copied ? "Copied ✓" : "Copy"}</button>}
          </div>
          {!result && <div style={{ color: "var(--text-muted)" }}>Generate a script to see the orchestration trace, code and validation.</div>}
          {result && (
            <>
              <div className="stepline">
                {result.steps.map((s, i) => (
                  <div key={i} className={`step step--${s.status === "fail" ? "fail" : "ok"}`}>
                    <span className="step__dot" /><span className="step__label">{s.label}</span><span className="step__detail">{s.detail}</span>
                  </div>
                ))}
              </div>
              <pre className="code">{result.script}</pre>
              <div className="gate__crit" style={{ marginTop: 12 }}>
                {result.validation.checks.map((c) => (
                  <span key={c.name} className={c.passed ? "ok" : "fail"}>{c.passed ? "✓" : "✕"} {c.name}</span>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
