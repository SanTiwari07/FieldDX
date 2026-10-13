import { Evidence } from "../api";
import { fmtDate, fmtDelta } from "../lib/format";
import { QualityBadge } from "./ui";

/* ---------- mini visuals ---------- */

function Strip({ items }: { items: { date: string; quality: string; alert: boolean }[] }) {
  return (
    <div className="mv-strip" role="img" aria-label="Quality of the last eight passes">
      {items.map((it) => (
        <div key={it.date} className={`mv-cell ${it.alert ? "is-alert" : ""}`}>
          <span className={`mv-sq mv-q-${it.quality}`} />
          <span className="mv-date">{fmtDate(it.date)}</span>
        </div>
      ))}
    </div>
  );
}

interface SparkPoint { date: string; quality: string; zone: number | null; interior: number | null }

function Spark({ points, label }: { points: SparkPoint[]; label: string }) {
  const W = 300, H = 76, padX = 6, padY = 8;
  const vals = points.flatMap((p) => [p.zone, p.interior]).filter((v): v is number => v !== null);
  const hasInterior = points.some((p) => p.interior !== null);
  const lo = Math.min(-0.05, ...vals), hi = Math.max(0.05, ...vals);
  const x = (i: number) => padX + (i * (W - 2 * padX)) / Math.max(1, points.length - 1);
  const y = (v: number) => padY + ((hi - v) * (H - 2 * padY)) / (hi - lo);
  const path = (key: "zone" | "interior") => {
    let d = "";
    let pen = false;
    points.forEach((p, i) => {
      const v = p[key];
      if (v === null || p.quality === "cloudy" || p.quality === "none") { pen = false; return; }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)} `;
      pen = true;
    });
    return d;
  };
  return (
    <figure className="mv-spark">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={hasInterior ? `ΔNDVI for ${label} against the interior` : `ΔNDVI for ${label}`}>
        <line x1={0} x2={W} y1={y(0)} y2={y(0)} stroke="var(--border-strong)" strokeDasharray="3 3" />
        <path d={path("interior")} fill="none" stroke="var(--border-strong)" strokeWidth={2} strokeLinecap="round" />
        <path d={path("zone")} fill="none" stroke="var(--ink)" strokeWidth={2.25} strokeLinecap="round" strokeLinejoin="round" />
        {points.map((p, i) => {
          if (p.zone === null) return <circle key={p.date} cx={x(i)} cy={y(0)} r={3} fill="var(--canvas)" stroke="var(--text-3)" strokeWidth={1.25} />;
          return <circle key={p.date} cx={x(i)} cy={y(p.zone)} r={3} fill={p.quality === "usable" ? "var(--ink)" : "var(--canvas)"} stroke="var(--ink)" strokeWidth={1.5} />;
        })}
      </svg>
      <figcaption>
        <span className="key"><i className="k-ink" /> {label || "Affected zone"}</span>
        {hasInterior && <span className="key"><i className="k-grey" /> Interior</span>}
        <span className="key muted">ΔNDVI vs baseline</span>
      </figcaption>
    </figure>
  );
}

function Bars({ rows, unit }: { rows: { label: string; value: number | null; anomalous?: boolean }[]; unit?: string }) {
  const max = Math.max(0.1, ...rows.map((r) => Math.abs(r.value ?? 0)));
  return (
    <div className="mv-bars" role="img" aria-label={`${unit ?? "Value"} by group`}>
      {rows.map((r) => {
        const v = r.value ?? 0;
        const w = (Math.abs(v) / max) * 50;
        return (
          <div key={r.label} className={`mv-bar-row ${r.anomalous ? "hot" : ""}`}>
            <span className="mv-bar-label">{r.label}</span>
            <span className="mv-bar-track">
              <span className="mv-bar-zero" />
              {r.value !== null && (
                <span className="mv-bar-fill" style={{ width: `${w}%`, [v < 0 ? "right" : "left"]: "50%" }} />
              )}
            </span>
            <span className="mv-bar-val">{r.value === null ? "n/a" : fmtDelta(r.value)}</span>
          </div>
        );
      })}
    </div>
  );
}

function Dots({ rows }: { rows: { id: string; name: string; delta: number; dropped: boolean; km: number }[] }) {
  return (
    <ul className="mv-dots" aria-label="Neighbouring plots">
      {rows.map((r) => (
        <li key={r.id} className={r.dropped ? "dropped" : ""} title={`${r.name}, ${r.km} km away`}>
          <span className="mv-dot" />
          <span className="mv-dot-id">{r.id}</span>
          <span className="mv-dot-val">{fmtDelta(r.delta)}</span>
        </li>
      ))}
    </ul>
  );
}

function Rain({ days }: { days: { date: string; rain: number; tmax: number }[] }) {
  const max = Math.max(10, ...days.map((d) => d.rain));
  return (
    <figure className="mv-rain">
      <div className="mv-rain-bars" role="img" aria-label="Daily rain, last 14 days">
        {days.map((d) => (
          <span key={d.date} className="mv-rain-col" title={`${fmtDate(d.date)}: ${d.rain} mm`}>
            <span className="mv-rain-bar" style={{ height: `${Math.max(d.rain > 0 ? 6 : 2, (d.rain / max) * 100)}%` }} />
          </span>
        ))}
      </div>
      <figcaption>
        <span>{fmtDate(days[0].date)}</span>
        <span className="muted">daily rain, mm</span>
        <span>{fmtDate(days[days.length - 1].date)}</span>
      </figcaption>
    </figure>
  );
}

function Months({ rows }: { rows: { month: string; value: number }[] }) {
  const max = 0.9;
  const names = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
  return (
    <figure className="mv-months">
      <div className="mv-months-bars" role="img" aria-label="Median NDVI by month over the past year">
        {rows.map((r) => (
          <span key={r.month} className="mv-month" title={`${r.month}: ${r.value.toFixed(2)}`}>
            <span className="mv-month-bar" style={{ height: `${Math.max(4, (r.value / max) * 100)}%` }} />
            <small>{names[Number(r.month.slice(5)) - 1]}</small>
          </span>
        ))}
      </div>
      <figcaption><span className="muted">median NDVI by month, last 12 months</span></figcaption>
    </figure>
  );
}

function Visual({ v }: { v: any }) {
  if (!v) return null;
  switch (v.type) {
    case "strip": return <Strip items={v.items} />;
    case "spark": return <Spark points={v.points} label={v.label} />;
    case "bars": return <Bars rows={v.rows} unit={v.unit} />;
    case "zones":
      return <Bars unit="ΔNDVI" rows={v.rows.map((r: any) => ({ label: r.label, value: r.value, anomalous: r.anomalous }))} />;
    case "dots": return <Dots rows={v.rows} />;
    case "rain": return <Rain days={v.days} />;
    case "months": return <Months rows={v.rows} />;
    default: return null;
  }
}

/* ---------- the card ---------- */

export function EvidenceCard({ e }: { e: Evidence }) {
  return (
    <article id={`ev-${e.id}`} className={`ev-card stance-${e.stance}`}>
      <header>
        <span className="ev-id">{e.id}</span>
        <h4>{e.title}</h4>
        <QualityBadge quality={e.quality} />
        {e.stance !== "neutral" && (
          <span className={`stance-word stance-word-${e.stance}`}>{e.stance === "for" ? "+ supports" : "− against"}</span>
        )}
      </header>
      <p>{e.finding}</p>
      <Visual v={e.visual} />
      <footer>
        {e.source} · {fmtDate(e.as_of)}
      </footer>
    </article>
  );
}
