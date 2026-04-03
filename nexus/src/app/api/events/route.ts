import { NextRequest } from "next/server";

const API_URL = process.env.ENGRAM_API_URL!;
const API_KEY = process.env.ENGRAM_API_KEY!;

export async function GET(req: NextRequest) {
  const project = req.nextUrl.searchParams.get("project") || "";
  const params = new URLSearchParams();
  if (project) params.set("project", project);

  const upstream = await fetch(`${API_URL}/api/events?${params.toString()}`, {
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      Accept: "text/event-stream",
    },
  });

  if (!upstream.ok) {
    return new Response(await upstream.text(), { status: upstream.status });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
