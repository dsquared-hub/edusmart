export type Theme = "sun" | "ocean" | "forest" | "berry";
export const THEMES: Theme[] = ["sun", "ocean", "forest", "berry"];

export type UserSettings = {
  theme: Theme;
  high_contrast: boolean;
  dyslexia_font: boolean;
  lang: string;
};

export type Me = {
  id: number;
  name: string;
  role: "student" | "parent" | "teacher" | null;
  has_telegram: boolean;
  login: string | null;
  settings: UserSettings;
  student: {
    points: number;
    level: number;
    streak: number;
    consent_confirmed: boolean;
    family_code: string;
    grade: number | null;
  } | null;
};

export type Visual = {
  type: "number_line" | "fractions" | "table" | "arrows" | "cards";
  data: Record<string, unknown>;
  caption?: string;
};

export type SimplerStep = {
  title: string;
  text: string;
  example: string;
  visual: Visual | null;
};

export type Step = SimplerStep & {
  check_question: string;
  options: string[];
  correct?: number;
  simpler?: SimplerStep | null;
  /** Сколько раз ещё можно попросить «Объясни проще» на этом шаге */
  simplify_left?: number;
};

export type PracticeTask = {
  question: string;
  options: string[];
  correct: number;
  hint: string;
};

export type Topic = {
  id: number;
  title: string | null;
  subject: string | null;
  grade: number | null;
  status: "in_progress" | "completed" | "abandoned";
  source: "bot" | "web";
  current_step: number;
  total_steps: number;
  wrong_count: number;
  points_earned: number;
  steps: Step[];
  practice: PracticeTask[] | null;
};

export type TopicBrief = Pick<
  Topic,
  "id" | "title" | "subject" | "status" | "source" | "current_step" | "total_steps" | "points_earned"
>;

export type Progress = {
  points: number;
  level: number;
  level_progress: number;
  points_to_next_level: number;
  streak: number;
  topics_completed: number;
  explanations_left_today: number;
  daily_limit: number;
  in_progress: TopicBrief[];
  recent: TopicBrief[];
};

export type AnswerResult = {
  correct: boolean;
  points_awarded: number;
  /** С какой попытки ответ верный: 10 очков за 1-ю, 5 за 2-ю, дальше 0 */
  attempts: number;
  completed: boolean;
  total_points: number;
  level: number;
  streak: number;
  topic: Topic;
};

export type JournalStudent = {
  id: number;
  name: string;
  grade: number | null;
  points: number;
  streak: number;
  last_active_on: string | null;
  topics_completed: number;
  topics_week: number;
  /** % вопросов, решённых с первой попытки; null — пока нет закрытых тем */
  accuracy: number | null;
  weak: { title: string; mistakes: number }[];
};

export type JournalEntry = {
  topic_id: number;
  student_id: number;
  student_name: string;
  title: string;
  subject: string | null;
  source: "bot" | "web";
  completed_at: string;
  questions: number;
  first_try: number;
  mistakes: number;
  points: number;
};

export type Journal = {
  students: JournalStudent[];
  entries: JournalEntry[];
  has_more: boolean;
};

export type SupportTicket = {
  id: number;
  text: string;
  status: "open" | "answered";
  reply: string | null;
  created_at: string;
  answered_at: string | null;
};

/* ---------- Academic Copilot: проверка рукописных работ ---------- */

export type CheckStatus = "queued" | "processing" | "review" | "confirmed" | "failed";
export type ReviewLevel = "one_click" | "review" | "manual";
export type Blocker = "not_ready" | "open_required" | "manual_required";

export type CheckMark = { box: [number, number, number, number]; type: string; note: string };

export type CheckItem = {
  id: number;
  student_id: number | null;
  file_name: string;
  mime: string;
  status: CheckStatus;
  ai_score: number | null;
  teacher_score: number | null;
  final_score: number | null;
  confidence: number | null;
  neatness: number | null;
  level: ReviewLevel | null;
  blocker: Blocker | null;
  viewed: boolean;
  confirmed_at: string | null;
  error: string | null;
};

export type CheckItemFull = CheckItem & {
  recognized_text: string | null;
  ai_comment: string | null;
  ai_marks: CheckMark[];
  teacher_comment: string | null;
  teacher_marks: CheckMark[] | null;
};

export type WorkCheck = {
  id: number;
  title: string;
  subject: string | null;
  grade: number | null;
  task_text: string | null;
  answer_key: string | null;
  max_score: number;
  training_consent: boolean;
  status: CheckStatus;
  created_at: string;
  confirmed_at: string | null;
  counts?: Partial<Record<CheckStatus, number>>;
  items?: CheckItem[];
};

/* ---------- Academic Copilot: учебники и материалы уроков ---------- */

export type Textbook = {
  id: number;
  title: string;
  subject: string | null;
  grade: number | null;
  pages: number;
  status: "processing" | "ready" | "failed";
  error: string | null;
  library: boolean;
  created_at: string;
};

export type Slide = { title: string; text: string; illustration: string; question?: string; options?: string[]; correct?: number };
export type TestTask = { text: string; points: number; answer: string };

export type MaterialContent = {
  plan: { title: string; goals: string[]; stages: { name: string; minutes: number; activity: string }[]; homework: string };
  stories: Slide[];
  test: { variants: { name: string; tasks: TestTask[] }[] };
  answer_key: { variant: string; n: number; answer: string; points: number }[];
};

export type Material = {
  id: number;
  topic: string;
  textbook_id: number | null;
  lang: string;
  sources: number[];
  created_at: string;
  updated_at: string;
  content?: MaterialContent;
};

export type PublicConfig = {
  bot_username: string;
  daily_limit: number;
  points_per_step: number;
  points_second_try: number;
  max_photo_mb: number;
  policy_version: string;
  operator_name: string;
  operator_contact: string;
  data_location: string;
};
