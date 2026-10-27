import type { Metadata } from "next";
import { Space_Grotesk, Inter, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

const display = Space_Grotesk({ subsets: ["latin"], variable: "--font-display", weight: ["400","500","600","700"] });
const body = Inter({ subsets: ["latin"], variable: "--font-body", weight: ["300","400","500","600"] });
const mono = IBM_Plex_Mono({ subsets: ["latin"], variable: "--font-mono", weight: ["400","500"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://socialboostweb.vercel.app"),
  applicationName: "SocialBoost AI",
  title: {
    default: "SocialBoost AI — Creator Analytics",
    template: "%s | SocialBoost AI",
  },
  description: "Analyze short-form videos, learn from real channel history, and plan smarter releases with SocialBoost AI.",
  icons: {
    icon: [{ url: "/icon.png", type: "image/png" }],
    shortcut: "/icon.png",
    apple: "/icon.png",
  },
  openGraph: {
    type: "website",
    siteName: "SocialBoost AI",
    title: "SocialBoost AI — Creator Analytics",
    description: "A calmer, evidence-first workspace for short-form video analysis and channel performance.",
    images: [{ url: "/brand/socialboost.png", alt: "SocialBoost AI" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "SocialBoost AI — Creator Analytics",
    description: "A calmer, evidence-first workspace for short-form video analysis and channel performance.",
    images: ["/brand/socialboost.png"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body><AuthProvider>{children}</AuthProvider></body>
    </html>
  );
}