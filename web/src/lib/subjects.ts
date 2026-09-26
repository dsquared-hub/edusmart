export const SUBJECT_ICON: Record<string, string> = {
  math: "🔢", russian: "📝", uzbek: "📖", english: "🇬🇧", physics: "⚡", nature: "🌿", history: "🏛️", other: "✨",
};

/** Платформа — для 5–11 классов */
export const GRADES = [5, 6, 7, 8, 9, 10, 11];

export function subjectIcon(subject: string | null | undefined): string {
  return SUBJECT_ICON[subject ?? ""] ?? "📘";
}
