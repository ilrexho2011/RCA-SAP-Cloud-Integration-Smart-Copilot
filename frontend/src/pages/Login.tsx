/* Login / Register — gate for the app (QDKEP theme). */
import { useState } from "react";
import { login, register } from "../api";

export default function Login({ onAuthed }: { onAuthed: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password);
      onAuthed();
    } catch (ex) { setErr(ex instanceof Error ? ex.message : "Failed"); }
    finally { setBusy(false); }
  }

  return (
    <div className="login">
      <div className="login__card card">
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
          <img src="/brand/rca-logo-white.png" alt="RealCore Albania" style={{ width: 130 }} />
        </div>
        <div className="eyebrow">AI Copilot for SAP Cloud Integration</div>
        <h1 className="login__title">Smart Copilot</h1>
        <p className="page__sub" style={{ marginBottom: 20 }}>
          {mode === "login" ? "Sign in to your workspace." : "Create your workspace."}
        </p>

        <form onSubmit={submit}>
          <label className="field">
            <span className="label-mono">Email</span>
            <input className="input" type="email" value={email} required onChange={(e) => setEmail(e.target.value)} placeholder="name@company.com" />
          </label>
          <label className="field" style={{ marginTop: 14 }}>
            <span className="label-mono">Password</span>
            <input className="input" type="password" value={password} required minLength={8} onChange={(e) => setPassword(e.target.value)} placeholder="min 8 characters" />
          </label>
          <button className="btn btn--primary" type="submit" disabled={busy} style={{ width: "100%", marginTop: 20, justifyContent: "center" }}>
            {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        {err && <div className="note-line" style={{ color: "var(--status-failed)" }}>{err}</div>}

        <div className="note-line" style={{ color: "var(--text-muted)" }}>
          {mode === "login" ? "No account yet?" : "Already have an account?"}{" "}
          <button className="link-btn" onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(null); }}>
            {mode === "login" ? "Register" : "Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}
