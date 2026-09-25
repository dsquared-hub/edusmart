export const SUBJECT_ICON: Record<string, string> = {
  math: "🔢", russian: "📝", uzbek: "📖", english: "🇬🇧", physics: "⚡", nature: "🌿", history: "🏛️", other: "✨",
};

export function subjectIcon(subject: string | null | undefined): string {
  return SUBJECT_ICON[subject ?? ""] ?? "📘";
}
