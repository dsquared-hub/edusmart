import { motion } from "framer-motion";
import { Lock } from "lucide-react";
import { PageHeader } from "@/components/layout/AppShell";
import { ProgressBar } from "@/design-system/components";
import { ACHIEVEMENTS } from "@/mock-data";
import { fmt, useL, useStore } from "@/lib/store";

/** Значок-медальон: объёмный круг с лентой и блеском. */
function Medal({ icon, color, earned }: { icon: string; color: string; earned: boolean }) {
  return (
    <div className="relative mx-auto h-24 w-24" aria-hidden="true">
      <span className="absolute left-1/2 top-[70%] h-10 w-4 -translate-x-[120%] rotate-[18deg] rounded-b-md" style={{ background: earned ? "#5E86B5" : "rgb(var(--c-line))" }} />
      <span className="absolute left-1/2 top-[70%] h-10 w-4 translate-x-[20%] -rotate-[18deg] rounded-b-md" style={{ background: earned ? "#C0675A" : "rgb(var(--c-line))" }} />
      <span
        className="absolute inset-0 grid place-items-center rounded-full text-4xl"
        style={
          earned
            ? {
                background: `radial-gradient(circle at 30% 25%, color-mix(in srgb, ${color} 45%, white), ${color} 60%, color-mix(in srgb, ${color} 65%, black))`,
                boxShadow: `inset 0 -5px 0 color-mix(in srgb, ${color} 60%, black), inset 0 3px 3px rgb(255 255 255 / .5), 0 10px 20px -8px color-mix(in srgb, ${color} 70%, black)`,
              }
            : { background: "rgb(var(--c-card))", boxShadow: "inset 0 -4px 0 rgb(var(--c-line))" }
        }
      >
        <span className={earned ? "drop-shadow" : "opacity-30 grayscale"}>{icon}</span>
        {!earned && <Lock className="absolute bottom-1 right-1 rounded-full bg-surface p-1 text-muted shadow-soft" size={26} />}
      </span>
    </div>
  );
}

export default function Achievements() {
  const { d } = useStore();
  const L = useL();
  const earned = ACHIEVEMENTS.filter((a) => a.done >= a.total).length;
  return (
    <div>
      <PageHeader title={d.achievements.title} subtitle={fmt(d.achievements.subtitle, { a: earned, b: ACHIEVEMENTS.length })} />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
        {ACHIEVEMENTS.map((a, i) => {
          const done = a.done >= a.total;
          return (
            <motion.div
              key={a.id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.04 }}
              whileHover={{ y: -4 }}
              className={`card flex flex-col gap-3 p-5 text-center ${done ? "" : "opacity-90"}`}
            >
              <Medal icon={a.icon} color={a.color} earned={done} />
              <div>
                <div className="font-black leading-tight text-coffee">{L(a.name)}</div>
                <div className="mt-0.5 text-sm font-semibold text-muted">{L(a.desc)}</div>
              </div>
              {done ? (
                <span className="badge mx-auto bg-good/15 text-good">✓ {d.achievements.earned}</span>
              ) : (
                <div className="flex items-center gap-2">
                  <ProgressBar value={a.done} max={a.total} size="sm" tone="gold" label={L(a.name)} />
                  <span className="text-xs font-black text-muted">{fmt(d.achievements.progress, { a: a.done, b: a.total })}</span>
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
