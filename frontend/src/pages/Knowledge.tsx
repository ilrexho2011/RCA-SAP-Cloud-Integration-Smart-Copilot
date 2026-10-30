/* Knowledge Base — generate governed .md/.json artifacts (KEDB / Runbooks /
   Catalog Docs) from the live inventory + MPL patterns, ready for QDKEP. */
import { useState } from "react";
import { kbGenerate, kbDownload, type KbResult, type KbDoc } from "../api";

const SCOPES = [
  { id: "all", label: "Everything" },
  { id: "errors", label: "MPL error patterns (KEDB + Runbooks)" },
  { id: "common", label: "Common CPI patterns (global)" },
  { id: "catalog", label: "iFlow catalog docs" },
];

const KIND_LABEL: Record<string, string> = {
  kedb: "KEDB", runbook: "Runbook", interface_inventory: "Catalog",
};

export default function Knowledge() {
  const [scope, setScope] = useState("all");
  const [result, setResult] = useState<KbResult | null>(null);
  const [sel, setSel] = useState<KbDoc | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function onGenerate() {
    setBusy("gen"); setErr(null); setResult(null); setSel(null);
    try { const r = await kbGenerate(scope); setResult(r); setSel(r.docs[0] ?? null); }
    catch (e) { setErr(e instanceof Error ? e.message : "Failed"); } finally { setBusy(null); }
  }
  async function onDownload() {
    setBusy("dl"); setErr(null);
    try { await kbDownload(); } catch (e) { setErr(e instanceof Error ? e.message : "Failed"); } finally { setBusy(null); }
  }

  const rd = result?.readiness;
  const tone = (s: number) => (s >= 80 ? "success" : s >= 70 ? "warn" : "failed");

  return (
    <div className="page page--wide">
      <div className="eyebrow">Quality-Driven Knowledge Engineering</div>
      <div className="page__head">
        <div>
          <h2 className="page__title">Knowledge Base</h2>
          <p className="page__sub">Generate governed KEDB, Runbooks and Integration Catalog Docs from the live inventory and MPL patterns — ready for QDKEP ingestion.</p>
        </div>
        <div className="page__actions">
          <select className="input" style={{ minWidth: 240 }} value={scope} onChange={(e) => setScope(e.target.value)}>
            {SCOPES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
          <button className="btn btn--primary" onClick={onGenerate} disabled={busy !== null}>{busy === "gen" ? "Generating…" : "Generate"}</button>
          {result && <button className="btn" onClick={onDownload} disabled={busy !== null}>{busy === "dl" ? "…" : "Download ZIP"}</button>}
        </div>
      </div>
      {err && <div className="note-line" style={{ color: "var(--status-failed)" }}>{err}</div>}

      {result && rd && (
        <>
          <div className={`gate gate--${rd.score >= 70 ? "ok" : "fail"}`} style={{ marginTop: 20 }}>
            <div className={`gate__score kpi-value--${tone(rd.score)}`}>{rd.score}<span>/100</span></div>
            <div>
              <div className="gate__status">{rd.status}</div>
              <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
                {result.manifest.counts.total} docs · {result.manifest.counts.kedb} KEDB · {result.manifest.counts.runbook} runbooks · {result.manifest.counts.interface_inventory} catalog · package {result.manifest.package_id}
              </div>
            </div>
          </div>
          {rd.note && <div className="note-line" style={{ color: "var(--text-muted)" }}>{rd.note}</div>}

          <div className="gen-grid" style={{ gridTemplateColumns: "340px minmax(0, 1fr)" }}>
            <section className="card panel" style={{ padding: 14, maxHeight: 640, overflowY: "auto" }}>
              <div className="label-mono" style={{ marginBottom: 10 }}>Artifacts ({result.docs.length})</div>
              <div className="iflow-list">
                {result.docs.map((d) => (
                  <div key={d.filename} className={"iflow-row" + (sel?.filename === d.filename ? " iflow-row--sel" : "")} style={{ cursor: "pointer" }} onClick={() => setSel(d)}>
                    <div style={{ minWidth: 0 }}>
                      <div className="iflow-row__name" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.filename}</div>
                    </div>
                    <span className="pill pill--info">{KIND_LABEL[d.kind] ?? d.kind}</span>
                  </div>
                ))}
              </div>
            </section>
            <section className="card panel" style={{ padding: 18 }}>
              <div className="label-mono" style={{ marginBottom: 10 }}>{sel?.filename ?? "Preview"}</div>
              <pre className="code" style={{ maxHeight: 600 }}>{sel?.content ?? "Select an artifact to preview."}</pre>
            </section>
          </div>
        </>
      )}
      {!result && !err && (
        <div className="card" style={{ padding: 40, marginTop: 24, color: "var(--text-muted)" }}>
          Pick a scope and Generate. Artifacts follow the AI4BIZ schema (stable metadata, approved headings, BM25-friendly phrasing, preserved MPL evidence) and are scored for ingestion readiness.
        </div>
      )}
    </div>
  );
}
