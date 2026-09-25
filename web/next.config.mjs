// Браузер ходит на тот же домен (/api/...), Next проксирует запросы в FastAPI.
// Так не нужны CORS и отдельный домен для API, и это работает внутри Telegram Mini App.
// В продакшене Caddy отправляет /api/* прямо в backend (см. deploy/Caddyfile).
const backend = process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";

// Content-Security-Policy: скрипты только свои и Telegram (виджет входа, Mini App SDK).
// 'unsafe-inline' нужен Next.js для встроенных скриптов гидратации.
// 'unsafe-eval' — только для `next dev`: dev-сборка webpack исполняет модули через eval.
const isDev = process.env.NODE_ENV !== "production";
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""} https://telegram.org`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://t.me https://*.telegram.org",
  "font-src 'self'",
  "connect-src 'self'",
  // PWA: service worker (офлайн + Web Push) и манифест только со своего домена
  "worker-src 'self'",
  "manifest-src 'self'",
  "frame-src https://oauth.telegram.org",
  // Mini App открывается в web.telegram.org внутри iframe — разрешаем только Telegram
  "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org",
  "form-action 'self'",
  "base-uri 'self'",
  "object-src 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=(), payment=()" },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Отдельная папка сборки, чтобы можно было запустить второй `next dev` на другом порту
  distDir: process.env.NEXT_DIST_DIR || ".next",
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  eslint: { ignoreDuringBuilds: true },
  // Объяснение с фото и проверкой ответа может готовиться дольше 30 секунд
  experimental: { proxyTimeout: 120_000 },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
  async headers() {
    return [
      { source: "/:path*", headers: securityHeaders },
      // Новая версия service worker должна подхватываться сразу, а не через сутки кэша
      {
        source: "/sw.js",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Service-Worker-Allowed", value: "/" },
        ],
      },
    ];
  },
};

export default nextConfig;
