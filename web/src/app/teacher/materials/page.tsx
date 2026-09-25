"use client";

/* Academic Copilot, Модуль 5.2: учебники и генерация материалов урока по учебнику. */
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { RequireTeacher } from "@/components/RequireTeacher";
import { Dots, IconButton, Notice, Page } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { Material, Textbook } from "@/lib/types";

const SUBJECTS = ["math", "russian", "uzbek", "english", "physics", "nature", "history", "other"];

function UploadTextbook({ onDone }: { onDone: () => void }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("math");
  const [grade, setGrade] = useState("");
  const [license, setLicense] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.set("title", title.trim());
      form.set("subject", subject);
      if (grade) form.set("grade", grade);
      form.set("license_note", license.trim());
      form.set("file", file, file.name);
      await api("/v1/teacher/textbooks", { method: "POST", form });
      setOpen(false);
      setTitle("");
      setLicense("");
      setFile(null);
      onDone();
    } catch (err) {
      setError(errorCode(err));
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button className="btn btn-soft" onClick={() => setOpen(true)}>
        📚 {t("materials.upload_book")}
      </button>
    );
  }
  return (
    <form onSubmit={submit} className="card flex flex-col gap-3">
      <h3 className="text-lg font-black">📚 {t("materials.upload_book")}</h3>
      {error && <Notice tone="error">{t(`errors.${error}`, { mb: 50 })}</Notice>}
      <input ref={input} type="file" accept="application/pdf" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <button type="button" className="btn btn-soft" onClick={() => input.current?.click()}>
        {file ? `📄 ${file.name}` : `📄 ${t("materials.pick_pdf")}`}
      </button>
      <label>
        <span className="label">{t("checks.title_label")}</span>
        <input className="field" value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={255} placeholder={t("materials.book_title_placeholder")} />
      </label>
      <div className="grid grid-cols-2 gap-3">
        <select className="field" value={subject} onChange={(e) => setSubject(e.target.value)} aria-label={t("learn.subject")}>
          {SUBJECTS.map((s) => (
            <option key={s} value={s}>
              {t(`subjects.${s}`)}
            </option>
          ))}
        </select>
        <select className="field" value={grade} onChange={(e) => setGrade(e.target.value)} aria-label={t("learn.grade")}>
          <option value="">{t("learn.grade")}</option>
          {Array.from({ length: 11 }, (_, i) => i + 1).map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>
      </div>
      <label>
        <span className="label">{t("materials.license")}</span>
        <input className="field" value={license} onChange={(e) => setLicense(e.target.value)} required minLength={3} maxLength={500} placeholder={t("materials.license_placeholder")} />
        <span className="mt-1 block text-xs font-semibold text-muted">{t("materials.license_hint")}</span>
      </label>
      <div className="grid grid-cols-2 gap-3">
        <button type="button" className="btn btn-soft" onClick={() => setOpen(false)}>
          {t("materials.cancel")}
        </button>
        <button className="btn btn-primary" disabled={busy || !file || !title.trim() || license.trim().length < 3}>
          {busy ? <Dots /> : t("materials.upload")}
        </button>
      </div>
    </form>
  );
}

function MaterialsView() {
  const t = useT();
  const router = useRouter();
  const [books, setBooks] = useState<Textbook[] | null>(null);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [bookId, setBookId] = useState<number | null>(null);
  const [topic, setTopic] = useState("");
  const [variants, setVariants] = useState(2);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<{ textbooks: Textbook[] }>("/v1/teacher/textbooks")
      .then((r) => {
        setBooks(r.textbooks);
        setBookId((cur) => cur ?? r.textbooks.find((b) => b.status === "ready")?.id ?? null);
      })
      .catch((e) => setError(errorCode(e)));
    api<{ materials: Material[] }>("/v1/teacher/materials")
      .then((r) => setMaterials(r.materials))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Учебник индексируется в фоне — обновляем, пока не будет готов
  const indexing = books?.some((b) => b.status === "processing");
  useEffect(() => {
    if (!indexing) return;
    const id = window.setInterval(load, 3000);
    return () => window.clearInterval(id);
  }, [indexing, load]);

  const generate = async (e: FormEvent) => {
    e.preventDefault();
    if (!bookId) return;
    setBusy(true);
    setError(null);
    try {
      const m = await api<Material>("/v1/teacher/materials", { method: "POST", json: { textbook_id: bookId, topic: topic.trim(), variants, lang: t.lang } });
      router.push(`/teacher/materials/${m.id}`);
    } catch (err) {
      setError(errorCode(err));
      setBusy(false);
    }
  };

  return (
    <Page className="gap-5 lg:max-w-6xl">
      <header className="flex items-center gap-3">
        <IconButton href="/journal" label={t("profile.back")}>‹</IconButton>
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-black">🧑‍🏫 {t("materials.title")}</h1>
          <p className="text-sm font-bold text-muted">{t("materials.subtitle")}</p>
        </div>
      </header>
      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="flex flex-col gap-3">
          <form onSubmit={generate} className="card flex flex-col gap-4">
            <h2 className="text-xl font-black">✨ {t("materials.generate")}</h2>
            <label>
              <span className="label">{t("materials.textbook")}</span>
              <select className="field" value={bookId ?? ""} onChange={(e) => setBookId(Number(e.target.value) || null)} required>
                <option value="">—</option>
                {books
                  ?.filter((b) => b.status === "ready")
                  .map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.library ? "🏛 " : ""}
                      {b.title}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              <span className="label">{t("materials.topic")}</span>
              <input className="field" value={topic} onChange={(e) => setTopic(e.target.value)} required maxLength={255} placeholder={t("materials.topic_placeholder")} />
            </label>
            <div>
              <span className="label">{t("materials.variants")}</span>
              <div className="flex gap-2">
                {[2, 3, 4].map((v) => (
                  <button key={v} type="button" className="chip flex-1 justify-center" aria-pressed={variants === v} onClick={() => setVariants(v)}>
                    {v}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-sm font-semibold text-muted">{t("materials.what_you_get")}</p>
            <button className="btn btn-primary" disabled={busy || !bookId || !topic.trim()}>
              {busy ? (
                <span className="flex items-center gap-2">
                  <Dots /> {t("materials.generating")}
                </span>
              ) : (
                `✨ ${t("materials.generate_btn")}`
              )}
            </button>
          </form>

          <h2 className="label mt-2">📚 {t("materials.textbooks")}</h2>
          {books === null && <Dots />}
          {books?.length === 0 && <Notice>{t("materials.no_books")}</Notice>}
          <ul className="flex flex-col gap-2">
            {books?.map((b) => (
              <li key={b.id} className="option !min-h-0 justify-between gap-2 !py-2.5">
                <span className="min-w-0">
                  <span className="block truncate">
                    {b.library ? "🏛 " : "📄 "}
                    {b.title}
                  </span>
                  <span className="block text-sm font-semibold text-muted">
                    {b.status === "ready"
                      ? t("materials.pages", { n: b.pages })
                      : b.status === "processing"
                        ? t("materials.indexing")
                        : t(`errors.${b.error ?? "unknown"}`)}
                  </span>
                </span>
                {b.status === "processing" && <Dots />}
              </li>
            ))}
          </ul>
          <UploadTextbook onDone={load} />
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="label">🗂 {t("materials.mine")}</h2>
          {materials.length === 0 && <Notice>{t("materials.empty")}</Notice>}
          {materials.map((m) => (
            <Link key={m.id} href={`/teacher/materials/${m.id}`} className="option flex-col !items-stretch gap-1">
              <span className="truncate">{m.topic}</span>
              <span className="text-sm font-semibold text-muted">{t("materials.sources", { pages: m.sources.join(", ") })}</span>
            </Link>
          ))}
        </section>
      </div>
    </Page>
  );
}

export default function MaterialsPage() {
  return (
    <RequireTeacher>
      <MaterialsView />
    </RequireTeacher>
  );
}
