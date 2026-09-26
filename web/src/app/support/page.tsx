"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Mascot } from "@/components/Mascot";
import { Dots, IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { homePath } from "@/lib/cabinet";
import { useT } from "@/lib/i18n";
import type { SupportTicket } from "@/lib/types";

const MAX_TEXT = 2000;
const REFRESH_MS = 30_000; // ответ появится сам, без перезагрузки страницы
const LOCALE: Record<string, string> = { ru: "ru-RU", uz: "uz-Latn-UZ", en: "en-GB" };

function TicketCard({ ticket }: { ticket: SupportTicket }) {
  const t = useT();
  const when = new Intl.DateTimeFormat(LOCALE[t.lang], {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(ticket.created_at));
  const answered = ticket.status === "answered";
  return (
    <li className="card flex flex-col gap-3 !p-4">
      <div className="flex items-center justify-between gap-2 text-sm font-extrabold">
        <span className="text-muted">
          #{ticket.id} · {when}
        </span>
        <span className={`rounded-full px-3 py-1 ${answered ? "bg-good/15 text-good" : "bg-accent/20"}`}>
          {answered ? `✅ ${t("support.answered")}` : `⏳ ${t("support.waiting")}`}
        </span>
      </div>
      <p className="whitespace-pre-wrap font-semibold [overflow-wrap:anywhere]">{ticket.text}</p>
      {ticket.reply && (
        <div className="rounded-2xl border-l-4 border-primary bg-soft px-4 py-3">
          <div className="mb-1 text-sm font-extrabold text-muted">💬 {t("support.reply")}</div>
          <p className="whitespace-pre-wrap font-semibold [overflow-wrap:anywhere]">{ticket.reply}</p>
        </div>
      )}
    </li>
  );
}

function SupportView() {
  const t = useT();
  const { me } = useAuth();
  const [tickets, setTickets] = useState<SupportTicket[] | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await api<{ tickets: SupportTicket[] }>("/support");
      setTickets(r.tickets);
    } catch (e) {
      setError(errorCode(e));
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSent(null);
    try {
      const ticket = await api<SupportTicket>("/support", { method: "POST", json: { text: text.trim() } });
      setTickets((prev) => [ticket, ...(prev ?? [])]);
      setText("");
      setSent(ticket.id);
    } catch (err) {
      setError(errorCode(err));
    } finally {
      setBusy(false);
    }
  };

  if (!tickets && !error) return <Splash />;

  return (
    <Page className="gap-5">
      <header className="flex items-center gap-3">
        <IconButton href={homePath(me?.role)} label={t("profile.back")}>‹</IconButton>
        <h1 className="flex-1 text-2xl font-black">💬 {t("support.title")}</h1>
      </header>

      <section className="card flex items-center gap-4">
        <Mascot size={64} />
        <p className="flex-1 font-semibold text-muted">{t("support.intro")}</p>
      </section>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}
      {sent !== null && <Notice>{t("support.sent", { id: sent })}</Notice>}

      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <label>
          <span className="label">{t("support.question")}</span>
          <textarea
            className="field min-h-[8rem] resize-y"
            value={text}
            onChange={(e) => setText(e.target.value.slice(0, MAX_TEXT))}
            placeholder={t("support.placeholder")}
            maxLength={MAX_TEXT}
            required
          />
        </label>
        <div className="text-right text-sm font-bold text-muted">
          {text.length} / {MAX_TEXT}
        </div>
        <button className="btn btn-primary" disabled={busy || !text.trim()}>
          {busy ? <Dots /> : <>✉️ {t("support.send")}</>}
        </button>
      </form>

      {tickets && tickets.length > 0 && (
        <section className="flex flex-col gap-3" aria-labelledby="support-history">
          <h2 id="support-history" className="label">
            🗂 {t("support.history")}
          </h2>
          <ul className="flex flex-col gap-3">
            {tickets.map((ticket) => (
              <TicketCard key={ticket.id} ticket={ticket} />
            ))}
          </ul>
        </section>
      )}
    </Page>
  );
}

export default function SupportPage() {
  const t = useT();
  const router = useRouter();
  const { status, me } = useAuth();

  useEffect(() => {
    if (status === "guest") router.replace("/login?next=/support");
  }, [status, router]);

  if (status !== "authed" || !me) return <Splash />;

  if (me.role !== "parent" && me.role !== "teacher") {
    return (
      <Page className="justify-center">
        <div className="card flex flex-col items-center gap-4 text-center">
          <Mascot size={96} />
          <h1 className="text-2xl font-black">{t("support.title")}</h1>
          <p className="text-muted">{t("errors.support_only_adults")}</p>
          <a className="btn btn-soft" href="/">
            ‹ {t("profile.back")}
          </a>
        </div>
      </Page>
    );
  }
  return <SupportView />;
}
