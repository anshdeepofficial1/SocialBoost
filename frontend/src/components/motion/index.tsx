"use client";
import { useEffect, useRef, ReactNode } from "react";
import { motion } from "framer-motion";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

export function PageTransition({ children }: { children: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}>
      {children}
    </motion.div>
  );
}

export function RevealText({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) return;
    gsap.fromTo(el, { clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)", duration: 0.9, ease: "power3.out", scrollTrigger: { trigger: el, start: "top 85%" } });
  }, []);
  return <div ref={ref} className={className}>{children}</div>;
}

export function SplitTextReveal({ text, className = "" }: { text: string; className?: string }) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) return;
    const lines = text.split("\n");
    el.innerHTML = lines.map((l) => `<span class="block overflow-hidden"><span class="block">${l}</span></span>`).join("");
    const spans = el.querySelectorAll("span > span");
    gsap.fromTo(spans, { y: "100%" }, { y: "0%", duration: 0.8, stagger: 0.08, ease: "power3.out", scrollTrigger: { trigger: el, start: "top 85%" } });
  }, [text]);
  return <h2 ref={ref} className={className}>{text}</h2>;
}

export function ScrollReveal({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) return;
    gsap.fromTo(el, { opacity: 0, y: 40 }, { opacity: 1, y: 0, duration: 0.8, ease: "power2.out", scrollTrigger: { trigger: el, start: "top 85%" } });
  }, []);
  return <div ref={ref} className={className}>{children}</div>;
}

export function SignalLine({ className = "" }: { className?: string }) {
  const ref = useRef<SVGPathElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) return;
    const len = el.getTotalLength();
    gsap.set(el, { strokeDasharray: len, strokeDashoffset: len });
    gsap.to(el, { strokeDashoffset: 0, duration: 1.6, ease: "power2.out", scrollTrigger: { trigger: el, start: "top 90%" } });
  }, []);
  return (
    <svg viewBox="0 0 1000 60" className={className}>
      <path ref={ref} d="M0,30 C200,10 400,50 600,25 S800,40 1000,30" fill="none" stroke="var(--signal)" strokeWidth="2" />
    </svg>
  );
}

export function AnimatedWaveform({ data, className = "" }: { data?: number[]; className?: string }) {
  const ref = useRef<SVGSVGElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) return;
    const bars = el.querySelectorAll("rect");
    gsap.fromTo(bars, { scaleY: 0, transformOrigin: "center" }, { scaleY: 1, duration: 0.6, stagger: 0.02, ease: "power2.out", scrollTrigger: { trigger: el, start: "top 90%" } });
  }, []);
  const vals = data || Array.from({ length: 60 }, (_, i) => 10 + Math.abs(Math.sin(i * 0.4)) * 40);
  return (
    <svg ref={ref} viewBox="0 0 600 80" className={className}>
      {vals.map((v, i) => (
        <rect key={i} x={i * 10} y={40 - v / 2} width={6} height={v} fill="var(--signal)" opacity={0.8} />
      ))}
    </svg>
  );
}

export function VideoFrameReveal({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) return;
    gsap.fromTo(el, { clipPath: "inset(10% 10% 10% 10% round 0px)" }, { clipPath: "inset(0% 0% 0% 0% round 0px)", duration: 1.2, ease: "power3.out", scrollTrigger: { trigger: el, start: "top 80%" } });
  }, []);
  return <div ref={ref} className={className}>{children}</div>;
}

export function NumberCounter({ value, className = "" }: { value: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) { el.textContent = String(value); return; }
    const obj = { v: 0 };
    gsap.to(obj, { v: value, duration: 1.4, ease: "power2.out", onUpdate: () => { el.textContent = Math.round(obj.v).toLocaleString(); } });
  }, [value]);
  return <span ref={ref} className={className}>0</span>;
}

export function StaggeredList({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) return;
    const items = el.children;
    gsap.fromTo(items, { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.6, stagger: 0.08, ease: "power2.out", scrollTrigger: { trigger: el, start: "top 85%" } });
  }, []);
  return <div ref={ref} className={className}>{children}</div>;
}

export function MagneticButton({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(pointer: coarse)").matches) return;
    const onMove = (e: MouseEvent) => {
      const r = el.getBoundingClientRect();
      const x = e.clientX - r.left - r.width / 2;
      const y = e.clientY - r.top - r.height / 2;
      gsap.to(el, { x: x * 0.25, y: y * 0.25, duration: 0.3, ease: "power2.out" });
    };
    const onLeave = () => gsap.to(el, { x: 0, y: 0, duration: 0.4, ease: "power2.out" });
    el.addEventListener("mousemove", onMove);
    el.addEventListener("mouseleave", onLeave);
    return () => {
      el.removeEventListener("mousemove", onMove);
      el.removeEventListener("mouseleave", onLeave);
    };
  }, []);
  return <button ref={ref} className={className}>{children}</button>;
}

export function AnimatedUnderline({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <span className={`relative inline-block ${className}`}>
      {children}
      <motion.span initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }} transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }} className="absolute left-0 bottom-0 h-[2px] w-full bg-[var(--signal)] origin-left" />
    </span>
  );
}

export function AnalysisProgress({ progress, label }: { progress: number; label: string }) {
  return (
    <div className="flex items-center gap-4">
      <div className="flex-1 h-2 bg-[var(--hairline)]">
        <motion.div className="h-2 bg-[var(--signal)]" initial={{ width: 0 }} animate={{ width: `${progress}%` }} transition={{ duration: 0.4 }} />
      </div>
      <span className="mono text-xs">{progress}%</span>
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function SmoothSectionTransition({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={className}>{children}</section>;
}