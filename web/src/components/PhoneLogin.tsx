"use client";

/* Вход по номеру телефона (+998) с SMS-кодом: номер → 6 цифр кода.
   Новый номер — новый пользователь: после входа он выбирает роль (/welcome). */
import { useEffect, useState, type FormEvent } from "react";
import { Dots } from "@/components/ui";
import { api, ApiError, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";

/** «901234567» → «90 123 45 67» */
function pretty(digits: string) {
  const d = digits.slice(0, 9);
  return [d.slice(0, 2), d.slice(2, 5), d.slice(5, 7), d.slice(7, 9)].filter(Boolean).join(" ");
}

export function PhoneLogin({ onError }: { onError: (code: string | null) => void }) {
  const t = useT();
  const { loginSms } = useAuth();
  const [digits, setDigits] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [wait, setWait] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (wait <= 0) return;
    const id = window.setTimeout(() => setWait((w) => w - 1), 1000);
    return () => window.clearTimeout(id);
  }, [wait]);

  const request = async (e?: FormEvent) => {
    e?.preventDefault();
    setBusy(true);
    onError(null);
    try {
      const r = await api<{ phone: string; resend_after: number }>("/v1/auth/sms/request", {
        method: "POST",
        json: { phone: digits, lang: t.lang },
      });
      setSentTo(r.phone);
      setWait(r.resend_after);
      setCode("");
    } catch (err) {
      onError(errorCode(err));
      if (err instanceof ApiError && typeof err.detail.retry_after === "number") setWait(err.detail.retry_after);
    } finally {
      setBusy(false);
    }
  };

  const verify = async (value: string) => {
    if (!sentTo || value.length !== 6) return;
    setBusy(true);
    onError(null);
    try {
      await loginSms(sentTo, value); // куда вести дальше (выбор роли / назад), решает страница входа
    } catch (err) {
      onError(errorCode(err));
      setCode("");
    } finally {
      setBusy(false);
    }
  };

  if (!sentTo) {
    return (
      <form onSubmit={request} className="flex flex-col gap-3">
        <label>
          <span className="label">{t("phone.label")}</span>
          <span className="field flex items-center gap-2 !p-0 focus-within:border-primary">
            <span className="border-r-[length:var(--border-w)] border-line px-3 py-3 font-black">🇺🇿 +998</span>
            <input
              className="min-w-0 flex-1 bg-transparent py-3 pr-3 text-lg font-bold tracking-wide outline-none"
              value={pretty(digits)}
              onChange={(e) => setDigits(e.target.value.replace(/\D/g, "").slice(0, 9))}
              inputMode="tel"
              autoComplete="tel-national"
              placeholder="90 123 45 67"
              aria-label={t("phone.label")}
            />
          </span>
        </label>
        <button className="btn btn-primary" disabled={busy || digits.length !== 9}>
          {busy ? <Dots /> : t("phone.send")}
        </button>
      </form>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-center font-bold">{t("phone.sent", { phone: sentTo })}</p>
      <input
        className="field text-center text-3xl font-black tracking-[0.5em]"
        value={code}
        onChange={(e) => {
          const v = e.target.value.replace(/\D/g, "").slice(0, 6);
          setCode(v);
          if (v.length === 6) verify(v);
        }}
        inputMode="numeric"
        autoComplete="one-time-code"
        placeholder="••••••"
        aria-label={t("phone.code")}
        autoFocus
      />
      {busy && <Dots />}
      <div className="flex justify-between text-sm font-bold">
        <button type="button" className="text-muted underline underline-offset-4" onClick={() => setSentTo(null)}>
          {t("phone.change")}
        </button>
        <button type="button" className="text-primary underline underline-offset-4 disabled:no-underline disabled:text-muted" disabled={wait > 0 || busy} onClick={() => request()}>
          {wait > 0 ? t("phone.resend_in", { s: wait }) : t("phone.resend")}
        </button>
      </div>
    </div>
  );
}
