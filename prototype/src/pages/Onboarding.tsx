/* Регистрация по номеру телефона: приветствие → номер (+998) → SMS-код (6 полей) →
   роль → имя, класс, язык и цвет Куби. Максимум 4 шага, с прогресс-баром. */
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, GraduationCap, Phone, User, Users } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Kubi } from "@/components/avatar/Kubi";
import { LangSwitch, ThemeButton } from "@/components/layout/AppShell";
import { WhyBlock } from "@/components/WhyBlock";
import { Button, Card, Icon3D, ProgressBar } from "@/design-system/components";
import { navigate } from "@/lib/router";
import { fmt, SKINS, useStore, type Role } from "@/lib/store";

const TOTAL = 4;

/** «90 123 45 67» — маска узбекского номера после +998. */
function formatPhone(digits: string): string {
  const d = digits.slice(0, 9);
  return [d.slice(0, 2), d.slice(2, 5), d.slice(5, 7), d.slice(7, 9)].filter(Boolean).join(" ");
}

function CodeInput({ onComplete }: { onComplete: () => void }) {
  const [code, setCode] = useState<string[]>(Array(6).fill(""));
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => refs.current[0]?.focus(), []);

  const put = (i: number, value: string) => {
    const digits = value.replace(/\D/g, "");
    if (!digits) {
      setCode((c) => c.map((x, j) => (j === i ? "" : x)));
      return;
    }
    // Вставка целого кода из SMS разом
    const next = [...code];
    digits.split("").forEach((ch, k) => {
      if (i + k < 6) next[i + k] = ch;
    });
    setCode(next);
    const focus = Math.min(5, i + digits.length);
    refs.current[focus]?.focus();
    if (next.every(Boolean)) window.setTimeout(onComplete, 250);
  };

  return (
    <div className="flex justify-center gap-2 sm:gap-3">
      {code.map((ch, i) => (
        <input
          key={i}
          ref={(el) => (refs.current[i] = el)}
          value={ch}
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          aria-label={`${i + 1}`}
          maxLength={6}
          onChange={(e) => put(i, e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Backspace" && !ch && i > 0) refs.current[i - 1]?.focus();
          }}
          className={`h-14 w-11 rounded-2xl border-2 bg-surface text-center text-2xl font-black text-coffee transition focus:border-coffee focus:outline-none focus:ring-4 focus:ring-gold/30 sm:h-16 sm:w-14 ${
            ch ? "border-caramel" : "border-line"
          }`}
        />
      ))}
    </div>
  );
}

export default function Onboarding() {
  const store = useStore();
  const { d, set, grade, skin } = store;
  const [step, setStep] = useState(0); // 0 — приветствие, 1–4 — шаги
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState<Role>("student");
  const [name, setName] = useState("");
  const [timer, setTimer] = useState(0);

  useEffect(() => {
    if (step !== 2) return;
    setTimer(59);
    const id = window.setInterval(() => setTimer((t) => Math.max(0, t - 1)), 1000);
    return () => window.clearInterval(id);
  }, [step]);

  const finish = () => {
    set({ onboarded: true, role, name: name.trim() || "Aziza", phone: `+998 ${formatPhone(phone)}` });
    navigate(role === "parent" ? "/parent" : role === "teacher" ? "/teacher" : "/home");
  };

  const roles: { value: Role; icon: typeof User; color: string }[] = [
    { value: "student", icon: User, color: "#D98B4E" },
    { value: "parent", icon: Users, color: "#6FA876" },
    { value: "teacher", icon: GraduationCap, color: "#5E86B5" },
  ];

  const slide = { initial: { opacity: 0, x: 40 }, animate: { opacity: 1, x: 0 }, exit: { opacity: 0, x: -40 }, transition: { duration: 0.25 } };

  return (
    <div className="min-h-[100dvh] bg-bg">
      <header className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-4">
        {step > 0 ? (
          <button className="grid h-10 w-10 place-items-center rounded-xl bg-card text-coffee" onClick={() => setStep((s) => s - 1)} aria-label={d.common.back}>
            <ArrowLeft size={20} />
          </button>
        ) : (
          <span className="coin3d grid h-9 w-9 place-items-center rounded-xl text-sm font-black text-[#6B4410]">EP</span>
        )}
        <span className="hidden font-black text-coffee sm:inline">{d.app.name}</span>
        <div className="ml-auto flex items-center gap-2">
          <LangSwitch />
          <ThemeButton />
        </div>
      </header>

      {step > 0 && (
        <div className="mx-auto mb-4 max-w-md px-4">
          <div className="mb-2 text-center text-sm font-extrabold text-muted">{fmt(d.onboarding.step, { n: step, total: TOTAL })}</div>
          <ProgressBar value={step} max={TOTAL} tone="coffee" size="sm" label={fmt(d.onboarding.step, { n: step, total: TOTAL })} />
        </div>
      )}

      <main className="mx-auto max-w-5xl px-4 pb-12">
        <AnimatePresence mode="wait">
          {step === 0 && (
            <motion.div key="welcome" {...slide} className="flex flex-col gap-10">
              <section className="grid items-center gap-8 pt-4 md:grid-cols-2">
                <div className="text-center md:text-left">
                  <div className="label mb-2">{d.app.tagline}</div>
                  <h1 className="text-3xl font-black leading-tight text-coffee [overflow-wrap:anywhere] sm:text-4xl md:text-5xl">{d.onboarding.welcomeTitle}</h1>
                  <p className="mt-4 text-lg font-semibold text-muted">{d.onboarding.welcomeText}</p>
                  <Button size="lg" className="mt-6 w-full sm:w-auto" onClick={() => setStep(1)}>
                    {d.onboarding.start}
                  </Button>
                </div>
                <div className="relative mx-auto">
                  <div className="absolute inset-0 -z-10 rounded-full bg-gold/25 blur-3xl" />
                  {/* Эволюция образа: новичок → знаток → легенда (на телефоне — компактнее) */}
                  <div className="flex max-w-full items-end gap-1 sm:gap-2">
                    <Kubi stage={0} skin={0} size={92} mood="idle" className="opacity-80 sm:h-auto sm:w-[120px]" />
                    <Kubi stage={3} skin={2} size={128} mood="happy" className="sm:h-auto sm:w-[150px]" />
                    <Kubi stage={6} skin={1} size={92} mood="idle" className="opacity-80 sm:h-auto sm:w-[120px]" />
                  </div>
                </div>
              </section>
              <WhyBlock />
            </motion.div>
          )}

          {step === 1 && (
            <motion.div key="phone" {...slide} className="mx-auto max-w-md">
              <Card className="flex flex-col gap-5 p-6">
                <Icon3D color="#B98A5E" size={60} className="mx-auto">
                  <Phone size={28} />
                </Icon3D>
                <div className="text-center">
                  <h1 className="h-title text-2xl">{d.onboarding.phoneTitle}</h1>
                  <p className="mt-1 font-semibold text-muted">{d.onboarding.phoneHint}</p>
                </div>
                <label className="flex flex-col gap-2">
                  <span className="label">{d.onboarding.phoneLabel}</span>
                  <div className="field flex items-center gap-2 !px-0 focus-within:border-coffee focus-within:ring-4 focus-within:ring-gold/30">
                    <span className="flex h-full items-center border-r border-line px-4 text-lg font-black text-coffee">🇺🇿 +998</span>
                    <input
                      value={formatPhone(phone)}
                      onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 9))}
                      inputMode="tel"
                      autoComplete="tel-national"
                      placeholder="90 123 45 67"
                      className="min-w-0 flex-1 bg-transparent py-3 pr-4 text-lg font-bold tracking-wide outline-none"
                      aria-label={d.onboarding.phoneLabel}
                    />
                  </div>
                </label>
                <Button size="lg" disabled={phone.length < 9} onClick={() => setStep(2)}>
                  {d.onboarding.sendCode}
                </Button>
              </Card>
            </motion.div>
          )}

          {step === 2 && (
            <motion.div key="code" {...slide} className="mx-auto max-w-md">
              <Card className="flex flex-col gap-5 p-6 text-center">
                <div>
                  <h1 className="h-title text-2xl">{d.onboarding.codeTitle}</h1>
                  <p className="mt-1 font-semibold text-muted">{fmt(d.onboarding.codeHint, { phone: `+998 ${formatPhone(phone)}` })}</p>
                </div>
                <CodeInput onComplete={() => setStep(3)} />
                <p className="text-sm font-bold text-muted">
                  {timer > 0 ? (
                    fmt(d.onboarding.resendIn, { s: timer })
                  ) : (
                    <button className="font-extrabold text-caramel underline" onClick={() => setTimer(59)}>
                      {d.onboarding.resend}
                    </button>
                  )}
                </p>
                <p className="rounded-2xl bg-gold/15 px-4 py-2 text-sm font-bold text-coffee">{d.onboarding.demoCode}</p>
              </Card>
            </motion.div>
          )}

          {step === 3 && (
            <motion.div key="role" {...slide} className="mx-auto max-w-lg">
              <h1 className="h-title mb-4 text-center text-2xl">{d.onboarding.roleTitle}</h1>
              <div className="flex flex-col gap-3" role="radiogroup" aria-label={d.onboarding.roleTitle}>
                {roles.map(({ value, icon: Icon, color }) => (
                  <motion.button
                    key={value}
                    role="radio"
                    aria-checked={role === value}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setRole(value)}
                    className={`card flex items-center gap-4 p-4 text-left transition ${role === value ? "!border-coffee ring-2 ring-coffee" : ""}`}
                  >
                    <Icon3D color={color} size={56}>
                      <Icon size={28} />
                    </Icon3D>
                    <span className="flex-1">
                      <span className="block text-lg font-black text-coffee">{d.onboarding.roles[value].t}</span>
                      <span className="block font-semibold text-muted">{d.onboarding.roles[value].d}</span>
                    </span>
                  </motion.button>
                ))}
              </div>
              <Button size="lg" className="mt-5 w-full" onClick={() => setStep(4)}>
                {d.common.next}
              </Button>
            </motion.div>
          )}

          {step === 4 && (
            <motion.div key="profile" {...slide} className="mx-auto grid max-w-3xl gap-5 md:grid-cols-2">
              <Card className="flex flex-col gap-4 p-6">
                <h1 className="h-title text-2xl">{d.onboarding.profileTitle}</h1>
                <label className="flex flex-col gap-2">
                  <span className="label">{d.onboarding.nameLabel}</span>
                  <input className="field text-lg" value={name} onChange={(e) => setName(e.target.value)} placeholder={d.onboarding.namePlaceholder} autoComplete="given-name" />
                </label>
                {role === "student" && (
                  <div className="flex flex-col gap-2">
                    <span className="label">{d.onboarding.gradeLabel}</span>
                    <div className="grid grid-cols-6 gap-2">
                      {Array.from({ length: 11 }, (_, i) => i + 1).map((g) => (
                        <button key={g} className="chip justify-center !px-0" aria-pressed={grade === g} onClick={() => set({ grade: g, mode: g <= 7 ? "junior" : "senior" })}>
                          {g}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                <div className="flex flex-col gap-2">
                  <span className="label">{d.common.lang}</span>
                  <LangSwitch />
                </div>
              </Card>
              <Card cream className="flex flex-col items-center gap-4 p-6 text-center">
                <h2 className="h-title">{d.onboarding.avatarTitle}</h2>
                <Kubi stage={0} skin={skin} mood="happy" size={170} />
                <p className="text-sm font-semibold text-muted">{d.onboarding.avatarHint}</p>
                <div className="flex gap-2" role="radiogroup" aria-label={d.onboarding.skin}>
                  {SKINS.map((color, i) => (
                    <button
                      key={color}
                      role="radio"
                      aria-checked={skin === i}
                      aria-label={`${d.onboarding.skin} ${i + 1}`}
                      onClick={() => set({ skin: i })}
                      className={`h-10 w-10 rounded-xl shadow-soft transition ${skin === i ? "scale-110 ring-4 ring-coffee ring-offset-2 ring-offset-card" : ""}`}
                      style={{ background: color }}
                    />
                  ))}
                </div>
              </Card>
              <Button size="lg" className="md:col-span-2" onClick={finish}>
                {d.onboarding.finish}
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
