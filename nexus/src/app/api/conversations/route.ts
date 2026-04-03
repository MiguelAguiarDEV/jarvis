import { NextRequest, NextResponse } from "next/server";
import { engramFetch } from "@/lib/engram";

export async function GET() {
  try {
    const data = await engramFetch("/api/conversations");
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { conversations: [], error: String(err) },
      { status: 502 },
    );
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const data = await engramFetch("/api/conversations", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return NextResponse.json(data, { status: 201 });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}
