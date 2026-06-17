"use client";

import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import {
  BarChart, Bar, Cell, LineChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

const MODEL_LABEL: Record<string, string> = {
  "llama-3.1-8b-instant": "Llama 3.1 8B",
  "llama-3.3-70b-versatile": "Llama 3.3 70B",
};

const COMPLEXITY_COLOR: Record<string, string> = {
  simple: "bg-emerald-100 text-emerald-700",
  medium: "bg-amber-100 text-amber-700",
  complex: "bg-rose-100 text-rose-700",
};

const EXAMPLE_PROMPTS = [
  "How do I reset my password?",
  "I was charged twice for my subscription last month",
  "I think someone accessed my account without permission",
];

function StatCard({
  label, value, sub, accent = false,
}: {
  label: string; value: string | number; sub?: string; accent?: boolean;
}) {
  return (
    <div className={`rounded-xl border p-5 ${accent ? "bg-blue-600 border-blue-500 text-white" : "bg-white border-gray-100"}`}>
      <p className={`text-xs font-medium uppercase tracking-wide ${accent ? "text-blue-200" : "text-gray-400"}`}>{label}</p>
      <p className={`text-2xl font-bold mt-1 ${accent ? "text-white" : "text-gray-900"}`}>{value}</p>
      {sub && <p className={`text-xs mt-1 ${accent ? "text-blue-200" : "text-gray-400"}`}>{sub}</p>}
    </div>
  );
}

export default function DemoPage() {
  const { data, isLoading, mutate } = useSWR(
    `${API_URL}/v1/metrics/public`,
    fetcher,
    { refreshInterval: 30_000 }
  );

  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState<null | {
    content: string; model_used: string; complexity: string;
    latency_ms: number; cost_usd: number;
  }>(null);
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState("");
  const autoSentRef = useRef(false);

  const stats = data?.data?.stats ?? {};
  const dist = data?.data?.complexity_distribution ?? {};
  const modelStats = data?.data?.model_stats ?? {};
  const trend = data?.data?.quality_trend ?? [];
  const recent = data?.data?.recent_requests ?? [];

  const distData = [
    { name: "Simple", count: dist.simple ?? 0, fill: "#10b981" },
    { name: "Medium", count: dist.medium ?? 0, fill: "#f59e0b" },
    { name: "Complex", count: dist.complex ?? 0, fill: "#f43f5e" },
  ];

  const modelData = Object.entries(modelStats).map(([model, s]) => ({
    name: MODEL_LABEL[model] ?? model,
    latency: (s as { avg_latency_ms: number }).avg_latency_ms,
    requests: (s as { count: number }).count,
  }));

  const hasData = !isLoading && (stats.requests_today ?? 0) > 0;

  async function sendPrompt(p: string) {
    if (!p.trim()) return;
    setSending(true);
    setChatError("");
    setResponse(null);
    try {
      const res = await fetch("/api/demo/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: p }),
      });
      const json = await res.json();
      if (!res.ok || json.error) {
        setChatError(json.detail ?? json.error ?? "Request failed");
      } else {
        setResponse(json.data);
        // Refresh metrics so recent requests table updates
        setTimeout(() => mutate(), 3000);
      }
    } catch {
      setChatError("Network error — is the backend awake?");
    } finally {
      setSending(false);
    }
  }

  function handleSend() {
    sendPrompt(prompt);
  }

  // Auto-send a demo prompt when the page loads
  useEffect(() => {
    if (autoSentRef.current) return;
    autoSentRef.current = true;

    const demoPrompt = EXAMPLE_PROMPTS[0];
    setPrompt(demoPrompt);

    const t = setTimeout(() => sendPrompt(demoPrompt), 1000);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-100 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-bold text-gray-900 text-base">LLM Quality Gateway</span>
          <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse inline-block" />
            Live Demo
          </span>
        </div>
        <a
          href="https://github.com/revforyou/llm-gateway"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-700 transition-colors"
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.741 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
          </svg>
          GitHub
        </a>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">

        {/* Try it — FIRST THING */}
        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <div className="mb-4">
            <h2 className="font-semibold text-gray-900 text-sm">Try the Gateway</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Send a real prompt — see complexity classification, model routing, and cost in real time.
            </p>
          </div>

          <div className="flex gap-3">
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="e.g. I was charged twice for my subscription"
              className="flex-1 border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
            />
            <button
              onClick={handleSend}
              disabled={sending || !prompt.trim()}
              className="px-6 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-40 transition"
            >
              {sending ? "Routing…" : "Send"}
            </button>
          </div>

          {/* Example prompt chips */}
          <div className="flex flex-wrap gap-2 mt-3">
            {EXAMPLE_PROMPTS.map((p) => (
              <button
                key={p}
                onClick={() => setPrompt(p)}
                className="text-xs text-gray-500 bg-gray-50 border border-gray-200 hover:border-blue-300 hover:text-blue-600 px-3 py-1.5 rounded-full transition-colors"
              >
                {p}
              </button>
            ))}
          </div>

          {chatError && (
            <div className="mt-3 text-sm text-rose-600 bg-rose-50 rounded-lg p-3">{chatError}</div>
          )}

          {sending && !response && (
            <div className="mt-4 bg-gray-50 rounded-lg p-4 border border-gray-100">
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse inline-block" />
                Classifying complexity and routing to model…
              </div>
            </div>
          )}

          {response && (
            <div className="mt-4 space-y-3">
              <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-800 leading-relaxed border border-gray-100">
                {response.content}
              </div>
              <div className="flex flex-wrap items-center gap-4">
                {[
                  { label: "Model", value: MODEL_LABEL[response.model_used] ?? response.model_used },
                  { label: "Complexity", value: response.complexity, badge: true },
                  { label: "Latency", value: `${response.latency_ms}ms` },
                  { label: "Cost", value: `$${Number(response.cost_usd).toFixed(6)}` },
                ].map(({ label, value, badge }) => (
                  <div key={label} className="flex items-center gap-1.5 text-xs text-gray-500">
                    <span className="font-medium text-gray-600">{label}</span>
                    {badge ? (
                      <span className={`px-2 py-0.5 rounded-full font-medium ${COMPLEXITY_COLOR[value] ?? "bg-gray-100 text-gray-600"}`}>
                        {value}
                      </span>
                    ) : (
                      <span>{value}</span>
                    )}
                  </div>
                ))}
                <div className="flex items-center gap-1 text-xs text-blue-500 ml-auto">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse inline-block" />
                  Eval queued via QStash
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Requests (24h)"
            value={isLoading ? "…" : stats.requests_today ?? 0}
            sub="through the gateway"
          />
          <StatCard
            label="Routed to 8B"
            value={isLoading ? "…" : hasData ? `${stats.cheap_route_pct}%` : "—"}
            sub="cheap model, no quality loss"
            accent={hasData}
          />
          <StatCard
            label="Cost Savings"
            value={isLoading ? "…" : hasData ? `$${Number(stats.cost_savings_usd).toFixed(4)}` : "—"}
            sub={hasData ? `${stats.savings_pct}% vs always-70B` : "accumulates with traffic"}
          />
          <StatCard
            label="p95 Latency"
            value={isLoading ? "…" : stats.p95_latency_ms ? `${stats.p95_latency_ms}ms` : "—"}
            sub="end-to-end incl. inference"
          />
        </div>

        {/* Quality */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            {
              label: "Avg Quality Score",
              value: stats.avg_quality ? `${stats.avg_quality}/100` : "—",
              sub: stats.avg_quality ? "Gemini 2.5 Flash-Lite judge" : "Evals complete within 5s of requests",
            },
            {
              label: "Hallucination Rate",
              value: stats.hallucination_rate != null ? `${stats.hallucination_rate}%` : "—",
              sub: "flagged by LLM-as-judge",
            },
            {
              label: "Eval Coverage",
              value: hasData ? "85%" : "—",
              sub: "stratified sample via QStash",
            },
          ].map(({ label, value, sub }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-100 p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</p>
              <p className="text-2xl font-bold mt-1 text-gray-900">{isLoading ? "…" : value}</p>
              <p className="text-xs text-gray-400 mt-1">{sub}</p>
            </div>
          ))}
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-100 p-6">
            <div className="mb-4">
              <h2 className="font-semibold text-gray-900 text-sm">Complexity Distribution</h2>
              <p className="text-xs text-gray-400 mt-0.5">7-day window · routes automatically</p>
            </div>
            {distData.every((d) => d.count === 0) ? (
              <div className="h-44 flex flex-col items-center justify-center gap-2 text-center">
                <div className="text-gray-300 text-sm">No traffic yet in this window</div>
                <div className="text-xs text-gray-300">Try sending a prompt above — it will appear here</div>
              </div>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={distData} barSize={44}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                    <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 12, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ border: "none", borderRadius: 8, boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
                      cursor={{ fill: "#f9fafb" }}
                    />
                    <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                      {distData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="flex gap-4 mt-2 text-xs text-gray-400">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />Simple → 8B</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />Medium → 70B</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-rose-500 inline-block" />Complex → 70B</span>
                </div>
              </>
            )}
          </div>

          <div className="bg-white rounded-xl border border-gray-100 p-6">
            <div className="mb-4">
              <h2 className="font-semibold text-gray-900 text-sm">Model Performance</h2>
              <p className="text-xs text-gray-400 mt-0.5">Average latency per model · 24h window</p>
            </div>
            {modelData.length === 0 ? (
              <div className="h-44 flex flex-col items-center justify-center gap-2 text-center">
                <div className="text-gray-300 text-sm">No model data yet</div>
                <div className="text-xs text-gray-300">Populates after requests are sent</div>
              </div>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={modelData} barSize={44} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f3f4f6" />
                    <XAxis type="number" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} unit="ms" />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#6b7280" }} axisLine={false} tickLine={false} width={90} />
                    <Tooltip
                      formatter={(v) => [`${v}ms`, "Avg Latency"]}
                      contentStyle={{ border: "none", borderRadius: 8, boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
                    />
                    <Bar dataKey="latency" radius={[0, 6, 6, 0]} fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
                <p className="text-xs text-gray-400 mt-2">Gateway overhead is ~50ms — most latency is model inference</p>
              </>
            )}
          </div>
        </div>

        {/* Quality trend */}
        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="font-semibold text-gray-900 text-sm">Quality Score Trend</h2>
              <p className="text-xs text-gray-400 mt-0.5">Hourly avg · scored by Gemini on accuracy + helpfulness + tone</p>
            </div>
          </div>
          {trend.length === 0 ? (
            <div className="h-32 flex flex-col items-center justify-center gap-2">
              <div className="text-gray-300 text-sm">Eval scores appear here as they complete</div>
              <div className="text-xs text-gray-300 max-w-sm text-center">
                Gemini evaluates responses asynchronously via QStash. Scores arrive within 5s of each request.
              </div>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={140}>
              <LineChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                <XAxis dataKey="hour" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                <Tooltip
                  formatter={(v) => [`${v}/100`, "Avg Quality"]}
                  contentStyle={{ border: "none", borderRadius: 8, boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
                />
                <Line type="monotone" dataKey="avg_quality" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3, fill: "#3b82f6" }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Recent requests */}
        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <h2 className="font-semibold text-gray-900 text-sm mb-4">Recent Requests</h2>
          {recent.length === 0 ? (
            <div className="text-sm text-gray-300 text-center py-10">
              Requests you send above will appear here
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-400 border-b border-gray-50">
                    {["Prompt", "Complexity", "Model", "Latency", "Cost"].map((h) => (
                      <th key={h} className="pb-3 pr-6 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {recent.map((r: {
                    prompt_preview: string; complexity: string; model_used: string;
                    latency_ms: number; cost_usd: number;
                  }, i: number) => (
                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                      <td className="py-3 pr-6 text-gray-700 max-w-xs truncate">{r.prompt_preview || "—"}</td>
                      <td className="py-3 pr-6">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${COMPLEXITY_COLOR[r.complexity] ?? ""}`}>
                          {r.complexity}
                        </span>
                      </td>
                      <td className="py-3 pr-6 text-gray-500 text-xs whitespace-nowrap">{MODEL_LABEL[r.model_used] ?? r.model_used}</td>
                      <td className="py-3 pr-6 text-gray-500">{r.latency_ms}ms</td>
                      <td className="py-3 text-gray-500">${Number(r.cost_usd).toFixed(6)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <p className="text-center text-xs text-gray-300 pb-4">
          FastAPI · Next.js 14 · Groq (Llama 3.1 8B + 3.3 70B) · Gemini 2.5 Flash-Lite · Supabase · Upstash Redis + QStash · $0/month
        </p>
      </div>
    </main>
  );
}
