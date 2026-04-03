import { NextRequest, NextResponse } from "next/server";
import { engramFetch } from "@/lib/engram";

export async function GET(req: NextRequest) {
  const project = req.nextUrl.searchParams.get("project") || "";
  const status = req.nextUrl.searchParams.get("status") || "";
  const priority = req.nextUrl.searchParams.get("priority") || "";

  const params = new URLSearchParams();
  if (project) params.set("project", project);
  if (status) params.set("status", status);
  if (priority) params.set("priority", priority);

  try {
    const data = await engramFetch(`/api/tasks?${params.toString()}`);
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { tasks: [], error: String(err) },
      { status: 502 },
    );
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const data = await engramFetch("/api/tasks", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return NextResponse.json(data, { status: 201 });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}

export async function PATCH(req: NextRequest) {
  try {
    const body = await req.json();
    const { id, ...updates } = body;
    const data = await engramFetch(`/api/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    });
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}

export async function DELETE(req: NextRequest) {
  try {
    const body = await req.json();
    const { id } = body;
    await engramFetch(`/api/tasks/${id}`, { method: "DELETE" });
    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}
