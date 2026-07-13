import type { Metadata } from "next";
import { Inter, Source_Serif_4 } from "next/font/google";
import "./globals.css";

// Inter for app chrome (tabular numerals on data), Source Serif 4 for the
// memo reading pane — loaded at build time via next/font (no runtime dep).
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const serif = Source_Serif_4({ subsets: ["latin"], variable: "--font-serif", display: "swap" });

export const metadata: Metadata = {
  title: "Prospectus — first-pass IC memos on any market",
  description:
    "Prospectus turns one market prompt into an institutional, verdict-first VC memo — dual-AI analyst debate, math computed in code, live dated research.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${serif.variable}`}>
      <body className="min-h-screen font-sans">{children}</body>
    </html>
  );
}
