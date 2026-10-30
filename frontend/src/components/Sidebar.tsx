import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { NAV } from "../nav";
import { getConnection, me, logout } from "../api";

export default function Sidebar({ onLogout }: { onLogout: () => void }) {
  const [mode, setMode] = useState<string>("demo");
  const [email, setEmail] = useState<string>("");
  useEffect(() => {
    getConnection().then((c) => setMode(c.mode)).catch(() => {});
    me().then((u) => setEmail(u.email)).catch(() => {});
  }, []);

  function signOut() { logout(); onLogout(); }

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <img src="/brand/rca-logo-white.png" alt="RealCore Albania" className="sidebar__logo" />
        <div className="sidebar__product eyebrow">RCA // v0.1</div>
        <h1 className="sidebar__title">Smart Copilot</h1>
        <p className="sidebar__subtitle">AI Copilot for SAP Cloud Integration</p>
      </div>

      <nav className="sidebar__nav">
        {NAV.map((item) => (
          <NavLink
            key={item.id}
            to={item.path}
            end={item.path === "/"}
            className={({ isActive }) => "navitem" + (isActive ? " navitem--active" : "")}
          >
            <span className="navitem__no">{item.no}</span>
            <span className="navitem__label">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar__footer">
        <div className="label-mono">Environment <span style={{ color: mode === "live" ? "var(--status-success)" : "var(--status-warn)" }}>{mode}</span></div>
        <div className="label-mono">Customer <span style={{ color: "var(--rca-lime)" }}>RCA</span></div>
      </div>

      <div className="sidebar__account">
        {email && <div className="sidebar__email">{email}</div>}
        <button className="link-btn" onClick={signOut}>Sign out</button>
      </div>
    </aside>
  );
}
