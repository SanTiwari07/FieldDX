/** The FieldDx mark: a field read in a 3 by 3 grid of zones, the centre one flagged. */
export function Mark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="mark">
      <rect width="32" height="32" rx="9" fill="var(--ink)" />
      <g fill="#fff">
        {[0, 1, 2].flatMap((r) =>
          [0, 1, 2].map((c) => (
            <rect key={`${r}${c}`} x={6 + c * 7} y={6 + r * 7} width="6" height="6" rx="1.5"
              opacity={r === 1 && c === 1 ? 0 : 0.5} />
          )),
        )}
      </g>
      <rect x="13" y="13" width="6" height="6" rx="1.5" fill="var(--turmeric)" />
    </svg>
  );
}
