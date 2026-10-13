import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { api, InboxRow } from "../api";
import { CROP_LABEL, fmtDate, fmtDelta } from "../lib/format";
import { ConfidenceMeter, ScenarioBanner, SeverityBadge, StatusBadge } from "../components/ui";

function Row({ row }: { row: InboxRow }) {
  const muted = row.outcome === "auto_dismissed";
  const h = row.headline;
  return (
    <Link to={`/case/${row.id}`} role="row" className={`inbox-row ${muted ? "is-dismissed" : ""} ${row.outcome === "resolved" ? "is-resolved" : ""}`}>
      <span role="cell" className="c-sev">
        {muted ? <StatusBadge outcome="auto_dismissed" /> : <SeverityBadge level={row.severity} />}
      </span>
      <span role="cell" className="c-field">
        <strong>{row.field.name}</strong>
        <small>{CROP_LABEL[row.field.crop]} · {row.field.area_ha} ha</small>
      </span>
      <span role="cell" className="c-change">
        {h ? (
          <>
            <span className="num">&Delta;NDVI {fmtDelta(h.delta)}</span>
            <small>{h.zone_label} · {fmtDate(h.date)}</small>
          </>
        ) : (
          <small>No change measured</small>
        )}
      </span>
      <span role="cell" className="c-lead">
        {muted ? (
          <>
            <span className="reason">{row.reason}</span>
            <small>Dismissed automatically</small>
          </>
        ) : (
          <>
            <span className="lead-name">{row.leading}</span>
            {row.outcome === "area_alert" && row.reason && <small>{row.reason}</small>}
          </>
        )}
      </span>
      <span role="cell" className="c-conf">{row.confidence ? <ConfidenceMeter level={row.confidence} /> : <span className="muted">&ndash;</span>}</span>
      <span role="cell" className="c-status">
        {muted ? <span className="muted small">{fmtDate(row.alert_date)}</span> : <StatusBadge outcome={row.outcome} />}
        <ChevronRight size={16} aria-hidden className="chev" />
      </span>
    </Link>
  );
}

export default function Inbox() {
  const [data, setData] = useState<{ banner: string; as_of: string; cases: InboxRow[] } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.inbox().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <main className="page"><p className="form-error" role="alert">Could not load the inbox: {error}. Is the API running on port 8000?</p></main>;
  if (!data) return <main className="page"><div className="skeleton-rows" aria-busy="true">{[0, 1, 2, 3].map((i) => <span key={i} />)}</div></main>;

  const open = data.cases.filter((c) => c.outcome === "field_case" || c.outcome === "unexplained");
  const area = data.cases.filter((c) => c.outcome === "area_alert");
  const resolved = data.cases.filter((c) => c.outcome === "resolved");
  const dismissed = data.cases.filter((c) => c.outcome === "auto_dismissed");

  const Head = () => (
    <div className="inbox-head" role="row" aria-hidden>
      <span>Severity</span><span>Field</span><span>What changed</span><span>Leading hypothesis</span><span>Confidence</span><span>Status</span>
    </div>
  );

  return (
    <main className="page">
      <ScenarioBanner text={data.banner} />
      <header className="page-head">
        <div>
          <h1>Inbox</h1>
          <p className="lede">
            Flagged fields in the Niphad cluster, ranked by severity and confidence. Data to {fmtDate(data.as_of)}.
          </p>
        </div>
        <dl className="tally">
          <div><dt>Need a visit</dt><dd>{open.length}</dd></div>
          <div><dt>Resolved</dt><dd>{resolved.length}</dd></div>
          <div><dt>Dismissed</dt><dd>{dismissed.length}</dd></div>
        </dl>
      </header>

      <section aria-labelledby="open-h" className="inbox" role="table" aria-label="Flagged fields">
        <h2 id="open-h" className="group-title">Open cases <span className="count">{open.length + area.length}</span></h2>
        <Head />
        <div className="rows">{[...open, ...area].map((r) => <Row key={r.id} row={r} />)}</div>

        {resolved.length > 0 && (
          <>
            <h2 className="group-title">Resolved <span className="count">{resolved.length}</span></h2>
            <div className="rows">{resolved.map((r) => <Row key={r.id} row={r} />)}</div>
          </>
        )}

        <h2 className="group-title divider">Dismissed automatically <span className="count">{dismissed.length}</span></h2>
        <p className="group-note">Never hidden. Each one shows the reason it was thrown out, so you can check the check.</p>
        <div className="rows">{dismissed.map((r) => <Row key={r.id} row={r} />)}</div>
      </section>
    </main>
  );
}
