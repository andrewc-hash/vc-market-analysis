"use client";

import { useState } from "react";
import type { MarketMap as MarketMapData } from "@/lib/api";
import { segmentColors, radiusFor } from "@/lib/viz";

interface Props {
  map: MarketMapData;
  ranking?: string[];
  onSelect?: (name: string) => void;
  // Light palette for the printed memo (the dark plot looks broken on white paper).
  light?: boolean;
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

export default function MarketMap({ map, ranking = [], onSelect, light = false }: Props) {
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

  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto"
        role="img"
        aria-label={`Market map plotting ${map.axes.x.label} against ${map.axes.y.label}`}
      >
        {/* plot area + quadrant dividers */}
        <rect x={ML} y={MT} width={PW} height={PH} fill={T.plotBg} stroke={T.frame} />
        <line x1={px(50)} y1={MT} x2={px(50)} y2={MT + PH} stroke={T.grid} strokeDasharray="4 4" />
        <line x1={ML} y1={py(50)} x2={ML + PW} y2={py(50)} stroke={T.grid} strokeDasharray="4 4" />

        {/* quadrant names */}
        {map.quadrants.map((q, i) => {
          const c = corner(q.x, q.y);
          return (
            <text key={i} x={c.x} y={c.y} textAnchor={c.anchor as "start" | "end"} fontSize="10.5" fill={T.quadrant}>
              {q.name}
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
                fontWeight={isTop ? 700 : 400}
                fontStyle={inc ? "italic" : undefined}
                fill={inc ? T.incumbentLabel : T.companyLabel}
              >
                {c.name}
              </text>
            </g>
          );
        })}

        {/* x-axis label + ends */}
        <text x={ML + PW / 2} y={H - 14} textAnchor="middle" fontSize="12" fontWeight={600} fill={T.axisLabel}>
          {map.axes.x.label}
        </text>
        <text x={ML} y={H - MB + 16} textAnchor="start" fontSize="9.5" fill={T.axisEnds}>
          ◀ {map.axes.x.low}
        </text>
        <text x={ML + PW} y={H - MB + 16} textAnchor="end" fontSize="9.5" fill={T.axisEnds}>
          {map.axes.x.high} ▶
        </text>

        {/* y-axis label + ends (rotated) */}
        <text
          x={16}
          y={MT + PH / 2}
          textAnchor="middle"
          fontSize="12"
          fontWeight={600}
          fill={T.axisLabel}
          transform={`rotate(-90 16 ${MT + PH / 2})`}
        >
          {map.axes.y.label}
        </text>
        <text
          x={ML - 6}
          y={MT + 10}
          textAnchor="end"
          fontSize="9.5"
          fill={T.axisEnds}
          transform={`rotate(-90 ${ML - 6} ${MT + 10})`}
        >
          {map.axes.y.high} ▲
        </text>
        <text
          x={ML - 6}
          y={MT + PH}
          textAnchor="start"
          fontSize="9.5"
          fill={T.axisEnds}
          transform={`rotate(-90 ${ML - 6} ${MT + PH})`}
        >
          ▼ {map.axes.y.low}
        </text>
      </svg>

      {/* legend */}
      <div className={`mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs ${light ? "text-slate-600" : "text-gray-400"}`}>
        {Object.entries(colors).map(([seg, col]) => (
          <span key={seg} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: col }} />
            {seg}
          </span>
        ))}
        {hasIncumbents && (
          <span className="inline-flex items-center gap-1.5">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full border border-dashed ${
                light ? "border-slate-500 bg-slate-400/40" : "border-gray-400 bg-gray-500/40"
              }`}
            />
            incumbent (reference)
          </span>
        )}
        <span className={light ? "text-amber-700" : "text-yellow-300"}>◇ white space</span>
        <span className={light ? "text-slate-500" : "text-gray-500"}>size = capital raised · ◯ ring = field leader (quality #1)</span>
      </div>
      <p className={`mt-1 text-[11px] ${light ? "text-slate-500" : "text-gray-600"}`}>
        Positions are scored 0–100 on each axis — illustrative framing, not exact measurement.
      </p>
    </div>
  );
}
