/* Моковые данные прототипа: реальные школьные предметы Узбекистана и узбекские имена.
   Тексты — в трёх языках ({ uz, ru, en }), выбираются через useL(). */
import type { L10n } from "@/lib/store";

export type Subject = {
  id: string;
  name: L10n;
  emoji: string;
  color: string;
  progress: number;
  topics: [number, number];
};

export const SUBJECTS: Subject[] = [
  { id: "math", name: { uz: "Matematika", ru: "Математика", en: "Mathematics" }, emoji: "🧮", color: "#D98B4E", progress: 72, topics: [18, 25] },
  { id: "algebra", name: { uz: "Algebra", ru: "Алгебра", en: "Algebra" }, emoji: "📐", color: "#B8744A", progress: 58, topics: [11, 19] },
  { id: "geometry", name: { uz: "Geometriya", ru: "Геометрия", en: "Geometry" }, emoji: "📏", color: "#C9A15B", progress: 41, topics: [7, 17] },
  { id: "physics", name: { uz: "Fizika", ru: "Физика", en: "Physics" }, emoji: "🧲", color: "#5E86B5", progress: 35, topics: [6, 17] },
  { id: "chemistry", name: { uz: "Kimyo", ru: "Химия", en: "Chemistry" }, emoji: "🧪", color: "#6FA876", progress: 22, topics: [3, 14] },
  { id: "biology", name: { uz: "Biologiya", ru: "Биология", en: "Biology" }, emoji: "🌿", color: "#5E9B6B", progress: 64, topics: [12, 19] },
  { id: "native", name: { uz: "Ona tili", ru: "Родной язык", en: "Native language" }, emoji: "📝", color: "#A86A8C", progress: 80, topics: [20, 25] },
  { id: "russian", name: { uz: "Rus tili", ru: "Русский язык", en: "Russian" }, emoji: "🔤", color: "#C0675A", progress: 55, topics: [11, 20] },
  { id: "english", name: { uz: "Ingliz tili", ru: "Английский язык", en: "English" }, emoji: "🇬🇧", color: "#4E7FA8", progress: 69, topics: [15, 22] },
  { id: "history", name: { uz: "Tarix", ru: "История", en: "History" }, emoji: "🏛️", color: "#9B7B55", progress: 47, topics: [9, 19] },
  { id: "geography", name: { uz: "Geografiya", ru: "География", en: "Geography" }, emoji: "🌍", color: "#4F9A9A", progress: 51, topics: [9, 18] },
  { id: "informatics", name: { uz: "Informatika", ru: "Информатика", en: "Computer science" }, emoji: "💻", color: "#6C6FB0", progress: 88, topics: [14, 16] },
];

export type Textbook = { id: string; subject: string; title: L10n; pages: number; cover: string; progress: number };

export const TEXTBOOKS: Textbook[] = [
  { id: "alg7", subject: "algebra", title: { uz: "Algebra. 7-sinf", ru: "Алгебра. 7 класс", en: "Algebra. Grade 7" }, pages: 176, cover: "#B8744A", progress: 46 },
  { id: "geo7", subject: "geometry", title: { uz: "Geometriya. 7-sinf", ru: "Геометрия. 7 класс", en: "Geometry. Grade 7" }, pages: 144, cover: "#C9A15B", progress: 31 },
  { id: "phy7", subject: "physics", title: { uz: "Fizika. 7-sinf", ru: "Физика. 7 класс", en: "Physics. Grade 7" }, pages: 160, cover: "#5E86B5", progress: 22 },
  { id: "bio7", subject: "biology", title: { uz: "Biologiya. 7-sinf", ru: "Биология. 7 класс", en: "Biology. Grade 7" }, pages: 192, cover: "#5E9B6B", progress: 58 },
  { id: "eng7", subject: "english", title: { uz: "English. 7-sinf", ru: "Английский. 7 класс", en: "English. Grade 7" }, pages: 128, cover: "#4E7FA8", progress: 64 },
  { id: "his7", subject: "history", title: { uz: "Oʻzbekiston tarixi. 7-sinf", ru: "История Узбекистана. 7 класс", en: "History of Uzbekistan. Grade 7" }, pages: 208, cover: "#9B7B55", progress: 12 },
];

/** Фрагмент учебника для читалки (алгебра, 7 класс). */
export const READER: { chapter: number; title: L10n; paragraphs: L10n[] } = {
  chapter: 3,
  title: { uz: "Qisqa koʻpaytirish formulalari", ru: "Формулы сокращённого умножения", en: "Short multiplication formulas" },
  paragraphs: [
    {
      uz: "Ikki son yigʻindisining kvadrati birinchi son kvadrati, birinchi va ikkinchi son koʻpaytmasining ikkilangani hamda ikkinchi son kvadratining yigʻindisiga teng: (a + b)² = a² + 2ab + b².",
      ru: "Квадрат суммы двух чисел равен квадрату первого числа плюс удвоенное произведение первого и второго чисел плюс квадрат второго числа: (a + b)² = a² + 2ab + b².",
      en: "The square of a sum of two numbers equals the square of the first number plus twice the product of both plus the square of the second: (a + b)² = a² + 2ab + b².",
    },
    {
      uz: "Bu formula koʻpaytmani tezroq hisoblash imkonini beradi. Masalan, 51² ni (50 + 1)² koʻrinishida yozish mumkin: 2500 + 100 + 1 = 2601.",
      ru: "Эта формула позволяет считать быстрее. Например, 51² можно записать как (50 + 1)²: 2500 + 100 + 1 = 2601.",
      en: "This formula lets you calculate faster. For example, 51² can be written as (50 + 1)²: 2500 + 100 + 1 = 2601.",
    },
    {
      uz: "Ikki son ayirmasining kvadrati shunga oʻxshash: (a − b)² = a² − 2ab + b². Faqat oʻrtadagi hadning ishorasi oʻzgaradi.",
      ru: "Квадрат разности устроен так же: (a − b)² = a² − 2ab + b². Меняется только знак среднего слагаемого.",
      en: "The square of a difference works the same way: (a − b)² = a² − 2ab + b². Only the sign of the middle term changes.",
    },
  ],
};

export const QUESTS = [
  { id: "q1", reward: 20, icon: "💬", total: 1 },
  { id: "q2", reward: 30, icon: "🧩", total: 3 },
  { id: "q3", reward: 15, icon: "📖", total: 5 },
] as const;

export const SUGGESTIONS: L10n[] = [
  { uz: "Trapetsiya yuzi qanday topiladi?", ru: "Как найти площадь трапеции?", en: "How do I find a trapezoid's area?" },
  { uz: "(a + b)² formulasini tushuntir", ru: "Объясни формулу (a + b)²", en: "Explain the (a + b)² formula" },
  { uz: "Fotosintez nima?", ru: "Что такое фотосинтез?", en: "What is photosynthesis?" },
  { uz: "Present Perfect qachon ishlatiladi?", ru: "Когда нужен Present Perfect?", en: "When do I use Present Perfect?" },
];

/** Пошаговое объяснение ИИ (демо): площадь трапеции. */
export const EXPLANATION = {
  steps: [
    {
      title: { uz: "Trapetsiya nima?", ru: "Что такое трапеция?", en: "What is a trapezoid?" },
      text: {
        uz: "Trapetsiya — ikki tomoni parallel boʻlgan toʻrtburchak. Parallel tomonlar asoslar deyiladi: a va b.",
        ru: "Трапеция — четырёхугольник, у которого две стороны параллельны. Параллельные стороны называются основаниями: a и b.",
        en: "A trapezoid is a quadrilateral with two parallel sides. The parallel sides are called bases: a and b.",
      },
      formula: null as string | null,
      simpler: {
        uz: "Tasavvur qil: stol ustidagi kitob — yuqori va pastki qirralari parallel, faqat biri qisqaroq.",
        ru: "Представь стопку кирпичей-пирамидку: верх и низ ровные и параллельные, просто верх короче.",
        en: "Picture a pile of bricks: the top and bottom are flat and parallel — the top is just shorter.",
      },
    },
    {
      title: { uz: "Balandlikni topamiz", ru: "Находим высоту", en: "Find the height" },
      text: {
        uz: "Balandlik h — asoslar orasidagi eng qisqa masofa. U asoslarga perpendikulyar.",
        ru: "Высота h — это кратчайшее расстояние между основаниями. Она перпендикулярна им.",
        en: "The height h is the shortest distance between the bases. It is perpendicular to them.",
      },
      formula: "h ⟂ a, b",
      simpler: {
        uz: "Balandlik — yuqoridan pastga tik tushirilgan chiziq, xuddi ipga osilgan tosh kabi.",
        ru: "Высота — это отвес: как камешек на нитке, который висит строго вниз.",
        en: "The height is a plumb line — like a pebble on a string hanging straight down.",
      },
    },
    {
      title: { uz: "Formula", ru: "Формула", en: "The formula" },
      text: {
        uz: "Asoslarning oʻrtachasini balandlikka koʻpaytiramiz:",
        ru: "Берём среднее оснований и умножаем на высоту:",
        en: "Take the average of the bases and multiply by the height:",
      },
      formula: "S = (a + b) / 2 · h",
      simpler: {
        uz: "Trapetsiyani oʻrtacha kenglikdagi toʻgʻri toʻrtburchak deb tasavvur qil.",
        ru: "Представь, что трапеция — это прямоугольник средней ширины.",
        en: "Imagine the trapezoid as a rectangle of average width.",
      },
    },
    {
      title: { uz: "Hisoblaymiz", ru: "Считаем", en: "Let's calculate" },
      text: {
        uz: "Agar a = 6 sm, b = 4 sm, h = 3 sm boʻlsa:",
        ru: "Если a = 6 см, b = 4 см, h = 3 см:",
        en: "If a = 6 cm, b = 4 cm, h = 3 cm:",
      },
      formula: "S = (6 + 4) / 2 · 3 = 15 sm²",
      simpler: {
        uz: "6 va 4 ning oʻrtachasi 5. 5 × 3 = 15. Tayyor!",
        ru: "Среднее 6 и 4 — это 5. 5 × 3 = 15. Готово!",
        en: "The average of 6 and 4 is 5. 5 × 3 = 15. Done!",
      },
    },
  ],
  example: {
    uz: "Bogʻdagi gulzor trapetsiya shaklida: asoslari 8 m va 6 m, eni 5 m. Gulzor yuzi (8 + 6) / 2 · 5 = 35 m² — shuncha joyga koʻchat ekish mumkin.",
    ru: "Клумба во дворе в форме трапеции: основания 8 м и 6 м, ширина 5 м. Площадь (8 + 6) / 2 · 5 = 35 м² — столько места под рассаду.",
    en: "A flower bed shaped like a trapezoid: bases 8 m and 6 m, width 5 m. Area (8 + 6) / 2 · 5 = 35 m² — that's the space for seedlings.",
  },
  practice: {
    question: {
      uz: "a = 10, b = 6, h = 4. Trapetsiya yuzi nechaga teng?",
      ru: "a = 10, b = 6, h = 4. Чему равна площадь трапеции?",
      en: "a = 10, b = 6, h = 4. What is the trapezoid's area?",
    },
    options: ["24", "32", "40", "64"],
    correct: 1,
    hint: {
      uz: "Asoslarni qoʻshishni unutma: (10 + 6) / 2 = 8, keyin 8 × 4.",
      ru: "Не забудь сложить основания: (10 + 6) / 2 = 8, затем 8 × 4.",
      en: "Don't forget to add the bases: (10 + 6) / 2 = 8, then 8 × 4.",
    },
    reward: 25,
  },
};

export const QUIZ: {
  kind: "choice" | "truefalse" | "input";
  q: L10n;
  options?: string[];
  answer: number | boolean | string;
  why: L10n;
}[] = [
  {
    kind: "choice",
    q: { uz: "(x + 3)² ni oching", ru: "Раскройте (x + 3)²", en: "Expand (x + 3)²" },
    options: ["x² + 9", "x² + 6x + 9", "x² + 3x + 9", "2x + 6"],
    answer: 1,
    why: { uz: "Oʻrtadagi had 2 · x · 3 = 6x. Uni unutish — eng keng tarqalgan xato.", ru: "Среднее слагаемое 2 · x · 3 = 6x. Забыть его — самая частая ошибка.", en: "The middle term is 2 · x · 3 = 6x. Forgetting it is the most common slip." },
  },
  {
    kind: "truefalse",
    q: { uz: "(a − b)² = a² − b²", ru: "(a − b)² = a² − b²", en: "(a − b)² = a² − b²" },
    answer: false,
    why: { uz: "Toʻgʻrisi: (a − b)² = a² − 2ab + b². a² − b² esa kvadratlar ayirmasi.", ru: "Верно так: (a − b)² = a² − 2ab + b². А a² − b² — это разность квадратов.", en: "Correct: (a − b)² = a² − 2ab + b². a² − b² is the difference of squares." },
  },
  {
    kind: "input",
    q: { uz: "51² ni formula bilan hisoblang", ru: "Вычислите 51² по формуле", en: "Calculate 51² with the formula" },
    answer: "2601",
    why: { uz: "(50 + 1)² = 2500 + 2 · 50 · 1 + 1 = 2601", ru: "(50 + 1)² = 2500 + 2 · 50 · 1 + 1 = 2601", en: "(50 + 1)² = 2500 + 2 · 50 · 1 + 1 = 2601" },
  },
  {
    kind: "choice",
    q: { uz: "Trapetsiya: a = 7, b = 5, h = 2. S = ?", ru: "Трапеция: a = 7, b = 5, h = 2. S = ?", en: "Trapezoid: a = 7, b = 5, h = 2. S = ?" },
    options: ["12", "24", "35", "6"],
    answer: 0,
    why: { uz: "(7 + 5) / 2 = 6, 6 × 2 = 12.", ru: "(7 + 5) / 2 = 6, 6 × 2 = 12.", en: "(7 + 5) / 2 = 6, 6 × 2 = 12." },
  },
];

export const ACTIVITY = [32, 45, 18, 52, 40, 64, 28]; // минут по дням недели

export const MASTERY: { topic: L10n; value: number }[] = [
  { topic: { uz: "Kvadrat formulalar", ru: "Формулы квадрата", en: "Square formulas" }, value: 86 },
  { topic: { uz: "Chiziqli tenglamalar", ru: "Линейные уравнения", en: "Linear equations" }, value: 74 },
  { topic: { uz: "Koʻpburchaklar yuzi", ru: "Площадь многоугольников", en: "Polygon areas" }, value: 61 },
  { topic: { uz: "Nyuton qonunlari", ru: "Законы Ньютона", en: "Newton's laws" }, value: 38 },
  { topic: { uz: "Kimyoviy formulalar", ru: "Химические формулы", en: "Chemical formulas" }, value: 27 },
];

export const TOPIC_MAP: { topic: L10n; subject: string; level: "strong" | "medium" | "weak" }[] = [
  { topic: { uz: "Kasrlar", ru: "Дроби", en: "Fractions" }, subject: "math", level: "strong" },
  { topic: { uz: "Foizlar", ru: "Проценты", en: "Percentages" }, subject: "math", level: "strong" },
  { topic: { uz: "(a+b)²", ru: "(a+b)²", en: "(a+b)²" }, subject: "algebra", level: "strong" },
  { topic: { uz: "Tenglamalar", ru: "Уравнения", en: "Equations" }, subject: "algebra", level: "medium" },
  { topic: { uz: "Burchaklar", ru: "Углы", en: "Angles" }, subject: "geometry", level: "medium" },
  { topic: { uz: "Trapetsiya", ru: "Трапеция", en: "Trapezoid" }, subject: "geometry", level: "weak" },
  { topic: { uz: "Tezlik", ru: "Скорость", en: "Speed" }, subject: "physics", level: "medium" },
  { topic: { uz: "Kuch", ru: "Сила", en: "Force" }, subject: "physics", level: "weak" },
  { topic: { uz: "Hujayra", ru: "Клетка", en: "Cell" }, subject: "biology", level: "strong" },
  { topic: { uz: "Valentlik", ru: "Валентность", en: "Valence" }, subject: "chemistry", level: "weak" },
  { topic: { uz: "Present Perfect", ru: "Present Perfect", en: "Present Perfect" }, subject: "english", level: "medium" },
  { topic: { uz: "Amir Temur", ru: "Амир Темур", en: "Amir Temur" }, subject: "history", level: "strong" },
];

export const HISTORY: { title: L10n; subject: string; when: L10n; coins: number }[] = [
  { title: { uz: "Trapetsiya yuzi", ru: "Площадь трапеции", en: "Trapezoid area" }, subject: "geometry", when: { uz: "Bugun, 16:40", ru: "Сегодня, 16:40", en: "Today, 16:40" }, coins: 25 },
  { title: { uz: "(x + 3)² ni ochish", ru: "Раскрыть (x + 3)²", en: "Expand (x + 3)²" }, subject: "algebra", when: { uz: "Bugun, 16:12", ru: "Сегодня, 16:12", en: "Today, 16:12" }, coins: 20 },
  { title: { uz: "Fotosintez bosqichlari", ru: "Этапы фотосинтеза", en: "Photosynthesis stages" }, subject: "biology", when: { uz: "Kecha, 18:05", ru: "Вчера, 18:05", en: "Yesterday, 18:05" }, coins: 15 },
  { title: { uz: "Tezlik va vaqt", ru: "Скорость и время", en: "Speed and time" }, subject: "physics", when: { uz: "Kecha, 17:30", ru: "Вчера, 17:30", en: "Yesterday, 17:30" }, coins: 20 },
];

export type Player = { name: string; coins: number; stage: number; skin: number; me?: boolean };

export const LEADERS: Record<"class" | "school" | "region", Player[]> = {
  class: [
    { name: "Jasur Toshmatov", coins: 1340, stage: 4, skin: 1 },
    { name: "Madina Yusupova", coins: 1215, stage: 3, skin: 0 },
    { name: "Aziza Karimova", coins: 1180, stage: 1, skin: 0, me: true },
    { name: "Sardor Rahimov", coins: 990, stage: 3, skin: 2 },
    { name: "Nilufar Abdullayeva", coins: 870, stage: 2, skin: 4 },
    { name: "Bekzod Aliyev", coins: 760, stage: 2, skin: 3 },
    { name: "Dilnoza Ergasheva", coins: 640, stage: 1, skin: 1 },
    { name: "Otabek Nurmatov", coins: 515, stage: 1, skin: 5 },
  ],
  school: [
    { name: "Shahzoda Qodirova", coins: 2480, stage: 5, skin: 0 },
    { name: "Jahongir Umarov", coins: 2210, stage: 5, skin: 2 },
    { name: "Jasur Toshmatov", coins: 1340, stage: 4, skin: 1 },
    { name: "Madina Yusupova", coins: 1215, stage: 3, skin: 0 },
    { name: "Aziza Karimova", coins: 1180, stage: 1, skin: 0, me: true },
    { name: "Farrux Saidov", coins: 1105, stage: 3, skin: 3 },
    { name: "Malika Xolmatova", coins: 1020, stage: 3, skin: 4 },
  ],
  region: [
    { name: "Ulugʻbek Mirzayev", coins: 4120, stage: 6, skin: 1 },
    { name: "Sevara Tursunova", coins: 3890, stage: 6, skin: 0 },
    { name: "Shahzoda Qodirova", coins: 2480, stage: 5, skin: 0 },
    { name: "Doston Karimov", coins: 2350, stage: 5, skin: 2 },
    { name: "Jahongir Umarov", coins: 2210, stage: 5, skin: 2 },
    { name: "Aziza Karimova", coins: 1180, stage: 1, skin: 0, me: true },
  ],
};

export const ACHIEVEMENTS: { id: string; icon: string; color: string; name: L10n; desc: L10n; done: number; total: number }[] = [
  { id: "first", icon: "🚀", color: "#D98B4E", name: { uz: "Birinchi savol", ru: "Первый вопрос", en: "First question" }, desc: { uz: "Sunʼiy intellektga savol ber", ru: "Задай вопрос ИИ", en: "Ask the AI a question" }, done: 1, total: 1 },
  { id: "streak7", icon: "🔥", color: "#E07A4E", name: { uz: "7 kun ketma-ket", ru: "7 дней подряд", en: "7-day streak" }, desc: { uz: "Bir hafta davomida oʻqi", ru: "Занимайся неделю", en: "Study for a week" }, done: 7, total: 7 },
  { id: "fixer", icon: "🛠️", color: "#6FA876", name: { uz: "Xatolar ustasi", ru: "Мастер исправлений", en: "Fix-it master" }, desc: { uz: "10 ta xatoni tuzat", ru: "Исправь 10 ошибок", en: "Fix 10 mistakes" }, done: 10, total: 10 },
  { id: "reader", icon: "📚", color: "#5E86B5", name: { uz: "Kitobxon", ru: "Книголюб", en: "Bookworm" }, desc: { uz: "50 bet oʻqi", ru: "Прочитай 50 страниц", en: "Read 50 pages" }, done: 50, total: 50 },
  { id: "math", icon: "🧮", color: "#B8744A", name: { uz: "Matematik", ru: "Математик", en: "Mathematician" }, desc: { uz: "100 ta masala yech", ru: "Реши 100 задач", en: "Solve 100 tasks" }, done: 74, total: 100 },
  { id: "streak30", icon: "🌙", color: "#6C6FB0", name: { uz: "Bir oy", ru: "Целый месяц", en: "Whole month" }, desc: { uz: "30 kun ketma-ket", ru: "30 дней подряд", en: "30-day streak" }, done: 12, total: 30 },
  { id: "polyglot", icon: "🌐", color: "#4F9A9A", name: { uz: "Poliglot", ru: "Полиглот", en: "Polyglot" }, desc: { uz: "3 tilda savol ber", ru: "Спроси на 3 языках", en: "Ask in 3 languages" }, done: 2, total: 3 },
  { id: "legend", icon: "👑", color: "#E8B64C", name: { uz: "Afsona", ru: "Легенда", en: "Legend" }, desc: { uz: "Kubini Afsona qiyofasiga yetkaz", ru: "Одень Куби в образ Легенды", en: "Get Kubi to the Legend look" }, done: 1, total: 6 },
  { id: "helper", icon: "🤝", color: "#A86A8C", name: { uz: "Yordamchi", ru: "Помощник", en: "Helper" }, desc: { uz: "Xatoga 5 marta ishora qil", ru: "Сообщи о 5 неточностях", en: "Report 5 inaccuracies" }, done: 0, total: 5 },
];

export const CHILDREN = [
  { name: "Aziza Karimova", grade: 7, streak: 12, week: [35, 42, 20, 50, 38, 60, 25], askedAi: 23, solved: 148 },
  { name: "Timur Karimov", grade: 3, streak: 4, week: [15, 20, 0, 18, 22, 30, 10], askedAi: 9, solved: 41 },
];

export const WEAK_TOPICS: { topic: L10n; subject: string; accuracy: number }[] = [
  { topic: { uz: "Kimyoviy valentlik", ru: "Химическая валентность", en: "Chemical valence" }, subject: "chemistry", accuracy: 38 },
  { topic: { uz: "Nyutonning II qonuni", ru: "Второй закон Ньютона", en: "Newton's second law" }, subject: "physics", accuracy: 45 },
  { topic: { uz: "Trapetsiya yuzi", ru: "Площадь трапеции", en: "Trapezoid area" }, subject: "geometry", accuracy: 52 },
];

export const CLASSES = ["7-A", "7-B", "8-A"] as const;

export const STUDENTS: { name: string; progress: number; last: "today" | "yesterday" | string; help?: boolean; stage: number; skin: number }[] = [
  { name: "Aziza Karimova", progress: 72, last: "today", stage: 1, skin: 0 },
  { name: "Jasur Toshmatov", progress: 84, last: "today", stage: 4, skin: 1 },
  { name: "Madina Yusupova", progress: 79, last: "today", stage: 3, skin: 0 },
  { name: "Sardor Rahimov", progress: 61, last: "yesterday", stage: 3, skin: 2 },
  { name: "Nilufar Abdullayeva", progress: 55, last: "yesterday", stage: 2, skin: 4 },
  { name: "Bekzod Aliyev", progress: 34, last: "3d", help: true, stage: 2, skin: 3 },
  { name: "Dilnoza Ergasheva", progress: 47, last: "today", stage: 1, skin: 1 },
  { name: "Otabek Nurmatov", progress: 28, last: "5d", help: true, stage: 1, skin: 5 },
];

export const CLASS_FAQ: { q: L10n; count: number; subject: string }[] = [
  { q: { uz: "Kvadratlar ayirmasi va ayirma kvadrati farqi nima?", ru: "Чем разность квадратов отличается от квадрата разности?", en: "How is a difference of squares different from a squared difference?" }, count: 14, subject: "algebra" },
  { q: { uz: "Trapetsiya balandligi qanday topiladi?", ru: "Как найти высоту трапеции?", en: "How do I find a trapezoid's height?" }, count: 9, subject: "geometry" },
  { q: { uz: "Massa va ogʻirlik bir xilmi?", ru: "Масса и вес — это одно и то же?", en: "Are mass and weight the same?" }, count: 7, subject: "physics" },
];

export const subjectById = (id: string) => SUBJECTS.find((s) => s.id === id) ?? SUBJECTS[0];
