import { useEffect, useState } from "react";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function fmtDate(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  return `${MONTHS[m - 1]} ${d}`;
}

export function fmtDelta(v: number | null | undefined): string {
  if (v === null || v === undefined) return "no value";
  const s = (v >= 0 ? "+" : "") + v.toFixed(2);
  return s.replace("-", "−");
}

export const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Change in NDVI against the field's own baseline: brown (loss) to teal (gain). */
export const DELTA_BINS = [
  { max: -0.15, color: "#7a3410", label: "≤ −0.15" },
  { max: -0.1, color: "#b8662a", label: "−0.15 to −0.10" },
  { max: -0.05, color: "#e7b98a", label: "−0.10 to −0.05" },
  { max: 0.05, color: "#f2f1ee", label: "−0.05 to +0.05" },
  { max: 0.1, color: "#a9d4cf", label: "+0.05 to +0.10" },
  { max: 0.15, color: "#4e9a93", label: "+0.10 to +0.15" },
  { max: Infinity, color: "#145e59", label: "≥ +0.15" },
];

export function deltaColor(v: number): string {
  return (DELTA_BINS.find((b) => v <= b.max) ?? DELTA_BINS[DELTA_BINS.length - 1]).color;
}

export const CROP_LABEL: Record<string, string> = { grape: "Grape", onion: "Onion" };

export function sentence(text: string): string {
  const i = text.search(/\.\s/);
  return i === -1 ? text : text.slice(0, i + 1);
}

export function idNum(id: string): number {
  return Number(id.replace(/\D/g, ""));
}

/** True while the media query matches. */
export function useMedia(query: string): boolean {
  const [match, setMatch] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setMatch(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return match;
}
