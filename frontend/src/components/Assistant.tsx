/* Floating AI Assistant — grounded chat over the tenant's live inventory + RAG. */
import { useEffect, useRef, useState } from "react";
import { assistantChat, type ChatMessage } from "../api";

const SUGGESTIONS = [
  "Why did my iFlow fail?",
  "Error handling best practice",
  "How many failed messages today?",
  "JMS adapter setup",
];

export default function Assistant() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight }); }, [messages, busy]);

  async function send(text?: string) {
    const content = (text ?? input).trim();
    if (!content || busy) return;
    const next = [...messages, { role: "user" as const, content }];
    setMessages(next); setInput(""); setBusy(true);
    try {
      const r = await assistantChat(next);
      setMessages([...next, { role: "assistant", content: r.reply }]);
    } catch {
      setMessages([...next, { role: "assistant", content: "Couldn't reach the assistant. Try again." }]);
    } finally { setBusy(false); }
  }

  return (
    <>
      <button className="asst-fab" onClick={() => setOpen((o) => !o)} aria-label="AI Assistant">
        {open ? "×" : "✦"}
      </button>
      {open && (
        <div className="asst">
          <div className="asst__head">
            <span><span className="asst__dot" /> AI Assistant <span className="label-mono" style={{ color: "var(--status-success)" }}>online</span></span>
            <button className="link-btn" onClick={() => setOpen(false)}>close</button>
          </div>
          <div className="asst__body" ref={bodyRef}>
            {messages.length === 0 && (
              <div className="asst__empty">
                Ask me anything about SAP CPI, APIM or AEM — iFlow design, monitoring, troubleshooting, or best practices. I'm grounded in your live inventory.
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`asst__msg asst__msg--${m.role}`}>{m.content}</div>
            ))}
            {busy && <div className="asst__msg asst__msg--assistant asst__typing">Thinking…</div>}
          </div>
          {messages.length === 0 && (
            <div className="asst__sugg">
              {SUGGESTIONS.map((s) => <button key={s} className="pill" style={{ cursor: "pointer" }} onClick={() => send(s)}>{s}</button>)}
            </div>
          )}
          <div className="asst__input">
            <input className="input" value={input} placeholder="Ask about SAP CPI…"
              onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") send(); }} />
            <button className="btn btn--primary" onClick={() => send()} disabled={busy || !input.trim()}>➤</button>
          </div>
        </div>
      )}
    </>
  );
}
