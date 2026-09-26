"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LanguagePicker } from "@/components/LanguagePicker";
import { Mascot } from "@/components/Mascot";
import { IconButton, Notice, Page, Splash } from "@/components/ui";
import { errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { homePath } from "@/lib/cabinet";
import { useT } from "@/lib/i18n";
import {
  canInstall,
  disablePush,
  enablePush,
  iosInstallHint,
  isStandalone,
  onInstallChange,
  promptInstall,
  pushState,
  testPush,
  type PushState,
} from "@/lib/pwa";
import { THEMES, type Theme, type UserSettings } from "@/lib/types";

// Превью темы — фиксированные цвета, чтобы было видно, как она выглядит
const SWATCH: Record<Theme, { bg: string; primary: string; accent: string; icon: string }> = {
  sun: { bg: "#f5ecde", primary: "#6f4226", accent: "#00d6c4", icon: "☕" }, // «Капучино»
  ocean: { bg: "#ecf5ff", primary: "#2a6ce2", accent: "#1ec4e8", icon: "🌊" },
  forest: { bg: "#eef8ee", primary: "#20864a", accent: "#a0d250", icon: "🌲" },
  berry: { bg: "#fcf0fa", primary: "#983ac4", accent: "#ff6ea6", icon: "🍇" },
};

function Toggle({
  checked,
  onChange,
  title,
  hint,
  icon,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  title: string;
  hint: string;
  icon: string;
}) {
  return (
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)} className="option">
      <span className="text-2xl" aria-hidden="true">{icon}</span>
      <span className="flex flex-1 flex-col">
        <span>{title}</span>
        <span className="text-sm font-semibold text-muted">{hint}</span>
      </span>
      <span
        aria-hidden="true"
        className={`relative h-8 w-14 shrink-0 rounded-full transition-colors ${checked ? "bg-primary" : "bg-line"}`}
      >
        <span
          className={`absolute top-1 h-6 w-6 rounded-full bg-surface shadow transition-all ${checked ? "left-7" : "left-1"}`}
        />
      </span>
    </button>
  );
}

/** Установка на главный экран и Web Push — замена Telegram-уведомлений. */
function AppSection({ adult, miniApp }: { adult: boolean; miniApp: boolean }) {
  const t = useT();
  const [push, setPush] = useState<PushState | null>(null);
  const [installable, setInstallable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    pushState().then(setPush).catch(() => setPush("unsupported"));
    const sync = () => setInstallable(canInstall());
    sync();
    return onInstallChange(sync);
  }, []);

  if (push === null) return null;
  if (miniApp) {
    return <p className="text-center text-sm font-semibold text-muted">🔔 {t("pwa.push_telegram")}</p>;
  }

  const toggle = async (value: boolean) => {
    setBusy(true);
    setNote(null);
    try {
      if (value) setPush(await enablePush());
      else {
        await disablePush();
        setPush("off");
      }
    } catch (e) {
      setNote(t(`errors.${errorCode(e)}`));
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setNote(null);
    try {
      setNote(t("pwa.test_sent", { n: await testPush() }));
    } catch (e) {
      setNote(t(`errors.${errorCode(e)}`));
    }
  };

  return (
    <section className="flex flex-col gap-3">
      <h2 className="label">📲 {t("pwa.section")}</h2>
      {installable && (
        <button type="button" className="option" onClick={() => promptInstall()}>
          <span className="text-2xl" aria-hidden="true">⬇️</span>
          <span className="flex flex-1 flex-col text-left">
            <span>{t("pwa.install")}</span>
            <span className="text-sm font-semibold text-muted">{t("pwa.install_hint")}</span>
          </span>
        </button>
      )}
      {!installable && iosInstallHint() && <Notice tone="info">{t("pwa.ios_hint")}</Notice>}
      {!installable && isStandalone() && <p className="text-sm font-bold text-good">{t("pwa.installed")}</p>}

      {(push === "on" || push === "off") && (
        <div className={busy ? "pointer-events-none opacity-60" : ""}>
          <Toggle
            icon="🔔"
            title={t("pwa.push")}
            hint={t(adult ? "pwa.push_hint_adult" : "pwa.push_hint_student")}
            checked={push === "on"}
            onChange={toggle}
          />
        </div>
      )}
      {push === "on" && (
        <button type="button" className="btn btn-soft" onClick={test}>
          🧪 {t("pwa.test")}
        </button>
      )}
      {push === "denied" && <Notice tone="error">{t("pwa.push_denied")}</Notice>}
      {push === "disabled" && <p className="text-sm font-semibold text-muted">{t("pwa.push_disabled")}</p>}
      {push === "unsupported" && <p className="text-sm font-semibold text-muted">{t("pwa.push_unsupported")}</p>}
      {note && (
        <p className="text-sm font-bold text-muted" role="status">
          {note}
        </p>
      )}
    </section>
  );
}

export default function ProfilePage() {
  const t = useT();
  const router = useRouter();
  const { status, me, isMiniApp, saveSettings, logoutEverywhere } = useAuth();
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "guest") router.replace("/login?next=/profile");
  }, [status, router]);

  if (status !== "authed" || !me) return <Splash />;

  const change = async (patch: Partial<UserSettings>) => {
    setError(null);
    try {
      await saveSettings(patch);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (e) {
      setError(errorCode(e));
    }
  };

  return (
    <Page className="gap-5">
      <header className="flex items-center gap-3">
        <IconButton href={homePath(me.role)} label={t("profile.back")}>
          ‹
        </IconButton>
        <h1 className="flex-1 text-2xl font-black">{t("profile.title")}</h1>
        <span className={`text-sm font-extrabold text-good transition-opacity ${saved ? "opacity-100" : "opacity-0"}`} role="status">
          {t("profile.saved")}
        </span>
      </header>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      <section className="card flex items-center gap-4">
        <Mascot size={72} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-2xl font-black">{me.name}</div>
          {me.student && (
            <div className="font-bold text-muted">
              ⚡ {t("home.level", { level: me.student.level })} · ⭐ {me.student.points}
            </div>
          )}
        </div>
      </section>

      {(me.login || me.student) && (
        <section className="card grid gap-3">
          {me.login && (
            <div>
              <div className="label">{t("profile.login")}</div>
              <div className="font-mono text-2xl font-black">{me.login}</div>
            </div>
          )}
          {me.student && (
            <div>
              <div className="label">{t("profile.family_code")}</div>
              <div className="font-mono text-3xl font-black tracking-[0.2em] text-primary">{me.student.family_code}</div>
              <p className="text-sm font-semibold text-muted">{t("profile.family_code_hint")}</p>
            </div>
          )}
        </section>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="label">🎨 {t("profile.look")}</h2>
        <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label={t("profile.look")}>
          {THEMES.map((theme) => {
            const sw = SWATCH[theme];
            const active = me.settings.theme === theme;
            return (
              <button
                key={theme}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => change({ theme })}
                className={`flex flex-col items-center gap-2 rounded-3xl p-4 font-extrabold transition-transform active:scale-95 ${
                  active ? "ring-4 ring-primary ring-offset-2 ring-offset-bg" : ""
                }`}
                style={{ background: sw.bg, color: "#2b263a", border: `3px solid ${sw.primary}` }}
              >
                <span className="flex gap-1.5" aria-hidden="true">
                  <span className="h-8 w-8 rounded-full" style={{ background: sw.primary }} />
                  <span className="h-8 w-8 rounded-full" style={{ background: sw.accent }} />
                </span>
                <span>
                  {sw.icon} {t(`profile.themes.${theme}`)}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="label">👓 {t("profile.a11y")}</h2>
        <Toggle
          icon="🌗"
          title={t("profile.contrast")}
          hint={t("profile.contrast_hint")}
          checked={me.settings.high_contrast}
          onChange={(high_contrast) => change({ high_contrast })}
        />
        <Toggle
          icon="🔤"
          title={t("profile.dyslexia")}
          hint={t("profile.dyslexia_hint")}
          checked={me.settings.dyslexia_font}
          onChange={(dyslexia_font) => change({ dyslexia_font })}
        />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="label">🌐 {t("profile.language")}</h2>
        <LanguagePicker />
        <p className="text-sm font-semibold text-muted">{t("profile.language_hint")}</p>
      </section>

      <AppSection adult={me.role === "parent" || me.role === "teacher"} miniApp={isMiniApp} />

      {(me.role === "student" || me.role === "parent") && (
        <a href="/family" className="btn btn-soft">
          👨‍👩‍👧 {t("family.title")}
        </a>
      )}

      <a href="/privacy" className="text-center text-sm font-bold text-muted underline underline-offset-4">
        📄 {t("login.privacy")}
      </a>

      {!isMiniApp && (
        <button
          className="btn btn-soft mt-auto"
          onClick={async () => {
            await disablePush(); // на общем устройстве чужие уведомления не нужны
            await logoutEverywhere();
            router.replace("/login");
          }}
        >
          🚪 {t("profile.logout")}
        </button>
      )}
    </Page>
  );
}
