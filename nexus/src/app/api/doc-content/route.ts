import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const KB_ROOT = process.env.KB_ROOT || "/home/mx/personal-knowledgebase";

export async function GET(req: NextRequest) {
  const filePath = req.nextUrl.searchParams.get("path");
  if (!filePath) {
    return new NextResponse("Missing path", { status: 400 });
  }

  // Security: only allow .md files within KB_ROOT
  const resolved = path.resolve(KB_ROOT, filePath);
  if (!resolved.startsWith(KB_ROOT) || !resolved.endsWith(".md")) {
    return new NextResponse("Forbidden", { status: 403 });
  }

  try {
    const content = fs.readFileSync(resolved, "utf8");
    return new NextResponse(content, {
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  } catch {
    return new NextResponse("Not found", { status: 404 });
  }
}
