import { motion } from "framer-motion";
import { Crown } from "lucide-react";
import { useState } from "react";
import { Kubi } from "@/components/avatar/Kubi";
import { PageHeader } from "@/components/layout/AppShell";
import { Card, Coin, Segmented } from "@/design-system/components";
import { LEADERS, type Player } from "@/mock-data";
import { fmt, useStore } from "@/lib/store";

type Scope = keyof typeof LEADERS;

function Podium({ players }: { players: Player[] }) {
  // Порядок на пьедестале: 2 — 1 — 3
  const order = [players[1], players[0], players[2]];
  const heights = [96, 128, 76];
  const medals = ["🥈", "🥇", "🥉"];
  return (
    <div className="flex items-end justify-center gap-2 sm:gap-4">
      {order.map((p, i) =>
        p ? (
          <motion.div key={p.name} initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }} className="flex w-28 flex-col items-center sm:w-36">
            {i === 1 && <Crown className="mb-1 text-gold" size={28} fill="currentColor" />}
            <Kubi stage={p.stage} skin={p.skin} size={i === 1 ? 96 : 78} mood={i === 1 ? "happy" : "idle"} />
            <div className="mt-1 w-full truncate text-center text-sm font-black">{p.name.split(" ")[0]}</div>
            <div className="flex items-center gap-1 text-sm font-black text-coffee">
              <Coin size={14} /> {p.coins}
            </div>
            <div
              className="mt-2 grid w-full place-items-start justify-center rounded-t-2xl bg-gradient-to-b from-latte to-card pt-2 text-3xl shadow-soft"
              style={{ height: heights[i] }}
            >
              {medals[i]}
            </div>
          </motion.div>
        ) : null,
      )}
    </div>
  );
}

export default function Leaderboard() {
  const { d } = useStore();
  const [scope, setScope] = useState<Scope>("class");
  const players = LEADERS[scope];
  const myPlace = players.findIndex((p) => p.me) + 1;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title={d.leaderboard.title} subtitle={`${fmt(d.leaderboard.yourPlace, { n: myPlace })} · ${d.leaderboard.week}`} />
      <Segmented
        label={d.leaderboard.title}
        value={scope}
        onChange={setScope}
        className="mb-6 w-full"
        options={(["class", "school", "region"] as const).map((s) => ({ value: s, label: d.leaderboard[s] }))}
      />
      <Card className="mb-4 pb-0">
        <Podium players={players} />
      </Card>
      <Card className="p-2 sm:p-3">
        <ol>
          {players.slice(3).map((p, i) => (
            <li key={p.name} className={`flex items-center gap-3 rounded-2xl px-3 py-2.5 ${p.me ? "bg-gold/20 ring-2 ring-gold/60" : ""}`}>
              <span className="w-6 text-center font-black text-muted">{i + 4}</span>
              <span className="grid h-12 w-12 place-items-center overflow-hidden rounded-2xl bg-card">
                <Kubi stage={p.stage} skin={p.skin} size={42} />
              </span>
              <span className="min-w-0 flex-1 truncate font-extrabold">
                {p.name}
                {p.me && <span className="ml-2 text-xs font-black text-caramel">({d.common.you})</span>}
              </span>
              <span className="flex items-center gap-1 font-black text-coffee">
                <Coin size={18} /> {p.coins}
              </span>
            </li>
          ))}
        </ol>
      </Card>
      <p className="mt-4 text-center text-sm font-bold text-muted">{d.leaderboard.friendly}</p>
    </div>
  );
}
