"use client";

/* ДТМ-симулятор: выбор двух профильных предметов, старт варианта (90 вопросов, 180 минут),
   продолжение начатого и история результатов. */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RequireStudent } from "@/components/RequireStudent";
import { Thinking } from "@/components/Thinking";
import { IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { DtmOverview, DtmTest } from "@/lib/types";

function Picker({
  label,
  options,
  value,
  disabled,
  onChange,
}: {
  label: string;
  options: DtmOverview["subjects"]["spec"];
  value: string;
  disabled: string;
  onChange: (code: string) => void;
}) {
  return (
    <fieldset>
      <legend className="label">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((s) => (
          <button
            key={s.code}
            type="button"
            className="chip"
            aria-pressed={value === s.code}
            disabled={disabled === s.code}
            onClick={() => onChange(s.code)}
          >
            {s.name}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

function DtmHome() {
  const t = useT();
  const router = useRouter();
  const [data, setData] = useState<DtmOverview | null>(null);
  const [spec1, setSpec1] = useState("math");
  const [spec2, setSpec2] = useState("physics");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<DtmOverview>("/dtm").then(setData).catch((e) => setError(errorCode(e)));
  }, []);

  if (!data && !error) return <Splash />;

  const active = data?.tests.find((x) => x.status === "active");
  const finished = data?.tests.filter((x) => x.status === "finished") ?? [];
  const tooYoung = !!data && data.grade !== null && data.grade < data.subjects.min_grade;

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const test = await api<DtmTest>("/dtm", { method: "POST", json: { spec1, spec2 } });
      router.push(`/dtm/${test.id}`);
    } catch (e) {
      setError(errorCode(e));
      setBusy(false);
    }
  };

  return (
    <Page className="gap-5">
      {busy && <Thinking title={t("dtm.preparing")} />}
      <header className="flex items-center gap-3">
        <IconButton href="/" label={t("profile.back")}>‹</IconButton>
        <h1 className="min-w-0 flex-1 text-2xl font-black leading-tight">🎓 {t("dtm.title")}</h1>
      </header>

      {data && (
        <section className="card flex flex-col gap-2 anim-rise">
          <p className="font-bold">
            {t("dtm.intro", { minutes: data.subjects.minutes, max: data.subjects.max_score })}
          </p>
          <ul className="flex flex-col gap-1 text-sm font-bold text-muted">
            <li>📘 {t("dtm.block_mandatory", { names: data.subjects.mandatory.map((s) => s.name).join(", ") })}</li>
            <li>🥇 {t("dtm.block_spec1")}</li>
            <li>🥈 {t("dtm.block_spec2")}</li>
          </ul>
        </section>
      )}

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}
      {tooYoung && <Notice>{t("dtm.too_young", { grade: data!.subjects.min_grade })}</Notice>}

      {active ? (
        <Link href={`/dtm/${active.id}`} className="btn btn-primary btn-xl flex-col gap-0 py-4 anim-rise">
          <span>▶️ {t("dtm.continue")}</span>
          <span className="text-sm font-bold opacity-80">
            {active.spec1.name} · {active.spec2.name} · {t("dtm.answered", { n: active.answered, total: active.total })}
          </span>
        </Link>
      ) : (
        data &&
        !tooYoung && (
          <section className="card flex flex-col gap-4 anim-rise">
            <Picker label={`🥇 ${t("dtm.spec1")}`} options={data.subjects.spec} value={spec1} disabled={spec2} onChange={setSpec1} />
            <Picker label={`🥈 ${t("dtm.spec2")}`} options={data.subjects.spec} value={spec2} disabled={spec1} onChange={setSpec2} />
            <button type="button" className="btn btn-primary" onClick={start} disabled={busy || spec1 === spec2}>
              🎓 {t("dtm.start", { minutes: data.subjects.minutes })}
            </button>
            <p className="text-center text-xs font-bold text-muted">{t("dtm.first_slow")}</p>
          </section>
        )
      )}

      {finished.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="label">{t("dtm.history")}</h2>
          {finished.map((x) => (
            <Link key={x.id} href={`/dtm/${x.id}`} className="option">
              <span className="text-3xl" aria-hidden="true">📊</span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate">{x.spec1.name} · {x.spec2.name}</span>
                <span className="text-sm font-bold text-muted">
                  {new Date(x.started_at).toLocaleDateString()} · {t("dtm.score", { score: x.score ?? 0, max: x.max_score })}
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

export default function DtmPage() {
  return (
    <RequireStudent>
      <DtmHome />
    </RequireStudent>
  );
}
