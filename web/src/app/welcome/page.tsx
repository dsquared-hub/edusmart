"use client";

/* Первый вход по номеру телефона: кто вы — ученик или родитель, имя, класс. */
import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Mascot } from "@/components/Mascot";
import { Dots, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";

export default function WelcomePage() {
  const t = useT();
  const router = useRouter();
  const { status, me, refresh } = useAuth();
  const [role, setRole] = useState<"student" | "parent">("student");
  const [name, setName] = useState("");
  const [grade, setGrade] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "guest") router.replace("/login");
    else if (status === "authed" && me?.role) router.replace("/");
  }, [status, me, router]);

  if (status !== "authed" || me?.role) return <Splash />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/v1/me/role", { method: "POST", json: { role, name: name.trim(), grade: role === "student" ? grade : null } });
      await refresh();
      router.replace(role === "parent" ? "/family" : "/");
    } catch (err) {
      setError(errorCode(err));
      setBusy(false);
    }
  };

  return (
    <Page className="justify-center gap-5">
      <header className="flex flex-col items-center gap-3 text-center">
        <Mascot size={110} className="anim-bob" />
        <h1 className="text-3xl font-black">{t("welcome.title")}</h1>
      </header>
      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}
      <form onSubmit={submit} className="card flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label={t("welcome.who")}>
          {(["student", "parent"] as const).map((r) => (
            <button
              key={r}
              type="button"
              role="radio"
              aria-checked={role === r}
              onClick={() => setRole(r)}
              className={`option flex-col !items-center gap-1 text-center ${role === r ? "!border-primary" : ""}`}
            >
              <span className="text-3xl">{r === "student" ? "🎒" : "👨‍👩‍👧"}</span>
              <span>{t(`welcome.${r}`)}</span>
            </button>
          ))}
        </div>
        <label>
          <span className="label">{t("welcome.name")}</span>
          <input className="field" value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} autoComplete="given-name" />
        </label>
        {role === "student" && (
          <label>
            <span className="label">{t("learn.grade")}</span>
            <select className="field" value={grade} onChange={(e) => setGrade(Number(e.target.value))}>
              {Array.from({ length: 11 }, (_, i) => i + 1).map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </label>
        )}
        <button className="btn btn-primary" disabled={busy || !name.trim()}>
          {busy ? <Dots /> : t("welcome.go")}
        </button>
      </form>
    </Page>
  );
}
