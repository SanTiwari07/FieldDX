import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, CheckCircle2, Clock, RefreshCw } from "lucide-react";
import { api, CaseResult, Movement, NextCheck } from "../api";
import { Refs, Spinner } from "./ui";

/** What the check is for: separating two causes, testing the one left, or (for a call or visit) nothing named. */
export function checkPurpose(nc: NextCheck, names: Record<string, string>): string {
  const [a, b] = nc.hypotheses.map((h) => names[h]?.toLowerCase());
  if (a && b) return `Separates ${a} from ${b}.`;
  if (a) return `Can support or count against ${a}.`;
  return "";
}

export function NextCheckSlip({ caseId, nc, names }: { caseId: string; nc: NextCheck; names: Record<string, string> }) {
  return (
    <section className="slip" aria-labelledby="slip-h">
      <div className="eyebrow slip-eyebrow" id="slip-h">Next best check</div>
      <p className="slip-instruction">{nc.label}</p>
      {nc.reason && <p className="slip-reason">{nc.reason}</p>}
      <ul className="slip-results">
        {nc.outcomes.map((o) => (
          <li key={o.key}>
            <span className="if">If</span> <strong>{o.label.toLowerCase()}</strong> <ArrowRight size={14} aria-hidden /> {o.then}
          </li>
        ))}
      </ul>
      <p className="slip-cost"><Clock size={13} aria-hidden /> About {nc.cost_min} minutes on site. {checkPurpose(nc, names)}</p>
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
      onSaved(await api.recordFinding(r.case_id, { check_id: nc.check_id, outcome: choice, note }));
    } catch (err: any) {
      setError(err.message || "Could not save the finding.");
      setBusy(false);
    }
  };

  return (
    <form className={`close-form ${large ? "large" : ""}`} onSubmit={submit} aria-labelledby="close-h">
      <div>
        <h3 id="close-h">Record what you found</h3>
        <p className="close-sub">It is saved with the case as new evidence. The causes are re-assessed and the case stays open.</p>
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
        {busy ? <Spinner /> : <CheckCircle2 size={16} aria-hidden />} {choice ? "Save the finding" : "Choose what you found first"}
      </button>
    </form>
  );
}

const MOVES: Record<Movement, { glyph: string; word: string }> = {
  more_likely: { glyph: "↑", word: "More likely" },
  less_likely: { glyph: "↓", word: "Less likely" },
  ruled_out: { glyph: "✕", word: "Ruled out" },
  newly_considered: { glyph: "+", word: "Newly considered" },
  unchanged: { glyph: "=", word: "Unchanged" },
};

/** A word and a glyph, never colour alone. */
export function MoveChip({ m }: { m: Movement }) {
  const { glyph, word } = MOVES[m];
  return <span className={`mv mv-${m}`}><span aria-hidden>{glyph}</span> {word}</span>;
}

/** What the latest finding changed: quiet, factual, and the case stays open. */
export function InvestigationUpdate({ r }: { r: CaseResult }) {
  const u = r.update;
  if (!u) return null;
  return (
    <section className="update" aria-labelledby="upd-h">
      <p className="update-pill" id="upd-h"><RefreshCw size={13} aria-hidden /> Investigation updated · still open</p>
      <p className="update-finding">
        <strong>{u.check_label}:</strong> {u.outcome_label.toLowerCase()}.{u.note && <> &ldquo;{u.note}&rdquo;</>} <Refs ids={[u.evidence_id]} />
      </p>
      <ol className="update-moves">
        {u.moves.map((m) => (
          <li key={m.id}>
            <div className="um-row">
              <MoveChip m={m.movement} />
              <strong>{m.name}</strong>
              <span className="um-rank">{m.before_rank === m.after_rank ? `#${m.after_rank}` : `#${m.before_rank} → #${m.after_rank}`}</span>
            </div>
            <p className="um-reason">{m.reason} {m.evidence_ids.length > 0 && <Refs ids={m.evidence_ids} />}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
