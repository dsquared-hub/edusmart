"use client";

/* PvP-дуэли: бросить вызов по теме (другу по коду или открытый), принять по коду,
   случайный соперник своего класса, список своих дуэлей. */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { RequireStudent } from "@/components/RequireStudent";
import { Thinking } from "@/components/Thinking";
import { IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { SUBJECT_ICON } from "@/lib/subjects";
import type { DuelView } from "@/lib/types";

function statusText(d: DuelView, t: ReturnType<typeof useT>) {
  if (d.status === "finished") return d.winner === "me" ? `🏆 ${t("duels.won")}` : d.winner === "draw" ? `🤝 ${t("duels.draw")}` : `⚔️ ${t("duels.lost")}`;
  if (d.status === "expired") return `⌛ ${t("duels.expired")}`;
  if (!d.me.done) return `▶️ ${t("duels.your_turn")}`;
  return `⏳ ${t("duels.waiting")}`;
}

function Duels() {
  const t = useT();
  const router = useRouter();
  const [list, setList] = useState<DuelView[] | null>(null);
  const [topic, setTopic] = useState("");
  const [subject, setSubject] = useState("math");
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ duels: DuelView[] }>("/duels").then((r) => setList(r.duels)).catch((e) => setError(errorCode(e)));
  }, []);

  if (!list && !error) return <Splash />;

  const go = async (key: string, path: string, json: Record<string, unknown>) => {
    setBusy(key);
    setError(null);
    try {
      const duel = await api<DuelView>(path, { method: "POST", json });
      router.push(`/duels/${duel.id}`);
    } catch (e) {
      setError(errorCode(e));
      setBusy(null);
    }
  };

  const create = (e: FormEvent) => {
    e.preventDefault();
    if (topic.trim()) void go("create", "/duels", { topic: topic.trim(), subject, public: open });
  };

  return (
    <Page className="gap-5">
      {busy === "create" && <Thinking title={t("duels.preparing")} />}
      <header className="flex items-center gap-3">
        <IconButton href="/" label={t("profile.back")}>‹</IconButton>
        <h1 className="min-w-0 flex-1 text-2xl font-black leading-tight">⚔️ {t("duels.title")}</h1>
      </header>
      <p className="font-bold text-muted">{t("duels.intro")}</p>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      <form onSubmit={create} className="card flex flex-col gap-3 anim-rise">
        <h2 className="text-lg font-black">🎯 {t("duels.challenge")}</h2>
        <input
          className="field text-lg font-bold"
          value={topic}
          onChange={(e) => setTopic(e.target.value.slice(0, 200))}
          placeholder={t("duels.topic_placeholder")}
          aria-label={t("duels.challenge")}
        />
        <div className="flex flex-wrap gap-2">
          {Object.entries(SUBJECT_ICON).map(([key, icon]) => (
            <button key={key} type="button" className="chip" aria-pressed={subject === key} onClick={() => setSubject(key)}>
              {icon} {t(`subjects.${key}`)}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-3 font-bold">
          <input type="checkbox" className="h-5 w-5 accent-[rgb(var(--primary))]" checked={open} onChange={(e) => setOpen(e.target.checked)} />
          {t("duels.public")}
        </label>
        <button className="btn btn-primary" disabled={!topic.trim() || busy !== null}>⚔️ {t("duels.create")}</button>
      </form>

      <section className="card flex flex-col gap-3 anim-rise">
        <h2 className="text-lg font-black">🤝 {t("duels.join_title")}</h2>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (code.trim().length >= 4) void go("join", "/duels/join", { code: code.trim() });
          }}
        >
          <input
            className="field min-w-0 flex-1 text-center text-xl font-black uppercase tracking-[0.3em]"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/[^a-zA-Z0-9]/g, "").slice(0, 6))}
            placeholder="ABC234"
            aria-label={t("duels.code")}
            autoCapitalize="characters"
          />
          <button className="btn btn-soft !w-auto px-5" disabled={code.trim().length < 4 || busy !== null}>{t("duels.join")}</button>
        </form>
        <button type="button" className="btn btn-soft" onClick={() => go("random", "/duels/random", {})} disabled={busy !== null}>
          🎲 {t("duels.random")}
        </button>
      </section>

      {list && list.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="label">{t("duels.mine")}</h2>
          {list.map((d) => (
            <Link key={d.id} href={`/duels/${d.id}`} className="option">
              <span className="text-3xl" aria-hidden="true">{SUBJECT_ICON[d.subject ?? ""] ?? "⚔️"}</span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate">{d.topic}</span>
                <span className="text-sm font-bold text-muted">
                  {d.opponent ? `vs ${d.opponent} · ` : ""}{statusText(d, t)}
                </span>
              </span>
              <span className="text-2xl text-muted" aria-hidden="true">›</span>
            </Link>
          ))}
        </section>
      )}
    </Page>
  );
}

export default function DuelsPage() {
  return (
    <RequireStudent>
      <Duels />
    </RequireStudent>
  );
}
