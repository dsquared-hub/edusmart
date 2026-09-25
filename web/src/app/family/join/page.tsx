"use client";

/* Ссылка из QR-кода приглашения: /family/join?code=123456 → страница семьи с кодом. */
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Splash } from "@/components/ui";

export default function JoinRedirect() {
  const router = useRouter();
  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get("code") ?? "";
    router.replace(`/family${/^\d{6}$/.test(code) ? `?code=${code}` : ""}`);
  }, [router]);
  return <Splash />;
}
