import { NextRequest, NextResponse } from "next/server";
import { engramFetch } from "@/lib/engram";
import os from "os";

export const dynamic = "force-dynamic";

// GET — proxy to engram for historical metrics
export async function GET(req: NextRequest) {
  const limit = req.nextUrl.searchParams.get("limit") || "60";
  try {
    const data = await engramFetch(`/api/metrics?limit=${limit}`);
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ metrics: [] });
  }
}

// POST — record current system metrics to engram
export async function POST() {
  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  const usedMem = totalMem - freeMem;

  const cpus = os.cpus();
  const cpuPct =
    cpus.reduce((acc, cpu) => {
      const total = Object.values(cpu.times).reduce((a, b) => a + b, 0);
      return acc + ((total - cpu.times.idle) / total) * 100;
    }, 0) / cpus.length;

  let diskPct = 0;
  try {
    const stat = require("fs").statfsSync("/");
    const total = stat.blocks * stat.bsize;
    const free = stat.bfree * stat.bsize;
    diskPct = ((total - free) / total) * 100;
  } catch {}

  const body = {
    cpu_pct: Math.round(cpuPct * 10) / 10,
    mem_pct: Math.round((usedMem / totalMem) * 100 * 10) / 10,
    disk_pct: Math.round(diskPct * 10) / 10,
    load_1m: Math.round(os.loadavg()[0] * 100) / 100,
    mem_used_mb: Math.round(usedMem / 1048576),
    mem_total_mb: Math.round(totalMem / 1048576),
  };

  try {
    await engramFetch("/api/metrics", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return NextResponse.json({ status: "ok" });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}
