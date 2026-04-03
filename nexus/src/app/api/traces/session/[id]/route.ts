import { NextRequest, NextResponse } from "next/server";
import { engramFetch } from "@/lib/engram";

export const dynamic = "force-dynamic";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const sp = req.nextUrl.searchParams;
  const limit = sp.get("limit") || "100";
  const offset = sp.get("offset") || "0";

  try {
    const data = await engramFetch(
      `/traces/session/${encodeURIComponent(id)}?limit=${limit}&offset=${offset}`,
    );
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ session_id: id, tool_calls: [], total: 0 });
  }
}
