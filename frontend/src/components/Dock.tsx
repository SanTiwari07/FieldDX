import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2, ClipboardList, Clock, Eye, EyeOff, MapPinned, Pencil, X } from "lucide-react";
import type { CaseResult } from "../api";
import { checkPurpose, CloseCaseForm } from "./NextCheck";
import { Refs } from "./ui";

/** The one place the next best check lives. It stays docked under the panel on every tab. */
export function Dock({ r, onRecord }: { r: CaseResult; onRecord: () => void }) {
  const nc = r.next_check;
  const names = Object.fromEntries(r.hypotheses.map((h) => [h.id, h.name]));

  if (r.outcome === "resolved" && r.resolution) {
    const ev = r.evidence[r.evidence.length - 1]?.id;
    return (
      <div className="dock dock-resolved">
        <CheckCircle2 size={20} aria-hidden />
        <div>
          <strong>{r.resolution.confirmed_name} confirmed</strong>
          <p>{r.resolution.outcome_label}{r.resolution.note && <>, &ldquo;{r.resolution.note}&rdquo;</>} {ev && <Refs ids={[ev]} />}</p>
        </div>
      </div>
    );
  }

  if (r.outcome === "field_case" && nc) {
    return (
      <div className="dock dock-slip">
        <p className="dock-kicker">Next best check</p>
        <p className="dock-instruction">{nc.label}</p>
        <ul className="dock-results">
          {nc.outcomes.map((o) => (
            <li key={o.key}><b>{o.label}</b><ArrowRight size={13} aria-hidden /><span>{o.then}</span></li>
          ))}
        </ul>
        <p className="dock-cost">
          <Clock size={13} aria-hidden /> About {nc.cost_min} minutes. {checkPurpose(nc, names)}
        </p>
        <div className="dock-actions">
          <button type="button" className="btn btn-inverse" onClick={onRecord}><Pencil size={15} aria-hidden /> Record finding</button>
          <Link to={`/case/${r.case_id}/check`} className="btn btn-outline-inverse"><ClipboardList size={15} aria-hidden /> Field checklist</Link>
        </div>
      </div>
    );
  }

  if (r.outcome === "unexplained") {
    const ask = r.visit_checklist[0];
    return (
      <div className="dock dock-slip">
        <p className="dock-kicker">Ask or visit</p>
        <p className="dock-instruction">No single check separates the causes. Start with the cheapest question.</p>
        {ask && <p className="dock-ask">{ask}</p>}
        <div className="dock-actions">
          {nc && <button type="button" className="btn btn-inverse" onClick={onRecord}><Pencil size={15} aria-hidden /> Record finding</button>}
          <Link to={`/case/${r.case_id}/check`} className="btn btn-outline-inverse"><ClipboardList size={15} aria-hidden /> Visit checklist</Link>
        </div>
      </div>
    );
  }

  if (r.outcome === "watch") {
    return (
      <div className="dock dock-quiet">
        <Eye size={18} aria-hidden />
        <div>
          <strong>Waiting for the next clear pass</strong>
          <p>Seen on one clear pass only. Nobody needs to go out yet. {r.stage_outcome?.confirm_with}</p>
        </div>
      </div>
    );
  }

  const area = r.outcome === "area_alert";
  return (
    <div className="dock dock-quiet">
      {area ? <MapPinned size={18} aria-hidden /> : <EyeOff size={18} aria-hidden />}
      <div>
        <strong>{area ? "Area alert, no field visit" : "No visit needed"}</strong>
        <p>{r.stage_outcome?.reason}. {r.stage_outcome?.confirm_with}</p>
      </div>
    </div>
  );
}

/** Modal sheet for recording what the officer found. */
export function RecordDialog({
  r, open, onClose, onSaved,
}: {
  r: CaseResult;
  open: boolean;
  onClose: () => void;
  onSaved: (r: CaseResult) => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className="sheet" onClose={onClose} onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      <div className="sheet-inner">
        <button type="button" className="sheet-x" aria-label="Close" onClick={onClose}><X size={18} aria-hidden /></button>
        {open && <CloseCaseForm r={r} onSaved={onSaved} />}
      </div>
    </dialog>
  );
}
