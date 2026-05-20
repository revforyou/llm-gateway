import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEMO_API_KEY = process.env.DEMO_API_KEY ?? "";

export async function POST(req: NextRequest) {
  if (!DEMO_API_KEY) {
    return NextResponse.json({ error: "Demo key not configured" }, { status: 503 });
  }
  const body = await req.json();
  const upstream = await fetch(`${API_URL}/v1/chat`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${DEMO_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ prompt: body.prompt }),
  });
  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
