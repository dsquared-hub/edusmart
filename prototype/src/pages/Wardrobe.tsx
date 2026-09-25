/* Гардероб: 7 этапов эволюции образа Куби. Открываются по порядку за монеты,
   закрытые — силуэтом с замком и суммой до открытия. */
import { AnimatePresence, motion } from "framer-motion";
import { Check, Lock } from "lucide-react";
import { useState } from "react";
import { Kubi } from "@/components/avatar/Kubi";
import { Confetti } from "@/components/Confetti";
import { PageHeader } from "@/components/layout/AppShell";
import { Badge, Button, Card, Coin, ProgressBar } from "@/design-system/components";
import { fmt, STAGE_COST, useStore } from "@/lib/store";

export default function Wardrobe() {
  const { d, coins, unlocked, worn, skin, set, react, mood } = useStore();
  const [selected, setSelected] = useState(worn);
  const [burst, setBurst] = useState(0);
  const [toast, setToast] = useState<string | null>(null);

  const isUnlocked = selected <= unlocked;
  const isNext = selected === unlocked + 1;
  const cost = STAGE_COST[selected];
  const need = Math.max(0, cost - coins);

  const unlock = () => {
    if (!isNext || need > 0) return;
    set({ coins: coins - cost, unlocked: selected, worn: selected });
    setBurst((b) => b + 1);
    react("happy", 3500);
    setToast(fmt(d.wardrobe.unlocked, { stage: d.wardrobe.stages[selected] }));
    window.setTimeout(() => setToast(null), 2800);
  };

  return (
    <div>
      <PageHeader
        title={d.wardrobe.title}
        subtitle={d.wardrobe.subtitle}
        action={
          <div className="flex items-center gap-2 rounded-2xl bg-gold/20 px-4 py-2 font-black text-coffee">
            <Coin size={24} /> {d.wardrobe.balance}: {coins}
          </div>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
        {/* Примерочная */}
        <Card className="relative flex flex-col items-center gap-4 overflow-hidden text-center lg:sticky lg:top-20 lg:self-start">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-2/3 bg-gradient-to-b from-gold/20 to-transparent" />
          <div className="relative pt-4">
            <AnimatePresence mode="wait">
              <motion.div key={selected} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }}>
                <Kubi stage={selected} skin={skin} mood={isUnlocked ? mood : "idle"} size={200} silhouette={!isUnlocked} />
              </motion.div>
            </AnimatePresence>
            {!isUnlocked && (
              <span className="absolute left-1/2 top-1/2 grid h-16 w-16 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-surface shadow-lift">
                <Lock className="text-coffee" size={28} />
              </span>
            )}
          </div>
          <div className="relative">
            <div className="label">{fmt("{n} / 7", { n: selected + 1 })}</div>
            <h2 className="text-2xl font-black text-coffee">{d.wardrobe.stages[selected]}</h2>
            <p className="font-semibold text-muted">{d.wardrobe.stageDesc[selected]}</p>
          </div>
          <div className="relative w-full">
            {selected === worn ? (
              <Button variant="soft" disabled className="w-full" icon={<Check size={18} />}>
                {d.wardrobe.current}
              </Button>
            ) : isUnlocked ? (
              <Button className="w-full" onClick={() => set({ worn: selected })}>
                {d.wardrobe.wear}
              </Button>
            ) : (
              <div className="flex flex-col gap-2">
                <Button variant="gold" className="w-full" onClick={unlock} disabled={!isNext || need > 0} icon={<Coin size={20} />}>
                  {fmt(d.wardrobe.unlock, { n: cost })}
                </Button>
                {need > 0 && (
                  <>
                    <ProgressBar value={coins} max={cost} tone="gold" size="sm" label={d.wardrobe.needMore} />
                    <span className="text-sm font-bold text-muted">{fmt(d.wardrobe.needMore, { n: need })}</span>
                  </>
                )}
              </div>
            )}
          </div>
        </Card>

        {/* Все этапы эволюции */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
          {d.wardrobe.stages.map((name, i) => {
            const open = i <= unlocked;
            const active = i === selected;
            return (
              <motion.button
                key={name}
                whileHover={{ y: -3 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => setSelected(i)}
                aria-pressed={active}
                className={`card relative flex flex-col items-center gap-2 p-4 text-center transition ${active ? "!border-coffee ring-2 ring-coffee" : ""}`}
              >
                {i === worn && (
                  <Badge tone="good" className="absolute left-3 top-3">
                    <Check size={12} /> {d.wardrobe.current}
                  </Badge>
                )}
                <div className="relative">
                  <Kubi stage={i} skin={skin} size={96} silhouette={!open} />
                  {!open && (
                    <span className="absolute left-1/2 top-1/2 grid h-10 w-10 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-surface shadow-soft">
                      <Lock size={18} className="text-coffee" />
                    </span>
                  )}
                </div>
                <div className="font-black leading-tight text-coffee">{name}</div>
                {open ? (
                  <span className="text-xs font-bold text-muted">{d.wardrobe.stageDesc[i]}</span>
                ) : (
                  <span className="flex items-center gap-1 text-sm font-black text-coffee">
                    <Coin size={16} /> {STAGE_COST[i]}
                  </span>
                )}
              </motion.button>
            );
          })}
        </div>
      </div>

      <AnimatePresence>
        {toast && (
          <motion.div
            role="status"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 30 }}
            className="fixed inset-x-4 bottom-28 z-50 mx-auto max-w-sm rounded-2xl bg-coffee px-5 py-4 text-center font-black text-on-caramel shadow-lift lg:bottom-8"
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
      <Confetti burst={burst} />
    </div>
  );
}
