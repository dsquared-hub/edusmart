import { motion } from "framer-motion";
import { ArrowRight, Award, BookOpen, Camera, CheckCircle2, ClipboardCheck, Mic, Shirt, Snowflake, Sparkles, Trophy } from "lucide-react";
import { Kubi } from "@/components/avatar/Kubi";
import { WhyBlock } from "@/components/WhyBlock";
import { Badge, Card, Coin, Icon3D, ProgressBar, Ring, SectionTitle } from "@/design-system/components";
import { LEADERS, QUESTS, SUBJECTS } from "@/mock-data";
import { Link } from "@/lib/router";
import { fmt, STAGE_COST, useL, useStore, XP_PER_LEVEL } from "@/lib/store";

function Hero() {
  const { d, name, mode, level, xpInLevel, mood, worn, skin, coins, unlocked } = useStore();
  const next = Math.min(unlocked + 1, 6);
  const need = STAGE_COST[next] - coins;
  const stageName = d.wardrobe.stages[next];
  return (
    <section className="card relative overflow-hidden p-6 sm:p-8">
      {/* мягкое «кофейное» свечение */}
      <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-gold/25 blur-3xl" />
      <div className="relative flex flex-col items-center gap-6 sm:flex-row">
        <div className="min-w-0 flex-1 text-center sm:text-left">
          <h1 className="h-display">{fmt(d.home.hello, { name })}</h1>
          <p className="mt-2 text-lg font-semibold text-muted">{mode === "junior" ? d.home.subJunior : d.home.subSenior}</p>
          <div className="mt-5 flex items-center gap-3">
            <Badge tone="coffee">{fmt(d.common.level, { n: level })}</Badge>
            <div className="flex-1">
              <ProgressBar value={xpInLevel} max={XP_PER_LEVEL} tone="gold" size="md" label={fmt(d.common.level, { n: level })} />
            </div>
            <span className="text-sm font-black text-muted">
              {xpInLevel}/{XP_PER_LEVEL}
            </span>
          </div>
          {unlocked < 6 && (
            <Link to="/wardrobe" className="mt-4 inline-flex items-center gap-2 rounded-2xl bg-card px-4 py-2.5 text-sm font-extrabold text-coffee hover:brightness-95">
              <Shirt size={18} />
              {need > 0 ? fmt(d.home.toStage, { stage: stageName, n: need }) : fmt(d.home.stageReady, { stage: stageName })}
              <ArrowRight size={16} />
            </Link>
          )}
        </div>
        <Link to="/wardrobe" aria-label={d.nav.wardrobe} className="shrink-0">
          <Kubi stage={worn} skin={skin} mood={mood} size={mode === "junior" ? 190 : 160} />
        </Link>
      </div>
    </section>
  );
}

function AskCta() {
  const { d } = useStore();
  return (
    <Link to="/ask" className="group relative block overflow-hidden rounded-[var(--radius-card)] bg-coffee p-6 text-on-caramel shadow-lift">
      <div className="pointer-events-none absolute -bottom-16 -right-10 h-48 w-48 rounded-full bg-caramel/40 blur-2xl" />
      <div className="relative flex items-center gap-4">
        <Icon3D color="#E8B64C" size={60}>
          <Sparkles size={30} strokeWidth={2.5} className="text-[#5A3A10]" />
        </Icon3D>
        <div className="min-w-0 flex-1">
          <div className="text-2xl font-black">{d.home.ask}</div>
          <div className="font-semibold opacity-85">{d.home.askHint}</div>
        </div>
        <div className="hidden gap-2 sm:flex" aria-hidden="true">
          {[Camera, Mic].map((I, i) => (
            <span key={i} className="grid h-11 w-11 place-items-center rounded-xl bg-white/15">
              <I size={20} />
            </span>
          ))}
        </div>
        <motion.span className="grid h-11 w-11 place-items-center rounded-full bg-white/20" whileHover={{ x: 4 }}>
          <ArrowRight />
        </motion.span>
      </div>
    </Link>
  );
}

function Quests() {
  const { d, quests } = useStore();
  const progress: Record<string, number> = { q1: quests.q1 ? 1 : 0, q2: quests.q2 ? 3 : 1, q3: 5 };
  const links: Record<string, string> = { q1: "/ask", q2: "/quiz", q3: "/textbooks" };
  return (
    <Card>
      <SectionTitle>{d.home.daily}</SectionTitle>
      <ul className="flex flex-col gap-3">
        {QUESTS.map((q) => {
          const done = Boolean(quests[q.id]) || progress[q.id] >= q.total;
          return (
            <li key={q.id}>
              <Link to={links[q.id]} className={`flex items-center gap-3 rounded-2xl p-3 transition hover:bg-card ${done ? "opacity-80" : ""}`}>
                <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-card text-2xl">{q.icon}</span>
                <div className="min-w-0 flex-1">
                  <div className={`font-extrabold ${done ? "text-muted line-through" : ""}`}>{d.home.quests[q.id]}</div>
                  <div className="mt-1.5 flex items-center gap-2">
                    <ProgressBar value={Math.min(progress[q.id], q.total)} max={q.total} size="sm" tone={done ? "good" : "caramel"} />
                    <span className="text-xs font-black text-muted">
                      {Math.min(progress[q.id], q.total)}/{q.total}
                    </span>
                  </div>
                </div>
                {done ? (
                  <CheckCircle2 className="text-good" size={28} />
                ) : (
                  <Badge tone="gold">
                    <Coin size={14} /> +{q.reward}
                  </Badge>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function ContinueLearning() {
  const { d } = useStore();
  const L = useL();
  const items = [SUBJECTS[1], SUBJECTS[2], SUBJECTS[3]];
  const topics = [
    { uz: "Qisqa koʻpaytirish formulalari", ru: "Формулы сокращённого умножения", en: "Short multiplication formulas" },
    { uz: "Trapetsiya yuzi", ru: "Площадь трапеции", en: "Trapezoid area" },
    { uz: "Nyuton qonunlari", ru: "Законы Ньютона", en: "Newton's laws" },
  ];
  return (
    <section>
      <SectionTitle action={<Link to="/subjects" className="text-sm font-extrabold text-caramel hover:underline">{d.common.seeAll}</Link>}>
        {d.home.continue}
      </SectionTitle>
      <div className="grid gap-3 sm:grid-cols-3">
        {items.map((s, i) => (
          <Link key={s.id} to={i === 0 ? "/reader/alg7" : "/ask"} className="card flex flex-col gap-3 p-4 transition hover:-translate-y-0.5 hover:shadow-lift">
            <div className="flex items-center gap-3">
              <Icon3D color={s.color} size={46}>
                <span className="text-2xl">{s.emoji}</span>
              </Icon3D>
              <div className="min-w-0">
                <div className="truncate text-xs font-extrabold uppercase tracking-wide text-muted">{L(s.name)}</div>
                <div className="line-clamp-2 font-black leading-tight">{L(topics[i])}</div>
              </div>
            </div>
            <ProgressBar value={s.progress} size="sm" />
          </Link>
        ))}
      </div>
    </section>
  );
}

function SideColumn() {
  const { d, freezes, streak } = useStore();
  return (
    <div className="flex flex-col gap-5">
      <Card cream className="flex items-center gap-4">
        <Icon3D color="#5E9ACB" size={52}>
          <Snowflake size={26} strokeWidth={2.6} />
        </Icon3D>
        <div className="min-w-0">
          <div className="font-black text-coffee">
            🔥 {fmt(d.common.days, { n: streak })} · {fmt(d.home.freeze, { n: freezes })}
          </div>
          <div className="text-sm font-semibold text-muted">{d.home.freezeHint}</div>
        </div>
      </Card>
      <Card className="flex items-center gap-4">
        <Ring value={60} size={72}>
          3/5
        </Ring>
        <div>
          <div className="font-black text-coffee">{d.home.weekGoal}</div>
          <div className="text-sm font-semibold text-muted">{fmt(d.home.weekGoalText, { a: 3, b: 5 })}</div>
        </div>
      </Card>
      <Card>
        <SectionTitle action={<Link to="/leaderboard" className="text-sm font-extrabold text-caramel hover:underline">{d.common.seeAll}</Link>}>
          {d.nav.leaderboard}
        </SectionTitle>
        <ol className="flex flex-col gap-2">
          {LEADERS.class.slice(0, 3).map((p, i) => (
            <li key={p.name} className={`flex items-center gap-3 rounded-2xl p-2 ${p.me ? "bg-gold/15" : ""}`}>
              <span className="w-5 text-center font-black text-muted">{i + 1}</span>
              <span className="grid h-10 w-10 place-items-center overflow-hidden rounded-xl bg-card">
                <Kubi stage={p.stage} skin={p.skin} size={34} />
              </span>
              <span className="min-w-0 flex-1 truncate font-bold">{p.name}</span>
              <span className="flex items-center gap-1 font-black text-coffee">
                <Coin size={16} />
                {p.coins}
              </span>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}

function QuickLinks() {
  const { d } = useStore();
  const links = [
    { to: "/textbooks", label: d.nav.textbooks, icon: BookOpen, color: "#9B7B55" },
    { to: "/quiz", label: d.nav.quiz, icon: ClipboardCheck, color: "#6FA876" },
    { to: "/leaderboard", label: d.nav.leaderboard, icon: Trophy, color: "#E8B64C" },
    { to: "/achievements", label: d.nav.achievements, icon: Award, color: "#D98B4E" },
  ];
  return (
    <div className="grid grid-cols-4 gap-2 lg:hidden">
      {links.map(({ to, label, icon: Icon, color }) => (
        <Link key={to} to={to} className="flex flex-col items-center gap-1.5 rounded-2xl p-2 text-center text-xs font-extrabold hover:bg-card">
          <Icon3D color={color} size={52}>
            <Icon size={24} strokeWidth={2.5} />
          </Icon3D>
          <span className="line-clamp-2 leading-tight">{label}</span>
        </Link>
      ))}
    </div>
  );
}

export default function Home() {
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="flex min-w-0 flex-col gap-6">
        <Hero />
        <AskCta />
        <QuickLinks />
        <Quests />
        <ContinueLearning />
        <div className="xl:hidden">
          <SideColumn />
        </div>
        <WhyBlock />
      </div>
      <aside className="hidden xl:block">
        <div className="sticky top-20">
          <SideColumn />
        </div>
      </aside>
    </div>
  );
}
