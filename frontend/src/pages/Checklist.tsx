import { Link, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Clock } from "lucide-react";
import { api, CaseResult } from "../api";
import { CROP_LABEL, fmtDate } from "../lib/format";
import { CloseCaseForm, ResolutionCard, VisitChecklist } from "../components/NextCheck";
import { ScenarioBanner } from "../components/ui";

/** Phone-first: one column, large tap targets, the instruction and the close form together. */
export default function Checklist() {
  const { id = "" } = useParams();
  const [r, setR] = useState<CaseResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getCase(id).then(setR).catch((e) => setError(e.message));
  }, [id]);

  if (error) return <main className="page narrow"><p className="form-error" role="alert">{error}</p></main>;
  if (!r) return <main className="page narrow"><div className="skeleton-rows" aria-busy="true">{[0, 1].map((i) => <span key={i} />)}</div></main>;

  const nc = r.next_check;
  const names = Object.fromEntries(r.hypotheses.map((h) => [h.id, h.name]));

  return (
    <main className="page narrow checklist">
      <Link to={`/case/${r.case_id}`} className="back"><ArrowLeft size={15} aria-hidden /> Back to case</Link>
      <div className="eyebrow">Field checklist · {fmtDate(r.alert_date)}</div>
      <h1>{r.field.name}</h1>
      <p className="meta">{CROP_LABEL[r.field.crop]} · {r.field.area_ha} ha</p>
      {r.replayed && <ScenarioBanner text={r.banner} />}

      {r.outcome === "field_case" && nc && (
        <>
          <section className="slip" aria-labelledby="cl-h">
            <div className="eyebrow slip-eyebrow" id="cl-h">Do this on site</div>
            <p className="slip-instruction">{nc.label}</p>
            <p className="slip-cost"><Clock size={13} aria-hidden /> About {nc.cost_min} minutes. Tells {names[nc.hypotheses[0]]?.toLowerCase()} apart from {names[nc.hypotheses[1]]?.toLowerCase()}.</p>
          </section>

          <section className="means" aria-labelledby="means-h">
            <h2 id="means-h">What each result means</h2>
            <ul>
              {nc.outcomes.map((o) => (
                <li key={o.key}>
                  <strong>{o.label}</strong>
                  <ArrowRight size={14} aria-hidden />
                  <span>{o.then}</span>
                </li>
              ))}
            </ul>
          </section>

          <CloseCaseForm r={r} onSaved={setR} large />
        </>
      )}

      {r.outcome === "resolved" && (
        <>
          <ResolutionCard r={r} />
          <Link to={`/case/${r.case_id}`} className="btn btn-primary">See the updated ranking <ArrowRight size={15} aria-hidden /></Link>
        </>
      )}

      {r.outcome === "unexplained" && <VisitChecklist items={r.visit_checklist} />}

      {(r.outcome === "auto_dismissed" || r.outcome === "area_alert") && (
        <p className="lede">This case was closed at an earlier stage ({r.stage_outcome?.reason}). No visit needed.
          {r.stage_outcome?.confirm_with && <> {r.stage_outcome.confirm_with}</>}</p>
      )}
    </main>
  );
}
