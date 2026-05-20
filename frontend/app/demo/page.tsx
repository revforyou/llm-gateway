"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis,
  Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

function StatCard({
  label,
  value,
  sub,
  color = "text-gray-900",
}: {
  label: string;
  value: string | number | null;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
      <div className="text-sm text-gray-500 font-medium">{label}</div>
      <div className={`text-3xl font-bold mt-2 ${color}`}>
        {value ?? "—"}
      </div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  );
}

const MODEL_SHORT: Record<string, string> = {
  "llama-3.1-8b-instant": "Llama 3.1 8B",
  "llama-3.3-70b-versatile": "Llama 3.3 70B",
};

const COMPLEXITY_COLOR: Record<string, string> = {
  simple: "bg-green-100 text-green-700",
  medium: "bg-yellow-100 text-yellow-700",
  complex: "bg-red-100 text-red-700",
};

export default function DemoPage() {
  const { data, isLoading } = useSWR(
    `${API_URL}/v1/metrics/public`,
    fetcher,
    { refreshInterval: 60_000 }
  );

  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState<null | {
    content: string;
    model_used: string;
    complexity: string;
    latency_ms: number;
    cost_usd: number;
  }>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const stats = data?.data?.stats ?? {};
  const dist = data?.data?.complexity_distribution ?? {};
  const trend = data?.data?.quality_trend ?? [];
  const recent = data?.data?.recent_requests ?? [];

  const distData = [
    { name: "Simple", count: dist.simple ?? 0, fill: "#22c55e" },
    { name: "Medium", count: dist.medium ?? 0, fill: "#eab308" },
    { name: "Complex", count: dist.complex ?? 0, fill: "#ef4444" },
  ];

  async function handleSend() {
    if (!prompt.trim()) return;
    setSending(true);
    setError("");
    setResponse(null);
    try {
      const res = await fetch("/api/demo/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      const json = await res.json();
      if (!res.ok || json.error) {
        setError(json.detail ?? json.error ?? "Request failed");
      } else {
        setResponse(json.data);
      }
    } catch {
      setError("Network error — is the backend awake?");
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="border-b bg-white px-8 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">LLM Gateway — Live Demo</h1>
          <p className="text-sm text-gray-500">Demo team · updates every 60s</p>
        </div>
        <a
          href="/"
          className="text-sm text-blue-600 hover:underline"
        >
          ← Back
        </a>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8 space-y-8">

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="Requests (24h)"
            value={isLoading ? "..." : stats.requests_today ?? 0}
            sub="through the gateway"
          />
          <StatCard
            label="Avg Quality Score"
            value={isLoading ? "..." : stats.avg_quality ? `${stats.avg_quality}/100` : "—"}
            sub="Gemini-judged"
            color={stats.avg_quality >= 80 ? "text-green-600" : "text-yellow-600"}
          />
          <StatCard
            label="Cost Saved (24h)"
            value={
              isLoading ? "..." :
              stats.total_cost_usd != null
                ? `$${Number(stats.total_cost_usd).toFixed(5)}`
                : "—"
            }
            sub="vs always-70B routing"
          />
          <StatCard
            label="p95 Latency"
            value={isLoading ? "..." : stats.p95_latency_ms ? `${stats.p95_latency_ms}ms` : "—"}
            sub="end-to-end"
          />
        </div>

        {/* Charts row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Complexity distribution */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">
              Complexity Distribution (7 days)
            </h2>
            {distData.every((d) => d.count === 0) ? (
              <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
                No data yet — traffic engine runs every 30 min
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={distData} barSize={40}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {distData.map((d, i) => (
                      <rect key={i} fill={d.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
            <p className="text-xs text-gray-400 mt-3">
              Simple → Llama 3.1 8B · Medium/Complex → Llama 3.3 70B
            </p>
          </div>

          {/* Quality trend */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">
              Quality Score Trend (24h)
            </h2>
            {trend.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
                No eval data yet — evals run async after each request
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                  <XAxis dataKey="hour" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => [`${v}/100`, "Avg Quality"]} />
                  <Line
                    type="monotone"
                    dataKey="avg_quality"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
            <p className="text-xs text-gray-400 mt-3">
              Scored by Gemini 2.5 Flash-Lite: accuracy + helpfulness + tone
            </p>
          </div>
        </div>

        {/* Try it */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">Try the Gateway</h2>
          <p className="text-xs text-gray-400 mb-4">
            Send a real prompt — the gateway classifies complexity, routes to the right model, and queues an async eval.
          </p>
          <div className="flex gap-3">
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="e.g. I was charged twice for my subscription last week"
              className="flex-1 border border-gray-200 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleSend}
              disabled={sending || !prompt.trim()}
              className="px-5 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
            >
              {sending ? "Sending..." : "Send"}
            </button>
          </div>

          {error && (
            <div className="mt-3 text-sm text-red-600 bg-red-50 rounded-lg p-3">{error}</div>
          )}

          {response && (
            <div className="mt-4 space-y-3">
              <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-800 leading-relaxed">
                {response.content}
              </div>
              <div className="flex gap-4 text-xs text-gray-500 flex-wrap">
                <span>
                  <span className="font-medium">Model:</span>{" "}
                  {MODEL_SHORT[response.model_used] ?? response.model_used}
                </span>
                <span>
                  <span className="font-medium">Complexity:</span>{" "}
                  <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${COMPLEXITY_COLOR[response.complexity] ?? ""}`}>
                    {response.complexity}
                  </span>
                </span>
                <span>
                  <span className="font-medium">Latency:</span> {response.latency_ms}ms
                </span>
                <span>
                  <span className="font-medium">Cost:</span> ${Number(response.cost_usd).toFixed(6)}
                </span>
                <span className="text-blue-500">Eval queued via QStash →</span>
              </div>
            </div>
          )}
        </div>

        {/* Recent requests */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Recent Requests</h2>
          {recent.length === 0 ? (
            <div className="text-sm text-gray-400 text-center py-8">
              No requests yet — traffic engine populates this every 30 min
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-400 border-b">
                    <th className="pb-2 pr-4 font-medium">Prompt</th>
                    <th className="pb-2 pr-4 font-medium">Complexity</th>
                    <th className="pb-2 pr-4 font-medium">Model</th>
                    <th className="pb-2 pr-4 font-medium">Latency</th>
                    <th className="pb-2 font-medium">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((r: {
                    prompt_preview: string;
                    complexity: string;
                    model_used: string;
                    latency_ms: number;
                    cost_usd: number;
                    created_at: string;
                  }, i: number) => (
                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
                      <td className="py-2 pr-4 text-gray-700 max-w-xs truncate">
                        {r.prompt_preview || "—"}
                      </td>
                      <td className="py-2 pr-4">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${COMPLEXITY_COLOR[r.complexity] ?? ""}`}>
                          {r.complexity}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-gray-500 text-xs">
                        {MODEL_SHORT[r.model_used] ?? r.model_used}
                      </td>
                      <td className="py-2 pr-4 text-gray-500">{r.latency_ms}ms</td>
                      <td className="py-2 text-gray-500">${Number(r.cost_usd).toFixed(6)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Architecture note */}
        <div className="text-center text-xs text-gray-400 pb-4 space-y-1">
          <p>Groq (Llama 3.1 8B + 3.3 70B) · Gemini 2.5 Flash-Lite · Supabase · Upstash Redis + QStash · Render · Vercel</p>
          <p>$0/month · GitHub Actions keep-warm · traffic engine · backfill eval</p>
        </div>
      </div>
    </main>
  );
}
