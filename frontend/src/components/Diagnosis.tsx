import { BadgeCheck, CircleHelp, Minus, Plus, Sparkles, FileText } from "lucide-react";
import type { CaseResult, Hypothesis, Line } from "../api";
import { useFlip } from "../hooks";
import { ConfidenceMeter, Refs } from "./ui";

function Lines({ kind, lines }: { kind: "for" | "against" | "unknown"; lines: Line[] }) {
  if (!lines.length) return null;
  const meta = {
    for: { glyph: <Plus size={13} strokeWidth={3} />, word: "Supports" },
    against: { glyph: <Minus size={13} strokeWidth={3} />, word: "Against" },
    unknown: { glyph: <CircleHelp size={13} strokeWidth={2.5} />, word: "Unknown" },
  }[kind];
  return (
    <div className={`dx-group dx-${kind}`}>
      <div className="dx-label">{meta.glyph}<span>{meta.word}</span></div>
      <ul>
        {lines.map((l, i) => (
          <li key={i}>
            <span>{l.text}</span> <Refs ids={l.evidence_ids} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function HypothesisCard({ h, rank, confirmed, setRef }: {
  h: Hypothesis; rank: number; confirmed: boolean; setRef: (el: HTMLElement | null) => void;
}) {
  return (
    <article ref={setRef} className={`hyp ${rank === 1 ? "hyp-lead" : ""}`}>
      <header>
        <span className="hyp-rank" aria-label={`Rank ${rank}`}>{rank}</span>
        <h3>{h.name}</h3>
        {confirmed ? (
          <span className="confirmed"><BadgeCheck size={15} aria-hidden /> Confirmed on site</span>
        ) : (
          <ConfidenceMeter level={h.confidence} />
        )}
      </header>
      <Lines kind="for" lines={h.for_lines} />
      <Lines kind="against" lines={h.against_lines} />
      <Lines kind="unknown" lines={h.unknown_lines} />
      {!h.for_lines.length && !h.against_lines.length && <p className="muted small">Nothing in the evidence points this way.</p>}
    </article>
  );
}

export function CaseFilePanel({ r }: { r: CaseResult }) {
  const n = r.narrative;
  if (!n) return <div className="casefile skeleton" aria-busy="true"><span /><span /><span /></div>;
  const names = Object.fromEntries(r.hypotheses.map((h) => [h.id, h.name]));
  return (
    <div className="casefile">
      <div className="casefile-head">
        <FileText size={14} aria-hidden /> <span className="eyebrow">Case file</span>
        <span className="casefile-src">
          {r.narrative_source === "gemini" ? <><Sparkles size={12} aria-hidden /> Written by Gemini, citing evidence only</> : "Narrative from template"}
        </span>
      </div>
      <p className="casefile-summary">{n.summary.text} <Refs ids={n.summary.evidence_ids} /></p>
      <details>
        <summary>Read the full case file</summary>
        <div className="casefile-more">
          {n.hypotheses.map((h) => (
            <div key={h.id}>
              <h4>{names[h.id] ?? h.id}</h4>
              <ul>{h.why.map((w, i) => <li key={i}>{w.text} <Refs ids={w.evidence_ids} /></li>)}</ul>
            </div>
          ))}
          {n.next_check_explainer && (
            <div><h4>Next best check</h4><p>{n.next_check_explainer.text} <Refs ids={n.next_check_explainer.evidence_ids} /></p></div>
          )}
          <div><h4>What the data cannot see</h4><p>{n.limits}</p></div>
        </div>
      </details>
    </div>
  );
}

export function Diagnosis({ r }: { r: CaseResult }) {
  const resolved = r.outcome === "resolved";
  const live = r.hypotheses.filter(
    (h) => (h.stage === 3 && (h.status === "leading" || h.status === "possible")) || (resolved && h.status === "leading"),
  );
  const ruledOut = r.hypotheses.filter((h) => h.status === "ruled_out" && h.brief);
  const flip = useFlip(live.map((h) => h.id));

  return (
    <section aria-labelledby="dx-h" className="rail-section dx">
      <div className="section-head"><h2 id="dx-h">Diagnosis</h2></div>

      {r.stage_outcome && (
        <div className={`outcome-card outcome-${r.stage_outcome.kind}`}>
          <div className="eyebrow">{r.stage_outcome.kind === "area_alert" ? "Area alert" : r.stage_outcome.kind === "watch" ? "Watching" : "Auto-dismissed"}</div>
          <h3>{r.stage_outcome.title.split(": ")[1]?.replace(/^./, (c) => c.toUpperCase()) ?? r.stage_outcome.title}</h3>
          <p className="outcome-reason">{r.stage_outcome.reason}. <Refs ids={r.stage_outcome.evidence_ids} /></p>
          {r.stage_outcome.confirm_with && <p className="outcome-confirm">{r.stage_outcome.confirm_with}</p>}
          {r.stage_outcome.kind === "auto_dismissed" && (
            <p className="muted small">This case never reaches the officer as an alert. It stays in the inbox, muted, so the dismissal can be checked.</p>
          )}
        </div>
      )}

      {r.outcome === "unexplained" && (
        <div className="outcome-card outcome-unexplained">
          <div className="eyebrow">Unexplained</div>
          <h3>Visit: no cause clears the evidence bar</h3>
          <p className="outcome-reason">The drop is real, but the evidence does not separate the causes well enough to name one. FieldDx would rather say so than guess.</p>
        </div>
      )}

      <CaseFilePanel r={r} />

      {live.length > 0 && (!r.stage_outcome || resolved) && (
        <div className="hyp-list">
          {live.map((h, i) => (
            <HypothesisCard key={h.id} h={h} rank={i + 1} confirmed={resolved && i === 0} setRef={flip(h.id)} />
          ))}
        </div>
      )}

      {ruledOut.length > 0 && (
        <div className="ruled-out">
          <div className="eyebrow">Considered and ruled out</div>
          <ul>
            {ruledOut.map((h) => (
              <li key={h.id}>
                <span className="ro-name">{h.name}</span>
                <span className="ro-why">{h.brief}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
