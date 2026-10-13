import type { ReactNode } from "react";
import {
  CheckCircle2, CircleDashed, CircleHelp, CloudOff, CircleDot, EyeOff, Info, MapPinned,
  OctagonAlert, TriangleAlert, CircleArrowDown, Satellite, Check, Eye,
} from "lucide-react";
import type { Confidence, Outcome, Quality, Severity } from "../api";

export function flashEvidence(id: string) {
  const el = document.getElementById(`ev-${id}`);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("flash");
  void el.offsetWidth;
  el.classList.add("flash");
  window.setTimeout(() => el.classList.remove("flash"), 1600);
}

export function EvidenceRef({ id }: { id: string }) {
  return (
    <button type="button" className="ev-ref" onClick={() => flashEvidence(id)} aria-label={`Evidence ${id}`}>
      {id}
    </button>
  );
}

export function Refs({ ids }: { ids: string[] }) {
  if (!ids.length) return null;
  return (
    <span className="refs">
      {ids.map((i) => (
        <EvidenceRef key={i} id={i} />
      ))}
    </span>
  );
}

const SEV = {
  high: { Icon: OctagonAlert, word: "High" },
  medium: { Icon: TriangleAlert, word: "Medium" },
  low: { Icon: CircleArrowDown, word: "Low" },
} as const;

export function SeverityBadge({ level }: { level: Severity | null }) {
  if (!level) return <span className="sev sev-none" aria-label="No severity">&ndash;</span>;
  const { Icon, word } = SEV[level];
  return (
    <span className={`badge sev sev-${level}`}>
      <Icon size={13} strokeWidth={2.25} aria-hidden /> {word}
    </span>
  );
}

export function StatusBadge({ outcome }: { outcome: Outcome }) {
  switch (outcome) {
    case "area_alert":
      return <span className="status status-area"><MapPinned size={14} aria-hidden /> Area alert</span>;
    case "auto_dismissed":
      return <span className="status status-dismissed"><EyeOff size={14} aria-hidden /> Dismissed</span>;
    case "resolved":
      return <span className="status status-resolved"><CheckCircle2 size={14} aria-hidden /> Resolved</span>;
    case "unexplained":
      return <span className="status status-open"><CircleHelp size={14} aria-hidden /> Ask or visit</span>;
    case "watch":
      return <span className="status status-watch"><Eye size={14} aria-hidden /> Watching</span>;
    default:
      return <span className="status status-open"><CircleDot size={14} aria-hidden /> Open</span>;
  }
}

const Q = {
  usable: { Icon: CheckCircle2, word: "Usable" },
  partial: { Icon: CircleDashed, word: "Partial" },
  cloudy: { Icon: CloudOff, word: "Cloudy" },
  none: { Icon: CircleHelp, word: "No image" },
} as const;

export function QualityBadge({ quality }: { quality: Quality }) {
  if (quality === "n/a") return null;
  const { Icon, word } = Q[quality];
  return (
    <span className={`badge q q-${quality}`}>
      <Icon size={12} strokeWidth={2.25} aria-hidden /> {word}
    </span>
  );
}

export function ConfidenceMeter({ level, label = true }: { level: Confidence; label?: boolean }) {
  const filled = level === "high" ? 3 : level === "medium" ? 2 : 1;
  return (
    <span className="conf" title={`${level} confidence`}>
      <span className="conf-bars" aria-hidden>
        {[0, 1, 2].map((i) => (
          <span key={i} className={i < filled ? "on" : ""} />
        ))}
      </span>
      {label && <span className="conf-word">{level[0].toUpperCase() + level.slice(1)}</span>}
    </span>
  );
}

export function DataNote({ text }: { text: string }) {
  return (
    <div className="data-note" role="note">
      <Satellite size={14} aria-hidden /> <span>{text}</span>
    </div>
  );
}

export function LimitsNote({ children }: { children: ReactNode }) {
  return (
    <div className="limits-note">
      <Info size={14} aria-hidden />
      <span>{children}</span>
    </div>
  );
}

export function Spinner({ size = 14 }: { size?: number }) {
  return <span className="spinner" style={{ width: size, height: size }} aria-hidden />;
}

export function TickIcon() {
  return <Check size={14} strokeWidth={2.5} aria-hidden />;
}
