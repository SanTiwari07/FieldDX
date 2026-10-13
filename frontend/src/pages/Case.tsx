import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { api, MapData, SeriesData } from "../api";
import { useInvestigation } from "../hooks";
import { CROP_LABEL, fmtDate, fmtDelta } from "../lib/format";
import { Diagnosis } from "../components/Diagnosis";
import { InvestigationRail } from "../components/Investigation";
import { MapFrame } from "../components/MapFrame";
import { CandidatesTable, CloseCaseForm, NextCheckSlip, ResolutionCard, VisitChecklist } from "../components/NextCheck";
import { Timeline } from "../components/Timeline";
import { LimitsNote, ScenarioBanner, SeverityBadge, StatusBadge } from "../components/ui";

export default function CasePage() {
  const { id = "" } = useParams();
  const inv = useInvestigation(id);
  const [map, setMap] = useState<MapData | null>(null);
  const [series, setSeries] = useState<SeriesData | null>(null);

  useEffect(() => {
    setMap(null);
    setSeries(null);
    api.map(id).then(setMap).catch(() => undefined);
    api.series(id).then(setSeries).catch(() => undefined);
  }, [id]);

  const r = inv.result;
  if (inv.phase === "error" && !r) {
    return <main className="page"><Link to="/" className="back"><ArrowLeft size={15} /> Inbox</Link><p className="form-error" role="alert">{inv.error}</p></main>;
  }
  if (!r) return <main className="page"><div className="skeleton-rows" aria-busy="true">{[0, 1, 2].map((i) => <span key={i} />)}</div></main>;

  const ready = inv.steps.next_check.state === "done" || inv.steps.next_check.state === "skipped";
  const live = ready ? { ...r, evidence: inv.evidence } : r;
  const names = Object.fromEntries(r.hypotheses.map((h) => [h.id, h.name]));
  const h = r.headline;

  return (
    <main className="page page-case">
      <Link to="/" className="back"><ArrowLeft size={15} aria-hidden /> Inbox</Link>
      {r.replayed && <ScenarioBanner text={r.banner} />}

      <header className="case-head">
        <div className="case-title">
          <div className="eyebrow">Case {r.case_id} · alert {fmtDate(r.alert_date)}</div>
          <h1>{r.field.name}</h1>
          <p className="meta">
            {CROP_LABEL[r.field.crop]} · {r.field.area_ha} ha · {r.field.anchor_label} {fmtDate(r.field.anchor_date)}
            {r.field.anchor_assumed && " (assumed)"}
          </p>
          <div className="case-badges"><StatusBadge outcome={r.outcome} /><SeverityBadge level={r.severity} /></div>
        </div>
        {h && (
          <div className="headline" aria-label="Headline change">
            <div className="data-lg">&Delta;NDVI {fmtDelta(h.delta)}</div>
            <div className="caption">{h.zone_label} · {fmtDate(h.date)}{h.quality === "partial" && " (partial scene)"}</div>
            <div className="caption muted">vs baseline {h.baseline_label}</div>
          </div>
        )}
      </header>

      <div className="case-grid">
        <div className="area-map">
          {map ? <MapFrame data={map} fieldName={r.field.name} /> : <div className="map-frame skeleton" aria-busy="true" />}
          <LimitsNote>{r.limits}</LimitsNote>
        </div>

        <div className="area-rail">
          <InvestigationRail steps={inv.steps} evidence={inv.evidence} phase={inv.phase} onReplay={inv.replay} />

          {ready && (
            <>
              <Diagnosis r={live} />
              {r.outcome === "field_case" && r.next_check && (
                <div className="rail-section">
                  <NextCheckSlip caseId={r.case_id} nc={r.next_check} names={names} />
                  <CandidatesTable r={r} />
                  <CloseCaseForm r={r} onSaved={inv.apply} />
                </div>
              )}
              {r.outcome === "unexplained" && (
                <div className="rail-section"><VisitChecklist items={r.visit_checklist} /></div>
              )}
              {r.outcome === "resolved" && <div className="rail-section"><ResolutionCard r={r} /></div>}
            </>
          )}
          {inv.phase === "error" && <p className="form-error" role="alert">{inv.error}</p>}
        </div>

        <div className="area-timeline">
          {series ? <Timeline series={series} /> : <div className="timeline skeleton" aria-busy="true" />}
        </div>
      </div>
    </main>
  );
}
