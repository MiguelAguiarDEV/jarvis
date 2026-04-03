import { NextRequest, NextResponse } from "next/server";
import { engramFetch } from "@/lib/engram";

export async function GET(req: NextRequest) {
  const project = req.nextUrl.searchParams.get("project") || "";
  const since = req.nextUrl.searchParams.get("since") || "";
  const cursor = req.nextUrl.searchParams.get("cursor") || "";

  const params = new URLSearchParams();
  if (project) params.set("project", project);
  if (since) params.set("since", since);
  if (cursor) params.set("cursor", cursor);

  try {
    const data = await engramFetch(`/api/activity?${params.toString()}`);
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { entries: [], error: String(err) },
      { status: 502 },
    );
  }
}
