import { Link, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, ClipboardList, Clock, Eye, EyeOff, MapPinned } from "lucide-react";
import { api, CaseResult } from "../api";
import { fmtDate } from "../lib/format";
import { CloseCaseForm, ResolutionCard, VisitChecklist } from "../components/NextCheck";

const cap = (t: string) => t.replace(/^./, (c) => c.toUpperCase());

/** Phone-first: one column, large tap targets, the instruction and the close form together. */
export default function Checklist() {
  const { id = "" } = useParams();
  const [r, setR] = useState<CaseResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getCase(id).then(setR).catch((e) => setError(e.message));
  }, [id]);

  if (error) return <main className="page narrow"><Link to={`/case/${id}`} className="back"><ArrowLeft size={15} aria-hidden /> Back to the case</Link><p className="form-error" role="alert">{error}</p></main>;
  if (!r) return <main className="page narrow"><div className="skeleton-rows" aria-busy="true">{[0, 1].map((i) => <span key={i} />)}</div></main>;

  const nc = r.next_check;
  const names = Object.fromEntries(r.hypotheses.map((h) => [h.id, h.name.toLowerCase()]));
  const quiet = r.outcome === "watch" || r.outcome === "auto_dismissed" || r.outcome === "area_alert";

  return (
    <main className="page narrow checklist">
      <Link to={`/case/${r.case_id}`} className="back"><ArrowLeft size={15} aria-hidden /> Back to {r.field.name}</Link>
      <header className="cl-head">
        <p className="home-where"><ClipboardList size={14} aria-hidden /> Field checklist</p>
        <h1>{r.field.name}</h1>
        <p className="meta">
          {r.field.class_label}, {r.field.area_ha} ha{r.field.mode === "whole" ? ", read as one zone" : ""}. Alert raised {fmtDate(r.alert_date)}.
        </p>
      </header>

      {r.outcome === "field_case" && nc && (
        <>
          <section className="slip cl-slip" aria-labelledby="cl-h">
            <p className="cl-kicker" id="cl-h">Do this at the field</p>
            <p className="slip-instruction">{nc.label}</p>
            <p className="slip-cost">
              <Clock size={14} aria-hidden /> About {nc.cost_min} minutes. It tells {names[nc.hypotheses[0]]} apart from {names[nc.hypotheses[1]]}.
            </p>
          </section>

          <section className="means" aria-labelledby="means-h">
            <h2 id="means-h">What each result means</h2>
            <ul>
              {nc.outcomes.map((o) => (
                <li key={o.key}>
                  <strong>{o.label}</strong>
                  <span><ArrowRight size={14} aria-hidden /> {cap(o.then)}</span>
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
          <Link to={`/case/${r.case_id}`} className="btn btn-primary btn-block cl-done">Back to the case <ArrowRight size={15} aria-hidden /></Link>
        </>
      )}

      {r.outcome === "unexplained" && (
        <>
          <VisitChecklist items={r.visit_checklist} />
          <CloseCaseForm r={r} onSaved={setR} large />
        </>
      )}

      {quiet && (
        <section className="cl-quiet">
          {r.outcome === "watch" ? <Eye size={18} aria-hidden /> : r.outcome === "area_alert" ? <MapPinned size={18} aria-hidden /> : <EyeOff size={18} aria-hidden />}
          <div>
            <strong>{r.outcome === "watch" ? "Nobody needs to go out yet" : r.outcome === "area_alert" ? "The whole area changed, not this field alone" : "No visit needed"}</strong>
            <p>
              {cap(r.stage_outcome?.reason ?? "This case was settled without a visit")}.
              {r.stage_outcome?.confirm_with && <> {r.stage_outcome.confirm_with}</>}
            </p>
          </div>
        </section>
      )}
    </main>
  );
}
