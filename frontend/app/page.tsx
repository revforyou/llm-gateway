import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center p-8">
      <div className="max-w-2xl w-full text-center space-y-6">
        <h1 className="text-5xl font-bold tracking-tight">LLM Quality Gateway</h1>
        <p className="text-xl text-gray-400">
          Multi-tenant LLM observability with complexity-based routing,
          async evaluation, A/B experimentation, and drift detection —
          running $0/month, forever.
        </p>
        <div className="flex gap-4 justify-center pt-4">
          <Link
            href="/demo"
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-semibold transition"
          >
            Live Demo
          </Link>
          <a
            href="https://github.com/revforyou/llm-gateway"
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-3 bg-gray-800 hover:bg-gray-700 rounded-lg font-semibold transition"
          >
            GitHub
          </a>
        </div>
        <div className="pt-8 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          {[
            ["~40%", "Cost reduction"],
            ["85+", "Quality score"],
            ["<500ms", "p95 overhead"],
            ["~12%", "Hallucination flag rate"],
          ].map(([val, label]) => (
            <div key={label} className="bg-gray-900 rounded-lg p-4">
              <div className="text-2xl font-bold text-blue-400">{val}</div>
              <div className="text-gray-400 mt-1">{label}</div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
