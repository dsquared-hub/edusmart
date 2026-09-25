"use client";

/* Редактор материалов урока: план на 45 минут, Stories, контрольная в вариантах, ключ.
   Всё редактируется; DOCX — с сервера, PDF — печатью страницы (печатаются все разделы). */
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { RequireTeacher } from "@/components/RequireTeacher";
import { Dots, IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, apiBlob, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { Material, MaterialContent } from "@/lib/types";

type Tab = "plan" | "stories" | "test" | "key";

function Field({ value, onChange, multiline = false, label }: { value: string; onChange: (v: string) => void; multiline?: boolean; label?: string }) {
  return multiline ? (
    <textarea className="field min-h-[3.5rem] print:border-0 print:p-0" value={value} aria-label={label} onChange={(e) => onChange(e.target.value)} />
  ) : (
    <input className="field print:border-0 print:p-0" value={value} aria-label={label} onChange={(e) => onChange(e.target.value)} />
  );
}

function Editor({ id }: { id: number }) {
  const t = useT();
  const [material, setMaterial] = useState<Material | null>(null);
  const [content, setContent] = useState<MaterialContent | null>(null);
  const [topic, setTopic] = useState("");
  const [tab, setTab] = useState<Tab>("plan");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api<Material>(`/v1/teacher/materials/${id}`)
      .then((m) => {
        setMaterial(m);
        setContent(m.content ?? null);
        setTopic(m.topic);
      })
      .catch((e) => setError(errorCode(e)));
  }, [id]);

  if (!material && !error) return <Splash />;

  // Правка через «рецепт»: копия контента → изменение → флаг несохранённых правок
  const edit = (fn: (c: MaterialContent) => void) => {
    setContent((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      fn(next);
      return next;
    });
    setDirty(true);
    setSaved(false);
  };

  const save = async () => {
    if (!content) return;
    setBusy(true);
    setError(null);
    try {
      const m = await api<Material>(`/v1/teacher/materials/${id}`, { method: "PUT", json: { content, topic } });
      setContent(m.content ?? content);
      setDirty(false);
      setSaved(true);
    } catch (e) {
      setError(errorCode(e));
    } finally {
      setBusy(false);
    }
  };

  const download = async () => {
    try {
      const blob = await apiBlob(`/v1/teacher/materials/${id}/export.docx`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${topic.slice(0, 60) || "lesson"}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(errorCode(e));
    }
  };

  const tabs: Tab[] = ["plan", "stories", "test", "key"];
  const section = (name: Tab) => (tab === name ? "flex" : "hidden print:flex");
  const minutes = content?.plan.stages.reduce((a, s) => a + s.minutes, 0) ?? 0;

  return (
    <Page className="gap-5 lg:max-w-4xl print:max-w-none">
      <header className="flex items-center gap-3 print:hidden">
        <IconButton href="/teacher/materials" label={t("profile.back")}>‹</IconButton>
        <input className="field min-w-0 flex-1 !text-xl !font-black" value={topic} onChange={(e) => { setTopic(e.target.value); setDirty(true); }} aria-label={t("materials.topic")} />
      </header>
      <h1 className="hidden text-3xl font-black print:block">{topic}</h1>
      {material && <p className="text-sm font-bold text-muted">📖 {t("materials.sources", { pages: material.sources.join(", ") })}</p>}
      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      <div className="flex flex-wrap gap-2 print:hidden">
        {tabs.map((name) => (
          <button key={name} className="chip" aria-pressed={tab === name} onClick={() => setTab(name)}>
            {t(`materials.tab.${name}`)}
          </button>
        ))}
        <div className="ml-auto flex gap-2">
          <button className="btn btn-soft !min-h-[2.75rem]" onClick={download} disabled={dirty}>
            ⬇ DOCX
          </button>
          <button className="btn btn-soft !min-h-[2.75rem]" onClick={() => window.print()} disabled={dirty}>
            🖨 PDF
          </button>
          <button className="btn btn-primary !min-h-[2.75rem]" onClick={save} disabled={busy || !dirty}>
            {busy ? <Dots /> : saved ? `✓ ${t("materials.saved")}` : t("checks.save")}
          </button>
        </div>
      </div>
      {dirty && <p className="text-sm font-bold text-muted print:hidden">{t("materials.save_before_export")}</p>}

      {content && (
        <>
          <section className={`${section("plan")} card flex-col gap-3`}>
            <h2 className="text-xl font-black">{t("materials.tab.plan")}</h2>
            <Field value={content.plan.title} onChange={(v) => edit((c) => void (c.plan.title = v))} label={t("checks.title_label")} />
            <div className="label">{t("materials.goals")}</div>
            {content.plan.goals.map((g, i) => (
              <Field key={i} value={g} onChange={(v) => edit((c) => void (c.plan.goals[i] = v))} />
            ))}
            <div className={`label ${minutes === 45 ? "" : "!text-bad"}`}>{t("materials.stages", { n: minutes })}</div>
            {content.plan.stages.map((s, i) => (
              <div key={i} className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-2 rounded-2xl bg-soft p-3">
                <input
                  className="field !px-2 text-center"
                  type="number"
                  min={1}
                  value={s.minutes}
                  aria-label={t("materials.minutes")}
                  onChange={(e) => edit((c) => void (c.plan.stages[i].minutes = Math.max(1, Number(e.target.value) || 1)))}
                />
                <Field value={s.name} onChange={(v) => edit((c) => void (c.plan.stages[i].name = v))} />
                <div className="col-span-2">
                  <Field multiline value={s.activity} onChange={(v) => edit((c) => void (c.plan.stages[i].activity = v))} />
                </div>
              </div>
            ))}
            <div className="label">{t("materials.homework")}</div>
            <Field multiline value={content.plan.homework} onChange={(v) => edit((c) => void (c.plan.homework = v))} />
          </section>

          <section className={`${section("stories")} flex-col gap-3`}>
            <h2 className="text-xl font-black">{t("materials.tab.stories")}</h2>
            {content.stories.map((s, i) => (
              <div key={i} className="card flex flex-col gap-2 break-inside-avoid">
                <div className="label">
                  {i + 1} / {content.stories.length} · 🎨 {s.illustration}
                </div>
                <Field value={s.title} onChange={(v) => edit((c) => void (c.stories[i].title = v))} />
                <Field multiline value={s.text} onChange={(v) => edit((c) => void (c.stories[i].text = v))} />
                {s.question && (
                  <div className="rounded-2xl bg-soft p-3">
                    <Field value={s.question} onChange={(v) => edit((c) => void (c.stories[i].question = v))} />
                    <ul className="mt-2 flex flex-col gap-1">
                      {s.options?.map((o, j) => (
                        <li key={j} className={`text-sm font-bold ${j === s.correct ? "text-good" : ""}`}>
                          {j === s.correct ? "✓" : "○"} {o}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </section>

          <section className={`${section("test")} flex-col gap-3`}>
            <h2 className="text-xl font-black">{t("materials.tab.test")}</h2>
            {content.test.variants.map((v, vi) => (
              <div key={vi} className="card flex flex-col gap-2 print:break-before-page">
                <h3 className="text-lg font-black">
                  {t("materials.variant")} {v.name}
                </h3>
                {v.tasks.map((task, ti) => (
                  <div key={ti} className="grid grid-cols-[2rem_minmax(0,1fr)_4rem] items-start gap-2">
                    <span className="pt-3 font-black">{ti + 1}.</span>
                    <Field multiline value={task.text} onChange={(val) => edit((c) => void (c.test.variants[vi].tasks[ti].text = val))} />
                    <input
                      className="field !px-2 text-center"
                      type="number"
                      min={1}
                      max={20}
                      value={task.points}
                      aria-label={t("materials.points")}
                      onChange={(e) => edit((c) => void (c.test.variants[vi].tasks[ti].points = Math.min(20, Math.max(1, Number(e.target.value) || 1))))}
                    />
                    <span />
                    <div className="col-span-2 print:hidden">
                      <Field value={task.answer} label={t("materials.answer")} onChange={(val) => edit((c) => void (c.test.variants[vi].tasks[ti].answer = val))} />
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </section>

          <section className={`${section("key")} card flex-col gap-2 print:break-before-page`}>
            <h2 className="text-xl font-black">{t("materials.tab.key")}</h2>
            <p className="text-sm font-semibold text-muted print:hidden">{t("materials.key_hint")}</p>
            <table className="w-full text-left">
              <tbody className="divide-y divide-line">
                {content.answer_key.map((row, i) => (
                  <tr key={i}>
                    <td className="py-1.5 pr-3 font-black">
                      {row.variant}-{row.n}
                    </td>
                    <td className="py-1.5">{row.answer}</td>
                    <td className="py-1.5 text-right text-sm text-muted">{row.points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </Page>
  );
}

export default function MaterialPage() {
  const params = useParams<{ id: string }>();
  return (
    <RequireTeacher>
      <Editor id={Number(params.id)} />
    </RequireTeacher>
  );
}
