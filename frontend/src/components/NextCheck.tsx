import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, CheckCircle2, Clock } from "lucide-react";
import { api, CaseResult, NextCheck } from "../api";
import { Refs, Spinner } from "./ui";

export function NextCheckSlip({ caseId, nc, names }: { caseId: string; nc: NextCheck; names: Record<string, string> }) {
  const [a, b] = nc.hypotheses;
  return (
    <section className="slip" aria-labelledby="slip-h">
      <div className="eyebrow slip-eyebrow" id="slip-h">Next best check</div>
      <p className="slip-instruction">{nc.label}</p>
      <ul className="slip-results">
        {nc.outcomes.map((o) => (
          <li key={o.key}>
            <span className="if">If</span> <strong>{o.label.toLowerCase()}</strong> <ArrowRight size={14} aria-hidden /> {o.then}
          </li>
        ))}
      </ul>
      <p className="slip-cost"><Clock size={13} aria-hidden /> About {nc.cost_min} minutes on site. Separates {names[a]?.toLowerCase()} from {names[b]?.toLowerCase()}.</p>
      <Link to={`/case/${caseId}/check`} className="btn btn-inverse">
        Open field checklist <ArrowRight size={15} aria-hidden />
      </Link>
    </section>
  );
}

export function VisitChecklist({ items }: { items: string[] }) {
  const [done, setDone] = useState<Record<number, boolean>>({});
  const n = Object.values(done).filter(Boolean).length;
  return (
    <section className="slip slip-plain" aria-labelledby="vc-h">
      <p className="cl-kicker" id="vc-h">Look at each of these</p>
      <p className="slip-instruction">No single check tells the causes apart, so go through the list once and tick what you looked at.</p>
      <ul className="visit-list">
        {items.map((t, i) => (
          <li key={i}>
            <label className={done[i] ? "on" : ""}>
              <input type="checkbox" checked={!!done[i]} onChange={() => setDone((d) => ({ ...d, [i]: !d[i] }))} />
              <span>{t}</span>
            </label>
          </li>
        ))}
      </ul>
      <p className="slip-cost" aria-live="polite">{n} of {items.length} looked at</p>
    </section>
  );
}

export function CandidatesTable({ r }: { r: CaseResult }) {
  const nc = r.next_check;
  if (!nc || nc.hypotheses.length < 2) return null;
  const [a, b] = nc.hypotheses;
  const name = (id: string) => r.hypotheses.find((h) => h.id === id)?.name ?? id;
  return (
    <details className="candidates">
      <summary>Why this check?</summary>
      <p className="muted small">
        Score is how cleanly a result separates {name(a).toLowerCase()} from {name(b).toLowerCase()}, divided by minutes on site.
        Checks that do not apply to this case are left out.
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>Check</th><th>Cost</th><th>Splits {a} vs {b}?</th><th>Score</th></tr>
          </thead>
          <tbody>
            {nc.candidates.map((c) => (
              <tr key={c.check_id} className={c.chosen ? "winner" : ""}>
                <td>{c.short}{c.chosen && <span className="chosen"><Check size={13} strokeWidth={3} aria-hidden /> Chosen</span>}</td>
                <td>{c.cost_min} min</td>
                <td>{c.split === 1 ? "Yes" : c.split === 0.5 ? "One way" : "No"}</td>
                <td>{c.score.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function CloseCaseForm({ r, onSaved, large = false }: { r: CaseResult; onSaved: (r: CaseResult) => void; large?: boolean }) {
  const nc = r.next_check;
  const [choice, setChoice] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!nc) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!choice) return;
    setBusy(true);
    setError("");
    try {
      onSaved(await api.close(r.case_id, { check_id: nc.check_id, outcome: choice, note }));
    } catch (err: any) {
      setError(err.message || "Could not save the finding.");
      setBusy(false);
    }
  };

  return (
    <form className={`close-form ${large ? "large" : ""}`} onSubmit={submit} aria-labelledby="close-h">
      <div>
        <h3 id="close-h">Record what you found</h3>
        <p className="close-sub">It is saved with the case as new evidence, and the likely cause is updated.</p>
      </div>
      <fieldset>
        <legend>What did you find?{!large && <small>{nc.label}</small>}</legend>
        <div className="chips">
          {nc.outcomes.map((o) => (
            <label key={o.key} className={`chip ${choice === o.key ? "on" : ""}`}>
              <input type="radio" name="result" value={o.key} checked={choice === o.key} onChange={() => setChoice(o.key)} />
              <i aria-hidden>{choice === o.key && <Check size={13} strokeWidth={3} />}</i>
              <span>{o.label}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <label className="field">
        <span className="field-label">Anything else you saw <small>(optional)</small></span>
        <textarea rows={3} maxLength={600} value={note} onChange={(e) => setNote(e.target.value)} placeholder="For example, the valve at the east end was clogged with silt" />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="btn btn-primary" disabled={!choice || busy}>
        {busy ? <Spinner /> : <CheckCircle2 size={16} aria-hidden />} {choice ? "Save and close the case" : "Choose what you found first"}
      </button>
    </form>
  );
}

export function ResolutionCard({ r }: { r: CaseResult }) {
  const res = r.resolution;
  if (!res) return null;
  const evId = r.evidence[r.evidence.length - 1]?.id;
  return (
    <section className="resolution" aria-labelledby="res-h">
      <p className="res-head" id="res-h"><CheckCircle2 size={16} aria-hidden /> Confirmed on the ground</p>
      <p className="res-title">{res.confirmed_name} {res.confirmed_id === r.hypotheses[0]?.id ? "confirmed" : "is now the likely cause"}</p>
      <p>{res.outcome_label}.{res.note && <> &ldquo;{res.note}&rdquo;</>} <Refs ids={evId ? [evId] : []} /></p>
      <p className="res-when">Closed {new Date(res.closed_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}. The case now includes this finding.</p>
    </section>
  );
}
