import { Area, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { SeriesData } from "../api";
import { fmtDate } from "../lib/format";

type Row = Record<string, any>;

function nearest(dates: string[], iso: string, dir: "up" | "down"): string | null {
  if (dir === "up") return dates.find((d) => d >= iso) ?? null;
  return [...dates].reverse().find((d) => d <= iso) ?? null;
}

/** Dot style by scene quality: solid usable, half-filled partial. Cloudy has no value to plot. */
function QDot(props: any) {
  const { cx, cy, payload, qkey } = props;
  if (cx == null || cy == null) return null;
  const q = payload[qkey];
  if (q === "partial")
    return (
      <g>
        <circle cx={cx} cy={cy} r={4} fill="#fff" stroke="#101c16" strokeWidth={1.5} />
        <path d={`M ${cx - 4} ${cy} A 4 4 0 0 0 ${cx + 4} ${cy} Z`} fill="#101c16" />
      </g>
    );
  return <circle cx={cx} cy={cy} r={3.5} fill="#101c16" stroke="#fff" strokeWidth={1} />;
}

function GapDot(props: any) {
  const { cx, cy, payload } = props;
  if (cx == null || cy == null) return null;
  const q = payload.__gap;
  if (!q) return null;
  return (
    <circle cx={cx} cy={cy} r={3.5} fill="#fff" stroke="#737b82" strokeWidth={1.5} strokeDasharray={q === "none" ? "2 2" : undefined}>
      <title>{q === "none" ? "No pass" : "Cloudy: no value"}</title>
    </circle>
  );
}

function TipBox({ active, payload, label, series }: any) {
  if (!active || !payload?.length) return null;
  const row: Row = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{fmtDate(label)}</strong>
      <span className={`q-word q-${row.__sceneQ}`}>{row.__sceneQ === "none" ? "No pass" : row.__sceneQ}</span>
      {series.zones.map((z: any) => {
        const v = row[z.id];
        return z.affected || v == null ? (
          <div key={z.id} className={z.affected ? "affected" : ""}>
            {z.label}: {v == null ? "no value" : v.toFixed(2)}
          </div>
        ) : null;
      })}
    </div>
  );
}

export function Timeline({ series }: { series: SeriesData }) {
  const affected = series.zones.filter((z) => z.affected);
  const others = series.zones.filter((z) => !z.affected);
  const dates = series.scenes.map((s) => s.date);

  const rows: Row[] = series.scenes.map((s, i) => {
    const row: Row = { date: s.date, __sceneQ: s.quality };
    for (const z of series.zones) {
      row[z.id] = s.zones[z.id].ndvi;
      row[`${z.id}__q`] = s.zones[z.id].quality;
    }
    const exp = series.expected[i].value;
    row.expected = [Math.max(0, exp - 0.08), Math.min(1, exp + 0.08)];
    row.__gap = s.quality === "cloudy" || s.quality === "none" ? s.quality : null;
    row.gap = row.__gap ? 0.04 : null;
    return row;
  });

  const ticks = dates.filter((_, i) => i % 3 === 0);
  return (
    <figure className="timeline">
      <div className="timeline-head">
        <h3>NDVI by zone</h3>
        <span className="muted small">Absolute NDVI, 2026 season · baseline {series.baseline}</span>
      </div>
      <div className="chart-box" role="img" aria-label="Line chart of NDVI per zone over the season, with the affected zones in dark ink and the alert date marked">
        <ResponsiveContainer width="100%" height={250}>
          <ComposedChart data={rows} margin={{ top: 14, right: 14, bottom: 4, left: -14 }}>
            <CartesianGrid stroke="var(--border-subtle)" vertical={false} />
            <XAxis dataKey="date" ticks={ticks} tickFormatter={fmtDate} tick={{ fontSize: 11, fill: "var(--text-3)" }} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
            <YAxis domain={[0, 0.9]} ticks={[0, 0.3, 0.6, 0.9]} tickFormatter={(v: number) => v.toFixed(1)} tick={{ fontSize: 11, fill: "var(--text-3)" }} tickLine={false} axisLine={false} />
            <Tooltip content={<TipBox series={series} />} />
            {series.windows.map((w) => {
              const x1 = nearest(dates, w.start, "up");
              const x2 = nearest(dates, w.end, "down") ?? dates[dates.length - 1];
              return x1 ? (
                <ReferenceArea key={w.id} x1={x1} x2={x2} fill="#e4e7b8" fillOpacity={0.55} strokeOpacity={0}
                  label={{ value: w.label + (w.verified ? "" : " (assumed)"), position: "insideTopLeft", fontSize: 10, fill: "#5c6670" }} />
              ) : null;
            })}
            <Area type="monotone" dataKey="expected" stroke="none" fill="var(--canvas-sunken)" fillOpacity={1} isAnimationActive={false} activeDot={false} />
            {others.map((z) => (
              <Line key={z.id} dataKey={z.id} stroke="var(--border-strong)" strokeWidth={1.25} dot={false} activeDot={false} connectNulls={false} isAnimationActive={false} />
            ))}
            {affected.map((z) => (
              <Line key={z.id} dataKey={z.id} stroke="var(--ink)" strokeWidth={2} connectNulls={false} isAnimationActive={false}
                dot={({ key, ...p }: any) => <QDot key={key ?? p.index} {...p} qkey={`${z.id}__q`} />} activeDot={{ r: 5 }} />
            ))}
            <Line dataKey="gap" stroke="none" isAnimationActive={false} activeDot={false} dot={({ key, ...p }: any) => <GapDot key={key ?? p.index} {...p} />} />
            <ReferenceLine x={series.alert_date} stroke="#b91c1c" strokeDasharray="4 3"
              label={{ value: "Alert", position: "top", fontSize: 10, fill: "#b91c1c" }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="timeline-legend">
        <span><i className="lg-line ink" /> Affected zone</span>
        <span><i className="lg-line grey" /> Other zones</span>
        <span><i className="lg-band" /> Expected range for the crop</span>
        <span><i className="lg-dot solid" /> Usable</span>
        <span><i className="lg-dot half" /> Partial</span>
        <span><i className="lg-dot hollow" /> Cloudy or no pass: no value, line breaks</span>
      </figcaption>
    </figure>
  );
}
