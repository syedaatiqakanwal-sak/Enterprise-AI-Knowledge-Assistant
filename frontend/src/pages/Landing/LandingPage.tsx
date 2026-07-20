import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Brain,
  Check,
  ChevronDown,
  Eye,
  FileText,
  MessageSquare,
  Mic,
  ScanText,
  Shield,
  Sparkles,
  Star,
  Zap,
} from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/common/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/common/Card";
import { cn } from "@/lib/utils";

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.5 },
};

const features = [
  {
    icon: MessageSquare,
    title: "RAG Chat",
    description:
      "Ask questions and get answers grounded in your uploaded company documents with source citations.",
  },
  {
    icon: FileText,
    title: "Document Intelligence",
    description:
      "Ingest PDFs, Word, Excel, PowerPoint, CSV, and web content into a unified knowledge base.",
  },
  {
    icon: Mic,
    title: "Meeting Intelligence",
    description:
      "Transcribe and summarize MP3/MP4 recordings with action items and searchable transcripts.",
  },
  {
    icon: ScanText,
    title: "OCR Pipeline",
    description:
      "Extract text from scanned documents and images with structured JSON export.",
  },
  {
    icon: Eye,
    title: "Vision AI",
    description:
      "Detect objects, read labels, and generate descriptions from uploaded images.",
  },
  {
    icon: Shield,
    title: "Enterprise Security",
    description:
      "Role-based access, audit logs, and data isolation designed for regulated industries.",
  },
];

const steps = [
  {
    step: "01",
    title: "Upload your data",
    description: "Drag and drop documents, recordings, and images into secure storage.",
  },
  {
    step: "02",
    title: "AI indexes knowledge",
    description: "Embeddings, OCR, and vision models process your content automatically.",
  },
  {
    step: "03",
    title: "Chat with confidence",
    description: "Ask natural language questions and receive cited, company-specific answers.",
  },
];

const capabilities = [
  "Llama 3 & Gemini LLM support",
  "Vector search with Qdrant",
  "Whisper audio transcription",
  "YOLO object detection",
  "PaddleOCR document parsing",
  "LangChain agent workflows",
];

const plans = [
  {
    name: "Starter",
    price: "$49",
    period: "/user/mo",
    description: "For small teams getting started with AI knowledge.",
    features: ["Up to 10 GB storage", "5 users", "RAG chat", "Email support"],
    highlighted: false,
  },
  {
    name: "Business",
    price: "$99",
    period: "/user/mo",
    description: "Full platform for growing enterprises.",
    features: [
      "Up to 100 GB storage",
      "Unlimited users",
      "OCR, Vision & Meetings",
      "Priority support",
      "Analytics dashboard",
    ],
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "Dedicated infrastructure and SLA for large orgs.",
    features: [
      "Unlimited storage",
      "SSO & SAML",
      "Dedicated AI models",
      "On-premise option",
      "24/7 support",
    ],
    highlighted: false,
  },
];

const testimonials = [
  {
    quote:
      "We reduced onboarding time by 40% because new hires can ask our AI assistant instead of hunting through SharePoint.",
    author: "Sarah Chen",
    role: "VP Operations, NexaCorp",
  },
  {
    quote:
      "Meeting summaries alone saved our legal team hundreds of hours per quarter. The ROI was immediate.",
    author: "Marcus Webb",
    role: "General Counsel, Atlas Industries",
  },
  {
    quote:
      "Finally, an AI product that answers from our data — not the internet. Compliance approved it in two weeks.",
    author: "Priya Sharma",
    role: "CISO, Meridian Health",
  },
];

const faqs = [
  {
    q: "Where is our data stored?",
    a: "Data is stored in encrypted storage with tenant isolation. Enterprise plans support dedicated VPC and on-premise deployment.",
  },
  {
    q: "Does the AI use our data to train public models?",
    a: "No. Your documents are used only for your organization's RAG pipeline. We never train foundation models on customer data.",
  },
  {
    q: "What file formats are supported?",
    a: "PDF, DOCX, XLSX, PPTX, CSV, TXT, MP3, MP4, PNG, JPG, and scanned documents via OCR.",
  },
  {
    q: "Can we integrate with existing tools?",
    a: "Yes. REST API, webhooks, and enterprise SSO integrations are available on Business and Enterprise plans.",
  },
];

export function LandingPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  return (
    <div className="min-h-screen bg-background">
      <nav className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/15 text-primary">
              <Brain className="h-5 w-5" />
            </div>
            <span className="font-display text-lg font-semibold">Enterprise AI</span>
          </Link>
          <div className="flex items-center gap-2 sm:gap-3">
            <Button asChild variant="ghost" size="sm">
              <Link to="/login">User Login</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to="/admin/login">Admin Login</Link>
            </Button>
            <Button asChild size="sm">
              <Link to="/register">Register</Link>
            </Button>
          </div>
        </div>
      </nav>

      <section className="relative overflow-hidden px-4 pb-24 pt-20 sm:px-6 lg:px-8">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/10 via-transparent to-transparent" />
        <div className="absolute left-1/2 top-0 h-[500px] w-[800px] -translate-x-1/2 rounded-full bg-primary/5 blur-3xl" />
        <motion.div
          className="relative mx-auto max-w-4xl text-center"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-1.5 text-sm text-primary">
            <Sparkles className="h-4 w-4" />
            Enterprise-grade AI knowledge platform
          </div>
          <h1 className="font-display text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
            Enterprise AI Knowledge Assistant
          </h1>
          <p className="mt-4 text-xl text-primary sm:text-2xl">
            Chat with your Company&apos;s Knowledge
          </p>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
            Upload policies, manuals, and meeting recordings — then ask questions
            with AI that cites your own data, not the public internet.
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Button asChild size="lg">
              <Link to="/login">
                User Portal
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link to="/admin/login">Admin Portal</Link>
            </Button>
            <Button asChild variant="ghost" size="lg">
              <Link to="/register">Create account</Link>
            </Button>
          </div>
          <div className="mx-auto mt-12 grid max-w-2xl gap-4 sm:grid-cols-2 text-left">
            <Link
              to="/login"
              className="rounded-xl border border-border bg-card/60 p-5 transition hover:border-primary/40 hover:shadow-glow"
            >
              <MessageSquare className="mb-2 h-6 w-6 text-primary" />
              <h3 className="font-display font-semibold">User Portal</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                ChatGPT-style assistant. Chat, history, and profile only.
              </p>
            </Link>
            <Link
              to="/admin/login"
              className="rounded-xl border border-border bg-card/60 p-5 transition hover:border-primary/40 hover:shadow-glow"
            >
              <Shield className="mb-2 h-6 w-6 text-primary" />
              <h3 className="font-display font-semibold">Admin Portal</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Enterprise Admin Center — users, documents, analytics, and more.
              </p>
            </Link>
          </div>
        </motion.div>
      </section>

      <section className="border-t border-border/60 px-4 py-24 sm:px-6 lg:px-8">
        <motion.div className="mx-auto max-w-7xl" {...fadeUp}>
          <div className="text-center">
            <h2 className="font-display text-3xl font-bold sm:text-4xl">
              Everything you need
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-muted-foreground">
              A complete AI knowledge stack built for enterprise teams who need
              accuracy, security, and speed.
            </p>
          </div>
          <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <Card
                  key={feature.title}
                  className="border-border/60 bg-card/50 transition-colors hover:border-primary/30"
                >
                  <CardHeader>
                    <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <Icon className="h-5 w-5" />
                    </div>
                    <CardTitle>{feature.title}</CardTitle>
                    <CardDescription>{feature.description}</CardDescription>
                  </CardHeader>
                </Card>
              );
            })}
          </div>
        </motion.div>
      </section>

      <section className="border-t border-border/60 bg-muted/20 px-4 py-24 sm:px-6 lg:px-8">
        <motion.div className="mx-auto max-w-7xl" {...fadeUp}>
          <div className="text-center">
            <h2 className="font-display text-3xl font-bold sm:text-4xl">
              How it works
            </h2>
            <p className="mt-4 text-muted-foreground">
              From upload to insight in three simple steps
            </p>
          </div>
          <div className="mt-16 grid gap-8 md:grid-cols-3">
            {steps.map((item) => (
              <div key={item.step} className="relative text-center">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/15 font-display text-lg font-bold text-primary">
                  {item.step}
                </div>
                <h3 className="mt-6 font-display text-xl font-semibold">
                  {item.title}
                </h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </motion.div>
      </section>

      <section className="border-t border-border/60 px-4 py-24 sm:px-6 lg:px-8">
        <motion.div className="mx-auto max-w-7xl" {...fadeUp}>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <div>
              <h2 className="font-display text-3xl font-bold sm:text-4xl">
                AI Capabilities
              </h2>
              <p className="mt-4 text-muted-foreground">
                Powered by production-grade models and infrastructure designed
                for scale and compliance.
              </p>
              <ul className="mt-8 space-y-3">
                {capabilities.map((cap) => (
                  <li key={cap} className="flex items-center gap-3">
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/15">
                      <Zap className="h-3.5 w-3.5 text-primary" />
                    </div>
                    <span className="text-sm">{cap}</span>
                  </li>
                ))}
              </ul>
            </div>
            <Card className="border-primary/20 bg-gradient-to-br from-primary/10 to-card">
              <CardContent className="p-8">
                <div className="space-y-4">
                  <div className="rounded-lg bg-background/60 p-4">
                    <p className="text-sm text-muted-foreground">You asked:</p>
                    <p className="mt-1 font-medium">
                      What is our remote work policy for EU employees?
                    </p>
                  </div>
                  <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
                    <p className="text-sm text-primary">AI Assistant</p>
                    <p className="mt-2 text-sm">
                      EU employees may work remotely up to 3 days per week per
                      HR Policy §4.2 (updated Jan 2025). Manager approval required.
                    </p>
                    <p className="mt-3 text-xs text-muted-foreground">
                      Sources: HR-Remote-Policy-2025.pdf, p. 12
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </motion.div>
      </section>

      <section className="border-t border-border/60 bg-muted/20 px-4 py-24 sm:px-6 lg:px-8">
        <motion.div className="mx-auto max-w-7xl" {...fadeUp}>
          <div className="text-center">
            <h2 className="font-display text-3xl font-bold sm:text-4xl">
              Simple, transparent pricing
            </h2>
            <p className="mt-4 text-muted-foreground">
              Choose the plan that fits your organization
            </p>
          </div>
          <div className="mt-16 grid gap-8 lg:grid-cols-3">
            {plans.map((plan) => (
              <Card
                key={plan.name}
                className={cn(
                  "relative border-border/60",
                  plan.highlighted &&
                    "border-primary/50 shadow-lg shadow-primary/10"
                )}
              >
                {plan.highlighted && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-0.5 text-xs font-medium text-primary-foreground">
                    Most popular
                  </div>
                )}
                <CardHeader>
                  <CardTitle>{plan.name}</CardTitle>
                  <CardDescription>{plan.description}</CardDescription>
                  <div className="pt-4">
                    <span className="font-display text-4xl font-bold">
                      {plan.price}
                    </span>
                    <span className="text-muted-foreground">{plan.period}</span>
                  </div>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3">
                    {plan.features.map((f) => (
                      <li key={f} className="flex items-center gap-2 text-sm">
                        <Check className="h-4 w-4 shrink-0 text-primary" />
                        {f}
                      </li>
                    ))}
                  </ul>
                  <Button
                    asChild
                    className="mt-8 w-full"
                    variant={plan.highlighted ? "default" : "outline"}
                  >
                    <Link to="/register">Get started</Link>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </motion.div>
      </section>

      <section className="border-t border-border/60 px-4 py-24 sm:px-6 lg:px-8">
        <motion.div className="mx-auto max-w-7xl" {...fadeUp}>
          <div className="text-center">
            <h2 className="font-display text-3xl font-bold sm:text-4xl">
              Trusted by enterprise teams
            </h2>
          </div>
          <div className="mt-16 grid gap-8 md:grid-cols-3">
            {testimonials.map((t) => (
              <Card key={t.author} className="border-border/60">
                <CardContent className="pt-6">
                  <div className="mb-4 flex gap-1">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Star
                        key={i}
                        className="h-4 w-4 fill-primary text-primary"
                      />
                    ))}
                  </div>
                  <p className="text-sm leading-relaxed">&ldquo;{t.quote}&rdquo;</p>
                  <div className="mt-6">
                    <p className="font-medium">{t.author}</p>
                    <p className="text-sm text-muted-foreground">{t.role}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </motion.div>
      </section>

      <section className="border-t border-border/60 bg-muted/20 px-4 py-24 sm:px-6 lg:px-8">
        <motion.div className="mx-auto max-w-3xl" {...fadeUp}>
          <div className="text-center">
            <h2 className="font-display text-3xl font-bold sm:text-4xl">
              Frequently asked questions
            </h2>
          </div>
          <div className="mt-12 space-y-3">
            {faqs.map((faq, index) => (
              <div
                key={faq.q}
                className="overflow-hidden rounded-xl border border-border bg-card"
              >
                <button
                  type="button"
                  onClick={() =>
                    setOpenFaq(openFaq === index ? null : index)
                  }
                  className="flex w-full items-center justify-between px-6 py-4 text-left"
                >
                  <span className="font-medium">{faq.q}</span>
                  <ChevronDown
                    className={cn(
                      "h-5 w-5 shrink-0 text-muted-foreground transition-transform",
                      openFaq === index && "rotate-180"
                    )}
                  />
                </button>
                {openFaq === index && (
                  <div className="border-t border-border px-6 pb-4 pt-2 text-sm text-muted-foreground">
                    {faq.a}
                  </div>
                )}
              </div>
            ))}
          </div>
        </motion.div>
      </section>

      <footer className="border-t border-border px-4 py-12 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 sm:flex-row">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary" />
            <span className="font-display font-semibold">Enterprise AI</span>
          </div>
          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} Enterprise AI Knowledge Assistant. All
            rights reserved.
          </p>
          <div className="flex gap-6 text-sm text-muted-foreground">
            <Link to="/login" className="hover:text-foreground">
              Login
            </Link>
            <Link to="/register" className="hover:text-foreground">
              Register
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
