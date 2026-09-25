import { motion } from "framer-motion";
import { PageHeader } from "@/components/layout/AppShell";
import { Icon3D, Ring } from "@/design-system/components";
import { SUBJECTS } from "@/mock-data";
import { Link } from "@/lib/router";
import { fmt, useL, useStore } from "@/lib/store";

export default function Subjects() {
  const { d, grade } = useStore();
  const L = useL();
  return (
    <div>
      <PageHeader title={d.subjects.title} subtitle={fmt(d.subjects.subtitle, { n: grade })} />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
        {SUBJECTS.map((s, i) => (
          <motion.div key={s.id} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
            <Link
              to="/textbooks"
              className="card group flex h-full flex-col gap-4 p-4 transition hover:-translate-y-1 hover:shadow-lift sm:p-5"
            >
              <div className="flex items-start justify-between gap-2">
                <Icon3D color={s.color} size={64} className="transition group-hover:rotate-[-6deg] group-hover:scale-105">
                  <span className="text-3xl">{s.emoji}</span>
                </Icon3D>
                <Ring value={s.progress} size={52} stroke={6} />
              </div>
              <div className="min-w-0">
                <div className="text-lg font-black leading-tight text-coffee [overflow-wrap:anywhere]">{L(s.name)}</div>
                <div className="mt-1 text-sm font-bold text-muted">{fmt(d.subjects.topics, { a: s.topics[0], b: s.topics[1] })}</div>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
