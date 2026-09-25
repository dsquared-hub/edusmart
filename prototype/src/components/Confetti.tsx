/* Конфетти для достижений и новых образов. При «меньше анимаций» не показываем. */
import { motion } from "framer-motion";
import { useMemo } from "react";
import { useReducedMotion } from "@/lib/store";

const COLORS = ["#E8B64C", "#B98A5E", "#6FA876", "#D2735A", "#F3EAD9", "#7A5236"];

export function Confetti({ burst }: { burst: number }) {
  const reduced = useReducedMotion();
  const pieces = useMemo(
    () =>
      Array.from({ length: 70 }, (_, i) => ({
        id: `${burst}-${i}`,
        x: (Math.random() - 0.5) * 900,
        y: 300 + Math.random() * 500,
        r: Math.random() * 720 - 360,
        size: 6 + Math.random() * 8,
        color: COLORS[i % COLORS.length],
        delay: Math.random() * 0.15,
        round: Math.random() > 0.6,
      })),
    [burst],
  );
  if (!burst || reduced) return null;
  return (
    <div className="pointer-events-none fixed inset-0 z-[70] overflow-hidden" aria-hidden="true">
      {pieces.map((p) => (
        <motion.span
          key={p.id}
          className="absolute left-1/2 top-1/3"
          style={{ width: p.size, height: p.size * (p.round ? 1 : 0.5), background: p.color, borderRadius: p.round ? 999 : 2 }}
          initial={{ x: 0, y: 0, opacity: 1, rotate: 0 }}
          animate={{ x: p.x, y: [0, -220 - Math.random() * 120, p.y], opacity: [1, 1, 0], rotate: p.r }}
          transition={{ duration: 1.8, delay: p.delay, ease: "easeOut" }}
        />
      ))}
    </div>
  );
}
