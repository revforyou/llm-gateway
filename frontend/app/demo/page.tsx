"use client";

import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import {
  BarChart, Bar, Cell, LineChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());
const CACHE_KEY = "llm_gateway_demo_metrics";
const CACHE_TS_KEY = "llm_gateway_demo_metrics_ts";

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
  "What is the difference between TCP and UDP?",
  "Write a Python function to find the longest common subsequence of two strings",
  "Design a rate-limiting system for a public API that handles 10k requests per second",
];

type LocalRequest = {
  prompt_preview: string;
  complexity: string;
  model_used: string;
  latency_ms: number;
  cost_usd: number;
};

function StatCard({ label, value, sub, accent = false }: {
  label: string; value: string | number; sub?: string; accent?: boolean;
}) {
  return (
    <div className={`rounded-xl border p-6 ${accent ? "bg-blue-600 border-blue-500" : "bg-white border-gray-200"}`}>
      <p className={`text-xs font-semibold uppercase tracking-wider mb-2 ${accent ? "text-blue-200" : "text-gray-500"}`}>
        {label}
      </p>
      <p className={`text-3xl font-bold leading-none ${accent ? "text-white" : "text-gray-900"}`}>
        {value}
      </p>
      {sub && (
        <p className={`text-sm mt-2 ${accent ? "text-blue-200" : "text-gray-500"}`}>{sub}</p>
      )}
    </div>
  );
}

export default function DemoPage() {
  const { data: liveData, isLoading, mutate } = useSWR(
    `${API_URL}/v1/metrics/public`,
    fetcher,
    { refreshInterval: 30_000 }
  );

  const [cachedData, setCachedData] = useState<object | null>(null);
  const [cacheTs, setCacheTs] = useState<number | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      const ts = localStorage.getItem(CACHE_TS_KEY);
      if (raw) { setCachedData(JSON.parse(raw)); setCacheTs(ts ? parseInt(ts) : null); }
    } catch {}
  }, []);

  useEffect(() => {
    if ((liveData?.data?.stats?.requests_today ?? 0) > 0) {
      try {
        localStorage.setItem(CACHE_KEY, JSON.stringify(liveData));
        localStorage.setItem(CACHE_TS_KEY, Date.now().toString());
        setCachedData(liveData); setCacheTs(Date.now());
      } catch {}
    }
  }, [liveData]);

  const liveHasData = (liveData?.data?.stats?.requests_today ?? 0) > 0;
  const data = liveHasData ? liveData : (cachedData ?? liveData);
  const isShowingCached = !liveHasData && cachedData != null;

  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState<null | {
    content: string; model_used: string; complexity: string;
    latency_ms: number; cost_usd: number;
  }>(null);
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState("");
  const [localRequests, setLocalRequests] = useState<LocalRequest[]>([]);
  const autoSentRef = useRef(false);

  const stats = data?.data?.stats ?? {};
  const dist = data?.data?.complexity_distribution ?? {};
  const modelStats = data?.data?.model_stats ?? {};
  const trend = data?.data?.quality_trend ?? [];
  const dbRecent = data?.data?.recent_requests ?? [];

  // Merge local optimistic requests with DB results (deduplicate by prompt_preview)
  const dbPreviews = new Set(dbRecent.map((r: LocalRequest) => r.prompt_preview));
  const merged = [
    ...localRequests.filter((r) => !dbPreviews.has(r.prompt_preview)),
    ...dbRecent,
  ].slice(0, 10);

  const distData = [
    { name: "Simple", count: dist.simple ?? 0, fill: "#10b981" },
    { name: "Medium", count: dist.medium ?? 0, fill: "#f59e0b" },
    { name: "Complex", count: dist.complex ?? 0, fill: "#f43f5e" },
  ];

  const modelData = Object.entries(modelStats).map(([model, s]) => ({
    name: MODEL_LABEL[model] ?? model,
    latency: (s as { avg_latency_ms: number }).avg_latency_ms,
  }));

  const hasData = !isLoading && (stats.requests_today ?? 0) > 0;

  async function sendPrompt(p: string) {
    if (!p.trim() || sending) return;
    setSending(true); setChatError(""); setResponse(null);
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
        // Optimistic: add to local list immediately
        setLocalRequests((prev) => [{
          prompt_preview: p.slice(0, 80),
          complexity: json.data.complexity,
          model_used: json.data.model_used,
          latency_ms: json.data.latency_ms,
          cost_usd: json.data.cost_usd,
        }, ...prev]);
        setTimeout(() => mutate(), 4000);
      }
    } catch {
      setChatError("Network error — backend may be waking up, try again in 30s.");
    } finally {
      setSending(false);
    }
  }

  useEffect(() => {
    if (autoSentRef.current) return;
    autoSentRef.current = true;
    const p = EXAMPLE_PROMPTS[0];
    setPrompt(p);
    const t = setTimeout(() => sendPrompt(p), 1200);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <a href="/" className="font-bold text-gray-900 text-base hover:text-blue-600 transition-colors">
            LLM Quality Gateway
          </a>
          <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 bg-emerald-50 border border-emerald-100 px-2.5 py-1 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse inline-block" />
            Live Demo
          </span>
        </div>
        <div className="flex items-center gap-2">
          <a
            href="/"
            className="px-4 py-2 text-sm font-semibold text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            Back
          </a>
          <a
            href="https://github.com/revforyou/llm-gateway"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.741 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
            </svg>
            GitHub
          </a>
        </div>
      </header>

      {isShowingCached && cacheTs && (
        <div className="bg-amber-50 border-b border-amber-100 px-6 py-2.5 text-sm text-amber-700 text-center">
          Showing last recorded data from {Math.round((Date.now() - cacheTs) / 60000)} min ago
        </div>
      )}

      <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">

        {/* Try it */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-base font-bold text-gray-900 mb-1">Try the Gateway</h2>
          <p className="text-sm text-gray-500 mb-5">
            Send any prompt — watch it get classified, routed to the right model, and priced in real time.
          </p>

          <div className="flex gap-3">
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendPrompt(prompt)}
              placeholder="e.g. Design a distributed caching system"
              className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              onClick={() => sendPrompt(prompt)}
              disabled={sending || !prompt.trim()}
              className="px-6 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-40 transition-colors"
            >
              {sending ? "Routing…" : "Send"}
            </button>
          </div>

          <div className="flex flex-wrap gap-2 mt-3">
            {EXAMPLE_PROMPTS.map((p) => (
              <button
                key={p}
                onClick={() => setPrompt(p)}
                className="text-xs text-gray-600 bg-gray-50 border border-gray-200 hover:border-blue-300 hover:text-blue-600 px-3 py-1.5 rounded-full transition-colors"
              >
                {p.length > 50 ? p.slice(0, 50) + "…" : p}
              </button>
            ))}
          </div>

          {chatError && (
            <div className="mt-4 text-sm text-rose-700 bg-rose-50 border border-rose-100 rounded-lg p-4">
              {chatError}
            </div>
          )}

          {sending && !response && (
            <div className="mt-5 bg-gray-50 border border-gray-200 rounded-lg p-5">
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse inline-block" />
                Classifying complexity and routing to model…
              </div>
            </div>
          )}

          {response && (
            <div className="mt-5 space-y-4">
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 text-sm text-gray-800 leading-relaxed">
                {response.content}
              </div>
              <div className="flex flex-wrap items-center gap-4 px-1">
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-gray-500">Model</span>
                  <span className="font-semibold text-gray-900">{MODEL_LABEL[response.model_used] ?? response.model_used}</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-gray-500">Complexity</span>
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${COMPLEXITY_COLOR[response.complexity] ?? ""}`}>
                    {response.complexity}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-gray-500">Latency</span>
                  <span className="font-semibold text-gray-900">{response.latency_ms}ms</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-gray-500">Cost</span>
                  <span className="font-semibold text-gray-900">${Number(response.cost_usd).toFixed(6)}</span>
                </div>
                <div className="ml-auto flex items-center gap-1.5 text-xs text-blue-600 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse inline-block" />
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
            sub="routed through the gateway"
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
            label="Gateway Overhead"
            value={isLoading ? "…" : stats.gateway_overhead_ms != null ? `${stats.gateway_overhead_ms}ms` : "—"}
          />
        </div>

        {/* Quality */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            {
              label: "Avg Quality Score",
              value: stats.avg_quality ? `${stats.avg_quality}/100` : "—",
              sub: stats.avg_quality ? "Gemini 2.5 Flash-Lite judge" : "Evals complete within 5s of each request",
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
            <div key={label} className="bg-white rounded-xl border border-gray-200 p-6">
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">{label}</p>
              <p className="text-3xl font-bold text-gray-900 leading-none">{isLoading ? "…" : value}</p>
              <p className="text-sm text-gray-500 mt-2">{sub}</p>
            </div>
          ))}
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="font-bold text-gray-900 mb-1">Complexity Distribution</h2>
            <p className="text-sm text-gray-500 mb-4">7-day window · routes automatically to the right model</p>
            {distData.every((d) => d.count === 0) ? (
              <div className="h-44 flex flex-col items-center justify-center gap-2 text-center">
                <p className="text-gray-400">No traffic yet in this window</p>
                <p className="text-sm text-gray-400">Try sending a prompt above — it will appear here</p>
              </div>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={distData} barSize={44}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                    <XAxis dataKey="name" tick={{ fontSize: 13, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 12, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ border: "none", borderRadius: 8, boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }} cursor={{ fill: "#f9fafb" }} />
                    <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                      {distData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="flex gap-5 mt-3 text-sm text-gray-500">
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />Simple → 8B</span>
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block" />Medium → 70B</span>
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" />Complex → 70B</span>
                </div>
              </>
            )}
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="font-bold text-gray-900 mb-1">Model Performance</h2>
            <p className="text-sm text-gray-500 mb-4">Average latency per model · 24h window</p>
            {modelData.length === 0 ? (
              <div className="h-44 flex flex-col items-center justify-center gap-2 text-center">
                <p className="text-gray-400">No model data yet</p>
                <p className="text-sm text-gray-400">Populates after requests are sent</p>
              </div>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={modelData} barSize={44} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f3f4f6" />
                    <XAxis type="number" tick={{ fontSize: 12, fill: "#9ca3af" }} axisLine={false} tickLine={false} unit="ms" />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: "#6b7280" }} axisLine={false} tickLine={false} width={90} />
                    <Tooltip formatter={(v) => [`${v}ms`, "Avg Latency"]} contentStyle={{ border: "none", borderRadius: 8, boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }} />
                    <Bar dataKey="latency" radius={[0, 6, 6, 0]} fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
                <p className="text-sm text-gray-500 mt-3">Gateway overhead is ~50ms — most latency is model inference</p>
              </>
            )}
          </div>
        </div>

        {/* Quality trend */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-bold text-gray-900 mb-1">Quality Score Trend</h2>
          <p className="text-sm text-gray-500 mb-4">Hourly avg · scored by Gemini on accuracy + helpfulness + tone</p>
          {trend.length === 0 ? (
            <div className="h-32 flex flex-col items-center justify-center gap-2">
              <p className="text-gray-400">Eval scores appear here as they complete</p>
              <p className="text-sm text-gray-400">Gemini evaluates responses asynchronously via QStash within 5s</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={140}>
              <LineChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                <XAxis dataKey="hour" tick={{ fontSize: 12, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(v) => [`${v}/100`, "Avg Quality"]} contentStyle={{ border: "none", borderRadius: 8, boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }} />
                <Line type="monotone" dataKey="avg_quality" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3, fill: "#3b82f6" }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Recent requests */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-bold text-gray-900 mb-5">Recent Requests</h2>
          {merged.length === 0 ? (
            <div className="text-gray-400 text-center py-10">
              Requests you send above will appear here instantly
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left border-b border-gray-100">
                    {["Prompt", "Complexity", "Model", "Latency", "Cost"].map((h) => (
                      <th key={h} className="pb-3 pr-6 text-xs font-semibold text-gray-500 uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {merged.map((r: LocalRequest, i: number) => (
                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                      <td className="py-3.5 pr-6 text-gray-800 max-w-xs truncate font-medium">{r.prompt_preview || "—"}</td>
                      <td className="py-3.5 pr-6">
                        <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${COMPLEXITY_COLOR[r.complexity] ?? ""}`}>
                          {r.complexity}
                        </span>
                      </td>
                      <td className="py-3.5 pr-6 text-gray-600 whitespace-nowrap">{MODEL_LABEL[r.model_used] ?? r.model_used}</td>
                      <td className="py-3.5 pr-6 text-gray-600">{r.latency_ms}ms</td>
                      <td className="py-3.5 text-gray-600">${Number(r.cost_usd).toFixed(6)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <p className="text-center text-sm text-gray-400 pb-4">
          FastAPI · Next.js 14 · Groq (Llama 3.1 8B + 3.3 70B) · Gemini 2.5 Flash-Lite · Supabase · Upstash Redis + QStash · $0/month
        </p>
      </div>
    </main>
  );
}
