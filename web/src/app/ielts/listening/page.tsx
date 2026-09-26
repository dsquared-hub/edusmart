"use client";

import { StartSection } from "@/components/ielts/StartSection";

export default function IeltsListeningPage() {
  return <StartSection path="/ielts/tests" body={{ kind: "listening" }} />;
}
