import type { Config } from "tailwindcss";

// Цвета — CSS-переменные темы (globals.css): 4 темы + высокий контраст.
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: token("surface"),
        soft: token("soft"),
        ink: token("ink"),
        muted: token("muted"),
        line: token("line"),
        primary: token("primary"),
        "on-primary": token("on-primary"),
        accent: token("accent"),
        good: token("good"),
        bad: token("bad"),
      },
      fontFamily: {
        body: ["var(--font-body)"],
      },
      borderRadius: {
        "4xl": "2rem",
      },
      maxWidth: {
        app: "34rem",
      },
    },
  },
  plugins: [],
};

export default config;
