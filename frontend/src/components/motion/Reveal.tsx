"use client";
import { useEffect, useRef, useState, ReactNode } from "react";

/** Reveals content as it enters the viewport. Content is visible by default (no-JS safe). */
export function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: any;
}) {
  const ref = useRef<HTMLElement | null>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const rect = el.getBoundingClientRect();
    if (rect.top < window.innerHeight * 0.92) return; // already in view: leave visible
    setHidden(true);
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            setHidden(false);
            io.disconnect();
          }
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -8% 0px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <Tag
      ref={ref as any}
      className={`reveal ${className}`}
      data-hidden={hidden ? "true" : "false"}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </Tag>
  );
}

/** Masked, line-by-line headline reveal. CSS-only so it always ends visible. */
export function SplitLines({
  lines,
  className = "",
  delay = 0,
  stagger = 90,
}: {
  lines: string[];
  className?: string;
  delay?: number;
  stagger?: number;
}) {
  return (
    <span className={`block ${className}`}>
      {lines.map((line, i) => (
        <span key={i} className="block">
          <span
            className="block anim-mask"
            style={{ animationDelay: `${delay + i * stagger}ms` }}
          >
            {line}
          </span>
        </span>
      ))}
    </span>
  );
}

/** Animated number that only animates once in view. */
export function Counter({ value, decimals = 0, prefix = "", suffix = "" }: { value: number; decimals?: number; prefix?: string; suffix?: string }) {
  const [shown, setShown] = useState(value);
  const ref = useRef<HTMLSpanElement>(null);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setShown(value); return; }
    const io = new IntersectionObserver((entries) => {
      if (!entries[0].isIntersecting || started.current) return;
      started.current = true;
      const start = performance.now();
      const dur = 1100;
      const tick = (now: number) => {
        const p = Math.min(1, (now - start) / dur);
        const eased = 1 - Math.pow(1 - p, 3);
        setShown(value * eased);
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
      io.disconnect();
    }, { threshold: 0.4 });
    io.observe(el);
    return () => io.disconnect();
  }, [value]);

  const formatted = shown.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  return <span ref={ref} className="mono">{prefix}{formatted}{suffix}</span>;
}

/** Small inline SVG that draws itself when scrolled into view. */
export function SignalRule({ className = "", height = 46, color = "var(--signal)" }: { className?: string; height?: number; color?: string }) {
  return (
    <svg viewBox="0 0 1200 46" preserveAspectRatio="none" className={className} style={{ height }} aria-hidden="true">
      <path
        d="M0 23 H160 L182 8 L204 38 L226 16 L248 30 L270 23 H520 L540 4 L560 42 L580 12 L600 34 L620 23 H900 L920 10 L940 36 L960 23 H1200"
        fill="none"
        stroke={color}
        strokeWidth="1.25"
        className="anim-draw"
        style={{ ["--len" as any]: 2600 }}
      />
    </svg>
  );
}
