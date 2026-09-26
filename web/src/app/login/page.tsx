"use client";

/* Вход на сайт — только по логину и коду. Регистрация — в Telegram-боте: родитель или
   учитель регистрирует ребёнка, и бот выдаёт ему логин и код для входа сюда. */
import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { LanguagePicker } from "@/components/LanguagePicker";
import { Mascot } from "@/components/Mascot";
import { Notice, Page, Splash } from "@/components/ui";
import { errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";

function nextPath(): string {
  const next = new URLSearchParams(window.location.search).get("next");
  // только внутренние пути — без открытых редиректов
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export default function LoginPage() {
  const t = useT();
  const router = useRouter();
  const { status, loginCode } = useAuth();
  const [login, setLogin] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authed") router.replace(nextPath());
  }, [status, router]);

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
        <Mascot size={120} className="anim-bob" />
        <h1 className="text-4xl font-black">{t("login.title")}</h1>
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
    </Page>
  );
}
