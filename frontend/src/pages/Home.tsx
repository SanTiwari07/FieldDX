import { lazy, Suspense, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertTriangle, Check, ChevronRight, CircleDashed, MapPin, RefreshCw, Stethoscope, Tractor, X } from "lucide-react";
import { api, BuildState, BuildStep, HomeData } from "../api";
import { useSession } from "../session";
import { fmtDate, plainDrop, sureWord } from "../lib/format";
import { SeverityBadge, Spinner } from "../components/ui";

const FieldsMap = lazy(() => import("../components/FieldsMap"));

function since(iso?: string, until?: string): string {
  if (!iso) return "";
  const s = Math.max(0, ((until ? new Date(until).getTime() : Date.now()) - new Date(iso).getTime()) / 1000);
  return s < 60 ? `${Math.round(s)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`;
}

/** Each build step in the officer's words, with what it is for until the build says more. */
const STEP_WORDS: Record<string, [string, string]> = {
  boundaries: ["Field shapes", "The outline of every field, from the Fields of the World map"],
  imagery: ["Satellite passes", "Sentinel-2 images of the area, with clouds taken out"],
  weather: ["Rain and heat", "Daily weather for the area"],
  fields: ["Fields to watch", "The fields big and clear enough to read from space"],
  seasons: ["Harvest season", "When crops here were cut last year"],
  alerts: ["Alerts", "Fields that lost green, and the likely reason"],
};

function StepRow({ s, said }: { s: BuildStep; said?: string }) {
  const [label, what] = STEP_WORDS[s.id] ?? [s.label, ""];
  const word = s.state === "done" ? "Done" : s.state === "running" ? "Working on it" : s.state === "failed" ? "Stopped" : "Waiting";
  return (
    <li className={`bstep bstep-${s.state}`} aria-current={s.state === "running" ? "step" : undefined}>
      <span className="bstep-icon" aria-hidden>
        {s.state === "done" ? <Check size={13} strokeWidth={3} /> : s.state === "running" ? <Spinner size={14} /> : s.state === "failed" ? <X size={13} strokeWidth={3} /> : <CircleDashed size={14} />}
      </span>
      <div className="bstep-body">
        <div className="bstep-head">
          <strong>{label}</strong>
          <small><span className="sr-only">{word}. </span>{s.state === "running" || s.state === "done" ? since(s.started_at, s.ended_at) : ""}</small>
        </div>
        <p>{said ?? (s.detail || what)}</p>
        {s.state === "running" && s.progress !== null && s.progress !== undefined && (
          <div className="bar" role="progressbar" aria-label={`${label} downloaded`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(s.progress * 100)}>
            <span style={{ width: `${Math.max(3, s.progress * 100)}%` }} />
          </div>
        )}
      </div>
    </li>
  );
}

const PENDING_STEPS: BuildStep[] = Object.entries(STEP_WORDS)
  .map(([id, [label]]) => ({ id, label, state: "queued", detail: "", progress: null }));

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

  const queued = b?.status === "queued";
  const now = steps.find((s) => s.state === "running");
  return (
    <main className="page narrow building">
      <header className="build-head">
        <p className="home-where"><MapPin size={14} aria-hidden /> {[area.region?.split(",")[0], area.km2 ? `${area.km2} km² marked` : ""].filter((x) => x && x !== area.name).join(", ") || "Your land"}</p>
        <h1>{failed ? `${area.name} could not be set up` : queued ? `${area.name} is next in line` : `Setting up ${area.name}`}</h1>
        <p className="lede">
          {failed
            ? canRetry
              ? "Nothing is lost. What was already downloaded is kept, and trying again carries on from there."
              : "The data came in, but none of the fields here are big enough to watch. Mark the land again with larger fields."
            : queued
              ? `Another area is being set up first${b?.queue_position ? `; this one is number ${b.queue_position} in line` : ""}. It starts on its own.`
              : "FieldDx is gathering real field shapes, satellite passes and weather for your land. This takes a few minutes, and you can close this page while it runs."}
        </p>
      </header>
      {!failed && (
        <div className="build-progress">
          <p><strong>{done} of {steps.length} steps done</strong>{now && <span>Now: {(STEP_WORDS[now.id]?.[0] ?? now.label).toLowerCase()}</span>}</p>
          <div className="bar big" role="progressbar" aria-label="Setting up the area" aria-valuemin={0} aria-valuemax={steps.length} aria-valuenow={done}>
            <span style={{ width: `${Math.max(4, (done / steps.length) * 100)}%` }} />
          </div>
        </div>
      )}
      {failed && (
        <div className="build-error" role="alert">
          <AlertTriangle size={18} aria-hidden />
          <div>
            <strong>{b?.status === "interrupted" ? "The server restarted partway through." : canRetry ? "One of the steps could not finish." : "No fields to watch here yet."}</strong>
            {b?.error && <p>{b.error}</p>}
            <div className="row">
              {canRetry && <button type="button" className="btn btn-primary" onClick={retry} disabled={busy}>{busy ? <Spinner /> : <RefreshCw size={14} aria-hidden />} Try again</button>}
              <button type="button" className={`btn ${canRetry ? "btn-outline" : "btn-primary"}`} onClick={other}>Mark the land again</button>
            </div>
          </div>
        </div>
      )}
      <ol className="bsteps" aria-label="Steps">
        {steps.map((s) => <StepRow key={s.id} s={s} said={s.state === "failed" && b?.error && s.detail && b.error.startsWith(s.detail.slice(0, 80)) ? "Stopped here, for the reason above." : undefined} />)}
      </ol>
      <p className="build-sources">
        Where the data comes from: field shapes from {area.field_source === "ftw_model" ? "the Fields of the World model, run on this land" : "the published Fields of the World map"};
        satellite images from Copernicus Sentinel-2 through Google Earth Engine, with clouds masked pixel by pixel; weather from Open-Meteo.
      </p>
    </main>
  );
}

type Seg = { key: string; label: string; n: number; note: string; to: string };

/** Every alert of the window in one bar: the few that need the officer first, then what FieldDx set aside and why. */
function Triage({ h }: { h: HomeData }) {
  const segs: Seg[] = [
    { key: "visit", label: "Need you", n: h.counts.visit, note: "a call or a visit", to: "/cases#visit" },
    { key: "watch", label: "Watching", n: h.counts.watch, note: "seen once, waiting for the next pass", to: "/cases#watching" },
    { key: "area", label: "Area-wide", n: h.counts.area_alert, note: "neighbours changed too", to: "/cases#area" },
    { key: "harvest", label: "Harvest", n: h.counts.harvest, note: "looks like a crop being cut", to: "/cases#harvest" },
    { key: "dismissed", label: "Set aside", n: h.counts.dismissed, note: "cloud, field edges or field work", to: "/cases#dismissed" },
  ].filter((s) => s.n > 0);
  const total = Math.max(1, segs.reduce((a, s) => a + s.n, 0));
  const aside = h.alerts - h.counts.visit;
  return (
    <section className="triage" aria-labelledby="triage-h">
      <h2 id="triage-h">
        {h.alerts} of {h.fields} fields lost green in the last three weeks. {aside > 0 ? `${aside} of them were explained without a visit.` : ""}
      </h2>
      <div className="triage-bar" role="img" aria-label={segs.map((s) => `${s.label} ${s.n}`).join(", ")}>
        {segs.map((s) => <span key={s.key} className={`tb-${s.key}`} style={{ flexGrow: s.n }} />)}
      </div>
      <ul className="triage-keys">
        {segs.map((s) => (
          <li key={s.key}>
            <Link to={s.to} className={`tk tk-${s.key}`}>
              <i aria-hidden />
              <strong>{s.n}</strong>
              <span>{s.label}<small>{s.note}</small></span>
            </Link>
          </li>
        ))}
      </ul>
      <p className="sr-only">{Math.round((h.counts.visit / total) * 100)}% of alerts need a person.</p>
    </section>
  );
}

function greeting(): string {
  const hr = new Date().getHours();
  return hr < 12 ? "Good morning" : hr < 17 ? "Good afternoon" : "Good evening";
}

/** Today's briefing: one sentence on the area, where the alerts went, and the fields to start with beside the map. */
function Briefing() {
  const { me } = useSession();
  const [h, setH] = useState<HomeData | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.home().then(setH).catch((e) => setError(e.message)); }, []);

  if (error) return <main className="page"><p className="form-error" role="alert">Could not load your area: {error}</p></main>;
  if (!h) return <main className="page"><div className="skeleton-rows" aria-busy="true">{[0, 1, 2].map((i) => <span key={i} />)}</div></main>;

  const v = h.counts.visit;
  return (
    <main className="page home">
      <header className="home-head">
        <div>
          <p className="home-where"><MapPin size={14} aria-hidden /> {h.area.name}{h.area.region ? `, ${h.area.region.split(",")[0]}` : ""}</p>
          <h1>
            {greeting()}{me?.officer.demo ? "" : `, ${h.officer.name.split(" ")[0]}`}.{" "}
            <span className="h-quiet">{v === 0 ? "No field needs you today." : v === 1 ? "One field needs you today." : `${v} fields need you today.`}</span>
          </h1>
          <p className="lede">Satellite passes up to {fmtDate(h.as_of)}{h.last_pass ? `, the latest on ${fmtDate(h.last_pass)}` : ""}. {h.fields} fields watched.</p>
        </div>
        {v > 0 && <Link to="/cases#visit" className="btn btn-primary btn-lg">See the {v} fields</Link>}
      </header>

      <Triage h={h} />

      <div className="home-work">
        <section className="start" aria-labelledby="start-h">
          <h2 id="start-h">Start with these</h2>
          {h.top.length ? (
            <ol className="start-list">
              {h.top.map((r) => (
                <li key={r.id}>
                  <Link to={`/case/${r.id}`}>
                    <span className="start-top">
                      <strong>{r.field.name}</strong>
                      <SeverityBadge level={r.severity} />
                    </span>
                    <span className="start-cause">{r.leading}{r.confidence ? <em className={`sure sure-${r.confidence}`}>{sureWord(r.confidence)}</em> : null}</span>
                    {r.headline && <small>{plainDrop(r.headline.delta, r.headline.zone_label)}, {fmtDate(r.headline.date)}</small>}
                  </Link>
                </li>
              ))}
            </ol>
          ) : (
            <p className="empty"><Tractor size={18} aria-hidden /> Nothing needs a visit. Every alert was explained by the data.</p>
          )}
          <Link to="/cases" className="more">All {h.alerts} fields with an alert <ChevronRight size={14} aria-hidden /></Link>
          <div className="how-tip">
            <Stethoscope size={16} aria-hidden />
            <p>Open a field to see the likely cause in plain words and the one quick check that settles it. Ask FieldDx anything about a field from the button at the bottom right.</p>
          </div>
        </section>

        <section className="home-map" aria-labelledby="map-h">
          <h2 id="map-h" className="sr-only">Your fields on the map</h2>
          <Suspense fallback={<div className="fieldsmap skeleton" aria-busy="true" />}>
            <FieldsMap />
          </Suspense>
        </section>
      </div>
    </main>
  );
}

export default function Home() {
  const { me } = useSession();
  if (!me?.area) return null;
  return me.area.status === "ready" ? <Briefing /> : <Building />;
}
