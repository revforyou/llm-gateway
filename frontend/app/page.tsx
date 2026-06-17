import Link from "next/link";

const PIPELINE = [
  {
    step: "01",
    icon: "🔑",
    title: "Auth + Rate Limit",
    detail: "bcrypt key verification with Redis-cached results (60s TTL). Token bucket enforces 60 req/min per key.",
  },
  {
    step: "02",
    icon: "🧠",
    title: "Classify Complexity",
    detail: "Rule-based fast path catches clear escalations instantly. TF-IDF + Logistic Regression handles ambiguous prompts. Predictions cached by prompt hash.",
  },
  {
    step: "03",
    icon: "⚡",
    title: "Route to Model",
    detail: "Simple → Llama 3.1 8B at $0.05/M tokens. Medium/Complex → Llama 3.3 70B at $0.59/M. Confidence threshold prevents mis-routing.",
  },
  {
    step: "04",
    icon: "💬",
    title: "LLM Call",
    detail: "Groq API with tenacity retries (3 attempts, exponential backoff + jitter). Tokens, latency, and attributed cost logged per request.",
  },
  {
    step: "05",
    icon: "📊",
    title: "Async Eval via QStash",
    detail: "Response returns to client immediately. QStash delivers eval job within 1–2s. Gemini scores accuracy, helpfulness, tone. Grounding check via cosine similarity on embeddings.",
  },
  {
    step: "06",
    icon: "✅",
    title: "Dashboard + Experiments",
    detail: "All data queryable per team via RLS-enforced Supabase. A/B experiments auto-conclude with Welch's t-test. Drift monitor runs hourly.",
  },
];

const FEATURES = [
  {
    tag: "ML",
    tagColor: "text-purple-400 bg-purple-500/10 border-purple-500/20",
    title: "Hybrid Complexity Classifier",
    desc: "Two-stage classifier avoids the latency of calling an LLM to classify. Rule-based fast path for unambiguous cases, TF-IDF + LogReg for everything else. Trained on 27k Bitext customer-support examples. Ships as classifier.pkl — no cold-start retraining.",
    bullets: [
      "Predictions cached in Redis by prompt hash (1h TTL)",
      "Confidence thresholds prevent under/over-routing",
      "Weekly retrain loop on eval feedback from production",
    ],
  },
  {
    tag: "Architecture",
    tagColor: "text-blue-400 bg-blue-500/10 border-blue-500/20",
    title: "Async Eval Pipeline",
    desc: "Zero latency added to the critical path. Client gets a response in <500ms. QStash delivers the eval job within 1–2s. Gemini judges accuracy, helpfulness, and tone in parallel with grounding and refusal checks via asyncio.gather.",
    bullets: [
      "Hallucination detection via text-embedding-004 cosine similarity",
      "85% stratified sample rate fits QStash free tier",
      "Nightly backfill job catches any missed evaluations",
    ],
  },
  {
    tag: "Statistics",
    tagColor: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    title: "A/B Experimentation Engine",
    desc: "SHA-256 hash of (experiment_id + request_key) gives deterministic, reproducible variant assignment. No sticky sessions. Welch's t-test runs on every recompute. Auto-concludes at p<0.05 and shifts traffic toward the winner.",
    bullets: [
      "Same input always maps to the same variant",
      "Effect size + p-value stored for audit trail",
      "Traffic shift capped at 60/40 as a guardrail",
    ],
  },
  {
    tag: "Infrastructure",
    tagColor: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    title: "Zero-Cost Persistence",
    desc: "Free-tier services pause on idle. Every layer has a keep-warm mechanism. GitHub Actions pings /health every 5 min (Render), touches Supabase on the same request, Redis is hit on every API call. The system has no single human dependency to stay alive.",
    bullets: [
      "Traffic engine: 12 req / 30 min forever, $0/month",
      "Volume math documented against real free-tier limits",
      "Drift monitor + eval backfill run on schedule via GH Actions",
    ],
  },
];

const STACK = [
  "FastAPI", "Next.js 14", "TypeScript", "Python 3.11",
  "Supabase Postgres", "Upstash Redis", "Upstash QStash",
  "Groq (Llama 3.1 / 3.3)", "Gemini 2.5 Flash-Lite",
  "scikit-learn", "scipy", "Recharts", "Tailwind CSS",
  "GitHub Actions", "Render", "Vercel",
];

export default function Home() {
  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Nav */}
      <nav className="border-b border-white/[0.06] px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <span className="text-sm font-semibold text-white/80 tracking-tight">
            LLM Quality Gateway
          </span>
          <a
            href="https://github.com/revforyou/llm-gateway"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-xs text-white/40 hover:text-white/70 transition-colors"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.741 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
            </svg>
            GitHub
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-6 pt-24 pb-20 text-center">
        <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 rounded-full px-4 py-1.5 text-xs text-blue-400 font-medium mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse inline-block" />
          Live · Free tier · Always on
        </div>

        <h1 className="text-6xl sm:text-7xl font-bold tracking-tight leading-[1.05] mb-6">
          <span className="text-white">LLM Quality</span>
          <br />
          <span className="bg-gradient-to-r from-blue-400 via-cyan-400 to-blue-300 bg-clip-text text-transparent">
            Gateway
          </span>
        </h1>

        <p className="text-lg text-white/50 max-w-2xl mx-auto leading-relaxed mb-10">
          A production-grade observability platform that classifies every request
          by complexity, routes it to the cheapest capable model, and scores every
          response with an async LLM-as-judge pipeline — running at $0/month, forever.
        </p>

        <div className="flex items-center justify-center gap-4 flex-wrap">
          <Link
            href="/demo"
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-semibold text-sm transition-all shadow-lg shadow-blue-600/25"
          >
            View Live Demo
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </Link>
          <a
            href="https://github.com/revforyou/llm-gateway"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-6 py-3 bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-white/70 hover:text-white/90 rounded-lg font-semibold text-sm transition-all"
          >
            View Source
          </a>
        </div>
      </section>

      {/* Stats */}
      <section className="max-w-5xl mx-auto px-6 pb-20">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { val: "~40%", label: "Cost reduction", sub: "vs always-70B routing" },
            { val: "85+", label: "Quality score", sub: "LLM-as-judge via Gemini" },
            { val: "<500ms", label: "p95 overhead", sub: "gateway only, not inference" },
            { val: "~12%", label: "Hallucination rate", sub: "flagged + tracked per request" },
          ].map(({ val, label, sub }) => (
            <div
              key={label}
              className="bg-white/[0.025] border border-white/[0.07] rounded-xl p-5"
            >
              <div className="text-2xl font-bold text-blue-400 tabular-nums">{val}</div>
              <div className="text-white/70 text-sm font-medium mt-1">{label}</div>
              <div className="text-white/25 text-xs mt-0.5">{sub}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline */}
      <section className="max-w-5xl mx-auto px-6 pb-24">
        <div className="mb-10">
          <h2 className="text-2xl font-bold text-white">How a request moves through the system</h2>
          <p className="text-white/35 text-sm mt-2">Every prompt goes through 6 stages before a response is returned</p>
        </div>

        <div className="bg-white/[0.02] border border-white/[0.07] rounded-2xl p-8">
          {PIPELINE.map(({ step, icon, title, detail }, i) => (
            <div key={step} className="flex gap-5 items-start">
              <div className="flex flex-col items-center flex-shrink-0">
                <div className="w-11 h-11 rounded-xl bg-blue-500/[0.08] border border-blue-500/20 flex items-center justify-center text-lg">
                  {icon}
                </div>
                {i < PIPELINE.length - 1 && (
                  <div className="w-px h-8 bg-gradient-to-b from-white/10 to-transparent mt-1" />
                )}
              </div>
              <div className={i < PIPELINE.length - 1 ? "pb-7" : ""}>
                <div className="flex items-center gap-2.5 mb-1.5">
                  <span className="text-[11px] text-white/20 font-mono tracking-widest">{step}</span>
                  <span className="text-white/85 font-semibold text-sm">{title}</span>
                </div>
                <p className="text-white/38 text-sm leading-relaxed">{detail}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="max-w-5xl mx-auto px-6 pb-24">
        <div className="mb-10">
          <h2 className="text-2xl font-bold text-white">Engineering decisions worth talking about</h2>
          <p className="text-white/35 text-sm mt-2">Each piece was built around a real constraint</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {FEATURES.map(({ tag, tagColor, title, desc, bullets }) => (
            <div
              key={title}
              className="bg-white/[0.02] border border-white/[0.07] hover:border-white/[0.15] rounded-xl p-6 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <h3 className="font-semibold text-white/90 text-sm leading-snug pr-3">{title}</h3>
                <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border flex-shrink-0 ${tagColor}`}>
                  {tag}
                </span>
              </div>
              <p className="text-white/40 text-sm leading-relaxed mb-4">{desc}</p>
              <ul className="space-y-1.5">
                {bullets.map((b) => (
                  <li key={b} className="flex items-start gap-2 text-xs text-white/28">
                    <span className="text-blue-500/70 mt-0.5 flex-shrink-0">→</span>
                    {b}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* Stack */}
      <section className="max-w-5xl mx-auto px-6 pb-20">
        <div className="border-t border-white/[0.06] pt-12 text-center">
          <p className="text-[11px] text-white/20 uppercase tracking-[0.2em] mb-6">Built with</p>
          <div className="flex flex-wrap items-center justify-center gap-2.5">
            {STACK.map((s) => (
              <span
                key={s}
                className="text-xs text-white/35 bg-white/[0.03] border border-white/[0.07] px-3 py-1.5 rounded-full"
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.06] px-6 py-6 text-center">
        <p className="text-xs text-white/20">
          Built by Revanth Jyothula ·{" "}
          <a
            href="https://github.com/revforyou/llm-gateway"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white/40 transition-colors"
          >
            github.com/revforyou/llm-gateway
          </a>
        </p>
      </footer>
    </main>
  );
}
