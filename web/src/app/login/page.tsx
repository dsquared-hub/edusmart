"use client";

/* Вход на сайт — только по логину и коду. Регистрация — в Telegram-боте: бот выдаёт
   логин и код родителю или учителю после регистрации, а ребёнку — когда взрослый его регистрирует. */
import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { LanguagePicker } from "@/components/LanguagePicker";
import { Mascot3D } from "@/components/Mascot3D";
import { Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { homePath } from "@/lib/cabinet";
import { useT } from "@/lib/i18n";
import type { Me, PublicConfig } from "@/lib/types";

/** Куда после входа: ?next= (только внутренние пути — без открытых редиректов), иначе
 *  по роли: ученик — сразу «Объясни тему», родитель и учитель — свой кабинет. */
function nextPath(me: Me | null): string {
  const next = new URLSearchParams(window.location.search).get("next");
  if (next && next.startsWith("/") && !next.startsWith("//") && next !== "/") return next;
  if (me?.role === "parent" || me?.role === "teacher") return homePath(me.role);
  if (me?.role === "student" && (me.student?.consent_confirmed ?? true)) return "/learn";
  return "/";
}

export default function LoginPage() {
  const t = useT();
  const router = useRouter();
  const { status, me, loginCode } = useAuth();
  const [login, setLogin] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bot, setBot] = useState<string | null>(null);

  useEffect(() => {
    api<PublicConfig>("/config")
      .then((c) => setBot(c.bot_username || null))
      .catch(() => setBot(null));
  }, []);

  useEffect(() => {
    if (status === "authed") router.replace(nextPath(me));
  }, [status, me, router]);

  if (status === "loading" || status === "authed") return <Splash />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await loginCode(login.trim().toLowerCase(), code.trim());
    } catch (err) {
      setError(errorCode(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page className="justify-center gap-6">
      <LanguagePicker compact />
      <header className="flex flex-col items-center gap-3 text-center anim-rise">
        <Mascot3D size={150} label={t("app.name")} />
        <h1 className="text-4xl font-black">
          <span className="hl-neon">{t("login.title")}</span>
        </h1>
        <p className="text-lg font-bold text-muted">{t("login.subtitle")}</p>
      </header>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      <form onSubmit={onSubmit} className="card flex flex-col gap-4 anim-rise">
        <h2 className="text-center text-xl font-black">🔑 {t("login.with_code")}</h2>
        <label>
          <span className="label">{t("login.login_label")}</span>
          <input
            className="field"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            placeholder={t("login.login_placeholder")}
            autoCapitalize="none"
            autoCorrect="off"
            autoComplete="username"
            spellCheck={false}
            required
            minLength={3}
          />
        </label>
        <label>
          <span className="label">{t("login.code_label")}</span>
          <input
            className="field text-center text-2xl font-black tracking-[0.4em] placeholder:text-lg placeholder:font-bold placeholder:tracking-normal"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder={t("login.code_placeholder")}
            inputMode="numeric"
            autoComplete="one-time-code"
            required
            minLength={6}
          />
        </label>
        <button className="btn btn-primary" disabled={busy || login.trim().length < 3 || code.length < 6}>
          {t("login.submit")}
        </button>
        <p className="text-center text-sm font-semibold text-muted">{t("login.code_hint")}</p>
      </form>

      {bot && (
        <section className="flex flex-col gap-2 anim-rise" aria-labelledby="register-title">
          <h2 id="register-title" className="text-center text-sm font-extrabold text-muted">
            {t("login.register_title")}
          </h2>
          <div className="grid grid-cols-2 gap-2">
            {(["parent", "teacher"] as const).map((role) => (
              <a
                key={role}
                className="btn btn-soft"
                href={`https://t.me/${bot}?start=${role}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                {t(`login.register_${role}`)}
              </a>
            ))}
          </div>
        </section>
      )}
    </Page>
  );
}
