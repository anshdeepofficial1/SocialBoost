export function Wordmark({
  size = 16,
  mark = 26,
  light = false,
}: {
  size?: number;
  mark?: number;
  light?: boolean;
}) {
  return (
    <span className="flex items-center gap-2.5">
      <span
        className="relative flex items-center justify-center shrink-0 rounded-[8px]"
        style={{ width: mark, height: mark, background: light ? "#FFFFFF" : "var(--ink)" }}
      >
        <span className="rounded-full bg-[var(--signal)]" style={{ width: 3, height: Math.round(mark * 0.42) }} />
      </span>
      <span
        className="font-display font-bold tracking-[-0.03em]"
        style={{ fontSize: size, color: light ? "#FFFFFF" : "var(--ink)" }}
      >
        SIGNAL<span className="text-[var(--signal)]">.</span>
      </span>
    </span>
  );
}
