import { useEffect, useRef } from "react";
import { ChevronLeft, ChevronRight, CloudOff, CircleDashed } from "lucide-react";
import type { SeriesData } from "../api";
import { fmtDate } from "../lib/format";

/**
 * Scene picker. Every pass is listed, including the ones the satellite could not see: those are
 * disabled and say why, so a gap reads as "looked, could not see" rather than "nothing happened".
 */
export function SceneBar({
  scenes, selected, alertDate, onSelect,
}: {
  scenes: SeriesData["scenes"];
  selected: string | null;
  alertDate: string;
  onSelect: (date: string) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const active = useRef<HTMLButtonElement>(null);

  const first = useRef(true);
  useEffect(() => {
    const el = active.current, b = box.current;
    if (!el || !b) return;
    const e = el.getBoundingClientRect(), t = b.getBoundingClientRect();
    const left = b.scrollLeft + (e.left - t.left) - t.width / 2 + e.width / 2;
    b.scrollTo({ left, behavior: first.current ? "auto" : "smooth" });
    first.current = false;
  }, [selected]);

  const step = (dir: number) => box.current?.scrollBy({ left: dir * 220, behavior: "smooth" });

  return (
    <div className="scenebar" role="group" aria-label="Pick a satellite pass">
      <button type="button" className="sb-arrow" aria-label="Earlier passes" onClick={() => step(-1)}>
        <ChevronLeft size={16} aria-hidden />
      </button>
      <div className="sb-track" ref={box}>
        {scenes.map((s) => {
          const viewable = s.quality === "usable" || s.quality === "partial";
          const on = s.date === selected;
          const word = s.quality === "cloudy" ? "Cloudy" : s.quality === "none" ? "No pass" : s.quality === "partial" ? "Partial" : "Clear";
          return (
            <button
              key={s.date}
              ref={on ? active : undefined}
              type="button"
              disabled={!viewable}
              aria-pressed={on}
              title={`${fmtDate(s.date)}: ${word}${s.date === alertDate ? ", alert raised" : ""}`}
              className={`sb-item q-${s.quality} ${on ? "on" : ""} ${s.date === alertDate ? "is-alert" : ""}`}
              onClick={() => onSelect(s.date)}
            >
              {s.quality === "cloudy" || s.quality === "none" ? <CloudOff size={13} aria-hidden /> : s.quality === "partial" ? <CircleDashed size={13} aria-hidden /> : <i aria-hidden />}
              <span>{fmtDate(s.date)}</span>
              {!viewable && <span className="sr-only">{word}</span>}
              {s.date === alertDate && <span className="sr-only">, alert raised</span>}
            </button>
          );
        })}
      </div>
      <button type="button" className="sb-arrow" aria-label="Later passes" onClick={() => step(1)}>
        <ChevronRight size={16} aria-hidden />
      </button>
    </div>
  );
}
