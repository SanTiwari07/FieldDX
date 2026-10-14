import { lazy, Suspense, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AlertTriangle, ArrowRight, Check, ChevronRight, CircleDashed, EyeOff, Eye, MapPinned, RefreshCw, Satellite,
  Stethoscope, Tractor, Wheat, X,
} from "lucide-react";
import { api, BuildState, BuildStep, HomeData } from "../api";
import { useSession } from "../session";
import { fmtDate, fmtDelta } from "../lib/format";
import { ConfidenceMeter, SeverityBadge, Spinner } from "../components/ui";

const FieldsMap = lazy(() => import("../components/FieldsMap"));

function since(iso?: string, until?: string): string {
  if (!iso) return "";
  const s = Math.max(0, ((until ? new Date(until).getTime() : Date.now()) - new Date(iso).getTime()) / 1000);
  return s < 60 ? `${Math.round(s)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`;
}

function StepRow({ s }: { s: BuildStep }) {
  return (
    <li className={`bstep bstep-${s.state}`}>
      <span className="bstep-icon" aria-hidden>
        {s.state === "done" ? <Check size={13} strokeWidth={3} /> : s.state === "running" ? <Spinner size={14} /> : s.state === "failed" ? <X size={13} strokeWidth={3} /> : <CircleDashed size={14} />}
      </span>
      <div className="bstep-body">
        <div className="bstep-head">
          <strong>{s.label}</strong>
          {(s.state === "running" || s.state === "done") && <small className="muted">{since(s.started_at, s.ended_at)}</small>}
        </div>
        {s.detail && <p>{s.detail}</p>}
        {s.state === "running" && s.progress !== null && s.progress !== undefined && (
          <div className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(s.progress * 100)}>
            <span style={{ width: `${Math.max(3, s.progress * 100)}%` }} />
          </div>
        )}
      </div>
    </li>
  );
}

const PENDING_STEPS: BuildStep[] = [
  ["boundaries", "Field boundaries"], ["imagery", "Sentinel-2 passes"], ["weather", "Weather"],
  ["fields", "Fields and pixel zones"], ["seasons", "Harvest season"], ["alerts", "Alerts"],
].map(([id, label]) => ({ id, label, state: "queued", detail: "", progress: null }));

/** While the area is being built: what is being fetched, from where, and how far along it is. */
function Building() {
  const { me, refresh, set } = useSession();
  const nav = useNavigate();
  const [b, setB] = useState<BuildState | null>(null);
  const [, tick] = useState(0);
  const [busy, setBusy] = useState(false);
  const area = me!.area!;

  useEffect(() => {
    let live = true;
    let t = 0;
    const poll = async () => {
      try {
        const r = await api.build();
        if (!live) return;
        setB(r.build);
        if (r.build.status === "ready") { await refresh(); return; }
      } catch { /* keep polling */ }
      t = window.setTimeout(poll, 2000);
    };
    void poll();
    const clock = window.setInterval(() => tick((n) => n + 1), 1000);
    return () => { live = false; window.clearTimeout(t); window.clearInterval(clock); };
  }, [refresh]);

  const failed = b?.status === "failed" || b?.status === "interrupted";
  const canRetry = b?.status === "interrupted" || b?.retryable !== false;
  const steps = b?.steps?.length ? b.steps : PENDING_STEPS;
  const done = steps.filter((s) => s.state === "done").length;

  const retry = async () => {
    setBusy(true);
    try { setB((await api.retryBuild()).build); } finally { setBusy(false); }
  };
  const other = async () => {
    set(await api.joinArea(null));
    nav("/setup");
  };

  return (
    <main className="page narrow building">
      <div className="eyebrow">Step 3 of 3 · Building your area</div>
      <h1>{failed ? `Setting up ${area.name} stopped` : `Setting up ${area.name}`}</h1>
      <p className="lede">
        {failed
          ? canRetry
            ? "Nothing is lost: what was already downloaded is kept, and a retry carries on from there."
            : "The data was fetched, but this area has nothing FieldDx can watch zone by zone. Mark it differently."
          : b?.status === "queued"
            ? `Waiting for another area to finish${b.queue_position ? ` (number ${b.queue_position} in line)` : ""}.`
            : `Real field shapes, satellite passes and weather for ${area.km2 ? `${area.km2} km²` : "your area"} in ${area.region || "your region"}. You can leave this page; it keeps going.`}
      </p>
      {!failed && <div className="bar big" aria-hidden><span style={{ width: `${Math.max(4, (done / steps.length) * 100)}%` }} /></div>}
      <ol className="bsteps">{steps.map((s) => <StepRow key={s.id} s={s} />)}</ol>
      {failed && (
        <div className="build-error" role="alert">
          <AlertTriangle size={16} aria-hidden />
          <div>
            <strong>{b?.status === "interrupted" ? "The server restarted during the build." : canRetry ? "The build could not finish." : "No fields to watch here yet."}</strong>
            {b?.error && <p>{b.error}</p>}
            <div className="row">
              {canRetry && <button type="button" className="btn btn-primary" onClick={retry} disabled={busy}>{busy ? <Spinner /> : <RefreshCw size={14} aria-hidden />} Try again</button>}
              <button type="button" className={`btn ${canRetry ? "btn-ghost" : "btn-primary"}`} onClick={other}>Mark the area again</button>
            </div>
          </div>
        </div>
      )}
      <p className="muted small">
        Field shapes: {area.field_source === "ftw_model" ? "the Fields of the World model, run on this area" : "the published Fields of the World map"}.
        Imagery: Copernicus Sentinel-2 L2A through Google Earth Engine, clouds masked per pixel. Weather: Open-Meteo.
      </p>
    </main>
  );
}

function Funnel({ h }: { h: HomeData }) {
  const max = Math.max(1, h.fields);
  const rows = [
    { key: "fields", label: "Fields watched", n: h.fields, Icon: Satellite, note: "Every clear pass, every 10 m pixel" },
    { key: "alerts", label: "Raised an alert", n: h.alerts, Icon: AlertTriangle, note: h.detector },
    ...(h.counts.harvest ? [{ key: "harvest", label: "Harvest under way", n: h.counts.harvest, Icon: Wheat, note: "Dropped in the inferred harvest season after a green crop" }] : []),
    { key: "dismissed", label: "Dismissed with a reason", n: h.counts.dismissed, Icon: EyeOff, note: h.counts.harvest ? "Cloud, boundary pixels or other field work" : "Cloud, boundary pixels, harvest or pruning" },
    { key: "area", label: "Area-wide events", n: h.counts.area_alert, Icon: MapPinned, note: "Neighbours changed too, so not one farm's problem" },
    { key: "watch", label: "Waiting for another pass", n: h.counts.watch, Icon: Eye, note: "Seen once; FieldDx waits before sending anyone" },
    { key: "visit", label: "Need a call or a visit", n: h.counts.visit, Icon: Stethoscope, note: "Ranked causes and one cheapest check each" },
  ];
  return (
    <ol className="funnel" aria-label="From fields watched to fields that need you">
      {rows.map(({ key, label, n, Icon, note }) => (
        <li key={key} className={`funnel-${key}`}>
          <div className="funnel-label"><Icon size={15} aria-hidden /> <span>{label}</span></div>
          <div className="funnel-bar" aria-hidden><span style={{ width: `${Math.max(n ? 2 : 0, (n / max) * 100)}%` }} /></div>
          <div className="funnel-n">{n}</div>
          <small className="funnel-note">{note}</small>
        </li>
      ))}
    </ol>
  );
}

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

/** Today's briefing: what the satellites saw in your area, what was thrown out, and where to start. */
function Briefing() {
  const { me } = useSession();
  const [h, setH] = useState<HomeData | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.home().then(setH).catch((e) => setError(e.message)); }, []);

  if (error) return <main className="page"><p className="form-error" role="alert">Could not load your area: {error}</p></main>;
  if (!h) return <main className="page"><div className="skeleton-rows" aria-busy="true">{[0, 1, 2].map((i) => <span key={i} />)}</div></main>;

  return (
    <main className="page home">
      <header className="home-head">
        <div>
          <div className="eyebrow">{h.area.region || "Your area"}</div>
          <h1>{greeting()}{me?.officer.demo ? "" : `, ${h.officer.name.split(" ")[0]}`}. Here is {h.area.name}.</h1>
          <p className="lede">
            Satellite data to {fmtDate(h.as_of)}{h.last_pass ? `, last pass ${fmtDate(h.last_pass)}` : ""}. Of {h.fields} fields, {h.counts.visit === 0 ? "none need" : h.counts.visit === 1 ? "one needs" : `${h.counts.visit} need`} you today.
          </p>
        </div>
        <Link to="/cases" className="btn btn-primary">Open today's cases <ArrowRight size={15} aria-hidden /></Link>
      </header>

      <div className="home-grid">
        <section className="card" aria-labelledby="funnel-h">
          <h2 id="funnel-h" className="card-h">What FieldDx did with this week's passes</h2>
          <Funnel h={h} />
        </section>

        <section className="card" aria-labelledby="start-h">
          <h2 id="start-h" className="card-h">Start here</h2>
          {h.top.length ? (
            <ul className="start-list">
              {h.top.map((r) => (
                <li key={r.id}>
                  <Link to={`/case/${r.id}`}>
                    <SeverityBadge level={r.severity} />
                    <span className="start-main">
                      <strong>{r.field.name}</strong>
                      <small>{r.leading}{r.headline ? ` · ΔNDVI ${fmtDelta(r.headline.delta)}, ${r.headline.zone_label.toLowerCase()}` : ""}</small>
                    </span>
                    {r.confidence ? <ConfidenceMeter level={r.confidence} label={false} /> : null}
                    <ChevronRight size={16} aria-hidden className="chev" />
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty"><Tractor size={18} aria-hidden /> Nothing needs a visit. Every alert was explained by the data.</p>
          )}
          <Link to="/cases" className="more">All {h.alerts} alerts, including the dismissed ones <ArrowRight size={14} aria-hidden /></Link>
          <ol className="how">
            <li><span><strong>Open a case.</strong> The investigation replays: scene quality, the drop, boundary, neighbours, pattern, weather, season.</span></li>
            <li><span><strong>Read the diagnosis.</strong> Each cause lists evidence for and against, with IDs you can tap.</span></li>
            <li><span><strong>Do the one check.</strong> Record what you found; the ranking updates and the case closes.</span></li>
          </ol>
        </section>
      </div>

      <section aria-labelledby="map-h">
        <h2 id="map-h" className="card-h">Your fields on the map</h2>
        <Suspense fallback={<div className="fieldsmap skeleton" aria-busy="true" />}>
          <FieldsMap />
        </Suspense>
      </section>
    </main>
  );
}

export default function Home() {
  const { me } = useSession();
  if (!me?.area) return null;
  return me.area.status === "ready" ? <Briefing /> : <Building />;
}
