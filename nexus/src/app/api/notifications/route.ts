import { NextRequest, NextResponse } from "next/server";
import { engramFetch } from "@/lib/engram";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const data = await engramFetch("/api/notifications", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}
