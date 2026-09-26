import type { Metadata, Viewport } from "next";
import Script from "next/script";
import "@fontsource/inter/400.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/inter/800.css";
import "@fontsource/inter/900.css";
import "@fontsource/nunito/400.css";
import "@fontsource/nunito/700.css";
import "@fontsource/nunito/800.css";
import "@fontsource/nunito/900.css";
import "@fontsource/andika/400.css";
import "@fontsource/andika/700.css";
import "./globals.css";
import { Providers } from "./providers";
import { SETTINGS_BOOT_SCRIPT } from "@/lib/settings";
import ru from "@messages/ru.json";

export const metadata: Metadata = {
  title: ru.app.name,
  description: ru.home.cta_hint,
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "EDU PROGRESSUZ", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5ecde" },
    { media: "(prefers-color-scheme: dark)", color: "#241b16" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" data-theme="sun" data-contrast="normal" data-font="default" data-age="standard" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: SETTINGS_BOOT_SCRIPT }} />
      </head>
      <body>
        {/* Telegram Mini App SDK: даёт initData для автоматического входа */}
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
