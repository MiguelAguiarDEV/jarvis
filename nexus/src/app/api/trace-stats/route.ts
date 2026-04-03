import { NextResponse } from "next/server";
import { engramFetch } from "@/lib/engram";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await engramFetch("/traces/stats");
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ total_calls: 0, unique_tools: 0, total_duration_ms: 0, by_tool: [], by_session: [], by_day: [] });
  }
}
