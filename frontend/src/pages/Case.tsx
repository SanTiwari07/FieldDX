import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, LineChart, ListChecks, MessageCircleQuestion, Stethoscope } from "lucide-react";
import { api, CaseResult, MapData, SeriesData } from "../api";
import { useInvestigation } from "../hooks";
import { fmtDate, fmtDelta } from "../lib/format";
import { Diagnosis } from "../components/Diagnosis";
import { Dock, RecordDialog } from "../components/Dock";
import { InvestigationRail } from "../components/Investigation";
import { MapWorkspace } from "../components/MapWorkspace";
import { CandidatesTable } from "../components/NextCheck";
import { Timeline } from "../components/Timeline";
import { Summary } from "../components/Summary";
import { AskPanel } from "../components/Ask";
import { LimitsNote, SeverityBadge, Spinner, StatusBadge } from "../components/ui";

type Tab = "summary" | "ask" | "evidence" | "trend";

function StageHead({ r }: { r: CaseResult }) {
  const h = r.headline;
  return (
    <header className="stage-head">
      <div className="sh-title">
        <Link to="/cases" className="back"><ArrowLeft size={14} aria-hidden /> Cases</Link>
        <h1>{r.field.name}</h1>
        <p className="meta">
          {r.field.class_label}, {r.field.area_ha} ha{r.field.mode === "whole" ? ", read as one zone" : ""}. Alert raised {fmtDate(r.alert_date)}.
        </p>
      </div>
      <div className="sh-status">
        <div className="case-badges"><StatusBadge outcome={r.outcome} /><SeverityBadge level={r.severity} /></div>
        {h && (
          <div className="case-delta" title={`Against baseline ${h.baseline_label}`}>
            <span className="data-lg">{fmtDelta(h.delta)}</span>
            <span className="caption">Greenness change (NDVI), {h.zone_label.toLowerCase()}, {fmtDate(h.date)}{h.quality === "partial" && ", partial scene"}</span>
          </div>
        )}
      </div>
    </header>
  );
}

export default function CasePage() {
  const { id = "" } = useParams();
  // the case opens on its summary; the checks run without replaying step by step unless the officer asks
  const inv = useInvestigation(id, true);
  const [map, setMap] = useState<MapData | null>(null);
  const [series, setSeries] = useState<SeriesData | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [recording, setRecording] = useState(false);

  useEffect(() => {
    setMap(null);
    setSeries(null);
    setTab("summary");
    api.map(id).then(setMap).catch(() => undefined);
    api.series(id).then(setSeries).catch(() => undefined);
  }, [id]);

  const r = inv.result;
  const ready = inv.steps.next_check.state === "done" || inv.steps.next_check.state === "skipped";

  const live = useMemo(() => (r && ready ? { ...r, evidence: inv.evidence } : r), [r, ready, inv.evidence]);

  if (inv.phase === "error" && !r) {
    return <main className="page"><Link to="/cases" className="back"><ArrowLeft size={15} /> Cases</Link><p className="form-error" role="alert">{inv.error}</p></main>;
  }
  if (!r || !live) return <main className="page"><div className="skeleton-rows" aria-busy="true">{[0, 1, 2].map((i) => <span key={i} />)}</div></main>;

  const onSaved = (next: CaseResult) => {
    inv.apply(next);
    setRecording(false);
    setTab("summary");
  };

  return (
    <div className="case-shell">
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
          <div className="tabs" role="tablist" aria-label="Case sections">
            {([
              ["summary", "Summary", Stethoscope, null],
              ["ask", "Ask", MessageCircleQuestion, null],
              ["evidence", "Evidence", ListChecks, inv.evidence.length],
              ["trend", "Trend", LineChart, null],
            ] as const).map(([k, label, Icon, n]) => (
              <button key={k} role="tab" id={`t-${k}`} aria-selected={tab === k} aria-controls={`p-${k}`} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>
                <Icon size={15} aria-hidden /> {label}{n ? <span className="tab-count">{n}</span> : null}
              </button>
            ))}
          </div>

          <div className="panel-body">
            <div role="tabpanel" id="p-summary" aria-labelledby="t-summary" hidden={tab !== "summary"}>
              <Summary r={live} onAsk={() => setTab("ask")} onEvidence={() => setTab("evidence")} />
            </div>
            <div role="tabpanel" id="p-ask" aria-labelledby="t-ask" hidden={tab !== "ask"} className="ask-tab">
              <AskPanel caseId={r.case_id} fieldName={r.field.name} />
            </div>
            <div role="tabpanel" id="p-evidence" aria-labelledby="t-evidence" hidden={tab !== "evidence"}>
              {ready && <Diagnosis r={live} />}
              <InvestigationRail steps={inv.steps} evidence={inv.evidence} phase={inv.phase} onReplay={inv.replay} />
              {ready && <CandidatesTable r={r} />}
              {ready && <LimitsNote>{r.limits}</LimitsNote>}
            </div>
            <div role="tabpanel" id="p-trend" aria-labelledby="t-trend" hidden={tab !== "trend"}>
              {series ? <Timeline series={series} /> : <div className="timeline skeleton" aria-busy="true" />}
              <LimitsNote>{r.limits}</LimitsNote>
            </div>
            {inv.phase === "error" && <p className="form-error" role="alert">{inv.error}</p>}
          </div>

          {tab !== "ask" && <Dock r={r} onRecord={() => setRecording(true)} />}
        </aside>
      </div>
      <RecordDialog r={r} open={recording} onClose={() => setRecording(false)} onSaved={onSaved} />
    </div>
  );
}
