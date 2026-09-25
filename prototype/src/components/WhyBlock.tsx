/* «Почему EDU ProgressUZ»: чем мы отличаемся от приложений, которые давят и наказывают. */
import { motion } from "framer-motion";
import { BookMarked, Brain, CalendarHeart, HeartHandshake, Infinity as InfinityIcon, ShieldCheck, Sparkles, Users } from "lucide-react";
import { Icon3D } from "@/design-system/components";
import { useStore } from "@/lib/store";

const ICONS = {
  mistakes: { icon: InfinityIcon, color: "#6FA876" },
  calm: { icon: HeartHandshake, color: "#C98A6A" },
  streak: { icon: CalendarHeart, color: "#D98B4E" },
  deep: { icon: Brain, color: "#7A5236" },
  understand: { icon: Sparkles, color: "#E8B64C" },
  free: { icon: ShieldCheck, color: "#5E86B5" },
  school: { icon: BookMarked, color: "#9B7B55" },
  family: { icon: Users, color: "#A86A8C" },
} as const;

export function WhyBlock({ compact = false }: { compact?: boolean }) {
  const { d } = useStore();
  return (
    <section aria-labelledby="why-title">
      <h2 id="why-title" className="h-title">
        {d.why.title}
      </h2>
      <p className="mb-4 font-semibold text-muted">{d.why.subtitle}</p>
      <div className={`grid gap-3 ${compact ? "sm:grid-cols-2" : "sm:grid-cols-2 xl:grid-cols-4"}`}>
        {d.why.items.map((item, i) => {
          const { icon: Icon, color } = ICONS[item.key as keyof typeof ICONS];
          return (
            <motion.div
              key={item.key}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.04 }}
              className="card flex gap-3 p-4"
            >
              <Icon3D color={color} size={44}>
                <Icon size={22} strokeWidth={2.6} />
              </Icon3D>
              <div className="min-w-0 text-sm">
                <div className="text-muted line-through decoration-bad/60 decoration-2">{item.them}</div>
                <div className="mt-0.5 font-extrabold text-ink">{item.us}</div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
