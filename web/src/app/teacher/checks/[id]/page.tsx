"use client";

/* Academic Copilot: очередь проверки пакета. ИИ предлагает — учитель решает:
   ≥90% уверенности — подтверждение в 1 клик, 70–89% — после открытия работы,
   ниже — только с оценкой учителя. */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { LevelBadge, MARK_COLORS, StatusBadge } from "@/components/checks";
import { RequireTeacher } from "@/components/RequireTeacher";
import { Dots, IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, apiBlob, ApiError, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { CheckItem, CheckItemFull, Journal, ReviewLevel, WorkCheck } from "@/lib/types";

type Filter = "all" | ReviewLevel;

function Viewer({
  check,
  itemId,
  studentName,
  onChanged,
}: {
  check: WorkCheck;
  itemId: number;
  studentName: string;
  onChanged: () => void;
}) {
  const t = useT();
  const [item, setItem] = useState<CheckItemFull | null>(null);
  const [src, setSrc] = useState<string | null>(null);
  const [score, setScore] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [showMarks, setShowMarks] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const base = `/v1/teacher/checks/${check.id}/items/${itemId}`;

  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    setItem(null);
    setSrc(null);
    setError(null);
    // Открытие работы фиксируется на сервере — после него «Проверьте» можно подтверждать
    api<CheckItemFull>(base)
      .then((full) => {
        if (cancelled) return;
        setItem(full);
        setScore(full.teacher_score ?? full.ai_score);
        setComment(full.teacher_comment ?? full.ai_comment ?? "");
        onChanged();
      })
      .catch((e) => !cancelled && setError(errorCode(e)));
    apiBlob(`${base}/file`)
      .then((blob) => {
        if (cancelled) return;
        url = URL.createObjectURL(blob);
        setSrc(url);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
    // onChanged намеренно не в зависимостях: перечитываем только при смене работы
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base]);

  if (error) return <Notice tone="error">{t(`errors.${error}`)}</Notice>;
  if (!item) return <div className="card grid min-h-[20rem] place-items-center"><Dots /></div>;

  const confirmed = item.confirmed_at !== null;
  const marks = item.teacher_marks ?? item.ai_marks;

  /** Сохранить правки учителя. Оценку отправляем, если она отличается от ИИ
   *  или работа требует ручной оценки (<70% уверенности). */
  const persist = async () => {
    const body: Record<string, unknown> = { comment };
    if (score !== null && (score !== item.ai_score || item.level === "manual")) body.score = score;
    const updated = await api<CheckItemFull>(base, { method: "PATCH", json: body });
    setItem(updated);
    return updated;
  };

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await persist();
      onChanged();
    } catch (e) {
      setError(errorCode(e));
    } finally {
      setBusy(false);
    }
  };

  // Подтверждение — только после успешного сохранения правок
  const confirmOne = async () => {
    setBusy(true);
    setError(null);
    try {
      await persist();
      await api(`/v1/teacher/checks/${check.id}/confirm`, { method: "POST", json: { item_ids: [item.id] } });
      setItem({ ...item, confirmed_at: new Date().toISOString(), status: "confirmed" });
      onChanged();
    } catch (e) {
      const blocker = e instanceof ApiError ? (e.detail.blockers as Record<string, string> | undefined)?.[String(item.id)] : undefined;
      setError(blocker ? `blocker_${blocker}` : errorCode(e));
    } finally {
      setBusy(false);
    }
  };

  const scores = Array.from({ length: check.max_score + 1 }, (_, i) => i);

  return (
    <div className="card flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-lg font-black">{studentName}</div>
          <div className="truncate text-sm font-bold text-muted">{item.file_name}</div>
        </div>
        <LevelBadge level={item.level} confidence={item.confidence} />
      </div>

      {item.mime === "application/pdf" ? (
        src && (
          <a className="btn btn-soft" href={src} target="_blank" rel="noreferrer">
            📄 {t("checks.open_pdf")}
          </a>
        )
      ) : (
        <div className="relative overflow-hidden rounded-2xl border-[length:var(--border-w)] border-line bg-soft">
          {src ? <img src={src} alt={item.file_name} className="block w-full" /> : <div className="grid h-64 place-items-center"><Dots /></div>}
          {src && showMarks &&
            marks.map((m, i) => (
              <span
                key={i}
                className="absolute rounded-md border-[3px]"
                style={{
                  left: `${m.box[0] * 100}%`,
                  top: `${m.box[1] * 100}%`,
                  width: `${m.box[2] * 100}%`,
                  height: `${m.box[3] * 100}%`,
                  borderColor: MARK_COLORS[m.type] ?? MARK_COLORS.other,
                  background: `${MARK_COLORS[m.type] ?? MARK_COLORS.other}22`,
                }}
                title={m.note}
              >
                <span className="absolute -top-3 left-1 grid h-6 w-6 place-items-center rounded-full bg-white text-xs font-black shadow" style={{ color: MARK_COLORS[m.type] }}>
                  {i + 1}
                </span>
              </span>
            ))}
        </div>
      )}

      {marks.length > 0 && (
        <div className="flex flex-col gap-2">
          <label className="flex items-center gap-2 text-sm font-bold">
            <input type="checkbox" checked={showMarks} onChange={(e) => setShowMarks(e.target.checked)} className="h-4 w-4" />
            {t("checks.show_marks")}
          </label>
          <ol className="flex flex-col gap-1.5">
            {marks.map((m, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-black text-white" style={{ background: MARK_COLORS[m.type] ?? MARK_COLORS.other }}>
                  {i + 1}
                </span>
                <span>
                  <b>{t(`checks.mark.${m.type}`)}:</b> {m.note}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {item.recognized_text && (
        <details className="rounded-2xl bg-soft px-4 py-3 text-sm">
          <summary className="cursor-pointer font-extrabold">{t("checks.recognized")}</summary>
          <pre className="mt-2 whitespace-pre-wrap font-mono text-sm">{item.recognized_text}</pre>
        </details>
      )}
      {item.error && <Notice tone="error">{t("checks.ai_failed")}</Notice>}

      <div>
        <div className="label">
          {t("checks.score")} {item.ai_score !== null && <span className="normal-case">· {t("checks.ai_suggests", { n: item.ai_score, max: check.max_score })}</span>}
        </div>
        {check.max_score <= 10 ? (
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={t("checks.score")}>
            {scores.map((s) => (
              <button
                key={s}
                type="button"
                role="radio"
                aria-checked={score === s}
                disabled={confirmed}
                onClick={() => setScore(s)}
                className={`h-11 min-w-[2.75rem] rounded-xl border-[length:var(--border-w)] px-3 text-lg font-black transition ${
                  score === s ? "border-primary bg-primary text-on-primary" : "border-line bg-surface"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        ) : (
          <input className="field" type="number" min={0} max={check.max_score} value={score ?? ""} disabled={confirmed} onChange={(e) => setScore(e.target.value === "" ? null : Number(e.target.value))} />
        )}
      </div>
      <label>
        <span className="label">{t("checks.comment")}</span>
        <textarea className="field min-h-[4.5rem]" value={comment} disabled={confirmed} onChange={(e) => setComment(e.target.value)} maxLength={2000} />
      </label>
      {item.neatness !== null && (
        <p className="text-sm font-bold text-muted">
          ✍️ {t("checks.neatness")}: {item.neatness}%
        </p>
      )}

      {error && <Notice tone="error">{t(error.startsWith("blocker_") ? `checks.${error}` : `errors.${error}`)}</Notice>}
      {confirmed ? (
        <Notice>✅ {t("checks.confirmed_note")}</Notice>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <button className="btn btn-soft" onClick={save} disabled={busy}>
            {t("checks.save")}
          </button>
          <button className="btn btn-primary" onClick={confirmOne} disabled={busy || (item.level === "manual" && score === null)}>
            {busy ? <Dots /> : `✓ ${t("checks.confirm_one")}`}
          </button>
        </div>
      )}
    </div>
  );
}

function CheckView({ id }: { id: number }) {
  const t = useT();
  const [check, setCheck] = useState<WorkCheck | null>(null);
  const [names, setNames] = useState<Record<number, string>>({});
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api<WorkCheck>(`/v1/teacher/checks/${id}`)
      .then(setCheck)
      .catch((e) => setError(errorCode(e)));
  }, [id]);

  useEffect(() => {
    load();
    api<Journal>("/journal?limit=1")
      .then((j) => setNames(Object.fromEntries(j.students.map((s) => [s.id, s.name]))))
      .catch(() => undefined);
  }, [load]);

  const processing = check?.status === "queued" || check?.status === "processing";
  useEffect(() => {
    if (!processing) return;
    const timer = window.setInterval(load, 3000);
    return () => window.clearInterval(timer);
  }, [processing, load]);

  const items = useMemo(() => check?.items ?? [], [check]);
  const shown = filter === "all" ? items : items.filter((i) => i.level === filter);
  const ready = items.filter((i) => !i.confirmed_at && i.blocker === null && i.status !== "queued" && i.status !== "processing");
  const done = items.filter((i) => !["queued", "processing"].includes(i.status)).length;
  const count = (l: ReviewLevel) => items.filter((i) => i.level === l).length;
  const nameOf = (item: CheckItem) => (item.student_id ? names[item.student_id] ?? `#${item.student_id}` : t("checks.student_unknown"));

  const confirmReady = async () => {
    setBusy(true);
    setError(null);
    try {
      setCheck(await api<WorkCheck>(`/v1/teacher/checks/${id}/confirm`, { method: "POST", json: { item_ids: ready.map((i) => i.id) } }));
    } catch (e) {
      setError(errorCode(e));
      load();
    } finally {
      setBusy(false);
    }
  };

  if (!check && !error) return <Splash />;

  return (
    <Page className="gap-5 lg:max-w-6xl">
      <header className="flex items-center gap-3">
        <IconButton href="/teacher/checks" label={t("profile.back")}>‹</IconButton>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-black">{check?.title ?? "…"}</h1>
          {check && (
            <p className="text-sm font-bold text-muted">
              {t("checks.progress", { done, total: items.length })} · {t("checks.max", { max: check.max_score })}
            </p>
          )}
        </div>
        {check && <StatusBadge status={check.status} />}
      </header>
      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      {check && (
        <>
          {processing && (
            <div className="card flex items-center gap-3">
              <Dots />
              <span className="font-bold">{t("checks.processing", { done, total: items.length })}</span>
            </div>
          )}
          <Notice>{t("checks.ai_is_helper")}</Notice>

          <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label={t("checks.filter")}>
            {(["all", "one_click", "review", "manual"] as Filter[]).map((f) => (
              <button key={f} className="chip" aria-pressed={filter === f} onClick={() => setFilter(f)}>
                {f === "all" ? `${t("checks.all")} · ${items.length}` : `${t(`checks.level.${f}`)} · ${count(f)}`}
              </button>
            ))}
            <button className="btn btn-primary !min-h-[2.75rem] lg:ml-auto" disabled={busy || ready.length === 0} onClick={confirmReady}>
              {busy ? <Dots /> : `✓ ${t("checks.confirm_ready", { n: ready.length })}`}
            </button>
          </div>

          <div className="grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <ul className="flex flex-col gap-2">
              {shown.map((item) => (
                <li key={item.id}>
                  <button
                    onClick={() => setSelected(item.id)}
                    aria-pressed={selected === item.id}
                    className={`option w-full flex-col !items-stretch gap-1.5 ${selected === item.id ? "!border-primary" : ""}`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="min-w-0 truncate">{nameOf(item)}</span>
                      {item.confirmed_at ? (
                        <span className="text-sm font-black text-good">✓ {item.final_score}/{check.max_score}</span>
                      ) : item.status === "queued" || item.status === "processing" ? (
                        <Dots />
                      ) : (
                        <LevelBadge level={item.level} confidence={item.confidence} />
                      )}
                    </span>
                    <span className="flex items-center justify-between gap-2 text-sm font-semibold text-muted">
                      <span className="truncate">{item.file_name}</span>
                      {!item.confirmed_at && item.final_score !== null && (
                        <span>
                          {item.final_score}/{check.max_score}
                        </span>
                      )}
                    </span>
                    {!item.confirmed_at && item.blocker && item.blocker !== "not_ready" && (
                      <span className="text-xs font-extrabold text-bad">{t(`checks.blocker_${item.blocker}`)}</span>
                    )}
                  </button>
                </li>
              ))}
              {shown.length === 0 && <Notice>{t("checks.nothing_here")}</Notice>}
            </ul>
            <div className="lg:sticky lg:top-4 lg:self-start">
              {selected !== null && items.some((i) => i.id === selected) ? (
                <Viewer
                  check={check}
                  itemId={selected}
                  studentName={nameOf(items.find((i) => i.id === selected)!)}
                  onChanged={load}
                />
              ) : (
                <div className="card text-center font-bold text-muted">{t("checks.pick")}</div>
              )}
            </div>
          </div>
        </>
      )}
    </Page>
  );
}

export default function CheckPage() {
  const params = useParams<{ id: string }>();
  return (
    <RequireTeacher>
      <CheckView id={Number(params.id)} />
    </RequireTeacher>
  );
}
