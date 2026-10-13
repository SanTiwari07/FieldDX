import { lazy, Suspense, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, List, Map as MapIcon } from "lucide-react";
import { api, InboxRow, Provenance } from "../api";
import { fmtDate, fmtDelta } from "../lib/format";
import { ConfidenceMeter, DataNote, SeverityBadge, StatusBadge } from "../components/ui";
import { paintRaster } from "../components/RasterOverlay";

const FieldsMap = lazy(() => import("../components/FieldsMap"));

function Thumb({ id }: { id: string }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let live = true;
    api.raster(id).then((r) => live && setUrl(paintRaster(r, "ndvi", false, 6))).catch(() => undefined);
    return () => { live = false; };
  }, [id]);
  return <span className="thumb" aria-hidden>{url && <img src={url} alt="" />}</span>;
}

function Row({ row }: { row: InboxRow }) {
  const muted = row.outcome === "auto_dismissed";
  const h = row.headline;
  return (
    <Link to={`/case/${row.id}`} role="row" className={`inbox-row ${muted ? "is-dismissed" : ""} ${row.outcome === "resolved" ? "is-resolved" : ""}`}>
      <span role="cell" className="c-sev">
        {muted || row.outcome === "watch" || row.outcome === "area_alert" ? <StatusBadge outcome={row.outcome} /> : <SeverityBadge level={row.severity} />}
      </span>
      <span role="cell" className="c-field">
        <Thumb id={row.id} />
        <span className="c-field-text">
          <strong>{row.field.name}</strong>
          <small>{row.field.class_label}, {row.field.area_ha} ha</small>
        </span>
      </span>
      <span role="cell" className="c-change">
        {h ? (
          <>
            <span className="num">&Delta;NDVI {fmtDelta(h.delta)}</span>
            <small>{h.zone_label}, {fmtDate(h.date)}</small>
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
            {(row.outcome === "area_alert" || row.outcome === "watch") && row.reason && <small>{row.reason}</small>}
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

function Group({ title, note, rows, divider }: { title: string; note?: string; rows: InboxRow[]; divider?: boolean }) {
  if (!rows.length) return null;
  return (
    <>
      <h2 className={`group-title ${divider ? "divider" : ""}`}>{title} <span className="count">{rows.length}</span></h2>
      {note && <p className="group-note">{note}</p>}
      <div className="inbox-head" role="row" aria-hidden>
        <span>Priority</span><span>Field</span><span>What changed</span><span>Leading explanation</span><span>Confidence</span><span>Status</span>
      </div>
      <div className="rows">{rows.map((r) => <Row key={r.id} row={r} />)}</div>
    </>
  );
}

function About({ p }: { p: Provenance }) {
  return (
    <section className="about" aria-labelledby="about-h">
      <h2 id="about-h">Where the data comes from</h2>
      <dl>
        <div><dt>Satellite imagery</dt><dd>Copernicus Sentinel-2 L2A at 10 m, read through Google Earth Engine. Clouds, shadow and cirrus are masked with Cloud Score+ (0.60) and the scene classification layer.</dd></div>
        <div><dt>Field shapes</dt><dd>Predicted by the Fields of the World model (EfficientNet-B5, CC-BY) from two Sentinel-2 dates in 2025. A shape is a remote-sensing field unit, not a legal parcel.</dd></div>
        <div><dt>Cropland</dt><dd>ESA WorldCover 2021 keeps only cropland. The crop itself is not known; canopy is called perennial or seasonal from a year of NDVI.</dd></div>
        <div><dt>Weather</dt><dd>Open-Meteo archive (ERA5 and ERA5-Land reanalysis) for the area centre.</dd></div>
        <div><dt>Alerts</dt><dd>Any zone 0.10 NDVI or more below the field's own baseline on a clear pass in the last 21 days. Nothing is hand-picked.</dd></div>
        <div><dt>Not verified yet</dt><dd>The harvest and pruning windows are placeholders until an agronomist confirms them. Each case says when it relies on one.</dd></div>
      </dl>
      {p.boundaries && <p className="muted small">{p.boundaries}</p>}
    </section>
  );
}

export default function Inbox() {
  const [data, setData] = useState<{ banner: string; as_of: string; provenance: Provenance; cases: InboxRow[] } | null>(null);
  const [error, setError] = useState("");
  const [view, setView] = useState<"list" | "map">("list");

  useEffect(() => {
    api.inbox().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <main className="page"><p className="form-error" role="alert">Could not load the inbox: {error}. Is the API running on port 8000?</p></main>;
  if (!data) return <main className="page"><div className="skeleton-rows" aria-busy="true">{[0, 1, 2, 3].map((i) => <span key={i} />)}</div></main>;

  const by = (...o: string[]) => data.cases.filter((c) => o.includes(c.outcome));
  const open = by("field_case", "unexplained");
  const watching = by("watch");
  const area = by("area_alert");
  const resolved = by("resolved");
  const dismissed = by("auto_dismissed");

  return (
    <main className="page">
      <DataNote text={data.banner} />
      <header className="page-head">
        <div>
          <h1>Inbox</h1>
          <p className="lede">
            Fields near Niphad, Nashik that raised an alert in the 21 days to {fmtDate(data.as_of)}, ranked by severity and confidence.
          </p>
        </div>
        <dl className="tally">
          <div><dt>Ask or visit</dt><dd>{open.length}</dd></div>
          <div><dt>Watching</dt><dd>{watching.length}</dd></div>
          <div><dt>Area alerts</dt><dd>{area.length}</dd></div>
          <div><dt>Dismissed</dt><dd>{dismissed.length}</dd></div>
        </dl>
      </header>

      <div className="seg view-toggle" role="group" aria-label="Inbox view">
        <button type="button" aria-pressed={view === "list"} className={view === "list" ? "on" : ""} onClick={() => setView("list")}><List size={14} aria-hidden /><span>List</span></button>
        <button type="button" aria-pressed={view === "map"} className={view === "map" ? "on" : ""} onClick={() => setView("map")}><MapIcon size={14} aria-hidden /><span>Map of fields</span></button>
      </div>

      {view === "map" ? (
        <Suspense fallback={<div className="fieldsmap skeleton" aria-busy="true" />}>
          <FieldsMap />
        </Suspense>
      ) : (
        <section className="inbox" role="table" aria-label="Flagged fields">
          <Group title="Needs a call or a visit" rows={open} />
          <Group title="Watching" rows={watching} note="Seen on one clear pass only. FieldDx waits for the next pass before asking anyone to go out." divider />
          <Group title="Area alerts" rows={area} note="Similar fields nearby changed at the same time, so this is an area event and not a field problem." divider />
          <Group title="Resolved" rows={resolved} divider />
          <Group title="Dismissed automatically" rows={dismissed} note="Never hidden. Each one shows the reason it was thrown out, so you can check the check." divider />
          {!data.cases.length && <p className="lede">No alerts in this window.</p>}
        </section>
      )}

      <About p={data.provenance} />
    </main>
  );
}
