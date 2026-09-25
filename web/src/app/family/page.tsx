"use client";

/* Семья: кто в ней, приглашение по коду или QR (24 часа) и вступление по коду.
   Все взрослые семьи видят всех её детей. */
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Dots, IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";

type Family = {
  family_id: number | null;
  members: { user_id: number; name: string; role: string; phone: string | null; me: boolean }[];
  limits: { adults: number; children: number };
};
type Invite = { code: string; expires_at: string; join_url: string; qr_svg: string };

function FamilyView() {
  const t = useT();
  const { me } = useAuth();
  const [family, setFamily] = useState<Family | null>(null);
  const [invite, setInvite] = useState<Invite | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [joined, setJoined] = useState(false);

  const load = useCallback(() => {
    api<Family>("/v1/family").then(setFamily).catch((e) => setError(errorCode(e)));
  }, []);

  useEffect(() => {
    load();
    const fromLink = new URLSearchParams(window.location.search).get("code");
    if (fromLink && /^\d{6}$/.test(fromLink)) setCode(fromLink); // пришли по QR-коду
  }, [load]);

  const makeInvite = async () => {
    setBusy(true);
    setError(null);
    try {
      setInvite(await api<Invite>("/v1/family/invites", { method: "POST" }));
      load();
    } catch (e) {
      setError(errorCode(e));
    } finally {
      setBusy(false);
    }
  };

  const join = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/v1/family/join", { method: "POST", json: { code } });
      setJoined(true);
      setCode("");
      load();
    } catch (err) {
      setError(errorCode(err));
    } finally {
      setBusy(false);
    }
  };

  if (!family && !error) return <Splash />;
  const back = me?.role === "student" ? "/" : "/journal";

  return (
    <Page className="gap-5">
      <header className="flex items-center gap-3">
        <IconButton href={back} label={t("profile.back")}>‹</IconButton>
        <h1 className="flex-1 text-2xl font-black">👨‍👩‍👧 {t("family.title")}</h1>
      </header>
      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}
      {joined && <Notice>✅ {t("family.joined")}</Notice>}

      {family && family.members.length > 0 && (
        <section className="card flex flex-col gap-2">
          <h2 className="label">{t("family.members")}</h2>
          <ul className="flex flex-col gap-2">
            {family.members.map((m) => (
              <li key={m.user_id} className="flex items-center gap-3 rounded-2xl bg-soft px-3 py-2.5">
                <span className="text-2xl" aria-hidden="true">{m.role === "student" ? "🎒" : "🧑"}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-extrabold">
                    {m.name} {m.me && <span className="text-sm text-muted">({t("family.you")})</span>}
                  </span>
                  <span className="block text-sm font-semibold text-muted">
                    {t(`family.role.${m.role}`)}
                    {m.phone ? ` · ${m.phone}` : ""}
                  </span>
                </span>
              </li>
            ))}
          </ul>
          <p className="text-sm font-semibold text-muted">{t("family.limits", { adults: family.limits.adults, children: family.limits.children })}</p>
        </section>
      )}

      <section className="card flex flex-col gap-3">
        <h2 className="text-xl font-black">➕ {t("family.invite")}</h2>
        <p className="font-semibold text-muted">{me?.role === "student" ? t("family.invite_hint_child") : t("family.invite_hint_adult")}</p>
        {invite ? (
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="rounded-2xl bg-white p-3" aria-label={t("family.qr")} dangerouslySetInnerHTML={{ __html: invite.qr_svg }} />
            <div className="font-mono text-4xl font-black tracking-[0.3em] text-primary">{invite.code}</div>
            <p className="text-sm font-semibold text-muted">
              {t("family.expires", { time: new Date(invite.expires_at).toLocaleString(t.lang === "en" ? "en-GB" : t.lang === "uz" ? "uz-Latn-UZ" : "ru-RU") })}
            </p>
          </div>
        ) : (
          <button className="btn btn-primary" onClick={makeInvite} disabled={busy}>
            {busy ? <Dots /> : t("family.make_invite")}
          </button>
        )}
      </section>

      <form onSubmit={join} className="card flex flex-col gap-3">
        <h2 className="text-xl font-black">🔑 {t("family.join")}</h2>
        <p className="font-semibold text-muted">{t("family.join_hint")}</p>
        <input
          className="field text-center text-3xl font-black tracking-[0.4em]"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
          inputMode="numeric"
          placeholder="••••••"
          aria-label={t("family.code")}
        />
        <button className="btn btn-soft" disabled={busy || code.length !== 6}>
          {t("family.join_btn")}
        </button>
      </form>
    </Page>
  );
}

export default function FamilyPage() {
  const router = useRouter();
  const { status } = useAuth();
  useEffect(() => {
    if (status === "guest") router.replace(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
  }, [status, router]);
  if (status !== "authed") return <Splash />;
  return <FamilyView />;
}
