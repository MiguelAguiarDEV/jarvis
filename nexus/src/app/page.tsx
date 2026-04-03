"use client";

import { useState, useEffect } from "react";
import {
  HudPanel,
  TerminalBar,
  HexStream,
  DataMatrix,
  Waveform,
  Equalizer,
  StatusLine,
  Metric,
} from "@/components/hud";
import type { TraceStats } from "@/lib/engram";

interface SystemInfo {
  cpu: number;
  memory: { total: number; used: number; pct: number };
  disk: { total: number; used: number; pct: number };
  uptime: number;
  hostname: string;
  cores: number;
  loadavg: number[];
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  return `${h}h ${m}m`;
}

function formatDuration(ms: number): string {
  const n = Number(ms) || 0;
  if (n < 1000) return `${n}ms`;
  if (n < 60000) return `${(n / 1000).toFixed(1)}s`;
  return `${(n / 60000).toFixed(1)}m`;
}

export default function StatusPage() {
  const [sys, setSys] = useState<SystemInfo | null>(null);
  const [stats, setStats] = useState<TraceStats | null>(null);
  const [now, setNow] = useState("");
  const [tick, setTick] = useState(0);
  const [cpuHistory, setCpuHistory] = useState<number[]>([]);
  const [memHistory, setMemHistory] = useState<number[]>([]);

  // Poll system info every 2s + record metrics every 10s
  useEffect(() => {
    let recordCounter = 0;

    const fetchAll = async () => {
      try {
        const sysRes = await fetch("/api/system").then((r) => r.json()).catch(() => null);
        if (sysRes) {
          setSys(sysRes);
          setCpuHistory((prev) => [...prev.slice(-59), sysRes.cpu]);
          setMemHistory((prev) => [...prev.slice(-59), sysRes.memory.pct]);
        }
      } catch {}

      setNow(new Date().toISOString().replace("T", " ").slice(0, 19));

      // Record to engram every 10s (every 5th tick)
      recordCounter++;
      if (recordCounter % 5 === 0) {
        fetch("/api/metrics", { method: "POST" }).catch(() => {});
      }
    };

    fetchAll();
    const interval = setInterval(() => {
      fetchAll();
      setTick((t) => t + 1);
    }, 2000);

    // Fetch trace stats every 10s
    fetch("/api/trace-stats").then((r) => r.json()).then(setStats).catch(() => {});
    const statsInterval = setInterval(() => {
      fetch("/api/trace-stats").then((r) => r.json()).then(setStats).catch(() => {});
    }, 10000);

    return () => { clearInterval(interval); clearInterval(statsInterval); };
  }, []);

  const maxToolCount = stats?.by_tool?.[0]?.count || 1;
  const byDay = stats?.by_day ?? [];
  const maxDayCount = byDay.length > 0 ? Math.max(...byDay.map((d) => d.count)) : 1;

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-kicker">CORE // SYSTEM OVERVIEW</div>
          <h2 className="page-title">System Status</h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          <span className="live-dot" />
          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-dim)" }}>
            {now} UTC
          </span>
        </div>
      </div>

      {/* Row 1: System Monitoring + Core Stability + Program Status */}
      <div className="hud-grid">
        <HudPanel label="SYSTEM MONITORING">
          {sys ? (
            <>
              <TerminalBar label="CPU" value={sys.cpu} />
              <TerminalBar label="MEMORY" value={sys.memory.pct} />
              <TerminalBar label="DISK" value={sys.disk.pct} />
              <TerminalBar label="LOAD" value={sys.loadavg[0]} max={sys.cores} unit="" />
              <div style={{ marginTop: "var(--space-2)" }}>
                <StatusLine items={[["CORES", String(sys.cores)], ["UPTIME", formatUptime(sys.uptime)]]} />
                <StatusLine items={[["RAM", `${sys.memory.used}/${sys.memory.total} GB`], ["DISK", `${sys.disk.used}/${sys.disk.total} GB`]]} />
                <StatusLine items={[["HOST", sys.hostname]]} />
              </div>
              {cpuHistory.length > 1 && (
                <div style={{ marginTop: "var(--space-2)" }}>
                  <div style={{ fontSize: "var(--font-size-xs)", color: "var(--text-dim)", letterSpacing: "0.1em", marginBottom: 2 }}>CPU HISTORY</div>
                  <div className="step-chart" style={{ height: 30 }}>
                    {cpuHistory.map((v, i) => (
                      <div key={i} className="step-bar" style={{ height: `${Math.max(v, 1)}%`, opacity: 0.4 + (i / cpuHistory.length) * 0.6 }} />
                    ))}
                  </div>
                </div>
              )}
              {memHistory.length > 1 && (
                <div style={{ marginTop: "var(--space-1)" }}>
                  <div style={{ fontSize: "var(--font-size-xs)", color: "var(--text-dim)", letterSpacing: "0.1em", marginBottom: 2 }}>MEMORY HISTORY</div>
                  <div className="step-chart" style={{ height: 20 }}>
                    {memHistory.map((v, i) => (
                      <div key={i} className="step-bar" style={{ height: `${v}%`, background: "var(--accent-green)", opacity: 0.3 + (i / memHistory.length) * 0.7 }} />
                    ))}
                  </div>
                </div>
              )}
              <HexStream seed={sys.uptime + tick} />
            </>
          ) : (
            <div className="empty-state"><div className="empty-label loading-pulse">CONNECTING...</div></div>
          )}
        </HudPanel>

        <HudPanel label="CORE STABILITY">
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-2)" }}>
            <Metric label="TOOL CALLS" value={stats?.total_calls?.toLocaleString() ?? "0"} />
            <Metric label="UNIQUE TOOLS" value={stats?.unique_tools ?? 0} />
          </div>
          <Waveform points={50} height={35} seed={(stats?.total_calls ?? 7) + tick} />
          <DataMatrix rows={3} cols={20} seed={(stats?.unique_tools ?? 42) + tick} />
          <StatusLine items={[["ENGRAM", "ONLINE"], ["DURATION", stats ? formatDuration(stats.total_duration_ms) : "—"]]} />
        </HudPanel>

        <HudPanel label="PROGRAM STATUS">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)", marginBottom: "var(--space-2)" }}>
            <Metric label="SESSIONS" value={stats?.by_session?.length ?? 0} />
            <Metric label="TOOLS" value={stats?.unique_tools ?? 0} />
            <Metric label="CALLS/DAY" value={stats?.by_day?.length ? Math.round(stats.by_day.reduce((a, d) => a + d.count, 0) / stats.by_day.length) : 0} sub="AVG" />
            <Metric label="DURATION" value={stats ? formatDuration(stats.total_duration_ms) : "—"} sub="TOTAL" />
          </div>
          <HexStream seed={tick + 99} />
          <Waveform points={30} height={25} seed={13 + tick} />
        </HudPanel>
      </div>

      {/* Row 2: Tool Usage + Activity + Sessions */}
      <div className="hud-grid">
        <HudPanel label="TOOL USAGE // HISTOGRAM">
          {stats?.by_tool && stats.by_tool.length > 0 ? (
            <>
              <Equalizer bars={stats.by_tool.length} data={stats.by_tool.map((t) => t.count)} maxVal={maxToolCount} />
              <table className="compact-table">
                <thead><tr><th>TOOL</th><th>N</th><th>AVG</th></tr></thead>
                <tbody>
                  {stats.by_tool.slice(0, 8).map((t) => (
                    <tr key={t.tool_name}>
                      <td style={{ color: "var(--text-secondary)" }}>{t.tool_name}</td>
                      <td>{t.count}</td>
                      <td>{t.avg_duration_ms}ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <div className="empty-state"><div className="empty-label">AWAITING DATA</div></div>
          )}
        </HudPanel>

        <HudPanel label="ACTIVITY // 30D SIGNAL">
          {stats?.by_day && stats.by_day.length > 0 ? (
            <>
              <div className="step-chart" style={{ height: 50 }}>
                {[...stats.by_day].reverse().map((d) => (
                  <div key={d.date} className="step-bar" style={{ height: `${(d.count / maxDayCount) * 100}%` }} title={`${d.date}: ${d.count}`} />
                ))}
              </div>
              <table className="compact-table" style={{ marginTop: "var(--space-2)" }}>
                <thead><tr><th>DATE</th><th>CALLS</th></tr></thead>
                <tbody>
                  {stats.by_day.slice(0, 6).map((d) => (
                    <tr key={d.date}><td>{d.date}</td><td>{d.count}</td></tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <>
              <Waveform points={60} height={50} seed={99 + tick} />
              <DataMatrix rows={4} cols={24} seed={77 + tick} />
              <div className="empty-state"><div className="empty-label">NO SIGNAL</div></div>
            </>
          )}
        </HudPanel>

        <HudPanel label="RECENT SESSIONS // INDEX">
          {stats?.by_session && stats.by_session.length > 0 ? (
            <table className="compact-table">
              <thead><tr><th>SESSION</th><th>PROJECT</th><th>N</th></tr></thead>
              <tbody>
                {stats.by_session.slice(0, 12).map((s) => (
                  <tr key={s.session_id}>
                    <td><a href={`/traces/${s.session_id}`}>{s.session_id.slice(0, 12)}...</a></td>
                    <td>{s.project || "—"}</td>
                    <td>{s.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <>
              <DataMatrix rows={6} cols={20} seed={33 + tick} />
              <HexStream seed={42 + tick} />
              <div className="empty-state"><div className="empty-label">NO SESSIONS</div></div>
            </>
          )}
        </HudPanel>
      </div>

      <div style={{ display: "flex", gap: "var(--space-4)", padding: "var(--space-2) 0" }}>
        <HexStream seed={1 + tick} />
        <HexStream seed={2 + tick} />
        <HexStream seed={3 + tick} />
      </div>
    </>
  );
}
