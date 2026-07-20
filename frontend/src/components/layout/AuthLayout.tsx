import { Link, Outlet } from "react-router-dom";
import { Brain, FileText, MessageSquare, Shield, Sparkles } from "lucide-react";

const highlights = [
  {
    icon: MessageSquare,
    title: "RAG-powered chat",
    description: "Answers grounded in your company documents.",
  },
  {
    icon: FileText,
    title: "Multi-format ingestion",
    description: "PDFs, spreadsheets, slides, and more.",
  },
  {
    icon: Shield,
    title: "Enterprise security",
    description: "Role-based access and audit-ready controls.",
  },
];

export function AuthLayout() {
  return (
    <div className="flex min-h-screen bg-background">
      <div className="relative hidden w-1/2 overflow-hidden lg:flex lg:flex-col lg:justify-between">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-background to-background" />
        <div className="absolute -left-20 top-20 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
        <div className="absolute bottom-20 right-10 h-96 w-96 rounded-full bg-primary/5 blur-3xl" />

        <div className="relative z-10 flex flex-col justify-center px-12 py-16 xl:px-20">
          <Link to="/" className="mb-12 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/15 text-primary">
              <Brain className="h-6 w-6" />
            </div>
            <span className="font-display text-2xl font-bold">Enterprise AI</span>
          </Link>

          <h1 className="font-display text-4xl font-bold leading-tight tracking-tight xl:text-5xl">
            Enterprise AI Knowledge Assistant
          </h1>
          <p className="mt-4 text-xl text-primary">
            Chat with your Company&apos;s Knowledge
          </p>
          <p className="mt-4 max-w-md text-muted-foreground">
            Upload your policies, manuals, and meeting recordings — then ask
            questions with AI that cites your own data.
          </p>

          <div className="mt-12 space-y-6">
            {highlights.map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.title} className="flex gap-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-medium">{item.title}</p>
                    <p className="text-sm text-muted-foreground">
                      {item.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="relative z-10 flex items-center gap-2 px-12 pb-8 text-sm text-muted-foreground xl:px-20">
          <Sparkles className="h-4 w-4 text-primary" />
          Trusted by enterprise teams worldwide
        </div>
      </div>

      <div className="flex w-full flex-col items-center justify-center px-4 py-12 lg:w-1/2">
        <div className="mb-8 flex items-center gap-2 lg:hidden">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <Brain className="h-5 w-5" />
          </div>
          <span className="font-display text-lg font-semibold">Enterprise AI</span>
        </div>
        <div className="w-full max-w-md">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
