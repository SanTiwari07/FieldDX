import { BadgeCheck, ChevronRight, CircleSlash, Eye, ListChecks, MapPinned, MessageCircleQuestion, Wheat } from "lucide-react";
import type { CaseResult } from "../api";
import { fmtDate, plainDrop, sureWord } from "../lib/format";

const strip = (t: string) => t.replace(/\s*\[[^\]]*\]/g, "").trim();

/** The headline of a case in one block: what FieldDx thinks happened, and how sure it is. */
function Verdict({ r }: { r: CaseResult }) {
  const lead = r.hypotheses.find((h) => h.status === "leading" && h.stage === 3);
  const said = r.narrative ? strip(r.narrative.summary.text) : "";

  if (r.outcome === "resolved" && r.resolution) {
    return (
      <div className="verdict v-resolved">
        <p className="v-kicker"><BadgeCheck size={15} aria-hidden /> Confirmed on the ground</p>
        <h2>{r.resolution.confirmed_name}</h2>
        <p>{r.resolution.check_label}: {r.resolution.outcome_label.toLowerCase()}.{r.resolution.note ? ` “${r.resolution.note}”` : ""}</p>
      </div>
    );
  }
  if (r.stage_outcome) {
    const so = r.stage_outcome;
    const Icon = so.kind === "area_alert" ? MapPinned : so.kind === "watch" ? Eye : /harvest/i.test(so.reason) ? Wheat : CircleSlash;
    const kicker = so.kind === "area_alert" ? "Area-wide, not this farm alone" : so.kind === "watch" ? "Watching, no visit yet" : "No visit needed";
    const title = so.title.split(": ")[1] ?? so.title;
    return (
      <div className={`verdict v-${so.kind}`}>
        <p className="v-kicker"><Icon size={15} aria-hidden /> {kicker}</p>
        <h2>{title.replace(/^./, (c) => c.toUpperCase())}</h2>
        <p>{so.reason}.</p>
        {so.confirm_with && <p className="v-confirm">{so.confirm_with}</p>}
      </div>
    );
  }
  if (r.outcome === "unexplained" || !lead) {
    return (
      <div className="verdict v-unexplained">
        <p className="v-kicker">The drop is real, the cause is not clear yet</p>
        <h2>Ask the farmer or visit</h2>
        <p>{said || "The satellite data does not separate the possible causes well enough to name one. FieldDx would rather say so than guess."}</p>
      </div>
    );
  }
  return (
    <div className="verdict v-case">
      <p className="v-kicker">Most likely cause <span className={`sure sure-${lead.confidence}`}>{sureWord(lead.confidence)}</span></p>
      <h2>{lead.name}</h2>
      {said && <p>{said}</p>}
    </div>
  );
}

/** A case for someone who is not a remote-sensing analyst: the verdict, what was seen, what else it could be. */
export function Summary({ r, onAsk, onEvidence }: { r: CaseResult; onAsk: () => void; onEvidence: () => void }) {
  const h = r.headline;
  const live = r.hypotheses.filter((x) => x.stage === 3 && (x.status === "leading" || x.status === "possible"));
  const others = r.stage_outcome ? [] : live.slice(1, 4);
  const ruled = r.hypotheses.filter((x) => x.status === "ruled_out" && x.brief).slice(0, 4);
  const lead = live[0];

  return (
    <section className="summary" aria-label="Summary">
      <Verdict r={r} />

      <dl className="facts">
        <div><dt>What the satellite saw</dt><dd>{h ? `${plainDrop(h.delta, h.zone_label)}, ${fmtDate(h.date)}` : "No change measured"}</dd></div>
        <div><dt>Field</dt><dd>{r.field.area_ha} ha, {r.field.class_label.toLowerCase()}</dd></div>
        <div><dt>Alert</dt><dd>{fmtDate(r.alert_date)}</dd></div>
      </dl>

      {lead && !r.stage_outcome && r.outcome !== "resolved" && lead.for_lines.length > 0 && (
        <div className="why">
          <h3>Why FieldDx thinks so</h3>
          <ul>{lead.for_lines.slice(0, 3).map((l, i) => <li key={i}>{strip(l.text)}</li>)}</ul>
        </div>
      )}

      {others.length > 0 && (
        <div className="alts">
          <h3>It could also be</h3>
          <ul>
            {others.map((x) => (
              <li key={x.id}><span>{x.name}</span><span className={`sure sure-${x.confidence}`}>{sureWord(x.confidence)}</span></li>
            ))}
          </ul>
        </div>
      )}

      {ruled.length > 0 && (
        <div className="ruled">
          <h3>Checked and ruled out</h3>
          <ul>{ruled.map((x) => <li key={x.id}><strong>{x.name}.</strong> {x.brief}</li>)}</ul>
        </div>
      )}

      <div className="summary-links">
        <button type="button" onClick={onAsk}><MessageCircleQuestion size={16} aria-hidden /> Ask a question about this field <ChevronRight size={15} aria-hidden /></button>
        <button type="button" onClick={onEvidence}><ListChecks size={16} aria-hidden /> See the {r.evidence.length} pieces of evidence <ChevronRight size={15} aria-hidden /></button>
      </div>
    </section>
  );
}
