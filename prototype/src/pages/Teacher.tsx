import { AnimatePresence, motion } from "framer-motion";
import { Activity, AlertCircle, ClipboardPlus, TrendingUp, Users } from "lucide-react";
import { useState } from "react";
import { Kubi } from "@/components/avatar/Kubi";
import { PageHeader } from "@/components/layout/AppShell";
import { Badge, Button, Card, Icon3D, Modal, ProgressBar, SectionTitle, Segmented, StatTile } from "@/design-system/components";
import { CLASS_FAQ, CLASSES, MASTERY, STUDENTS, subjectById } from "@/mock-data";
import { fmt, useL, useStore } from "@/lib/store";

export default function Teacher() {
  const { d } = useStore();
  const L = useL();
  const [cls, setCls] = useState<string>(CLASSES[0]);
  const [open, setOpen] = useState(false);
  const [topic, setTopic] = useState(0);
  const [toast, setToast] = useState<string | null>(null);

  const avg = Math.round(STUDENTS.reduce((a, s) => a + s.progress, 0) / STUDENTS.length);
  const active = STUDENTS.filter((s) => s.last === "today").length;
  const lastLabel = (last: string) => (last === "today" ? d.teacher.today : last === "yesterday" ? d.teacher.yesterday : last);

  const send = () => {
    setOpen(false);
    setToast(fmt(d.teacher.assigned, { cls }));
    window.setTimeout(() => setToast(null), 2600);
  };

  return (
    <div>
      <PageHeader
        title={d.teacher.title}
        action={
          <Button icon={<ClipboardPlus size={18} />} onClick={() => setOpen(true)}>
            {d.teacher.assign}
          </Button>
        }
      />
      <Segmented label={d.teacher.students} value={cls} onChange={setCls} className="mb-6" options={CLASSES.map((c) => ({ value: c, label: c }))} />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-3">
        <StatTile icon={<Icon3D color="#5E86B5" size={44}><Users size={22} /></Icon3D>} value={STUDENTS.length} label={d.teacher.students} />
        <StatTile icon={<Icon3D color="#6FA876" size={44}><TrendingUp size={22} /></Icon3D>} value={`${avg}%`} label={d.teacher.avgProgress} />
        <StatTile icon={<Icon3D color="#D98B4E" size={44}><Activity size={22} /></Icon3D>} value={`${active}/${STUDENTS.length}`} label={d.teacher.active} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card className="overflow-hidden p-0">
          <div className="p-5 pb-2">
            <SectionTitle>{d.teacher.students}</SectionTitle>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[34rem] text-left">
              <thead>
                <tr className="label border-b border-line">
                  <th className="px-5 py-2 font-extrabold">{d.teacher.name}</th>
                  <th className="px-3 py-2 font-extrabold">{d.teacher.progress}</th>
                  <th className="px-5 py-2 font-extrabold">{d.teacher.lastActive}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {STUDENTS.map((s) => (
                  <tr key={s.name} className="transition hover:bg-card/60">
                    <td className="px-5 py-2.5">
                      <div className="flex items-center gap-3">
                        <span className="grid h-11 w-11 shrink-0 place-items-center overflow-hidden rounded-xl bg-card">
                          <Kubi stage={s.stage} skin={s.skin} size={38} />
                        </span>
                        <div className="min-w-0">
                          <div className="truncate font-extrabold">{s.name}</div>
                          {s.help && (
                            <Badge tone="bad">
                              <AlertCircle size={12} /> {d.teacher.needsHelp}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="w-44 px-3">
                      <div className="flex items-center gap-2">
                        <ProgressBar value={s.progress} size="sm" tone={s.progress >= 70 ? "good" : s.progress >= 45 ? "gold" : "caramel"} label={s.name} />
                        <span className="w-9 text-right text-sm font-black text-coffee">{s.progress}%</span>
                      </div>
                    </td>
                    <td className="px-5 text-sm font-bold text-muted">{lastLabel(s.last)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <SectionTitle>{d.teacher.faq}</SectionTitle>
          <ul className="flex flex-col gap-3">
            {CLASS_FAQ.map((f) => {
              const s = subjectById(f.subject);
              return (
                <li key={f.q.en} className="rounded-2xl bg-card p-4">
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">{s.emoji}</span>
                    <div className="min-w-0">
                      <div className="font-extrabold leading-snug">{L(f.q)}</div>
                      <div className="mt-1 text-sm font-bold text-muted">
                        {L(s.name)} · {fmt(d.teacher.faqCount, { n: f.count })}
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={d.teacher.assignTitle}>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <span className="label">{d.teacher.assignTopic}</span>
            <div className="flex flex-col gap-2">
              {MASTERY.slice(0, 4).map((m, i) => (
                <button key={m.topic.en} className="chip justify-start !py-2.5 text-base" aria-pressed={topic === i} onClick={() => setTopic(i)}>
                  {L(m.topic)}
                </button>
              ))}
            </div>
          </div>
          <label className="flex flex-col gap-2">
            <span className="label">{d.teacher.assignDue}</span>
            <input type="date" className="field" defaultValue="2026-10-02" />
          </label>
          <Button size="lg" onClick={send}>
            {d.teacher.assignSend} · {cls}
          </Button>
        </div>
      </Modal>

      <AnimatePresence>
        {toast && (
          <motion.div role="status" initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 30 }} className="fixed inset-x-4 bottom-28 z-50 mx-auto max-w-sm rounded-2xl bg-coffee px-5 py-4 text-center font-black text-on-caramel shadow-lift lg:bottom-8">
            ✓ {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
