/* Цвета текущей темы для SVG-графиков (Recharts): атрибуты SVG не понимают var(),
   поэтому читаем токены и перечитываем при смене data-theme. */
import { useEffect, useState } from "react";

const NAMES = ["caramel", "coffee", "gold", "good", "bad", "line", "muted", "ink", "surface", "latte"] as const;
type Colors = Record<(typeof NAMES)[number], string>;

function read(): Colors {
  const style = getComputedStyle(document.documentElement);
  return Object.fromEntries(
    NAMES.map((n) => [n, `rgb(${style.getPropertyValue(`--c-${n}`).trim().split(/\s+/).join(", ")})`]),
  ) as Colors;
}

export function useThemeColors(): Colors {
  const [colors, setColors] = useState(read);
  useEffect(() => {
    const observer = new MutationObserver(() => setColors(read()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);
  return colors;
}
