/* Учебники по классу и читалка: выделил непонятный фрагмент — сразу спросил ИИ. */
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/layout/AppShell";
import { Button, ProgressBar } from "@/design-system/components";
import { READER, subjectById, TEXTBOOKS } from "@/mock-data";
import { Link, navigate } from "@/lib/router";
import { fmt, useL, useStore } from "@/lib/store";

function Cover({ color, emoji, title }: { color: string; emoji: string; title: string }) {
  // Объёмная обложка: корешок, блик и тень страниц
  return (
    <div className="relative aspect-[3/4] w-full" aria-hidden="true">
      <div className="absolute inset-y-1 right-0 left-2 rounded-r-xl bg-[#F3EAD9] shadow-soft" />
      <div
        className="absolute inset-0 right-2 flex flex-col justify-between rounded-xl rounded-l-md p-3 text-white shadow-lift"
        style={{ background: `linear-gradient(135deg, color-mix(in srgb, ${color} 80%, white), ${color} 45%, color-mix(in srgb, ${color} 70%, black))` }}
      >
        <span className="absolute inset-y-0 left-0 w-2.5 rounded-l-md bg-black/15" />
        <span className="text-4xl drop-shadow">{emoji}</span>
        <span className="line-clamp-3 text-sm font-black leading-tight drop-shadow">{title}</span>
      </div>
    </div>
  );
}

export function TextbookList() {
  const { d, grade } = useStore();
  const L = useL();
  return (
    <div>
      <PageHeader title={d.textbooks.title} subtitle={fmt(d.textbooks.subtitle, { n: grade })} />
      <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {TEXTBOOKS.map((b) => {
          const s = subjectById(b.subject);
          return (
            <Link key={b.id} to={`/reader/${b.id}`} className="group flex flex-col gap-3">
              <div className="transition group-hover:-translate-y-1.5 group-hover:rotate-[-1.5deg]">
                <Cover color={b.cover} emoji={s.emoji} title={L(b.title)} />
              </div>
              <div>
                <div className="font-black leading-tight">{L(b.title)}</div>
                <div className="mb-1.5 text-xs font-bold text-muted">{fmt(d.textbooks.pages, { n: b.pages })}</div>
                <ProgressBar value={b.progress} size="sm" label={L(b.title)} />
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export function Reader({ id }: { id?: string }) {
  const { d } = useStore();
  const L = useL();
  const book = TEXTBOOKS.find((b) => b.id === id) ?? TEXTBOOKS[0];
  const [selection, setSelection] = useState<{ text: string; x: number; y: number } | null>(null);
  const article = useRef<HTMLElement>(null);

  useEffect(() => {
    const onSelect = () => {
      const sel = window.getSelection();
      const text = sel?.toString().trim() ?? "";
      if (!sel || !text || !article.current?.contains(sel.anchorNode)) {
        setSelection(null);
        return;
      }
      const rect = sel.getRangeAt(0).getBoundingClientRect();
      setSelection({ text: text.slice(0, 80), x: rect.left + rect.width / 2, y: rect.top });
    };
    document.addEventListener("selectionchange", onSelect);
    return () => document.removeEventListener("selectionchange", onSelect);
  }, []);

  const askAi = () => {
    if (!selection) return;
    sessionStorage.setItem("edu.ask.prefill", fmt(d.textbooks.explainSelection, { text: selection.text }));
    navigate("/ask");
  };

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/textbooks" className="mb-4 inline-flex items-center gap-2 font-extrabold text-caramel hover:underline">
        <ArrowLeft size={18} /> {d.nav.textbooks}
      </Link>
      <div className="mb-4 flex items-center gap-2 rounded-2xl bg-gold/15 px-4 py-3 font-bold text-coffee">
        <Sparkles size={18} /> {d.textbooks.readerHint}
      </div>
      <article ref={article} className="card p-6 sm:p-10" style={{ fontFamily: 'Georgia, "Times New Roman", serif' }}>
        <div className="label font-sans">
          {L(book.title)} · {fmt(d.textbooks.chapter, { n: READER.chapter })}
        </div>
        <h1 className="mb-6 mt-1 font-sans text-3xl font-black text-coffee">{L(READER.title)}</h1>
        {READER.paragraphs.map((p, i) => (
          <p key={i} className="mb-5 text-lg leading-relaxed selection:bg-gold/50">
            {L(p)}
          </p>
        ))}
        <div className="mt-8 flex justify-between font-sans text-sm font-bold text-muted">
          <span>§ 12</span>
          <span>47 / {book.pages}</span>
        </div>
      </article>

      {/* Всплывающая кнопка над выделением */}
      <AnimatePresence>
        {selection && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0 }}
            className="fixed z-40 -translate-x-1/2 -translate-y-full"
            style={{ left: selection.x, top: selection.y - 10 }}
          >
            <Button size="sm" variant="gold" onMouseDown={(e) => e.preventDefault()} onClick={askAi} icon={<Sparkles size={16} />}>
              {d.textbooks.askAbout}
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
