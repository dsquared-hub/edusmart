import { AnimatePresence, motion } from "framer-motion";
import { Brain, CheckCircle2, Clock, Download, Flame } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Kubi } from "@/components/avatar/Kubi";
import { PageHeader } from "@/components/layout/AppShell";
import { Badge, Button, Card, Icon3D, ProgressBar, SectionTitle, Segmented, StatTile, Toggle } from "@/design-system/components";
import { CHILDREN, HISTORY, subjectById, WEAK_TOPICS } from "@/mock-data";
import { fmt, useL, useStore } from "@/lib/store";
import { useThemeColors } from "@/lib/useThemeColors";

export default function Parent() {
  const { d } = useStore();
  const L = useL();
  const c = useThemeColors();
  const [child, setChild] = useState("0");
  const [remind, setRemind] = useState(true);
  const [toast, setToast] = useState(false);
  const kid = CHILDREN[Number(child)];
  const total = kid.week.reduce((a, b) => a + b, 0);
  const data = kid.week.map((min, i) => ({ day: d.progress.weekdays[i], min }));

  return (
    <div>
      <PageHeader
        title={d.parent.title}
        action={
          <Button
            variant="soft"
            icon={<Download size={18} />}
            onClick={() => {
              setToast(true);
              window.setTimeout(() => setToast(false), 2400);
            }}
          >
            {d.parent.report}
          </Button>
        }
      />
      <Segmented
        label={d.parent.child}
        value={child}
        onChange={setChild}
        className="mb-6"
        options={CHILDREN.map((k, i) => ({ value: String(i), label: `${k.name.split(" ")[0]} · ${fmt(d.common.grade, { n: k.grade })}` }))}
      />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile icon={<Icon3D color="#D98B4E" size={44}><Clock size={22} /></Icon3D>} value={fmt(d.common.minutes, { n: total })} label={d.parent.weekTime} />
        <StatTile icon={<Icon3D color="#7A5236" size={44}><Brain size={22} /></Icon3D>} value={kid.askedAi} label={d.parent.askedAi} />
        <StatTile icon={<Icon3D color="#6FA876" size={44}><CheckCircle2 size={22} /></Icon3D>} value={kid.solved} label={d.parent.solvedTasks} />
        <StatTile icon={<Icon3D color="#D2735A" size={44}><Flame size={22} /></Icon3D>} value={fmt(d.common.days, { n: kid.streak })} label={d.common.streak} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card>
          <SectionTitle>
            {d.parent.weekTime} · {fmt(d.parent.avgDaily, {})}: {fmt(d.common.minutes, { n: Math.round(total / 7) })}
          </SectionTitle>
          <div className="h-56" role="img" aria-label={`${d.parent.weekTime}: ${kid.week.join(", ")}`}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid stroke={c.line} vertical={false} />
                <XAxis dataKey="day" tick={{ fill: c.muted, fontWeight: 700, fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: c.muted, fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip
                  cursor={{ fill: c.line, opacity: 0.4 }}
                  contentStyle={{ background: c.surface, border: `1px solid ${c.line}`, borderRadius: 14, fontWeight: 800, color: c.ink }}
                  formatter={(v: number) => [fmt(d.common.minutes, { n: v }), ""]}
                  separator=""
                />
                <Bar dataKey="min" fill={c.caramel} radius={[10, 10, 4, 4]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <SectionTitle>{d.parent.weakTopics}</SectionTitle>
          <ul className="flex flex-col gap-4">
            {WEAK_TOPICS.map((w) => {
              const s = subjectById(w.subject);
              return (
                <li key={w.topic.en} className="flex items-center gap-3">
                  <Icon3D color={s.color} size={42}>
                    <span className="text-xl">{s.emoji}</span>
                  </Icon3D>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex justify-between gap-2 text-sm font-extrabold">
                      <span className="truncate">{L(w.topic)}</span>
                      <span className="text-bad">{w.accuracy}%</span>
                    </div>
                    <ProgressBar value={w.accuracy} size="sm" tone="caramel" label={L(w.topic)} />
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>

        <Card>
          <SectionTitle>{d.parent.recent}</SectionTitle>
          <ul className="divide-y divide-line">
            {HISTORY.map((h) => (
              <li key={h.title.en} className="flex items-center gap-3 py-2.5">
                <span className="text-xl">{subjectById(h.subject).emoji}</span>
                <span className="min-w-0 flex-1 truncate font-bold">{L(h.title)}</span>
                <span className="text-sm font-semibold text-muted">{L(h.when)}</span>
              </li>
            ))}
          </ul>
        </Card>

        <div className="flex flex-col gap-6">
          <Card>
            <SectionTitle>{d.parent.reminders}</SectionTitle>
            <p className="mb-2 text-sm font-semibold text-muted">{d.parent.remindersText}</p>
            <Toggle label={d.profile.notifDaily} checked={remind} onChange={setRemind} />
          </Card>
          <Card cream className="flex items-center gap-4">
            <Kubi stage={1} skin={0} mood="support" size={80} />
            <div>
              <Badge tone="gold">{d.parent.tip}</Badge>
              <p className="mt-1 font-bold">{d.parent.tipText}</p>
            </div>
          </Card>
        </div>
      </div>

      <AnimatePresence>
        {toast && (
          <motion.div role="status" initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 30 }} className="fixed inset-x-4 bottom-28 z-50 mx-auto max-w-sm rounded-2xl bg-coffee px-5 py-4 text-center font-black text-on-caramel shadow-lift lg:bottom-8">
            ✓ {d.parent.reportReady}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
