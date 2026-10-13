import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { api, CaseFile, CaseResult, Evidence } from "./api";
import { prefersReducedMotion } from "./lib/format";

export interface StepDef {
  tool: string;
  title: string;
  running: string;
}

export const STEPS: StepDef[] = [
  { tool: "scene_quality", title: "Scene quality", running: "Checking scene quality" },
  { tool: "ndvi_series", title: "NDVI change", running: "Measuring the NDVI change" },
  { tool: "boundary_check", title: "Boundary check", running: "Testing the field boundary" },
  { tool: "neighbour_compare", title: "Neighbours", running: "Comparing same-crop neighbours" },
  { tool: "spatial_pattern", title: "Spatial pattern", running: "Reading the spatial pattern" },
  { tool: "weather", title: "Weather", running: "Pulling weather for the window" },
  { tool: "crop_calendar", title: "Crop calendar", running: "Checking the crop calendar" },
  { tool: "engine", title: "Hypothesis rules", running: "Applying the hypothesis rules" },
  { tool: "next_check", title: "Next best check", running: "Choosing the next best check" },
];

export interface StepState {
  state: "queued" | "running" | "done" | "skipped";
  reason?: string;
  summary?: string;
  evidenceIds?: string[];
}

const fresh = (): Record<string, StepState> =>
  Object.fromEntries(STEPS.map((s) => [s.tool, { state: "queued" } as StepState]));

export type Phase = "loading" | "running" | "done" | "error";

/** Loads a case, then replays its investigation over server-sent events. */
export function useInvestigation(caseId: string, instant = false) {
  const [steps, setSteps] = useState<Record<string, StepState>>(fresh);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [result, setResult] = useState<CaseResult | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState("");
  const source = useRef<EventSource | null>(null);

  const stop = () => {
    source.current?.close();
    source.current = null;
  };

  const run = useCallback(
    (pace?: number) => {
      stop();
      setSteps(fresh());
      setEvidence([]);
      setPhase("running");
      const url = `/api/cases/${caseId}/investigate${pace === undefined ? "" : `?pace=${pace}`}`;
      const es = new EventSource(url);
      source.current = es;
      const on = (name: string, fn: (d: any) => void) =>
        es.addEventListener(name, (e) => fn(JSON.parse((e as MessageEvent).data)));

      on("step", (d) =>
        setSteps((s) => ({
          ...s,
          [d.tool]: { state: d.state, reason: d.reason, summary: d.summary, evidenceIds: d.evidence_ids },
        })),
      );
      on("evidence", (d) => setEvidence((list) => (list.some((e) => e.id === d.id) ? list : [...list, d])));
      on("diagnosis", (d: CaseResult) => {
        setResult(d);
        setEvidence(d.evidence);
      });
      on("narrative", (d: { narrative: CaseFile; source: "gemini" | "template" }) =>
        setResult((r) => (r ? { ...r, narrative: d.narrative, narrative_source: d.source } : r)),
      );
      on("done", () => {
        setPhase("done");
        stop();
      });
      es.onerror = () => {
        if (source.current) {
          setPhase((p) => (p === "done" ? p : "error"));
          setError("The investigation stream was interrupted.");
          stop();
        }
      };
    },
    [caseId],
  );

  useEffect(() => {
    let cancelled = false;
    setResult(null);
    setPhase("loading");
    api
      .getCase(caseId)
      .then((c) => {
        if (cancelled) return;
        setResult(c);
        const quick = instant || prefersReducedMotion() || c.outcome === "resolved";
        run(quick ? 0 : undefined);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e.message);
          setPhase("error");
        }
      });
    return () => {
      cancelled = true;
      stop();
    };
  }, [caseId, instant, run]);

  const replay = () => run(prefersReducedMotion() ? 0 : undefined);
  const apply = (r: CaseResult) => {
    setResult(r);
    setEvidence(r.evidence);
  };
  return { steps, evidence, result, phase, error, replay, apply };
}

/** FLIP animation: when the order of keys changes, glide each item from its old place. */
export function useFlip(order: string[]) {
  const nodes = useRef(new Map<string, HTMLElement>());
  const rects = useRef(new Map<string, number>());
  const key = order.join("|");

  useLayoutEffect(() => {
    const reduce = prefersReducedMotion();
    nodes.current.forEach((el, id) => {
      const next = el.getBoundingClientRect().top + window.scrollY;
      const prev = rects.current.get(id);
      if (prev !== undefined && !reduce) {
        const dy = prev - next;
        if (Math.abs(dy) > 1) {
          el.style.transition = "none";
          el.style.transform = `translateY(${dy}px)`;
          void el.offsetWidth;
          el.style.transition = "transform 320ms var(--ease)";
          el.style.transform = "";
        }
      }
      rects.current.set(id, next);
    });
  }, [key]);

  return (id: string) => (el: HTMLElement | null) => {
    if (el) nodes.current.set(id, el);
    else nodes.current.delete(id);
  };
}
