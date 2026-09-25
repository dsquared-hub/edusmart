import { Clock, Coins, Target, Trophy } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PageHeader } from "@/components/layout/AppShell";
import { Badge, Card, Coin, Icon3D, ProgressBar, SectionTitle, StatTile } from "@/design-system/components";
import { ACTIVITY, HISTORY, MASTERY, subjectById, TOPIC_MAP } from "@/mock-data";
import { fmt, useL, useStore, XP_PER_LEVEL } from "@/lib/store";
import { useThemeColors } from "@/lib/useThemeColors";

const LEVEL_STYLE = {
  strong: "bg-good/20 text-good border-good/40",
  medium: "bg-gold/25 text-coffee border-gold/50",
  weak: "bg-bad/15 text-bad border-bad/40",
} as const;

export default function Progress() {
  const { d, level, xpInLevel, solved, coins } = useStore();
  const L = useL();
  const c = useThemeColors();
  const data = ACTIVITY.map((min, i) => ({ day: d.progress.weekdays[i], min }));
  const total = ACTIVITY.reduce((a, b) => a + b, 0);

  return (
    <div>
      <PageHeader title={d.progress.title} />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile icon={<Icon3D color="#6FA876" size={44}><Target size={22} /></Icon3D>} value={solved} label={d.progress.solved} />
        <StatTile icon={<Icon3D color="#5E86B5" size={44}><Trophy size={22} /></Icon3D>} value="86%" label={d.progress.accuracy} />
        <StatTile icon={<Icon3D color="#D98B4E" size={44}><Clock size={22} /></Icon3D>} value={fmt(d.common.minutes, { n: total })} label={d.progress.time} />
        <StatTile icon={<Icon3D color="#E8B64C" size={44}><Coins size={22} /></Icon3D>} value={coins} label={d.common.coins} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card>
          <SectionTitle>{d.progress.activity}</SectionTitle>
          <div className="h-56" role="img" aria-label={`${d.progress.activity}: ${ACTIVITY.join(", ")} ${d.progress.minutesLabel}`}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                <defs>
                  <linearGradient id="act" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={c.caramel} stopOpacity={0.55} />
                    <stop offset="100%" stopColor={c.caramel} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={c.line} vertical={false} />
                <XAxis dataKey="day" tick={{ fill: c.muted, fontWeight: 700, fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: c.muted, fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip
                  cursor={{ stroke: c.latte }}
                  contentStyle={{ background: c.surface, border: `1px solid ${c.line}`, borderRadius: 14, fontWeight: 800, color: c.ink }}
                  formatter={(v: number) => [fmt(d.common.minutes, { n: v }), ""]}
                  separator=""
                />
                <Area type="monotone" dataKey="min" stroke={c.coffee} strokeWidth={3} fill="url(#act)" dot={{ r: 4, fill: c.coffee }} activeDot={{ r: 6 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <SectionTitle>{fmt(d.common.level, { n: level })}</SectionTitle>
          {/* Шкала уровней: пройденные — кофейные, текущий — с прогрессом */}
          <div className="mb-3 flex items-end gap-1.5" aria-hidden="true">
            {Array.from({ length: 10 }, (_, i) => {
              const lv = Math.max(1, level - 4) + i;
              const done = lv < level;
              const cur = lv === level;
              return (
                <div key={lv} className="flex flex-1 flex-col items-center gap-1">
                  <div
                    className={`w-full rounded-lg ${done ? "bg-coffee" : cur ? "bg-gold" : "bg-line"}`}
                    style={{ height: 14 + i * 5 }}
                  />
                  <span className={`text-[10px] font-black ${cur ? "text-coffee" : "text-muted"}`}>{lv}</span>
                </div>
              );
            })}
          </div>
          <ProgressBar value={xpInLevel} max={XP_PER_LEVEL} tone="gold" label={fmt(d.common.level, { n: level })} />
          <p className="mt-2 text-sm font-bold text-muted">{fmt(d.progress.levelBar, { n: level + 1, xp: XP_PER_LEVEL - xpInLevel })}</p>
        </Card>

        <Card>
          <SectionTitle>{d.progress.mastery}</SectionTitle>
          <ul className="flex flex-col gap-4">
            {MASTERY.map((m) => (
              <li key={m.topic.en}>
                <div className="mb-1.5 flex justify-between gap-2 text-sm font-extrabold">
                  <span className="truncate">{L(m.topic)}</span>
                  <span className="text-coffee">{m.value}%</span>
                </div>
                <ProgressBar value={m.value} tone={m.value >= 70 ? "good" : m.value >= 45 ? "gold" : "caramel"} size="sm" label={L(m.topic)} />
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <SectionTitle>{d.progress.map}</SectionTitle>
          <div className="mb-3 flex flex-wrap gap-2 text-xs font-extrabold">
            {(["strong", "medium", "weak"] as const).map((l) => (
              <span key={l} className={`badge border ${LEVEL_STYLE[l]}`}>
                {d.progress[l]}
              </span>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {TOPIC_MAP.map((t) => (
              <div key={t.topic.en} className={`rounded-2xl border px-3 py-2.5 ${LEVEL_STYLE[t.level]}`}>
                <div className="text-lg leading-none">{subjectById(t.subject).emoji}</div>
                <div className="mt-1 truncate text-sm font-black">{L(t.topic)}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <SectionTitle>{d.progress.history}</SectionTitle>
          <ul className="divide-y divide-line">
            {HISTORY.map((h) => {
              const s = subjectById(h.subject);
              return (
                <li key={h.title.en} className="flex items-center gap-3 py-3">
                  <Icon3D color={s.color} size={42}>
                    <span className="text-xl">{s.emoji}</span>
                  </Icon3D>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-extrabold">{L(h.title)}</div>
                    <div className="text-sm font-semibold text-muted">
                      {L(s.name)} · {L(h.when)}
                    </div>
                  </div>
                  <Badge tone="gold">
                    <Coin size={14} /> +{h.coins}
                  </Badge>
                </li>
              );
            })}
          </ul>
        </Card>
      </div>
    </div>
  );
}
