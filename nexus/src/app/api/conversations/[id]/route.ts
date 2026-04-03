import { NextRequest, NextResponse } from "next/server";
import { mnemoFetch } from "@/lib/mnemo";

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  try {
    await mnemoFetch(`/api/conversations/${id}`, { method: "DELETE" });
    return NextResponse.json({ status: "deleted" });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await req.json();
  try {
    await mnemoFetch(`/api/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    return NextResponse.json({ status: "renamed" });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}
