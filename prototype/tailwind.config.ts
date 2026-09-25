import type { Config } from "tailwindcss";

// Все цвета — CSS-переменные (src/design-system/tokens.css): светлая и тёмная тема
// переключаются одним атрибутом data-theme, без дублирования классов.
const token = (name: string) => `rgb(var(--c-${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: token("surface"),
        card: token("card"),
        latte: token("latte"),
        caramel: token("caramel"),
        coffee: token("coffee"),
        ink: token("ink"),
        muted: token("muted"),
        line: token("line"),
        gold: token("gold"),
        good: token("good"),
        bad: token("bad"),
        "on-caramel": token("on-caramel"),
      },
      fontFamily: { sans: ["Nunito", "ui-rounded", "system-ui", "sans-serif"] },
      borderRadius: { "4xl": "2rem", "5xl": "2.5rem" },
      boxShadow: {
        soft: "0 1px 2px rgb(var(--c-shadow) / .06), 0 8px 24px -8px rgb(var(--c-shadow) / .18)",
        lift: "0 2px 4px rgb(var(--c-shadow) / .08), 0 18px 40px -12px rgb(var(--c-shadow) / .28)",
        press: "inset 0 -4px 0 rgb(0 0 0 / .14)",
      },
      spacing: { 18: "4.5rem" },
      screens: { xs: "360px" },
    },
  },
  plugins: [],
} satisfies Config;
