import { FormEvent, Fragment, ReactNode, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ArrowUp, ArrowUpRight, MessageCircleQuestion, X } from "lucide-react";
import { api, AskAnswer, AskTurn } from "../api";
import { useSession } from "../session";
import { flashEvidence, Spinner } from "./ui";

interface Msg extends AskTurn {
  sources?: AskAnswer["sources"];
  mode?: AskAnswer["mode"];
  error?: boolean;
}

const AREA_QUESTIONS = [
  "Which fields should I visit first today?",
  "Which drops are only harvest?",
  "How much rain fell in the last three weeks?",
];
const CASE_QUESTIONS = [
  "Explain this field in simple words",
  "What should I ask the farmer?",
  "Why not pest or disease?",
  "How sure is FieldDx about this?",
];

/** Answer text with [F128], [F128 E2] and [E2] turned into links to the field, or to the evidence on this page. */
function Cited({ text, caseId }: { text: string; caseId?: string }) {
  const parts = text.split(/(\[(?:F\d{3,4}|E\d+)(?:[ ,]+E\d+)*\])/g);
  return (
    <>
      {parts.map((p, i) => {
        const m = p.match(/^\[(F\d{3,4})?[ ,]*((?:E\d+[ ,]*)*)\]$/);
        if (!m) return <Fragment key={i}>{p}</Fragment>;
        const field = m[1] ?? caseId;
        const evs = m[2].match(/E\d+/g) ?? [];
        if (field === caseId) {
          // the open field: its name is on the page already, so only its evidence is worth a chip
          if (!evs.length) return null;
          return <span key={i} className="ask-ref">{evs.map((e) => <button key={e} type="button" onClick={() => flashEvidence(e)} title="Show this evidence">{e}</button>)}</span>;
        }
        if (!field) return <Fragment key={i}>{p}</Fragment>;
        const name = field.replace(/^F/, "Field ");
        // "Field 071 [F071]": the name is already there, so the chip is only the way to open it
        const named = new RegExp(`Field 0*${field.replace(/^F0*/, "")}\\W*$`).test(parts[i - 1] ?? "");
        return (
          <Link key={i} className={`ask-ref ${named ? "is-icon" : ""}`} to={`/case/${field}`} aria-label={`Open ${name}`} title={`Open ${name}`}>
            {named ? <ArrowUpRight size={13} aria-hidden /> : name}
          </Link>
        );
      })}
    </>
  );
}

const BULLET = /^\s*([-*•]|\d+\.)\s+/;

/** Paragraphs and lists, from the plain text the assistant writes. */
function Paras({ text, caseId }: { text: string; caseId?: string }) {
  const out: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) out.push(<ul key={`u${out.length}`}>{list.map((l, j) => <li key={j}><Cited text={l} caseId={caseId} /></li>)}</ul>);
    list = [];
  };
  for (const raw of text.replace(/\*\*/g, "").split("\n")) {
    const line = raw.trim();
    if (!line) { flush(); continue; }
    if (BULLET.test(line)) { list.push(line.replace(BULLET, "")); continue; }
    flush();
    out.push(<p key={`p${out.length}`}><Cited text={line} caseId={caseId} /></p>);
  }
  flush();
  return <>{out}</>;
}

/**
 * Ask FieldDx: questions about the officer's fields, answered from the area's own case data.
 * On a case page it is about that field; elsewhere about the whole area.
 */
export function AskPanel({ caseId, fieldName, intro }: { caseId?: string; fieldName?: string; intro?: ReactNode }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { setMsgs([]); }, [caseId]);
  useEffect(() => { end.current?.scrollIntoView({ block: "end", behavior: "smooth" }); }, [msgs, busy]);

  const send = async (text: string) => {
    const question = text.trim();
    if (!question || busy) return;
    const history: AskTurn[] = msgs.filter((m) => !m.error).map(({ role, text: t }) => ({ role, text: t }));
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setQ("");
    setBusy(true);
    try {
      const a = await api.ask({ question, case_id: caseId, history });
      setMsgs((m) => [...m, { role: "assistant", text: a.answer, sources: a.sources, mode: a.mode }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", text: `Could not get an answer: ${(e as Error).message}`, error: true }]);
    } finally {
      setBusy(false);
      box.current?.focus();
    }
  };

  const submit = (e: FormEvent) => { e.preventDefault(); void send(q); };
  const ideas = caseId ? CASE_QUESTIONS : AREA_QUESTIONS;

  return (
    <div className="ask">
      <div className="ask-log" aria-live="polite">
        {!msgs.length && (
          <div className="ask-empty">
            {intro ?? <p>Ask about {fieldName ?? "any field in your area"}. Answers come only from FieldDx's own records of your fields, with the field cited.</p>}
            <div className="ask-ideas">
              {ideas.map((t) => <button key={t} type="button" onClick={() => send(t)}>{t}</button>)}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`ask-msg ask-${m.role} ${m.error ? "is-error" : ""}`}>
            {m.role === "user" ? <p>{m.text}</p> : <Paras text={m.text} caseId={caseId} />}
            {m.sources && m.sources.some((s) => s.cited || !caseId) && (
              <div className="ask-sources">
                <span>From</span>
                {m.sources.filter((s) => s.cited || !caseId).slice(0, 4).map((s) => (
                  s.link && s.id !== caseId
                    ? <Link key={s.id} to={s.link}>{s.title}</Link>
                    : <span key={s.id} className="src-plain">{s.title}</span>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="ask-msg ask-assistant ask-wait"><Spinner size={14} /> Reading the field records</div>}
        <div ref={end} />
      </div>
      <form className="ask-form" onSubmit={submit}>
        <textarea ref={box} value={q} rows={1} maxLength={600} placeholder={caseId ? "Ask about this field" : "Ask about your fields"}
          aria-label="Your question" onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(q); } }} />
        <button type="submit" className="ask-send" aria-label="Ask" disabled={!q.trim() || busy}><ArrowUp size={18} aria-hidden /></button>
      </form>
    </div>
  );
}

/** The Ask button on the briefing and the inbox. A case page has its own Ask tab instead. */
export function AskLauncher() {
  const { me } = useSession();
  const loc = useLocation();
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open]);
  if (me?.area?.status !== "ready" || loc.pathname.startsWith("/case/") || loc.pathname === "/setup") return null;
  return (
    <>
      {!open && (
        <button type="button" className="ask-fab" onClick={() => setOpen(true)}>
          <MessageCircleQuestion size={20} aria-hidden /> Ask FieldDx
        </button>
      )}
      {(
        <aside className="ask-drawer" aria-label="Ask FieldDx" hidden={!open}>
          <header>
            <div><strong>Ask FieldDx</strong><small>About the fields in {me.area.name}</small></div>
            <button type="button" className="icon-btn" aria-label="Close" onClick={() => setOpen(false)}><X size={18} aria-hidden /></button>
          </header>
          <AskPanel />
        </aside>
      )}
    </>
  );
}
