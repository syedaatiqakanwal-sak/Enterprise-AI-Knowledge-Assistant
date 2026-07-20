import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, Brain, Home } from "lucide-react";
import { Button } from "@/components/common/Button";
import { useAuth } from "@/contexts/AuthContext";

export function NotFoundPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-4">
      <div className="pointer-events-none absolute inset-0 bg-hero-glow" />
      <div
        className="pointer-events-none absolute inset-0 bg-grid-fade bg-grid opacity-40"
        aria-hidden
      />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 flex flex-col items-center text-center"
      >
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/15 text-primary shadow-glow">
          <Brain className="h-8 w-8" aria-hidden />
        </div>
        <h1 className="mt-8 font-display text-7xl font-bold tracking-tight text-primary">
          404
        </h1>
        <h2 className="mt-4 font-display text-2xl font-semibold tracking-tight">
          Page not found
        </h2>
        <p className="mt-2 max-w-md text-muted-foreground">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
          Let&apos;s get you back on track.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Button asChild>
            <Link to={isAuthenticated ? "/dashboard" : "/"}>
              <Home className="h-4 w-4" />
              {isAuthenticated ? "Go to dashboard" : "Go home"}
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/">
              <ArrowLeft className="h-4 w-4" />
              Back to landing
            </Link>
          </Button>
        </div>
      </motion.div>
    </div>
  );
}
