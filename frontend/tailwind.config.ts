import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Primary accent — azure (one accent for all UI chrome: buttons, focus, links,
        // slider, active toggles, focal/sector badges). Distinct from the green->red score scale.
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
        },
        // Cool-slate ramp (overrides the default neutral gray) so every surface, border and
        // text token adopts the azure-slate theme at once. Lightness ramps so layered surfaces
        // gain elevation: body 950 < card 900 < input/chip 800 < border 700.
        gray: {
          50: "#f4f7fb",
          100: "#e6edf5", // headings / strong text
          200: "#cbd5e3",
          300: "#a6b3c6", // body text
          400: "#7e8ca0", // labels / muted
          500: "#5d6b80", // placeholder / hint
          600: "#3e4a5c", // faint footnotes
          700: "#243044", // input border / dividers (lighter than the surface)
          750: "#202a38", // hover surface
          800: "#1b2430", // input bg / chips / card border
          850: "#131a24",
          900: "#0f1620", // cards
          950: "#0a0f16", // app background (deep cool slate, not flat black)
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        // Border-first elevation: flat cards, one soft pop for menus/drawer,
        // and a paper-sheet shadow for the white memo pane.
        card: "0 1px 2px 0 rgba(0,0,0,0.4)",
        pop: "0 4px 6px -2px rgba(0,0,0,0.35), 0 12px 16px -4px rgba(0,0,0,0.45)",
        sheet: "0 8px 24px -8px rgba(2,6,23,0.55)",
      },
    },
  },
  plugins: [],
};

export default config;
