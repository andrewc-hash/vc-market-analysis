"use client";

import { Fragment, useState } from "react";
import type { MarketMap as MarketMapData } from "@/lib/api";
import { segmentColors, radiusFor } from "@/lib/viz";

interface Props {
  map: MarketMapData;
  ranking?: string[];
  onSelect?: (name: string) => void;
  // Light palette for the printed memo (the dark plot looks broken on white paper).
  light?: boolean;
  // Side layout: plot fills the viewport height on the left, vertical key on the right
  // (for the full-width Market Map tab — the stacked layout is kept for print).
  side?: boolean;
}

const W = 480;
const H = 470;
const ML = 70; // left margin (y label)
const MR = 20;
const MT = 26;
const MB = 70; // bottom margin (x label)
const PW = W - ML - MR;
const PH = H - MT - MB;

// Chrome palettes — the Okabe-Ito segment colors themselves work on both themes.
const DARK = {
  plotBg: "#0b1220",
  frame: "#374151",
  grid: "#374151",
  quadrant: "#6b7280",
  axisLabel: "#d1d5db",
  axisEnds: "#6b7280",
  companyLabel: "#e5e7eb",
  incumbentLabel: "#9ca3af",
  incumbentFill: "#6b7280",
  incumbentStroke: "#9ca3af",
  dotStroke: "#0b1220",
  highlight: "#F0E442", // top-pick ring + white-space marker (yellow reads on dark)
};
const LIGHT = {
  plotBg: "#f8fafc",
  frame: "#cbd5e1",
  grid: "#cbd5e1",
  quadrant: "#64748b",
  axisLabel: "#334155",
  axisEnds: "#64748b",
  companyLabel: "#1e293b",
  incumbentLabel: "#64748b",
  incumbentFill: "#94a3b8",
  incumbentStroke: "#64748b",
  dotStroke: "#ffffff",
  highlight: "#ca8a04", // amber-600 — yellow is invisible on white
};

export default function MarketMap({ map, ranking = [], onSelect, light = false, side = false }: Props) {
  const [hover, setHover] = useState<string | null>(null);
  const T = light ? LIGHT : DARK;
  const colors = segmentColors(map.companies.filter((c) => !c.is_incumbent).map((c) => c.segment));
  const hasIncumbents = map.companies.some((c) => c.is_incumbent);
  const maxRaised = Math.max(1, ...map.companies.map((c) => c.raised_usd_m || 0));
  const top = ranking[0];

  const px = (x: number) => ML + (Math.max(0, Math.min(100, x)) / 100) * PW;
  const py = (y: number) => MT + (1 - Math.max(0, Math.min(100, y)) / 100) * PH;

  const corner = (qx: string, qy: string) => ({
    x: qx === "high" ? ML + PW - 6 : ML + 6,
    y: qy === "high" ? MT + 14 : MT + PH - 8,
    anchor: qx === "high" ? "end" : "start",
  });

  const svgEl = (
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className={side ? "h-full max-w-full" : "w-full h-auto"}
        style={side ? { aspectRatio: `${W} / ${H}`, width: "auto" } : undefined}
        role="img"
        aria-label={`Market map plotting ${map.axes.x.label} against ${map.axes.y.label}`}
      >
        {/* plot area + quadrant dividers */}
        <rect x={ML} y={MT} width={PW} height={PH} fill={T.plotBg} stroke={T.frame} />
        <line x1={px(50)} y1={MT} x2={px(50)} y2={MT + PH} stroke={T.grid} strokeDasharray="4 4" />
        <line x1={ML} y1={py(50)} x2={ML + PW} y2={py(50)} stroke={T.grid} strokeDasharray="4 4" />

        {/* quadrant names — in the side (exhibit) layout they step back to tracked
            small-caps so they read as plot furniture, not company labels. The stacked
            layout (print PDF + Present) is untouched. */}
        {map.quadrants.map((q, i) => {
          const c = corner(q.x, q.y);
          return (
            <text
              key={i}
              x={c.x}
              y={c.y}
              textAnchor={c.anchor as "start" | "end"}
              fontSize={side ? 8.5 : 10.5}
              fontWeight={side ? 500 : undefined}
              letterSpacing={side ? "0.09em" : undefined}
              opacity={side ? 0.85 : undefined}
              fill={T.quadrant}
            >
              {side ? q.name.toUpperCase() : q.name}
            </text>
          );
        })}

        {/* investable white-space marker */}
        {map.white_space && (
          <rect
            x={px(map.white_space.x) - 7}
            y={py(map.white_space.y) - 7}
            width="14"
            height="14"
            transform={`rotate(45 ${px(map.white_space.x)} ${py(map.white_space.y)})`}
            fill="none"
            stroke={T.highlight}
            strokeWidth="1.5"
          />
        )}

        {/* company bubbles */}
        {map.companies.map((c) => {
          const inc = !!c.is_incumbent;
          const r = inc ? 8 : radiusFor(c.raised_usd_m, maxRaised);
          const isTop = !inc && c.name === top;
          const isHover = c.name === hover;
          const fill = inc ? T.incumbentFill : colors[c.segment || "Other"];
          const detail =
            `${c.name}${inc ? " (incumbent)" : ""}` +
            (c.segment ? ` · ${c.segment}` : "") +
            (c.stage ? ` · ${c.stage}` : "") +
            (c.raised_usd_m != null ? ` · $${c.raised_usd_m}M raised` : "") +
            (c.weighted_score != null ? ` · score ${c.weighted_score}` : "") +
            (c.rationale ? `\n${c.rationale}` : "");
          return (
            <g
              key={c.name}
              className="cursor-pointer"
              onMouseEnter={() => setHover(c.name)}
              onMouseLeave={() => setHover(null)}
              onClick={() => onSelect?.(c.name)}
            >
              <title>{detail}</title>
              <circle
                cx={px(c.x)}
                cy={py(c.y)}
                r={r}
                fill={fill}
                fillOpacity={inc ? 0.4 : isHover ? 0.95 : 0.7}
                stroke={isTop ? T.highlight : inc ? T.incumbentStroke : T.dotStroke}
                strokeWidth={isTop ? 2.5 : 1}
                strokeDasharray={inc ? "3 2" : undefined}
              />
              <text
                x={px(c.x)}
                y={py(c.y) - r - 3}
                textAnchor="middle"
                fontSize="10"
                fontWeight={isTop ? 700 : side ? 500 : 400}
                fontStyle={inc ? "italic" : undefined}
                fill={inc ? T.incumbentLabel : T.companyLabel}
                // Side layout only: a plot-background halo keeps company names legible
                // where they cross gridlines/bubbles (print + Present untouched).
                stroke={side ? T.plotBg : undefined}
                strokeWidth={side ? 3 : undefined}
                strokeLinejoin={side ? "round" : undefined}
                paintOrder={side ? "stroke" : undefined}
              >
                {c.name}
              </text>
            </g>
          );
        })}

        {/* x-axis label + ends — side layout tightens them into the tracked
            instrument voice; stacked (print/Present) keeps the original treatment */}
        <text
          x={ML + PW / 2}
          y={H - 14}
          textAnchor="middle"
          fontSize={side ? 10.5 : 12}
          fontWeight={600}
          letterSpacing={side ? "0.1em" : undefined}
          fill={T.axisLabel}
        >
          {side ? map.axes.x.label.toUpperCase() : map.axes.x.label}
        </text>
        <text x={ML} y={H - MB + 16} textAnchor="start" fontSize={side ? 9 : 9.5} fill={T.axisEnds}>
          {side ? `← ${map.axes.x.low}` : `◀ ${map.axes.x.low}`}
        </text>
        <text x={ML + PW} y={H - MB + 16} textAnchor="end" fontSize={side ? 9 : 9.5} fill={T.axisEnds}>
          {side ? `${map.axes.x.high} →` : `${map.axes.x.high} ▶`}
        </text>

        {/* y-axis label + ends (rotated) */}
        <text
          x={16}
          y={MT + PH / 2}
          textAnchor="middle"
          fontSize={side ? 10.5 : 12}
          fontWeight={600}
          letterSpacing={side ? "0.1em" : undefined}
          fill={T.axisLabel}
          transform={`rotate(-90 16 ${MT + PH / 2})`}
        >
          {side ? map.axes.y.label.toUpperCase() : map.axes.y.label}
        </text>
        <text
          x={ML - 6}
          y={MT + 10}
          textAnchor="end"
          fontSize={side ? 9 : 9.5}
          fill={T.axisEnds}
          transform={`rotate(-90 ${ML - 6} ${MT + 10})`}
        >
          {side ? `${map.axes.y.high} →` : `${map.axes.y.high} ▲`}
        </text>
        <text
          x={ML - 6}
          y={MT + PH}
          textAnchor="start"
          fontSize={side ? 9 : 9.5}
          fill={T.axisEnds}
          transform={`rotate(-90 ${ML - 6} ${MT + PH})`}
        >
          {side ? `← ${map.axes.y.low}` : `▼ ${map.axes.y.low}`}
        </text>
      </svg>
  );

  const segmentEntries = Object.entries(colors).map(([seg, col]) => (
    <span key={seg} className="inline-flex items-center gap-1.5">
      <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: col }} />
      {seg}
    </span>
  ));
  const incumbentEntry = hasIncumbents && (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full border border-dashed ${
          light ? "border-slate-500 bg-slate-400/40" : "border-gray-400 bg-gray-500/40"
        }`}
      />
      incumbent (reference)
    </span>
  );
  const footnote = (
    <p className={`text-[11px] leading-relaxed ${light ? "text-slate-500" : "text-gray-600"}`}>
      Positions are scored 0–100 on each axis — illustrative framing, not exact measurement.
    </p>
  );

  if (side) {
    // Exhibit key: every symbol sits in a fixed 14px lead column so the color dots
    // and glyphs align on one vertical grid; headings use the shared .panel-kicker.
    const keyText = light ? "text-slate-600" : "text-gray-400";
    const keyGrid = `grid grid-cols-[14px_1fr] gap-x-2 gap-y-1.5 text-xs ${keyText}`;
    const glyphHi = `justify-self-center ${light ? "text-amber-700" : "text-yellow-300"}`;
    const glyphLo = `justify-self-center ${light ? "text-slate-400" : "text-gray-500"}`;
    return (
      <div className="flex items-center justify-center gap-10">
        <div className="flex min-w-0 justify-center" style={{ height: "min(70vh, 740px)" }}>{svgEl}</div>
        <div className="w-60 shrink-0 space-y-5">
          <div>
            <div className="panel-kicker mb-2.5">Segments</div>
            <div className={`${keyGrid} items-baseline`}>
              {Object.entries(colors).map(([seg, col]) => (
                <Fragment key={seg}>
                  <span className="inline-block h-2.5 w-2.5 self-center justify-self-center rounded-full" style={{ background: col }} />
                  <span className="leading-snug">{seg}</span>
                </Fragment>
              ))}
              {hasIncumbents && (
                <>
                  <span
                    className={`inline-block h-2.5 w-2.5 self-center justify-self-center rounded-full border border-dashed ${
                      light ? "border-slate-500 bg-slate-400/40" : "border-gray-400 bg-gray-500/40"
                    }`}
                  />
                  <span className="leading-snug">incumbent (reference)</span>
                </>
              )}
            </div>
          </div>
          <div>
            <div className="panel-kicker mb-2.5">Reading the map</div>
            <div className={keyGrid}>
              <span className={glyphHi}>◇</span>
              <span className="leading-snug">investable white space</span>
              <span className={glyphHi}>◯</span>
              <span className="leading-snug">ring = field leader (quality #1)</span>
              <span className={glyphLo}>●</span>
              <span className="leading-snug">bubble size = capital raised</span>
              <span className={glyphLo}>→</span>
              <span className="leading-snug">click a company to open its profile</span>
            </div>
          </div>
          <div className={`border-t pt-3 ${light ? "border-slate-200" : "border-gray-800"}`}>{footnote}</div>
        </div>
      </div>
    );
  }

  return (
    <div>
      {svgEl}
      <div className={`mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs ${light ? "text-slate-600" : "text-gray-400"}`}>
        {segmentEntries}
        {incumbentEntry}
        <span className={light ? "text-amber-700" : "text-yellow-300"}>◇ white space</span>
        <span className={light ? "text-slate-500" : "text-gray-500"}>size = capital raised · ◯ ring = field leader (quality #1)</span>
      </div>
      <div className="mt-1">{footnote}</div>
    </div>
  );
}
