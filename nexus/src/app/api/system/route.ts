import { NextResponse } from "next/server";
import os from "os";
import fs from "fs";

function getCpuUsage(): number {
  try {
    const stat = fs.readFileSync("/proc/stat", "utf8").split("\n")[0];
    const parts = stat.split(/\s+/).slice(1).map(Number);
    const idle = parts[3];
    const total = parts.reduce((a, b) => a + b, 0);
    return Math.round(((total - idle) / total) * 100 * 10) / 10;
  } catch {
    const cpus = os.cpus();
    const avg = cpus.reduce((acc, cpu) => {
      const total = Object.values(cpu.times).reduce((a, b) => a + b, 0);
      return acc + ((total - cpu.times.idle) / total) * 100;
    }, 0) / cpus.length;
    return Math.round(avg * 10) / 10;
  }
}

function getDiskUsage(): { total: number; used: number; pct: number } {
  try {
    const stat = fs.statfsSync("/");
    const total = stat.blocks * stat.bsize;
    const free = stat.bfree * stat.bsize;
    const used = total - free;
    return {
      total: Math.round(total / 1073741824),
      used: Math.round(used / 1073741824),
      pct: Math.round((used / total) * 100 * 10) / 10,
    };
  } catch {
    return { total: 0, used: 0, pct: 0 };
  }
}

export const dynamic = "force-dynamic";

export async function GET() {
  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  const usedMem = totalMem - freeMem;
  const disk = getDiskUsage();

  return NextResponse.json({
    cpu: getCpuUsage(),
    memory: {
      total: Math.round(totalMem / 1073741824 * 10) / 10,
      used: Math.round(usedMem / 1073741824 * 10) / 10,
      pct: Math.round((usedMem / totalMem) * 100 * 10) / 10,
    },
    disk,
    uptime: Math.round(os.uptime()),
    hostname: os.hostname(),
    platform: `${os.type()} ${os.release()}`,
    cores: os.cpus().length,
    loadavg: os.loadavg().map((l) => Math.round(l * 100) / 100),
  });
}
