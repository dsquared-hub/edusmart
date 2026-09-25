/* Глобальное состояние прототипа: настройки, профиль, игровая экономика и события
   аватара. Всё хранится в localStorage — прогресс «синхронизируется» между вкладками
   и переживает перезагрузку, как в настоящей экосистеме. */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { en } from "@/locales/en";
import { ru, type Dict } from "@/locales/ru";
import { uz } from "@/locales/uz";

export type Lang = "uz" | "ru" | "en";
export type ThemePref = "light" | "dark" | "system";
export type Mode = "junior" | "senior";
export type Role = "student" | "parent" | "teacher";
export type Mood = "idle" | "happy" | "support" | "thinking";

const DICTS: Record<Lang, Dict> = { uz, ru, en };

/** Цена каждого из 7 образов Куби (индекс = этап). */
export const STAGE_COST = [0, 150, 350, 700, 1200, 2000, 3500] as const;
export const XP_PER_LEVEL = 250;
/** Цвета Куби на выбор в онбординге. */
export const SKINS = ["#F2C28B", "#E0A774", "#B97A4F", "#8D5A3B", "#F6D36B", "#9FD0C7"] as const;

type State = {
  lang: Lang;
  theme: ThemePref;
  mode: Mode;
  reducedMotion: boolean;
  notif: { daily: boolean; time: string; quiet: boolean; reports: boolean; weekend: boolean };
  onboarded: boolean;
  role: Role;
  name: string;
  grade: number;
  phone: string;
  skin: number;
  coins: number;
  xp: number;
  streak: number;
  freezes: number;
  unlocked: number; // максимальный открытый этап
  worn: number; // надетый этап
  quests: Record<string, boolean>;
  solved: number;
};

const DEFAULTS: State = {
  lang: "uz",
  theme: "system",
  mode: "junior",
  reducedMotion: false,
  notif: { daily: true, time: "17:00", quiet: true, reports: true, weekend: true },
  onboarded: false,
  role: "student",
  name: "Aziza",
  grade: 7,
  phone: "",
  skin: 0,
  coins: 420,
  xp: 1840,
  streak: 12,
  freezes: 2,
  unlocked: 1,
  worn: 1,
  quests: { q3: true },
  solved: 148,
};

const KEY = "edu.state.v1";

function load(): State {
  // ?demo — сразу в приложение без регистрации (презентации); ?demo=dark|light, ?lang=ru|en|uz
  const params = new URLSearchParams(window.location.search);
  const demo: Partial<State> = params.has("demo") ? { onboarded: true } : {};
  const theme = params.get("demo");
  if (theme === "dark" || theme === "light") demo.theme = theme;
  const lang = params.get("lang");
  if (lang === "ru" || lang === "en" || lang === "uz") demo.lang = lang;
  try {
    const raw = localStorage.getItem(KEY);
    return { ...DEFAULTS, ...(raw ? JSON.parse(raw) : {}), ...demo };
  } catch {
    return { ...DEFAULTS, ...demo };
  }
}

export type Flight = { id: number; x: number; y: number; amount: number };

type Store = State & {
  d: Dict;
  level: number;
  xpInLevel: number;
  mood: Mood;
  flights: Flight[];
  set: (patch: Partial<State>) => void;
  /** Начислить монеты с анимацией полёта от элемента-источника к счётчику. */
  reward: (amount: number, from?: HTMLElement | null, xp?: number) => void;
  landFlight: (flight: Flight) => void;
  react: (mood: Mood, ms?: number) => void;
  completeQuest: (id: string, amount: number, from?: HTMLElement | null) => void;
  reset: () => void;
};

const Ctx = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>(load);
  const [mood, setMood] = useState<Mood>("idle");
  const [flights, setFlights] = useState<Flight[]>([]);
  const moodTimer = useRef<number>();
  const flightId = useRef(0);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
      localStorage.setItem("edu.theme", state.theme);
    } catch {
      /* приватный режим — живём в памяти */
    }
  }, [state]);

  // Тема, режим и язык — атрибутами на <html>: CSS-токены переключаются мгновенно
  useEffect(() => {
    const root = document.documentElement;
    const media = matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const dark = state.theme === "dark" || (state.theme === "system" && media.matches);
      root.dataset.theme = dark ? "dark" : "light";
      document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#1E1510" : "#FAF6EF");
    };
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [state.theme]);

  useEffect(() => {
    document.documentElement.dataset.mode = state.mode;
    document.documentElement.lang = state.lang;
    document.documentElement.dataset.motion = state.reducedMotion ? "reduced" : "full";
  }, [state.mode, state.lang, state.reducedMotion]);

  const set = useCallback((patch: Partial<State>) => setState((s) => ({ ...s, ...patch })), []);

  const react = useCallback((next: Mood, ms = 2600) => {
    window.clearTimeout(moodTimer.current);
    setMood(next);
    if (next !== "idle") moodTimer.current = window.setTimeout(() => setMood("idle"), ms);
  }, []);

  const reward = useCallback(
    (amount: number, from?: HTMLElement | null, xp = amount * 2) => {
      const rect = from?.getBoundingClientRect();
      const x = rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
      const y = rect ? rect.top + rect.height / 2 : window.innerHeight / 2;
      setFlights((f) => [...f, { id: ++flightId.current, x, y, amount }]);
      setState((s) => ({ ...s, xp: s.xp + xp, solved: s.solved + 1 }));
      react("happy", 3000);
    },
    [react],
  );

  // Монеты зачисляются, когда долетели до счётчика — счётчик «подпрыгивает».
  // Id запоминаем: StrictMode и повторный onComplete не зачислят дважды.
  const landed = useRef(new Set<number>());
  const landFlight = useCallback((flight: Flight) => {
    if (landed.current.has(flight.id)) return;
    landed.current.add(flight.id);
    setFlights((f) => f.filter((x) => x.id !== flight.id));
    setState((s) => ({ ...s, coins: s.coins + flight.amount }));
  }, []);

  const completeQuest = useCallback(
    (id: string, amount: number, from?: HTMLElement | null) => {
      setState((s) => ({ ...s, quests: { ...s.quests, [id]: true } }));
      reward(amount, from);
    },
    [reward],
  );

  const reset = useCallback(() => setState({ ...DEFAULTS }), []);

  const value = useMemo<Store>(() => {
    const level = Math.floor(state.xp / XP_PER_LEVEL) + 1;
    return {
      ...state,
      d: DICTS[state.lang],
      level,
      xpInLevel: state.xp % XP_PER_LEVEL,
      mood,
      flights,
      set,
      reward,
      landFlight,
      react,
      completeQuest,
      reset,
    };
  }, [state, mood, flights, set, reward, landFlight, react, completeQuest, reset]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore(): Store {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useStore вне StoreProvider");
  return ctx;
}

/** Подстановка переменных: fmt("Уровень {n}", { n: 3 }). */
export function fmt(template: string, vars: Record<string, string | number> = {}): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => (key in vars ? String(vars[key]) : `{${key}}`));
}

/** Текст из моковых данных вида { uz, ru, en }. */
export type L10n = Record<Lang, string>;
export function useL() {
  const { lang } = useStore();
  return useCallback((text: L10n) => text[lang], [lang]);
}

/** Уважаем и системную настройку, и переключатель в профиле. */
export function useReducedMotion(): boolean {
  const { reducedMotion } = useStore();
  const [system, setSystem] = useState(() => matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setSystem(media.matches);
    media.addEventListener("change", on);
    return () => media.removeEventListener("change", on);
  }, []);
  return reducedMotion || system;
}
