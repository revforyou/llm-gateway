const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  const json = await res.json();
  if (!res.ok || json.error) {
    throw new Error(json.error?.message ?? `API error ${res.status}`);
  }
  return json.data as T;
}

export const api = {
  chat: (prompt: string, apiKey: string) =>
    apiFetch("/v1/chat", {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({ prompt }),
    }),

  metrics: {
    overview: (apiKey: string) =>
      apiFetch("/v1/metrics/overview", {
        headers: { Authorization: `Bearer ${apiKey}` },
      }),
    distribution: (apiKey: string) =>
      apiFetch("/v1/metrics/distribution", {
        headers: { Authorization: `Bearer ${apiKey}` },
      }),
  },

  health: () => apiFetch<{ status: string; db: string; redis: string }>("/health"),
};
