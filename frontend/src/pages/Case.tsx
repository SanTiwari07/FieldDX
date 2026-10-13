import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Check, LineChart, ListChecks, Stethoscope } from "lucide-react";
import { api, CaseResult, MapData, SeriesData } from "../api";
import { STEPS, useInvestigation } from "../hooks";
import { CROP_LABEL, fmtDate, fmtDelta } from "../lib/format";
import { Diagnosis } from "../components/Diagnosis";
import { Dock, RecordDialog } from "../components/Dock";
import { InvestigationRail } from "../components/Investigation";
import { MapWorkspace } from "../components/MapWorkspace";
import { CandidatesTable } from "../components/NextCheck";
import { Timeline } from "../components/Timeline";
import { LimitsNote, SeverityBadge, Spinner, StatusBadge } from "../components/ui";

type Tab = "findings" | "evidence" | "trend";

function StageHead({ r }: { r: CaseResult }) {
  const h = r.headline;
  return (
    <header className="stage-head">
      <div className="sh-title">
        <Link to="/" className="back"><ArrowLeft size={14} aria-hidden /> Inbox</Link>
        <h1>{r.field.name}</h1>
        <p className="meta">
          {CROP_LABEL[r.field.crop]}, {r.field.area_ha} ha. {r.field.anchor_label[0].toUpperCase() + r.field.anchor_label.slice(1)} {fmtDate(r.field.anchor_date)}
          {r.field.anchor_assumed && " (assumed)"}. Alert {fmtDate(r.alert_date)}.
        </p>
      </div>
      <div className="sh-status">
        <div className="case-badges"><StatusBadge outcome={r.outcome} /><SeverityBadge level={r.severity} /></div>
        {h && (
          <div className="case-delta" title={`Against baseline ${h.baseline_label}`}>
            <span className="data-lg">&Delta;NDVI {fmtDelta(h.delta)}</span>
            <span className="caption">{h.zone_label}, {fmtDate(h.date)}{h.quality === "partial" && ", partial scene"}</span>
          </div>
        )}
      </div>
    </header>
  );
}

export default function CasePage() {
  const { id = "" } = useParams();
  const inv = useInvestigation(id);
  const [map, setMap] = useState<MapData | null>(null);
  const [series, setSeries] = useState<SeriesData | null>(null);
  const [tab, setTab] = useState<Tab>("evidence");
  const [recording, setRecording] = useState(false);
  const shown = useRef(false);

  useEffect(() => {
    setMap(null);
    setSeries(null);
    shown.current = false;
    setTab("evidence");
    api.map(id).then(setMap).catch(() => undefined);
    api.series(id).then(setSeries).catch(() => undefined);
  }, [id]);

  const r = inv.result;
  const ready = inv.steps.next_check.state === "done" || inv.steps.next_check.state === "skipped";
  const done = STEPS.filter((s) => inv.steps[s.tool].state === "done" || inv.steps[s.tool].state === "skipped").length;
  const running = inv.phase === "running";
  const current = STEPS.find((s) => inv.steps[s.tool].state === "running");

  // open the evidence while it streams, then land on the findings once
  useEffect(() => {
    if (ready && !shown.current) {
      shown.current = true;
      setTab("findings");
    }
  }, [ready]);
  useEffect(() => {
    if (inv.phase === "running" && !ready) setTab("evidence");
  }, [inv.phase, ready]);

  const live = useMemo(() => (r && ready ? { ...r, evidence: inv.evidence } : r), [r, ready, inv.evidence]);

  if (inv.phase === "error" && !r) {
    return <main className="page"><Link to="/" className="back"><ArrowLeft size={15} /> Inbox</Link><p className="form-error" role="alert">{inv.error}</p></main>;
  }
  if (!r || !live) return <main className="page"><div className="skeleton-rows" aria-busy="true">{[0, 1, 2].map((i) => <span key={i} />)}</div></main>;

  const onSaved = (next: CaseResult) => {
    inv.apply(next);
    setRecording(false);
    setTab("findings");
  };

  return (
    <div className="case-shell">
      {r.replayed && <div className="strip" role="note">{r.banner}</div>}
      <div className="workspace">
        <section className="stage" aria-label="Field map">
          <StageHead r={r} />
          <div className="stage-map">
            {map && series ? (
              <MapWorkspace caseId={r.case_id} map={map} series={series} headlineDate={r.headline?.date ?? null} />
            ) : (
              <div className="stage-loading" aria-busy="true"><Spinner size={18} /> Loading the map</div>
            )}
          </div>
        </section>

        <aside className="panel" aria-label="Case file">
          {running && (
            <div className="progress" role="status">
              <div className="progress-bar"><span style={{ width: `${(done / STEPS.length) * 100}%` }} /></div>
              <p><Spinner size={12} /> {current ? `${current.running}…` : "Starting"} <span className="muted">{done} of {STEPS.length}</span></p>
            </div>
          )}
          <div className="tabs" role="tablist" aria-label="Case sections">
            <button role="tab" id="t-findings" aria-selected={tab === "findings"} aria-controls="p-findings" className={tab === "findings" ? "on" : ""} onClick={() => setTab("findings")}>
              <Stethoscope size={15} aria-hidden /> Findings
            </button>
            <button role="tab" id="t-evidence" aria-selected={tab === "evidence"} aria-controls="p-evidence" className={tab === "evidence" ? "on" : ""} onClick={() => setTab("evidence")}>
              <ListChecks size={15} aria-hidden /> Evidence <span className="tab-count">{inv.evidence.length}</span>
            </button>
            <button role="tab" id="t-trend" aria-selected={tab === "trend"} aria-controls="p-trend" className={tab === "trend" ? "on" : ""} onClick={() => setTab("trend")}>
              <LineChart size={15} aria-hidden /> Trend
            </button>
          </div>

          <div className="panel-body">
            <div role="tabpanel" id="p-findings" aria-labelledby="t-findings" hidden={tab !== "findings"}>
              {ready ? (
                <>
                  <Diagnosis r={live} />
                  <CandidatesTable r={r} />
                  <LimitsNote>{r.limits}</LimitsNote>
                </>
              ) : (
                <div className="waiting"><Spinner size={16} /> The diagnosis appears when the last check finishes. <button className="linklike" onClick={() => setTab("evidence")}>Watch the evidence</button></div>
              )}
            </div>
            <div role="tabpanel" id="p-evidence" aria-labelledby="t-evidence" hidden={tab !== "evidence"}>
              <InvestigationRail steps={inv.steps} evidence={inv.evidence} phase={inv.phase} onReplay={inv.replay} />
              {ready && <button className="btn btn-secondary wide" onClick={() => setTab("findings")}><Check size={15} aria-hidden /> See the diagnosis</button>}
            </div>
            <div role="tabpanel" id="p-trend" aria-labelledby="t-trend" hidden={tab !== "trend"}>
              {series ? <Timeline series={series} /> : <div className="timeline skeleton" aria-busy="true" />}
              <LimitsNote>{r.limits}</LimitsNote>
            </div>
            {inv.phase === "error" && <p className="form-error" role="alert">{inv.error}</p>}
          </div>

          {ready && <Dock r={r} onRecord={() => setRecording(true)} />}
        </aside>
      </div>
      <RecordDialog r={r} open={recording} onClose={() => setRecording(false)} onSaved={onSaved} />
    </div>
  );
}
