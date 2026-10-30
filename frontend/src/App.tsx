import { useEffect, useState } from "react";
import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Generate from "./pages/Generate";
import Iflows from "./pages/Iflows";
import Groovy from "./pages/Groovy";
import Monitor from "./pages/Monitoring";
import Knowledge from "./pages/Knowledge";
import Settings from "./pages/Settings";
import Login from "./pages/Login";
import Assistant from "./components/Assistant";
import { me } from "./api";

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null); // null = checking

  useEffect(() => {
    me().then(() => setAuthed(true)).catch(() => setAuthed(false));
    const onUnauth = () => setAuthed(false);
    window.addEventListener("rca-unauth", onUnauth);
    return () => window.removeEventListener("rca-unauth", onUnauth);
  }, []);

  if (authed === null) {
    return <div style={{ display: "grid", placeItems: "center", height: "100vh", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>Loading…</div>;
  }
  if (!authed) return <Login onAuthed={() => setAuthed(true)} />;

  return (
    <div className="app-shell">
      <Sidebar onLogout={() => setAuthed(false)} />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/generate" element={<Generate />} />
          <Route path="/iflows" element={<Iflows />} />
          <Route path="/groovy" element={<Groovy />} />
          <Route path="/monitor" element={<Monitor />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
      <Assistant />
    </div>
  );
}
