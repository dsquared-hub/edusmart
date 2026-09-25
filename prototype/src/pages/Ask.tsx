/* «Задать вопрос» — ключевой экран. Три способа ввода (текст, фото с рамкой обрезки,
   голос), пошаговый ответ ИИ, «Объясни проще / Покажи пример / Проверь меня» и
   задача на закрепление: монеты — за понимание, ошибка — повод разобраться. */
import { AnimatePresence, motion } from "framer-motion";
import { Camera, Check, Image as ImageIcon, Lightbulb, Mic, RotateCcw, Send, Sparkles, Square, Type, Wand2 } from "lucide-react";
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { Kubi } from "@/components/avatar/Kubi";
import { Formula } from "@/components/Formula";
import { PageHeader } from "@/components/layout/AppShell";
import { Badge, Button, Card, Coin, Segmented } from "@/design-system/components";
import { EXPLANATION, SUGGESTIONS } from "@/mock-data";
import { fmt, useL, useReducedMotion, useStore } from "@/lib/store";

type InputMode = "text" | "photo" | "voice";
type Depth = "easy" | "normal" | "deep";

/* ---------------- Фото: рамка обрезки с перетаскиваемыми углами ---------------- */

function PhotoInput({ onSubmit }: { onSubmit: (label: string) => void }) {
  const { d } = useStore();
  const [src, setSrc] = useState<string | null>(null);
  const [crop, setCrop] = useState({ l: 10, t: 14, r: 10, b: 18 }); // отступы рамки в %
  const box = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => () => void (src && URL.revokeObjectURL(src)), [src]);

  const drag = (corner: "tl" | "tr" | "bl" | "br") => (e: ReactPointerEvent) => {
    e.preventDefault();
    const rect = box.current!.getBoundingClientRect();
    const move = (ev: PointerEvent) => {
      const x = ((ev.clientX - rect.left) / rect.width) * 100;
      const y = ((ev.clientY - rect.top) / rect.height) * 100;
      const clamp = (v: number) => Math.max(0, Math.min(40, v));
      setCrop((c) => ({
        l: corner.includes("l") ? clamp(x) : c.l,
        r: corner.includes("r") ? clamp(100 - x) : c.r,
        t: corner[0] === "t" ? clamp(y) : c.t,
        b: corner[0] === "b" ? clamp(100 - y) : c.b,
      }));
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  return (
    <div className="flex flex-col gap-3">
      <div ref={box} className="relative aspect-[4/3] w-full touch-none overflow-hidden rounded-3xl bg-[#2A1E17]">
        {src ? (
          <img src={src} alt="" className="h-full w-full object-cover" />
        ) : (
          // Демо-«тетрадь», пока фото не выбрано
          <div className="flex h-full flex-col justify-center gap-3 bg-[repeating-linear-gradient(0deg,#FFFDF7_0_27px,#D9E4F2_27px_28px)] px-10 font-serif text-lg text-[#2B3A55] sm:text-xl">
            <span className="font-bold">№ 214.</span>
            <span>Trapetsiyaning asoslari 10 sm va 6 sm,</span>
            <span>balandligi 4 sm. Yuzini toping.</span>
          </div>
        )}
        {/* затемнение вне рамки + рамка с углами */}
        <div
          className="absolute rounded-2xl border-2 border-gold shadow-[0_0_0_9999px_rgb(20_14_10_/_.45)]"
          style={{ left: `${crop.l}%`, top: `${crop.t}%`, right: `${crop.r}%`, bottom: `${crop.b}%` }}
        >
          {(["tl", "tr", "bl", "br"] as const).map((c) => (
            <span
              key={c}
              onPointerDown={drag(c)}
              className="absolute h-8 w-8 cursor-grab touch-none"
              style={{
                [c[0] === "t" ? "top" : "bottom"]: -14,
                [c[1] === "l" ? "left" : "right"]: -14,
              }}
              aria-hidden="true"
            >
              <span
                className="absolute inset-2 border-gold"
                style={{
                  borderTopWidth: c[0] === "t" ? 4 : 0,
                  borderBottomWidth: c[0] === "b" ? 4 : 0,
                  borderLeftWidth: c[1] === "l" ? 4 : 0,
                  borderRightWidth: c[1] === "r" ? 4 : 0,
                  borderRadius: 4,
                }}
              />
            </span>
          ))}
        </div>
        <span className="absolute inset-x-0 bottom-2 text-center text-xs font-bold text-white/85">{d.ask.photoCrop}</span>
      </div>
      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) setSrc(URL.createObjectURL(file));
        }}
      />
      <div className="grid grid-cols-2 gap-3">
        <Button variant="soft" icon={<ImageIcon size={18} />} onClick={() => input.current?.click()}>
          {d.ask.photoPick}
        </Button>
        <Button icon={<Wand2 size={18} />} onClick={() => onSubmit("📷 № 214")}>
          {d.ask.photoUse}
        </Button>
      </div>
    </div>
  );
}

/* ---------------- Голос: большая кнопка и анимированная волна ---------------- */

function VoiceInput({ onSubmit }: { onSubmit: (text: string) => void }) {
  const { d } = useStore();
  const L = useL();
  const reduced = useReducedMotion();
  const [listening, setListening] = useState(false);
  const timer = useRef<number>();

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const toggle = () => {
    if (listening) {
      window.clearTimeout(timer.current);
      setListening(false);
      return;
    }
    setListening(true);
    // Демо: «распознаём» речь через 2.5 секунды
    timer.current = window.setTimeout(() => {
      setListening(false);
      onSubmit(L(SUGGESTIONS[0]));
    }, 2500);
  };

  return (
    <div className="flex flex-col items-center gap-5 py-4">
      <div className="flex h-16 items-center gap-1.5" aria-hidden="true">
        {Array.from({ length: 13 }, (_, i) => (
          <motion.span
            key={i}
            className="w-2 rounded-full bg-caramel"
            animate={listening && !reduced ? { height: [10, 18 + ((i * 7) % 40), 10] } : { height: 10 }}
            transition={{ duration: 0.7 + (i % 4) * 0.15, repeat: Infinity, ease: "easeInOut" }}
          />
        ))}
      </div>
      <motion.button
        onClick={toggle}
        whileTap={{ scale: 0.94 }}
        className={`relative grid h-28 w-28 place-items-center rounded-full text-on-caramel shadow-lift transition ${listening ? "bg-bad" : "bg-coffee"}`}
        aria-pressed={listening}
        aria-label={listening ? d.ask.voiceStop : d.ask.voiceHold}
      >
        {listening && !reduced && (
          <motion.span
            className="absolute inset-0 rounded-full bg-bad"
            animate={{ scale: [1, 1.5], opacity: [0.4, 0] }}
            transition={{ duration: 1.2, repeat: Infinity }}
          />
        )}
        {listening ? <Square size={36} fill="currentColor" /> : <Mic size={44} strokeWidth={2.4} />}
      </motion.button>
      <p className="font-extrabold text-coffee" aria-live="polite">
        {listening ? d.ask.voiceListening : d.ask.voiceHold}
      </p>
    </div>
  );
}

/* ---------------- Ответ ИИ ---------------- */

function Thinking() {
  const { d } = useStore();
  return (
    <div className="flex items-center gap-3 text-muted" role="status">
      <span className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="h-2.5 w-2.5 rounded-full bg-caramel"
            animate={{ y: [0, -6, 0] }}
            transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.15 }}
          />
        ))}
      </span>
      <span className="font-bold">{d.ask.thinking}</span>
    </div>
  );
}

function Practice({ onDone }: { onDone: () => void }) {
  const { d, reward, react } = useStore();
  const L = useL();
  const p = EXPLANATION.practice;
  const [picked, setPicked] = useState<number | null>(null);
  const [wrongOnce, setWrongOnce] = useState(false);
  const [solved, setSolved] = useState(false);

  const pick = (i: number, el: HTMLElement) => {
    if (solved) return;
    setPicked(i);
    if (i === p.correct) {
      setSolved(true);
      // Монеты за понимание: с первой попытки — полные, после исправления — тоже (за исправление)
      reward(wrongOnce ? 15 : p.reward, el);
      onDone();
    } else {
      setWrongOnce(true);
      react("support", 3500); // Куби поддерживает, а не грустит
    }
  };

  return (
    <Card className="border-2 !border-gold/60">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge tone="gold">
          <Coin size={14} /> +{p.reward}
        </Badge>
        <h3 className="font-black text-coffee">{d.ask.practiceTitle}</h3>
        <span className="text-sm font-bold text-muted">· {d.ask.practiceHint}</span>
      </div>
      <p className="mb-4 text-lg font-bold">{L(p.question)}</p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {p.options.map((o, i) => {
          const state = picked === i ? (i === p.correct ? "good" : "bad") : solved && i === p.correct ? "good" : null;
          return (
            <motion.button
              key={o}
              whileTap={{ scale: 0.96 }}
              onClick={(e) => pick(i, e.currentTarget)}
              disabled={solved}
              className={`min-h-[3.5rem] rounded-2xl border-2 text-xl font-black transition ${
                state === "good"
                  ? "border-good bg-good/15 text-good"
                  : state === "bad"
                    ? "border-bad bg-bad/10 text-bad"
                    : "border-line bg-surface hover:border-caramel"
              }`}
            >
              {o}
            </motion.button>
          );
        })}
      </div>
      <AnimatePresence mode="wait">
        {picked !== null && (
          <motion.div
            key={solved ? "ok" : "fix"}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={`mt-4 rounded-2xl p-4 font-bold ${solved ? "bg-good/12 text-good" : "bg-bad/10"}`}
            aria-live="polite"
          >
            {solved ? (
              wrongOnce ? d.ask.fixed : d.ask.right
            ) : (
              <>
                <div className="text-bad">{d.ask.wrong}</div>
                <div className="mt-1 text-ink">{L(p.hint)}</div>
                <div className="mt-2 text-sm text-coffee">💡 {d.ask.fixIt} (+15)</div>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}

function Answer({ depth, onNew }: { depth: Depth; onNew: () => void }) {
  const { d } = useStore();
  const L = useL();
  const steps = EXPLANATION.steps;
  // В режиме «Проще» упрощённые формулировки видны сразу у каждого шага
  const [shown, setShown] = useState(1);
  const [simpler, setSimpler] = useState<Record<number, boolean>>({});
  const [example, setExample] = useState(false);
  const [practice, setPractice] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [shown, example, practice]);

  const last = shown - 1;
  const allShown = shown >= steps.length;

  return (
    <div className="flex flex-col gap-4">
      {steps.slice(0, shown).map((s, i) => (
        <motion.div key={i} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
          <Card>
            <div className="mb-2 flex items-center gap-3">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-coffee font-black text-on-caramel">{i + 1}</span>
              <div className="min-w-0">
                <div className="label">{fmt(d.ask.stepOf, { n: i + 1, total: steps.length })}</div>
                <h3 className="text-lg font-black text-coffee">{L(s.title)}</h3>
              </div>
            </div>
            <p className="text-[1.05rem] font-semibold leading-relaxed">{L(s.text)}</p>
            {s.formula && (
              <div className="mt-3">
                <Formula big={i === 2}>{s.formula}</Formula>
              </div>
            )}
            {(simpler[i] || depth === "easy") && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="mt-3 flex gap-3 rounded-2xl bg-gold/15 p-3">
                <Lightbulb className="mt-0.5 shrink-0 text-caramel" size={20} />
                <div>
                  <Badge tone="gold" className="mb-1">
                    {d.ask.simplerBadge}
                  </Badge>
                  <p className="font-semibold">{L(s.simpler)}</p>
                </div>
              </motion.div>
            )}
            {depth === "deep" && i === 2 && (
              <p className="mt-3 text-sm font-semibold text-muted">
                (a + b) / 2 — {L({ uz: "oʻrta chiziq uzunligi", ru: "это длина средней линии", en: "is the midline length" })}.
              </p>
            )}
            {i === last && (
              <div className="mt-4 flex flex-wrap gap-2">
                {!allShown && (
                  <Button size="sm" onClick={() => setShown((n) => n + 1)} icon={<Sparkles size={16} />}>
                    {d.ask.nextStep}
                  </Button>
                )}
                {!simpler[i] && depth !== "easy" && (
                  <Button size="sm" variant="soft" onClick={() => setSimpler((m) => ({ ...m, [i]: true }))} icon={<Lightbulb size={16} />}>
                    {d.ask.simpler}
                  </Button>
                )}
                {!example && (
                  <Button size="sm" variant="soft" onClick={() => setExample(true)} icon={<ImageIcon size={16} />}>
                    {d.ask.example}
                  </Button>
                )}
                {!practice && (
                  <Button size="sm" variant="gold" onClick={() => setPractice(true)} icon={<Check size={16} />}>
                    {d.ask.checkMe}
                  </Button>
                )}
              </div>
            )}
          </Card>
        </motion.div>
      ))}

      {example && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <Card cream>
            <div className="mb-1 font-black text-coffee">🌷 {d.ask.exampleTitle}</div>
            <p className="font-semibold leading-relaxed">{L(EXPLANATION.example)}</p>
          </Card>
        </motion.div>
      )}

      {(practice || allShown) && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <Practice onDone={() => undefined} />
        </motion.div>
      )}

      <div ref={bottom} className="flex justify-center pt-2">
        <Button variant="ghost" onClick={onNew} icon={<RotateCcw size={18} />}>
          {d.ask.newQuestion}
        </Button>
      </div>
    </div>
  );
}

/* ---------------- Экран ---------------- */

export default function Ask() {
  const { d, mood, skin, worn, react, quests, completeQuest, mode } = useStore();
  const L = useL();
  const [inputMode, setInputMode] = useState<InputMode>("text");
  const [depth, setDepth] = useState<Depth>("normal");
  const [text, setText] = useState("");
  const [question, setQuestion] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
  const sendBtn = useRef<HTMLButtonElement>(null);

  const ask = (q: string) => {
    if (!q.trim()) return;
    setQuestion(q.trim());
    setText("");
    setThinking(true);
    react("thinking", 1600);
    window.setTimeout(() => setThinking(false), 1400);
    if (!quests.q1) window.setTimeout(() => completeQuest("q1", 20, sendBtn.current), 1500);
  };

  const reset = () => {
    setQuestion(null);
    setThinking(false);
  };

  // Пришли из читалки с выделенным фрагментом — сразу спрашиваем
  useEffect(() => {
    const prefill = sessionStorage.getItem("edu.ask.prefill");
    if (prefill) {
      sessionStorage.removeItem("edu.ask.prefill");
      ask(prefill);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={d.ask.title}
        subtitle={d.ask.subtitle}
        action={
          <div className="ml-auto">
            <Kubi size={mode === "junior" ? 92 : 76} mood={thinking ? "thinking" : mood} stage={worn} skin={skin} className="-mb-3" />
          </div>
        }
      />

      {!question ? (
        <Card className="flex flex-col gap-5">
          <Segmented
            label={d.ask.title}
            value={inputMode}
            onChange={setInputMode}
            className="w-full"
            options={[
              { value: "text", label: <span className="inline-flex items-center gap-1.5"><Type size={16} />{d.ask.modeText}</span> },
              { value: "photo", label: <span className="inline-flex items-center gap-1.5"><Camera size={16} />{d.ask.modePhoto}</span> },
              { value: "voice", label: <span className="inline-flex items-center gap-1.5"><Mic size={16} />{d.ask.modeVoice}</span> },
            ]}
          />

          {inputMode === "text" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                ask(text);
              }}
              className="flex flex-col gap-3"
            >
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={d.ask.placeholder}
                rows={3}
                className="field resize-none py-3 text-lg"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    ask(text);
                  }
                }}
              />
              <Button ref={sendBtn} size="lg" disabled={!text.trim()} icon={<Send size={20} />}>
                {d.ask.send}
              </Button>
            </form>
          )}
          {inputMode === "photo" && <PhotoInput onSubmit={ask} />}
          {inputMode === "voice" && <VoiceInput onSubmit={ask} />}

          <div className="flex flex-col gap-2">
            <span className="label">{d.ask.levelLabel}</span>
            <Segmented
              label={d.ask.levelLabel}
              value={depth}
              onChange={setDepth}
              options={(["easy", "normal", "deep"] as const).map((v) => ({ value: v, label: d.ask.levels[v] }))}
            />
          </div>

          <div>
            <div className="label mb-2">{d.ask.suggestions}</div>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s.en} className="chip" onClick={() => ask(L(s))}>
                  {L(s)}
                </button>
              ))}
            </div>
          </div>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="ml-auto max-w-[85%] rounded-3xl rounded-br-lg bg-coffee px-5 py-3 text-lg font-bold text-on-caramel shadow-soft">
            {question}
          </motion.div>
          {thinking ? <Thinking /> : <Answer depth={depth} onNew={reset} />}
        </div>
      )}
    </div>
  );
}
