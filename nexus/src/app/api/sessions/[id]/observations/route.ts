import { NextRequest, NextResponse } from "next/server";
import { engramFetch } from "@/lib/engram";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const limit = req.nextUrl.searchParams.get("limit") || "50";

  try {
    const data = await engramFetch<Record<string, unknown>>(
      `/api/sessions/${encodeURIComponent(id)}/observations?limit=${limit}`,
    );
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { error: String(err) },
      { status: 502 },
    );
  }
}
