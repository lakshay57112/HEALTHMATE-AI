import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    container: { center: true, padding: "1.25rem", screens: { "2xl": "1280px" } },
    extend: {
      colors: {
        primary: { DEFAULT: "#4D8B73", foreground: "#FFFFFF", 50: "#F2F7F4", 100: "#E8F1EC", 200: "#CFE2D7", 300: "#A9CBB8", 600: "#3F7560", 700: "#335F4E", 800: "#284A3D" },
        secondary: { DEFAULT: "#E8F1EC", foreground: "#284A3D" },
        background: "#FAFBFA",
        surface: "#FFFFFF",
        ink: { DEFAULT: "#202923", soft: "#3C4741" },
        muted: { DEFAULT: "#84918A", foreground: "#84918A", bg: "#F3F5F3" },
        line: { DEFAULT: "#E6EAE7", strong: "#D5DBD7" },
        warning: { DEFAULT: "#E9AA53", bg: "#FDF4E7", ink: "#8A5A16" },
        danger: { DEFAULT: "#D96C6C", bg: "#FBECEC", ink: "#9B3434" },
        info: { DEFAULT: "#6C8EBF", bg: "#EEF3FA" },
        border: "#E6EAE7",
        input: "#D5DBD7",
        ring: "#4D8B73",
        foreground: "#202923",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "Inter", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
        hindi: ["var(--font-geist-sans)", "Noto Sans Devanagari", "Mangal", "sans-serif"],
      },
      borderRadius: { xl: "14px", "2xl": "18px", "3xl": "24px" },
      boxShadow: {
        card: "0 1px 2px rgba(32,41,35,0.04), 0 1px 1px rgba(32,41,35,0.02)",
        soft: "0 4px 24px -8px rgba(32,41,35,0.10)",
        lift: "0 12px 32px -12px rgba(32,41,35,0.18)",
      },
      keyframes: {
        "fade-up": { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        pulseRing: { "0%": { boxShadow: "0 0 0 0 rgba(77,139,115,0.35)" }, "100%": { boxShadow: "0 0 0 12px rgba(77,139,115,0)" } },
      },
      animation: { "fade-up": "fade-up .35s ease-out both", "pulse-ring": "pulseRing 1.8s ease-out infinite" },
    },
  },
  plugins: [animate],
};
export default config;
