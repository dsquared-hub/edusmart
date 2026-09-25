"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Mascot } from "@/components/Mascot";
import { celebrate } from "@/lib/confetti";
import { useT } from "@/lib/i18n";
import type { Topic } from "@/lib/types";

type Totals = { points: number; level: number; streak: number };

export function DoneScreen({
  topic,
  totals,
  onPractice,
}: {
  topic: Topic;
  totals: Totals | null;
  onPractice: () => void;
}) {
  const t = useT();

  useEffect(() => {
    celebrate(true);
  }, []);

  const stats: [string, string | number, string][] = [
    ["⭐", `+${topic.points_earned}`, t("done.earned")],
    ...(totals
      ? ([
          ["✨", totals.points, t("done.total")],
          ["⚡", totals.level, t("done.level")],
          ["🔥", t("home.streak_value", { n: totals.streak }), t("done.streak")],
        ] as [string, string | number, string][])
      : []),
  ];

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 py-6 text-center">
      <Mascot mood="cheer" size={150} className="anim-pop" />
      <div className="flex flex-col gap-2 anim-rise">
        <h1 className="text-4xl font-black">🎉 {t("done.title")}</h1>
        <p className="text-xl font-bold text-muted">{topic.title}</p>
      </div>

      <div className="grid w-full grid-cols-3 gap-2 anim-rise">
        {stats.map(([icon, value, label], i) => (
          <div key={label} className={`card flex flex-col items-center gap-0.5 px-1 py-4 ${i === 0 ? "col-span-3 bg-accent/20" : ""}`}>
            <span className="text-3xl" aria-hidden="true">{icon}</span>
            <span className={`font-black ${i === 0 ? "text-4xl" : "text-2xl"}`}>{value}</span>
            <span className="text-xs font-extrabold uppercase tracking-wide text-muted">{label}</span>
          </div>
        ))}
      </div>

      <div className="flex w-full flex-col gap-3 anim-rise">
        <button className="btn btn-primary btn-xl" onClick={onPractice} autoFocus>
          💪 {t("done.practice")}
        </button>
        <Link href="/learn" className="btn btn-soft">🤔 {t("done.new_topic")}</Link>
        <Link href="/" className="btn btn-soft">🏠 {t("done.home")}</Link>
      </div>
    </div>
  );
}
