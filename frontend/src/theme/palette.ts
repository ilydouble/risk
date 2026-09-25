/**
 * Chart palette — literal color values mirroring the light-mode design tokens in index.css.
 * Porcelain cobalt blue primary + gold accent on a porcelain-white canvas.
 * Recharts renders SVG attributes, so real color strings are used here.
 */
export const chartPalette = {
  primary: "#447ac9",
  primarySoft: "rgba(68, 122, 201, 0.16)",
  accent: "#b47a1e",
  accentSoft: "rgba(180, 122, 30, 0.16)",
  secondary: "#6f7580",
  riskLow: "#2f5da8",
  riskMedium: "#b6770b",
  riskHigh: "#c9302d",
  grid: "#e4e7ec",
  axis: "#8b93a3",
  surface: "#ffffff",
} as const;