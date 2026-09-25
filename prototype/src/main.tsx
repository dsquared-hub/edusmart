import { MotionConfig } from "framer-motion";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "@/App";
import "@/design-system/tokens.css";
import { StoreProvider, useReducedMotion } from "@/lib/store";

function Root() {
  // «Меньше анимаций» — глобально для всех framer-motion анимаций
  const reduced = useReducedMotion();
  return (
    <MotionConfig reducedMotion={reduced ? "always" : "never"}>
      <App />
    </MotionConfig>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <StoreProvider>
      <Root />
    </StoreProvider>
  </StrictMode>,
);
