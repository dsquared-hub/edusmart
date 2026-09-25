/* Каркас: десктоп — боковое меню слева; телефон — нижняя навигация с центральной
   кнопкой «Спросить»; сверху — монеты, серия, язык и тема. */
import { AnimatePresence, motion, useAnimationControls } from "framer-motion";
import {
  Award,
  BookOpen,
  Flame,
  GraduationCap,
  Home,
  LayoutGrid,
  Menu,
  Monitor,
  Moon,
  Palette,
  Shirt,
  Sparkles,
  Sun,
  Trophy,
  TrendingUp,
  User,
  Users,
  ClipboardCheck,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Coin, Modal } from "@/design-system/components";
import { Link, useRoute } from "@/lib/router";
import { fmt, useReducedMotion, useStore, type Lang, type ThemePref } from "@/lib/store";

type NavKey = keyof ReturnType<typeof useStore>["d"]["nav"];
type Item = { to: string; key: NavKey; icon: LucideIcon };

const LEARN: Item[] = [
  { to: "/home", key: "home", icon: Home },
  { to: "/subjects", key: "subjects", icon: LayoutGrid },
  { to: "/textbooks", key: "textbooks", icon: BookOpen },
  { to: "/ask", key: "ask", icon: Sparkles },
  { to: "/quiz", key: "quiz", icon: ClipboardCheck },
];
const GAME: Item[] = [
  { to: "/progress", key: "progress", icon: TrendingUp },
  { to: "/leaderboard", key: "leaderboard", icon: Trophy },
  { to: "/achievements", key: "achievements", icon: Award },
  { to: "/wardrobe", key: "wardrobe", icon: Shirt },
];
const CABINETS: Item[] = [
  { to: "/parent", key: "parent", icon: Users },
  { to: "/teacher", key: "teacher", icon: GraduationCap },
  { to: "/design", key: "design", icon: Palette },
];
const BOTTOM: Item[] = [
  { to: "/home", key: "home", icon: Home },
  { to: "/subjects", key: "subjects", icon: LayoutGrid },
  { to: "/ask", key: "ask", icon: Sparkles },
  { to: "/progress", key: "progress", icon: TrendingUp },
  { to: "/profile", key: "profile", icon: User },
];

function NavGroup({ title, items, current, onPick }: { title: string; items: Item[]; current: string; onPick?: () => void }) {
  const { d } = useStore();
  return (
    <div className="flex flex-col gap-1">
      <div className="label px-3 pb-1 pt-3">{title}</div>
      {items.map(({ to, key, icon: Icon }) => {
        const active = current === to;
        return (
          <Link
            key={to}
            to={to}
            onClick={onPick}
            aria-current={active ? "page" : undefined}
            className={`group flex min-h-[2.75rem] items-center gap-3 rounded-2xl px-3 font-bold transition ${
              active ? "bg-coffee text-on-caramel shadow-soft" : "text-ink hover:bg-card"
            }`}
          >
            <Icon size={20} strokeWidth={2.4} className={active ? "" : "text-caramel"} />
            <span className="truncate">{d.nav[key]}</span>
          </Link>
        );
      })}
    </div>
  );
}

const LANGS: { value: Lang; label: string }[] = [
  { value: "uz", label: "UZ" },
  { value: "ru", label: "RU" },
  { value: "en", label: "EN" },
];

export function LangSwitch() {
  const { lang, set, d } = useStore();
  return (
    <div role="radiogroup" aria-label={d.common.lang} className="flex rounded-xl bg-card p-0.5">
      {LANGS.map((l) => (
        <button
          key={l.value}
          role="radio"
          aria-checked={lang === l.value}
          onClick={() => set({ lang: l.value })}
          className={`min-h-[2.25rem] rounded-lg px-2.5 text-xs font-black transition ${
            lang === l.value ? "bg-coffee text-on-caramel" : "text-muted hover:text-ink"
          }`}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}

export function ThemeButton() {
  const { theme, set, d } = useStore();
  const next: Record<ThemePref, ThemePref> = { light: "dark", dark: "system", system: "light" };
  const Icon = { light: Sun, dark: Moon, system: Monitor }[theme];
  const label = { light: d.common.light, dark: d.common.dark, system: d.common.system }[theme];
  return (
    <button
      onClick={() => set({ theme: next[theme] })}
      className="grid h-10 w-10 place-items-center rounded-xl bg-card text-coffee transition hover:brightness-95"
      aria-label={`${d.common.theme}: ${label}`}
      title={`${d.common.theme}: ${label}`}
    >
      <Icon size={19} strokeWidth={2.4} />
    </button>
  );
}

/** Счётчик монет — цель, куда «летят» награды; подпрыгивает при зачислении. */
function CoinCounter() {
  const { coins, d } = useStore();
  const controls = useAnimationControls();
  const prev = useRef(coins);
  useEffect(() => {
    if (coins > prev.current) controls.start({ scale: [1, 1.25, 1], transition: { duration: 0.35 } });
    prev.current = coins;
  }, [coins, controls]);
  return (
    <motion.div
      id="coin-counter"
      animate={controls}
      className="flex h-10 items-center gap-1.5 rounded-xl bg-gold/20 pl-1.5 pr-3 font-black text-coffee"
      aria-label={`${d.common.coins}: ${coins}`}
    >
      <Coin size={26} />
      <span className="tabular-nums">{coins.toLocaleString()}</span>
    </motion.div>
  );
}

function StreakChip() {
  const { streak, d } = useStore();
  return (
    <div className="flex h-10 items-center gap-1 rounded-xl bg-bad/10 px-2.5 font-black text-bad" aria-label={`${d.common.streak}: ${streak}`}>
      <Flame size={18} strokeWidth={2.6} />
      <span>{streak}</span>
    </div>
  );
}

/** Полёт монет от кнопки к счётчику. */
function CoinFlights() {
  const { flights, landFlight } = useStore();
  const reduced = useReducedMotion();
  return (
    <div className="pointer-events-none fixed inset-0 z-[60]" aria-live="polite">
      <AnimatePresence>
        {flights.map((f) => {
          const target = document.getElementById("coin-counter")?.getBoundingClientRect();
          const tx = target ? target.left + 18 : window.innerWidth - 60;
          const ty = target ? target.top + 20 : 24;
          const count = reduced ? 1 : Math.min(8, Math.max(3, Math.round(f.amount / 5)));
          return (
            <div key={f.id}>
              <motion.div
                className="absolute font-black text-gold [text-shadow:0_2px_0_rgb(62_42_30_/_.35)]"
                style={{ left: f.x - 20, top: f.y - 30, fontSize: 26 }}
                initial={{ opacity: 0, y: 0 }}
                animate={{ opacity: [0, 1, 1, 0], y: -50 }}
                transition={{ duration: 1.1 }}
              >
                +{f.amount}
              </motion.div>
              {Array.from({ length: count }, (_, i) => (
                <motion.div
                  key={i}
                  className="absolute"
                  style={{ left: 0, top: 0 }}
                  initial={{ x: f.x - 13, y: f.y - 13, scale: 0.6, opacity: 0 }}
                  animate={{
                    x: [f.x - 13, f.x - 13 + (i - count / 2) * 18, tx - 13],
                    y: [f.y - 13, f.y - 60 - (i % 3) * 14, ty - 13],
                    scale: [0.6, 1.1, 0.7],
                    opacity: [0, 1, 1],
                  }}
                  transition={{ duration: reduced ? 0.01 : 0.9, delay: reduced ? 0 : i * 0.06, ease: [0.4, 0, 0.2, 1] }}
                  onAnimationComplete={() => i === count - 1 && landFlight(f)}
                >
                  <Coin size={26} />
                </motion.div>
              ))}
            </div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}

function Brand() {
  return (
    <Link to="/home" className="flex items-center gap-2.5">
      <span className="coin3d grid h-9 w-9 place-items-center rounded-xl text-sm font-black text-[#6B4410]">EP</span>
      <span className="text-lg font-black leading-none text-coffee">
        EDU <span className="text-caramel">ProgressUZ</span>
      </span>
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { d, level } = useStore();
  const { path } = useRoute();
  const [menu, setMenu] = useState(false);

  return (
    <div className="min-h-[100dvh] lg:pl-72">
      {/* Боковое меню (десктоп) */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 flex-col gap-2 overflow-y-auto border-r border-line bg-surface/70 p-5 backdrop-blur lg:flex">
        <Brand />
        <nav className="mt-3 flex flex-col" aria-label="main">
          <NavGroup title={d.nav.learn} items={LEARN} current={path} />
          <NavGroup title={d.nav.game} items={GAME} current={path} />
          <NavGroup title={d.nav.cabinets} items={CABINETS} current={path} />
        </nav>
        <Link to="/profile" className="mt-auto flex items-center gap-3 rounded-2xl bg-card p-3 font-bold hover:brightness-95">
          <User size={20} className="text-caramel" />
          <span className="flex-1">{d.nav.profile}</span>
          <span className="badge bg-gold/25 text-coffee">{fmt(d.common.level, { n: level })}</span>
        </Link>
      </aside>

      {/* Верхняя панель */}
      <header className="glass sticky top-0 z-20 flex items-center gap-2 px-4 py-2.5 lg:px-8">
        <button className="grid h-10 w-10 place-items-center rounded-xl bg-card text-coffee lg:hidden" onClick={() => setMenu(true)} aria-label={d.common.menu}>
          <Menu size={20} />
        </button>
        <div className="lg:hidden">
          <span className="text-base font-black text-coffee">EDU</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <StreakChip />
          <CoinCounter />
          <div className="hidden sm:block">
            <LangSwitch />
          </div>
          <ThemeButton />
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 pb-32 pt-5 lg:px-8 lg:pb-12">{children}</main>

      {/* Нижняя навигация (телефон) */}
      <nav className="glass fixed inset-x-0 bottom-0 z-30 flex items-end justify-around px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-1.5 lg:hidden" aria-label="bottom">
        {BOTTOM.map(({ to, key, icon: Icon }) => {
          const active = path === to;
          if (key === "ask") {
            return (
              <Link key={to} to={to} className="-mt-7 flex flex-col items-center gap-1" aria-current={active ? "page" : undefined}>
                <span className="grid h-16 w-16 place-items-center rounded-[1.4rem] bg-coffee text-on-caramel shadow-lift ring-4 ring-bg">
                  <Sparkles size={28} strokeWidth={2.4} />
                </span>
                <span className="text-[11px] font-extrabold text-coffee">{d.nav.ask}</span>
              </Link>
            );
          }
          return (
            <Link
              key={to}
              to={to}
              aria-current={active ? "page" : undefined}
              className={`flex min-h-[3.25rem] min-w-[3.5rem] flex-col items-center justify-center gap-0.5 rounded-2xl text-[11px] font-extrabold ${
                active ? "text-coffee" : "text-muted"
              }`}
            >
              <Icon size={22} strokeWidth={active ? 2.8 : 2.2} />
              <span className="max-w-[4.5rem] truncate">{d.nav[key]}</span>
            </Link>
          );
        })}
      </nav>

      {/* Меню «все разделы» на телефоне */}
      <Modal open={menu} onClose={() => setMenu(false)} title={d.app.name}>
        <div className="mb-3 sm:hidden">
          <LangSwitch />
        </div>
        <div className="max-h-[60vh] overflow-y-auto">
          <NavGroup title={d.nav.learn} items={LEARN} current={path} onPick={() => setMenu(false)} />
          <NavGroup title={d.nav.game} items={GAME} current={path} onPick={() => setMenu(false)} />
          <NavGroup title={d.nav.cabinets} items={CABINETS} current={path} onPick={() => setMenu(false)} />
        </div>
      </Modal>

      <CoinFlights />
    </div>
  );
}

/** Заголовок страницы с подзаголовком и действием справа. */
export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="h-display">{title}</h1>
        {subtitle && <p className="mt-1 font-semibold text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
