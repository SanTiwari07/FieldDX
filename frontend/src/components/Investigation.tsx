import { Check, Minus, Circle, RotateCcw } from "lucide-react";
import type { Evidence } from "../api";
import { Phase, STEPS, StepState } from "../hooks";
import { sentence } from "../lib/format";
import { EvidenceCard } from "./Evidence";
import { Refs, Spinner } from "./ui";

function StepRow({ title, running, st }: { title: string; running: string; st: StepState }) {
  const line =
    st.state === "done" ? sentence(st.summary ?? "") : st.state === "skipped" ? st.reason : st.state === "running" ? `${running}…` : "Waiting";
  return (
    <div className={`step step-${st.state}`}>
      <span className="step-icon" aria-hidden>
        {st.state === "done" && <Check size={14} strokeWidth={2.75} />}
        {st.state === "skipped" && <Minus size={14} strokeWidth={2.75} />}
        {st.state === "running" && <Spinner />}
        {st.state === "queued" && <Circle size={12} />}
      </span>
      <div className="step-body">
        <div className="step-head">
          <strong>{title}</strong>
          <span className="step-state">
            {st.state === "done" ? "Done" : st.state === "skipped" ? "Skipped" : st.state === "running" ? "Running" : "Waiting"}
          </span>
          {st.state === "done" && st.evidenceIds && <Refs ids={st.evidenceIds} />}
        </div>
        <p>{line}</p>
      </div>
    </div>
  );
}

export function InvestigationRail({
  steps, evidence, phase, onReplay,
}: {
  steps: Record<string, StepState>;
  evidence: Evidence[];
  phase: Phase;
  onReplay: () => void;
}) {
  const visit = evidence.filter((e) => e.tool === "field_visit");
  return (
    <section aria-labelledby="inv-h" className="rail-section">
      <h2 id="inv-h" className="sr-only">Investigation</h2>
      <div className="section-head">
        <p className="section-sub">Each check runs on the cached data and leaves a piece of evidence. The diagnosis can only cite what is here.</p>
        <button type="button" className="btn btn-ghost" onClick={onReplay} disabled={phase === "running" || phase === "loading"}>
          <RotateCcw size={14} aria-hidden /> Replay
        </button>
      </div>
      <div className="steps" aria-live="polite">
        {STEPS.map((s) => (
          <div key={s.tool} className={steps[s.tool].state === "queued" ? "" : "step-in"}>
            <StepRow title={s.title} running={s.running} st={steps[s.tool]} />
            {evidence.filter((e) => e.tool === s.tool).map((e) => (
              <div key={e.id} className="step-in ev-wrap">
                <EvidenceCard e={e} />
              </div>
            ))}
          </div>
        ))}
        {visit.map((e) => (
          <div key={e.id} className="step-in">
            <div className="step step-done">
              <span className="step-icon" aria-hidden><Check size={14} strokeWidth={2.75} /></span>
              <div className="step-body">
                <div className="step-head"><strong>Field visit</strong><span className="step-state">Recorded</span><Refs ids={[e.id]} /></div>
              </div>
            </div>
            <div className="ev-wrap"><EvidenceCard e={e} /></div>
          </div>
        ))}
      </div>
    </section>
  );
}
