import Link from "next/link";
import { Mascot } from "@/components/Mascot";
import ru from "@messages/ru.json";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-[100dvh] max-w-app flex-col items-center justify-center gap-5 px-4 text-center">
      <Mascot mood="thinking" size={120} />
      <h1 className="text-3xl font-black">404</h1>
      <p className="text-lg font-bold text-muted">{ru.errors.topic_not_found}</p>
      <Link href="/" className="btn btn-primary">🏠 {ru.done.home}</Link>
    </main>
  );
}
