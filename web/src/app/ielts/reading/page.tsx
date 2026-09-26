"use client";

import { StartSection } from "@/components/ielts/StartSection";

export default function IeltsReadingPage() {
  return <StartSection path="/ielts/tests" body={{ kind: "reading" }} />;
}
