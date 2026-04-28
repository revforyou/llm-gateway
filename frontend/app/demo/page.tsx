export default function DemoPage() {
  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">LLM Gateway — Live Demo</h1>
        <p className="text-gray-500 mb-8">Read-only view of the demo team. Data updates every 30 minutes.</p>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          {["Requests Today", "Avg Quality", "Total Cost (attr.)", "p95 Latency"].map((label) => (
            <div key={label} className="bg-white rounded-xl border p-6">
              <div className="text-sm text-gray-500">{label}</div>
              <div className="text-3xl font-bold text-gray-900 mt-2">—</div>
            </div>
          ))}
        </div>
        <p className="text-gray-400 text-sm text-center">
          Charts and detailed metrics will populate once the backend is deployed and traffic flows.
        </p>
      </div>
    </main>
  );
}
