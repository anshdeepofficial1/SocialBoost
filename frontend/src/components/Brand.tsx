"use client";

import Image from "next/image";

export function Wordmark({
  size = 16,
  mark = 28,
  light = false,
}: {
  size?: number;
  mark?: number;
  light?: boolean;
}) {
  return (
    <span className={`brand-lockup ${light ? "brand-lockup-light" : ""}`} aria-label="SocialBoost AI">
      <span className="brand-icon" style={{ width: mark, height: mark }}>
        <Image
          src="/brand/socialboost.png"
          alt=""
          width={mark}
          height={mark}
          sizes={`${mark}px`}
          className="brand-icon-image"
        />
      </span>
      <span
        className="brand-word"
        style={{ fontSize: size, color: light ? "#FFFFFF" : "var(--ink)" }}
      >
        SocialBoost<span className="brand-ai"> AI</span>
      </span>
    </span>
  );
}
