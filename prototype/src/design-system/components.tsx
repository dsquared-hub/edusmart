/* Базовые компоненты EDU ProgressUZ. Стили — токены из tokens.css,
   поэтому всё сразу работает в светлой и тёмной теме и в режимах Junior/Senior. */
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { forwardRef, useEffect, useId, type ButtonHTMLAttributes, type ReactNode } from "react";
import { useReducedMotion } from "@/lib/store";

type Variant = "primary" | "gold" | "soft" | "ghost";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md" | "lg"; icon?: ReactNode };

// forwardRef: из кнопки «вылетают» монеты — нужна её позиция на экране
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", icon, className = "", children, ...rest },
  ref,
) {
  const sizes = { sm: "text-sm !min-h-[2.5rem] px-4", md: "text-base", lg: "text-lg px-7 !min-h-[3.75rem] rounded-3xl" };
  // Полные имена классов: Tailwind выкидывает из сборки классы, собранные шаблоном строки
  const variants: Record<Variant, string> = { primary: "btn-primary", gold: "btn-gold", soft: "btn-soft", ghost: "btn-ghost" };
  return (
    <button ref={ref} className={`btn ${variants[variant]} ${sizes[size]} ${className}`} {...rest}>
      {icon}
      {children}
    </button>
  );
});

export function Card({ children, className = "", cream = false }: { children: ReactNode; className?: string; cream?: boolean }) {
  return <div className={`${cream ? "card-cream" : "card"} p-5 ${className}`}>{children}</div>;
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 flex items-end justify-between gap-3">
      <h2 className="h-title">{children}</h2>
      {action}
    </div>
  );
}

type Tone = "gold" | "good" | "bad" | "coffee" | "latte";
const TONES: Record<Tone, string> = {
  gold: "bg-gold/20 text-coffee",
  good: "bg-good/15 text-good",
  bad: "bg-bad/15 text-bad",
  coffee: "bg-coffee text-on-caramel",
  latte: "bg-latte/40 text-ink",
};

export function Badge({ tone = "latte", children, className = "" }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={`badge ${TONES[tone]} ${className}`}>{children}</span>;
}

export function ProgressBar({
  value,
  max = 100,
  tone = "caramel",
  size = "md",
  label,
}: {
  value: number;
  max?: number;
  tone?: "caramel" | "gold" | "good" | "coffee";
  size?: "sm" | "md" | "lg";
  label?: string;
}) {
  const reduced = useReducedMotion();
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const h = { sm: "h-2", md: "h-3", lg: "h-4" }[size];
  const fill = { caramel: "bg-caramel", gold: "bg-gold", good: "bg-good", coffee: "bg-coffee" }[tone];
  return (
    <div
      className={`w-full overflow-hidden rounded-full bg-line ${h}`}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      aria-label={label}
    >
      <motion.div
        className={`h-full rounded-full ${fill} relative`}
        initial={reduced ? false : { width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.9, ease: [0.2, 0.8, 0.2, 1] }}
      >
        <span className="absolute inset-x-1 top-[2px] h-[35%] rounded-full bg-white/35" />
      </motion.div>
    </div>
  );
}

/** Кольцо прогресса для предметов и статистики. */
export function Ring({ value, size = 56, stroke = 7, children }: { value: number; size?: number; stroke?: number; children?: ReactNode }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} style={{ stroke: "rgb(var(--c-line))" }} strokeWidth={stroke} fill="none" />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          style={{ stroke: "rgb(var(--c-caramel))" }}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - value / 100) }}
          transition={{ duration: 1, ease: "easeOut" }}
        />
      </svg>
      <span className="absolute text-xs font-black text-coffee">{children ?? `${value}%`}</span>
    </div>
  );
}

/** Сегментированный переключатель (язык, тема, режим, вкладки рейтинга). */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  className = "",
}: {
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (value: T) => void;
  label: string;
  className?: string;
}) {
  const id = useId();
  return (
    <div role="radiogroup" aria-label={label} className={`inline-flex rounded-2xl bg-card p-1 ${className}`}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={`relative min-h-[2.5rem] flex-1 whitespace-nowrap rounded-xl px-3.5 text-sm font-extrabold transition ${
              active ? "text-on-caramel" : "text-muted hover:text-ink"
            }`}
          >
            {active && (
              <motion.span layoutId={`seg-${id}`} className="absolute inset-0 rounded-xl bg-coffee shadow-soft" transition={{ type: "spring", bounce: 0.2, duration: 0.4 }} />
            )}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange: (v: boolean) => void; label: string; hint?: string }) {
  return (
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)} className="flex w-full items-center gap-4 rounded-2xl px-1 py-2 text-left">
      <span className="flex-1">
        <span className="block font-bold">{label}</span>
        {hint && <span className="block text-sm text-muted">{hint}</span>}
      </span>
      <span className={`relative h-8 w-14 shrink-0 rounded-full transition-colors ${checked ? "bg-good" : "bg-line"}`}>
        <motion.span
          className="absolute top-1 h-6 w-6 rounded-full bg-white shadow"
          animate={{ left: checked ? 28 : 4 }}
          transition={{ type: "spring", stiffness: 500, damping: 30 }}
        />
      </span>
    </button>
  );
}

export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 grid place-items-end sm:place-items-center" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-[#1E1510]/50 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={title}
            className="card relative m-0 w-full max-w-lg rounded-b-none p-6 sm:m-4 sm:rounded-b-[var(--radius-card)]"
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            transition={{ type: "spring", bounce: 0.2, duration: 0.45 }}
          >
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="h-title">{title}</h2>
              <button className="btn btn-ghost !min-h-[2.5rem] !px-2" onClick={onClose} aria-label="close">
                <X size={22} />
              </button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** 3D-монета: объём — градиентами, ребро — внутренней тенью. */
export function Coin({ size = 22, className = "" }: { size?: number; className?: string }) {
  return (
    <span
      className={`coin3d inline-grid shrink-0 place-items-center rounded-full font-black text-[#8A5E14] ${className}`}
      style={{ width: size, height: size, fontSize: size * 0.5 }}
      aria-hidden="true"
    >
      ★
    </span>
  );
}

/** Объёмная иконка-«пузырь»: мягкий градиент, блик и тень — вместо плоских иконок. */
export function Icon3D({ children, color = "#B98A5E", size = 56, className = "" }: { children: ReactNode; color?: string; size?: number; className?: string }) {
  return (
    <span
      className={`relative inline-grid shrink-0 place-items-center text-white ${className}`}
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.32,
        background: `radial-gradient(120% 120% at 30% 20%, color-mix(in srgb, ${color} 55%, white) 0%, ${color} 55%, color-mix(in srgb, ${color} 70%, black) 100%)`,
        boxShadow: `inset 0 -${size * 0.07}px 0 color-mix(in srgb, ${color} 65%, black), inset 0 ${size * 0.04}px ${size * 0.05}px rgb(255 255 255 / .45), 0 ${size * 0.12}px ${size * 0.25}px -${size * 0.08}px color-mix(in srgb, ${color} 60%, black)`,
      }}
      aria-hidden="true"
    >
      <span className="drop-shadow-[0_2px_1px_rgb(0_0_0_/_.25)]">{children}</span>
    </span>
  );
}

export function StatTile({ icon, value, label }: { icon: ReactNode; value: ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-card px-4 py-3">
      {icon}
      <div className="min-w-0">
        <div className="text-xl font-black leading-tight text-coffee">{value}</div>
        <div className="truncate text-xs font-bold text-muted">{label}</div>
      </div>
    </div>
  );
}
