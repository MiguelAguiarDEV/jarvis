import { NextRequest } from "next/server";

const API_URL = process.env.ENGRAM_API_URL!;
const API_KEY = process.env.ENGRAM_API_KEY!;

export async function POST(req: NextRequest) {
  const body = await req.json();

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 90000); // 90s timeout before Cloudflare's 100s

    const upstream = await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!upstream.ok) {
      const status = upstream.status;
      // Return clean SSE error instead of raw HTML
      const errorStream = new ReadableStream({
        start(ctrl) {
          const msg = status === 524 || status === 504
            ? "JARVIS took too long to respond. The model may be warming up — try again."
            : `Server error (${status}). Try again in a moment.`;
          ctrl.enqueue(new TextEncoder().encode(`data: ${JSON.stringify({ error: msg })}\n\n`));
          ctrl.close();
        },
      });
      return new Response(errorStream, {
        headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
      });
    }

    return new Response(upstream.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  } catch (err) {
    const msg = err instanceof Error && err.name === "AbortError"
      ? "Request timed out — JARVIS is taking too long. Try a shorter message or try again."
      : "Connection error. Check if JARVIS services are running.";

    const errorStream = new ReadableStream({
      start(ctrl) {
        ctrl.enqueue(new TextEncoder().encode(`data: ${JSON.stringify({ error: msg })}\n\n`));
        ctrl.close();
      },
    });
    return new Response(errorStream, {
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
    });
  }
}
