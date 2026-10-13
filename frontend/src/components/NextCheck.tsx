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
  return (
    <section className="slip slip-plain" aria-labelledby="vc-h">
      <div className="eyebrow slip-eyebrow" id="vc-h">General visit checklist</div>
      <p className="slip-instruction">No single check separates the causes, so look at everything once.</p>
      <ul className="visit-list">
        {items.map((t, i) => (
          <li key={i}>
            <label>
              <input type="checkbox" checked={!!done[i]} onChange={() => setDone((d) => ({ ...d, [i]: !d[i] }))} />
              <span>{t}</span>
            </label>
          </li>
        ))}
      </ul>
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
      <h3 id="close-h">Close the case</h3>
      <p className="muted small">What did you find? The finding is stored against the case as new evidence and the ranking updates.</p>
      <fieldset>
        <legend className="eyebrow">Result: {nc.label.toLowerCase()}</legend>
        <div className="chips">
          {nc.outcomes.map((o) => (
            <label key={o.key} className={`chip ${choice === o.key ? "on" : ""}`}>
              <input type="radio" name="result" value={o.key} checked={choice === o.key} onChange={() => setChoice(o.key)} />
              <span>{o.label}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <label className="field">
        <span className="eyebrow">What you saw (optional)</span>
        <textarea rows={3} maxLength={600} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Valve at the east end was clogged with silt" />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="btn btn-primary" disabled={!choice || busy}>
        {busy ? <Spinner /> : <CheckCircle2 size={16} aria-hidden />} Save finding and close case
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
      <div className="res-head"><CheckCircle2 size={18} aria-hidden /><span className="eyebrow" id="res-h">Resolved</span></div>
      <p className="res-title">{res.confirmed_name} {res.confirmed_id === r.hypotheses[0]?.id ? "confirmed" : "now leads"}.</p>
      <p>{res.outcome_label}. {res.note && <>&ldquo;{res.note}&rdquo; </>}<Refs ids={evId ? [evId] : []} /></p>
      <p className="muted small">Closed {new Date(res.closed_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}. The ranking above reflects this finding.</p>
    </section>
  );
}
