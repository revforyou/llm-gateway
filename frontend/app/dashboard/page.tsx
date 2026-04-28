export default function DashboardPage() {
  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Dashboard</h1>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {["Requests Today", "Avg Quality", "Total Cost (attr.)", "p95 Latency"].map((label) => (
            <div key={label} className="bg-white rounded-xl border p-6">
              <div className="text-sm text-gray-500">{label}</div>
              <div className="text-3xl font-bold text-gray-900 mt-2">—</div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
