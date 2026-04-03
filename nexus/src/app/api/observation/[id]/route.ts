import { NextRequest, NextResponse } from "next/server";
import { engramFetch } from "@/lib/engram";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  try {
    const data = await engramFetch<Record<string, unknown>>(
      `/api/observations/${id}`,
    );
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { error: String(err) },
      { status: 502 },
    );
  }
}
