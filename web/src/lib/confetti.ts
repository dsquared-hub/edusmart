import confetti from "canvas-confetti";

function themeColor(name: string): string {
  const triplet = getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
  const parts = triplet.split(/\s+/).map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return "#ffcc33";
  return "#" + parts.map((p) => p.toString(16).padStart(2, "0")).join("");
}

/** Конфетти в цветах текущей темы. Уважает «уменьшить движение». */
export function celebrate(big = true) {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const colors = ["primary", "accent", "good"].map(themeColor);
  const base = { colors, disableForReducedMotion: true, zIndex: 60 };
  if (!big) {
    confetti({ ...base, particleCount: 70, spread: 70, origin: { y: 0.7 } });
    return;
  }
  confetti({ ...base, particleCount: 120, spread: 90, origin: { y: 0.6 } });
  setTimeout(() => confetti({ ...base, particleCount: 60, angle: 60, spread: 60, origin: { x: 0, y: 0.7 } }), 250);
  setTimeout(() => confetti({ ...base, particleCount: 60, angle: 120, spread: 60, origin: { x: 1, y: 0.7 } }), 400);
}
