"use client";

/* Вход на сайт — только по логину и коду. Регистрация — в Telegram-боте: бот выдаёт
   логин и код родителю или учителю после регистрации, а ребёнку — когда взрослый его регистрирует. */
import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { LanguagePicker } from "@/components/LanguagePicker";
import { ThemeToggle } from "@/components/AppShell";
import { RhinoHero } from "@/components/RhinoHero";
import { Notice, Splash } from "@/components/ui";
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
    <main className="mx-auto grid min-h-[100dvh] w-full max-w-app grid-cols-[minmax(0,1fr)] items-center gap-6 px-4 py-6 lg:max-w-6xl lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:gap-12 lg:px-10">
      {/* Сцена: логотип, 3D-носорог с анимацией, что умеет платформа */}
      <section className="flex flex-col items-center gap-4 text-center lg:gap-6">
        <div className="flex w-full items-center justify-between">
          <span className="logo h-14 w-20 lg:h-20 lg:w-28" role="img" aria-label={t("app.name")} />
          <ThemeToggle compact />
        </div>
        <RhinoHero size={150} label={t("app.name")} />
        <h1 className="anim-rise text-4xl font-black lg:text-5xl">
          <span className="hl-neon">{t("login.title")}</span>
        </h1>
        <p className="anim-rise text-lg font-bold text-muted">{t("login.subtitle")}</p>
        <ul className="stagger hidden flex-col gap-2 text-left lg:flex">
          {(["hero_1", "hero_2", "hero_3"] as const).map((key) => (
            <li key={key} className="chip w-fit">
              {t(`login.${key}`)}
            </li>
          ))}
        </ul>
      </section>

      <div className="stagger flex flex-col gap-4">
        <LanguagePicker compact />
        {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

        <form onSubmit={onSubmit} className="card flex flex-col gap-4">
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
          <section className="flex flex-col gap-2" aria-labelledby="register-title">
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
      </div>
    </main>
  );
}
