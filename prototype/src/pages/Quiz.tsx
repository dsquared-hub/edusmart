/* Тесты: выбор ответа, «верно/неверно», ввод числа. Без жизней: ошибка открывает
   разбор, после исправления — монеты. */
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Infinity as InfinityIcon, Lightbulb, RotateCcw } from "lucide-react";
import { useRef, useState } from "react";
import { Kubi } from "@/components/avatar/Kubi";
import { PageHeader } from "@/components/layout/AppShell";
import { Badge, Button, Card, ProgressBar } from "@/design-system/components";
import { QUIZ } from "@/mock-data";
import { fmt, useL, useStore } from "@/lib/store";

export default function Quiz() {
  const { d, reward, react, mood, skin, worn, quests, completeQuest } = useStore();
  const L = useL();
  const [index, setIndex] = useState(0);
  const [value, setValue] = useState<number | boolean | string | null>(null);
  const [status, setStatus] = useState<"idle" | "right" | "wrong">("idle");
  const [firstTry, setFirstTry] = useState(0);
  const [missed, setMissed] = useState(false);
  const [finished, setFinished] = useState(false);
  const checkBtn = useRef<HTMLButtonElement>(null);

  const q = QUIZ[index];

  const check = () => {
    const ok = q.kind === "input" ? String(value).trim() === q.answer : value === q.answer;
    if (ok) {
      setStatus("right");
      if (!missed) setFirstTry((n) => n + 1);
      reward(missed ? 5 : 10, checkBtn.current); // исправил — тоже монеты
    } else {
      setStatus("wrong");
      setMissed(true);
      react("support", 3500);
    }
  };

  const next = () => {
    if (index + 1 >= QUIZ.length) {
      setFinished(true);
      if (!quests.q2) completeQuest("q2", 30, checkBtn.current);
      return;
    }
    setIndex((i) => i + 1);
    setValue(null);
    setStatus("idle");
    setMissed(false);
  };

  const restart = () => {
    setIndex(0);
    setValue(null);
    setStatus("idle");
    setMissed(false);
    setFirstTry(0);
    setFinished(false);
  };

  if (finished) {
    return (
      <div className="mx-auto max-w-lg">
        <Card className="flex flex-col items-center gap-4 p-8 text-center">
          <Kubi stage={worn} skin={skin} mood="happy" size={170} />
          <h1 className="h-display">{d.quiz.result}</h1>
          <p className="text-lg font-bold text-muted">{fmt(d.quiz.resultText, { a: firstTry, b: QUIZ.length })}</p>
          <Button onClick={restart} icon={<RotateCcw size={18} />}>
            {d.quiz.again}
          </Button>
        </Card>
      </div>
    );
  }

  const choiceClass = (active: boolean, correct: boolean) =>
    `min-h-[3.5rem] rounded-2xl border-2 px-4 text-left text-lg font-extrabold transition ${
      status === "right" && correct
        ? "border-good bg-good/15 text-good"
        : status === "wrong" && active
          ? "border-bad bg-bad/10 text-bad"
          : active
            ? "border-coffee bg-card"
            : "border-line bg-surface hover:border-caramel"
    }`;

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title={d.quiz.title}
        subtitle={d.quiz.subtitle}
        action={
          <Badge tone="good" className="!text-sm">
            <InfinityIcon size={16} /> {d.quiz.noLives}
          </Badge>
        }
      />
      <div className="mb-4 flex items-center gap-3">
        <span className="shrink-0 text-sm font-black text-muted">{fmt(d.quiz.question, { n: index + 1, total: QUIZ.length })}</span>
        <ProgressBar value={index + (status === "right" ? 1 : 0)} max={QUIZ.length} tone="coffee" size="sm" label={d.quiz.title} />
      </div>

      <AnimatePresence mode="wait">
        <motion.div key={index} initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -30 }}>
          <Card className="flex flex-col gap-5">
            <div className="flex items-start gap-4">
              <h2 className="flex-1 text-2xl font-black text-coffee">{L(q.q)}</h2>
              <Kubi stage={worn} skin={skin} mood={status === "wrong" ? "support" : mood} size={70} />
            </div>

            {q.kind === "choice" && (
              <div className="grid gap-3 sm:grid-cols-2">
                {q.options!.map((o, i) => (
                  <button key={o} className={choiceClass(value === i, i === q.answer)} onClick={() => status !== "right" && (setValue(i), setStatus("idle"))}>
                    {o}
                  </button>
                ))}
              </div>
            )}
            {q.kind === "truefalse" && (
              <div className="grid grid-cols-2 gap-3">
                {[true, false].map((v) => (
                  <button key={String(v)} className={`${choiceClass(value === v, v === q.answer)} text-center`} onClick={() => status !== "right" && (setValue(v), setStatus("idle"))}>
                    {v ? `✅ ${d.quiz.trueLabel}` : `❌ ${d.quiz.falseLabel}`}
                  </button>
                ))}
              </div>
            )}
            {q.kind === "input" && (
              <input
                className="field text-2xl font-black"
                inputMode="numeric"
                value={(value as string) ?? ""}
                onChange={(e) => {
                  setValue(e.target.value);
                  if (status === "wrong") setStatus("idle");
                }}
                placeholder={d.quiz.inputPlaceholder}
                disabled={status === "right"}
              />
            )}

            <AnimatePresence>
              {status !== "idle" && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className={`flex gap-3 rounded-2xl p-4 ${status === "right" ? "bg-good/12" : "bg-bad/10"}`}
                  aria-live="polite"
                >
                  {status === "right" ? <CheckCircle2 className="shrink-0 text-good" /> : <Lightbulb className="shrink-0 text-bad" />}
                  <div>
                    <div className={`font-black ${status === "right" ? "text-good" : "text-bad"}`}>
                      {status === "right" ? (missed ? d.ask.fixed : d.ask.right) : d.quiz.whyWrong}
                    </div>
                    {status === "wrong" && <p className="mt-1 font-semibold">{L(q.why)}</p>}
                    {status === "wrong" && <p className="mt-1 text-sm font-bold text-coffee">💡 {d.ask.fixIt}</p>}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {status === "right" ? (
              <Button size="lg" onClick={next}>
                {d.common.continue}
              </Button>
            ) : (
              <Button ref={checkBtn} size="lg" onClick={check} disabled={value === null || value === ""}>
                {d.quiz.check}
              </Button>
            )}
          </Card>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
