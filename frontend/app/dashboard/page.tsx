"use client";

import { useState } from "react";
import useSWR from "swr";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function fetcher(url: string, apiKey: string) {
  return fetch(url, { headers: { Authorization: `Bearer ${apiKey}` } }).then((r) => r.json());
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

export default function DashboardPage() {
  const [apiKey, setApiKey] = useState("");
  const [submittedKey, setSubmittedKey] = useState("");
  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState<null | {
    content: string;
    model_used: string;
    complexity: string;
    latency_ms: number;
    cost_usd: number;
    eval_status: string;
  }>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const { data: overviewData } = useSWR(
    submittedKey ? [`${API_URL}/v1/metrics/overview`, submittedKey] : null,
    ([url, key]) => fetcher(url, key),
    { refreshInterval: 30_000 }
  );

  const { data: distData } = useSWR(
    submittedKey ? [`${API_URL}/v1/metrics/distribution`, submittedKey] : null,
    ([url, key]) => fetcher(url, key),
    { refreshInterval: 30_000 }
  );

  const stats = overviewData?.data ?? {};
  const dist = distData?.data?.counts ?? {};
  const distChartData = [
    { name: "Simple", count: dist.simple ?? 0 },
    { name: "Medium", count: dist.medium ?? 0 },
    { name: "Complex", count: dist.complex ?? 0 },
  ];

  async function handleSend() {
    if (!prompt.trim() || !submittedKey) return;
    setSending(true);
    setError("");
    setResponse(null);
    try {
      const res = await fetch(`${API_URL}/v1/chat`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${submittedKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ prompt }),
      });
      const json = await res.json();
      if (!res.ok || json.error) {
        setError(json.detail ?? json.error?.message ?? "Request failed");
      } else {
        setResponse(json.data);
      }
    } catch {
      setError("Network error");
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="border-b bg-white px-8 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">Dashboard</h1>
        <a href="/demo" className="text-sm text-blue-600 hover:underline">
          View public demo →
        </a>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">

        {/* API Key input */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Your API Key</h2>
          <div className="flex gap-3">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk_live_..."
              className="flex-1 border border-gray-200 rounded-lg px-4 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={() => setSubmittedKey(apiKey)}
              className="px-5 py-2 bg-gray-900 text-white text-sm font-semibold rounded-lg hover:bg-gray-700 transition"
            >
              Connect
            </button>
          </div>
          {submittedKey && (
            <p className="text-xs text-green-600 mt-2">
              ✓ Connected — metrics loading below
            </p>
          )}
        </div>

        {submittedKey && (
          <>
            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "Requests (24h)", value: stats.requests_today ?? "—" },
                {
                  label: "Avg Quality",
                  value: stats.avg_quality ? `${stats.avg_quality}/100` : "—",
                },
                {
                  label: "Cost (24h)",
                  value: stats.total_cost_usd != null
                    ? `$${Number(stats.total_cost_usd).toFixed(5)}`
                    : "—",
                },
                {
                  label: "p95 Latency",
                  value: stats.p95_latency_ms ? `${stats.p95_latency_ms}ms` : "—",
                },
              ].map(({ label, value }) => (
                <div key={label} className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                  <div className="text-xs text-gray-500 font-medium">{label}</div>
                  <div className="text-2xl font-bold text-gray-900 mt-1">{value}</div>
                </div>
              ))}
            </div>

            {/* Distribution chart */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">
                Complexity Distribution (7 days)
              </h2>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={distChartData} barSize={40}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Chat */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
              <h2 className="text-sm font-semibold text-gray-700 mb-3">Send a Request</h2>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSend()}
                  placeholder="Type a prompt..."
                  className="flex-1 border border-gray-200 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={handleSend}
                  disabled={sending || !prompt.trim()}
                  className="px-5 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
                >
                  {sending ? "..." : "Send"}
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
                    <span><span className="font-medium">Model:</span> {MODEL_SHORT[response.model_used] ?? response.model_used}</span>
                    <span>
                      <span className="font-medium">Complexity:</span>{" "}
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${COMPLEXITY_COLOR[response.complexity] ?? ""}`}>
                        {response.complexity}
                      </span>
                    </span>
                    <span><span className="font-medium">Latency:</span> {response.latency_ms}ms</span>
                    <span><span className="font-medium">Cost:</span> ${Number(response.cost_usd).toFixed(6)}</span>
                    <span className="text-blue-500">Eval {response.eval_status}</span>
                  </div>
                </div>
              )}
            </div>
          </>
        )}

        {!submittedKey && (
          <div className="text-center text-sm text-gray-400 py-12">
            Enter your API key above to view your team&apos;s metrics and send requests.
            <br />
            <a href="/demo" className="text-blue-500 hover:underline mt-2 inline-block">
              Or view the public demo →
            </a>
          </div>
        )}
      </div>
    </main>
  );
}
