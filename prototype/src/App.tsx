import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";
import { AppShell } from "@/components/layout/AppShell";
import Achievements from "@/pages/Achievements";
import Ask from "@/pages/Ask";
import DesignSystem from "@/pages/DesignSystem";
import Home from "@/pages/Home";
import Leaderboard from "@/pages/Leaderboard";
import Onboarding from "@/pages/Onboarding";
import Parent from "@/pages/Parent";
import Profile from "@/pages/Profile";
import Progress from "@/pages/Progress";
import Quiz from "@/pages/Quiz";
import Subjects from "@/pages/Subjects";
import Teacher from "@/pages/Teacher";
import { Reader, TextbookList } from "@/pages/Textbooks";
import Wardrobe from "@/pages/Wardrobe";
import { navigate, useRoute } from "@/lib/router";
import { useStore } from "@/lib/store";

export default function App() {
  const { path, params } = useRoute();
  const { onboarded } = useStore();

  // Первый вход — регистрация; «/» — на главную
  useEffect(() => {
    if (!onboarded && path !== "/onboarding") navigate("/onboarding");
    else if (onboarded && (path === "/" || path === "/onboarding")) navigate("/home");
  }, [onboarded, path]);

  if (path === "/onboarding" || !onboarded) return <Onboarding />;

  const page = (() => {
    switch (path) {
      case "/subjects": return <Subjects />;
      case "/textbooks": return <TextbookList />;
      case "/reader": return <Reader id={params[0]} />;
      case "/ask": return <Ask />;
      case "/quiz": return <Quiz />;
      case "/progress": return <Progress />;
      case "/leaderboard": return <Leaderboard />;
      case "/achievements": return <Achievements />;
      case "/wardrobe": return <Wardrobe />;
      case "/profile": return <Profile />;
      case "/parent": return <Parent />;
      case "/teacher": return <Teacher />;
      case "/design": return <DesignSystem />;
      default: return <Home />;
    }
  })();

  return (
    <AppShell>
      <AnimatePresence mode="wait">
        <motion.div key={path + params.join("/")} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.2 }}>
          {page}
        </motion.div>
      </AnimatePresence>
    </AppShell>
  );
}
