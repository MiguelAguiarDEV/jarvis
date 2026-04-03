import { NextRequest, NextResponse } from "next/server";
import { engramFetch } from "@/lib/engram";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const period = req.nextUrl.searchParams.get("period") || "month";
  const limit = req.nextUrl.searchParams.get("limit") || "50";
  try {
    const data = await engramFetch(
      `/api/costs/sessions?period=${period}&limit=${limit}`,
    );
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ sessions: [], period });
  }
}
