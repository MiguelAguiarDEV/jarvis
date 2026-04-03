import { NextRequest, NextResponse } from "next/server";
import { engramFetch } from "@/lib/engram";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  try {
    const data = await engramFetch<unknown>(`/api/conversations/${id}/messages`);
    // Normalize: mnemo may return [...] or { messages: [...] }
    let messages: unknown[];
    if (Array.isArray(data)) {
      messages = data;
    } else if (data && typeof data === "object" && "messages" in data && Array.isArray((data as { messages: unknown[] }).messages)) {
      messages = (data as { messages: unknown[] }).messages;
    } else {
      messages = [];
    }
    return NextResponse.json({ messages });
  } catch (err) {
    return NextResponse.json(
      { messages: [], error: String(err) },
      { status: 502 }
    );
  }
}
