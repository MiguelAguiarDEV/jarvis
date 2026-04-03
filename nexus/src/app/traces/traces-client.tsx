"use client";

import { useState, useMemo } from "react";
import type { TraceStats, ToolCall } from "@/lib/mnemo";

// ── Tool color mapping ──────────────────────────────────────────────
function toolColor(name: string): string {
  switch (name.toLowerCase()) {
    case "read":
      return "var(--accent-blue)";
    case "write":
    case "edit":
      return "var(--accent-green)";
    case "bash":
    case "shell":
      return "var(--accent-amber)";
    case "grep":
    case "glob":
    case "search":
      return "var(--accent-purple)";
    default:
      return "var(--text-muted)";
  }
}

function toolBadge(name: string): string {
  switch (name.toLowerCase()) {
    case "read":
      return "badge-blue";
    case "write":
    case "edit":
      return "badge-green";
    case "bash":
    case "shell":
      return "badge-amber";
    case "grep":
    case "glob":
    case "search":
      return "badge-purple";
    default:
      return "badge-muted";
  }
}

// ── Date formatting ─────────────────────────────────────────────────
function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function formatTimeShort(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function formatDurationTotal(ms: number): string {
  if (ms === 0) return "0ms";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

// ── Session grouping ────────────────────────────────────────────────
interface SessionGroup {
  sessionId: string;
  project: string;
  calls: ToolCall[];
  totalDuration: number;
  startTime: string;
  endTime: string;
}

function groupBySession(calls: ToolCall[]): SessionGroup[] {
  const map = new Map<string, ToolCall[]>();
  for (const tc of calls) {
    const arr = map.get(tc.session_id) ?? [];
    arr.push(tc);
    map.set(tc.session_id, arr);
  }

  const groups: SessionGroup[] = [];
  Array.from(map.entries()).forEach(([sessionId, sessionCalls]) => {
    sessionCalls.sort(
      (a, b) =>
        new Date(a.occurred_at).getTime() - new Date(b.occurred_at).getTime(),
    );
    const totalDuration = sessionCalls.reduce(
      (sum, tc) => sum + (tc.duration_ms ?? 0),
      0,
    );
    groups.push({
      sessionId,
      project: sessionCalls[0]?.project ?? "",
      calls: sessionCalls,
      totalDuration,
      startTime: sessionCalls[0]?.occurred_at ?? "",
      endTime: sessionCalls[sessionCalls.length - 1]?.occurred_at ?? "",
    });
  });

  groups.sort(
    (a, b) =>
      new Date(b.startTime).getTime() - new Date(a.startTime).getTime(),
  );
  return groups;
}

// ── Props ───────────────────────────────────────────────────────────
interface TracesClientProps {
  stats: TraceStats | null;
  initialCalls: ToolCall[];
}

export default function TracesClient({
  stats,
  initialCalls,
}: TracesClientProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "mnemo" | "tool">(
    "all",
  );
  const [expandedSessions, setExpandedSessions] = useState<Set<string>>(
    () => new Set(stats?.by_session?.slice(0, 3).map((s) => s.session_id) ?? []),
  );
  const [expandedTraces, setExpandedTraces] = useState<Set<number>>(new Set());

  // ── Compute derived data ────────────────────────────────────────
  const byTool = stats?.by_tool ?? [];
  const byDay = stats?.by_day ?? [];
  const maxToolCount = byTool[0]?.count ?? 1;

  // ── Duration histogram buckets ──────────────────────────────────
  const durationBuckets = useMemo(() => {
    const buckets = { fast: 0, medium: 0, slow: 0, verySlow: 0 };
    for (const tc of initialCalls) {
      const d = tc.duration_ms ?? 0;
      if (d < 100) buckets.fast++;
      else if (d < 1000) buckets.medium++;
      else if (d < 10000) buckets.slow++;
      else buckets.verySlow++;
    }
    return buckets;
  }, [initialCalls]);

  const maxBucket = Math.max(
    durationBuckets.fast,
    durationBuckets.medium,
    durationBuckets.slow,
    durationBuckets.verySlow,
    1,
  );

  // ── Filter calls ───────────────────────────────────────────────
  const filteredCalls = useMemo(() => {
    let calls = initialCalls;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      calls = calls.filter(
        (tc) =>
          tc.tool_name.toLowerCase().includes(q) ||
          tc.session_id.toLowerCase().includes(q) ||
          (tc.project ?? "").toLowerCase().includes(q) ||
          tc.agent.toLowerCase().includes(q),
      );
    }
    if (statusFilter === "mnemo") {
      calls = calls.filter((tc) => tc.is_mnemo_legacy); // is_mnemo_legacy is the API field name
    } else if (statusFilter === "tool") {
      calls = calls.filter((tc) => !tc.is_mnemo_legacy);
    }
    return calls;
  }, [initialCalls, searchQuery, statusFilter]);

  const sessionGroups = useMemo(
    () => groupBySession(filteredCalls),
    [filteredCalls],
  );

  // ── Toggle helpers ────────────────────────────────────────────
  const toggleSession = (id: string) => {
    setExpandedSessions((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleTrace = (id: number) => {
    setExpandedTraces((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const hasData = stats && stats.total_calls > 0;

  return (
    <>
      {/* Page header */}
      <div className="page-header">
        <div>
          <div className="page-kicker">TRACE // AGENT TELEMETRY</div>
          <h2 className="page-title">Agent Traces</h2>
        </div>
        <span className="badge badge-amber">
          {stats?.total_calls ?? 0} TOTAL
        </span>
      </div>

      {/* Stats bar */}
      <div className="traces-stats-bar">
        <div className="traces-stat">
          <span className="traces-stat-label">TOTAL CALLS</span>
          <span className="traces-stat-value">
            {stats?.total_calls ?? 0}
          </span>
        </div>
        <div className="traces-stat">
          <span className="traces-stat-label">UNIQUE TOOLS</span>
          <span className="traces-stat-value">
            {stats?.unique_tools ?? 0}
          </span>
        </div>
        <div className="traces-stat">
          <span className="traces-stat-label">SESSIONS</span>
          <span className="traces-stat-value">
            {stats?.by_session?.length ?? 0}
          </span>
        </div>
        <div className="traces-stat">
          <span className="traces-stat-label">TOTAL DURATION</span>
          <span className="traces-stat-value">
            {formatDurationTotal(stats?.total_duration_ms ?? 0)}
          </span>
        </div>
        <div className="traces-stat-tools">
          {byTool.slice(0, 6).map((t) => (
            <span key={t.tool_name} className={`badge ${toolBadge(t.tool_name)}`}>
              {t.tool_name} ({t.count})
            </span>
          ))}
        </div>
      </div>

      {hasData ? (
        <>
          {/* Tool distribution + Duration histogram */}
          <div className="traces-charts-row">
            <div className="traces-chart-panel">
              <div className="traces-chart-label">TOOL DISTRIBUTION</div>
              <div className="traces-bar-chart">
                {byTool.map((t) => (
                  <div key={t.tool_name} className="traces-bar-row">
                    <span className="traces-bar-label">{t.tool_name}</span>
                    <span className="traces-bar-track">
                      <span
                        className="traces-bar-fill"
                        style={{
                          width: `${(t.count / maxToolCount) * 100}%`,
                          backgroundColor: toolColor(t.tool_name),
                        }}
                      />
                    </span>
                    <span className="traces-bar-value">{t.count}</span>
                    <span className="traces-bar-avg">
                      {t.avg_duration_ms > 0
                        ? formatDuration(t.avg_duration_ms)
                        : "--"}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="traces-chart-panel">
              <div className="traces-chart-label">DURATION HISTOGRAM</div>
              <div className="traces-bar-chart">
                <div className="traces-bar-row">
                  <span className="traces-bar-label">&lt;100ms</span>
                  <span className="traces-bar-track">
                    <span
                      className="traces-bar-fill"
                      style={{
                        width: `${(durationBuckets.fast / maxBucket) * 100}%`,
                        backgroundColor: "var(--accent-green)",
                      }}
                    />
                  </span>
                  <span className="traces-bar-value">
                    {durationBuckets.fast}
                  </span>
                </div>
                <div className="traces-bar-row">
                  <span className="traces-bar-label">&lt;1s</span>
                  <span className="traces-bar-track">
                    <span
                      className="traces-bar-fill"
                      style={{
                        width: `${(durationBuckets.medium / maxBucket) * 100}%`,
                        backgroundColor: "var(--accent-blue)",
                      }}
                    />
                  </span>
                  <span className="traces-bar-value">
                    {durationBuckets.medium}
                  </span>
                </div>
                <div className="traces-bar-row">
                  <span className="traces-bar-label">&lt;10s</span>
                  <span className="traces-bar-track">
                    <span
                      className="traces-bar-fill"
                      style={{
                        width: `${(durationBuckets.slow / maxBucket) * 100}%`,
                        backgroundColor: "var(--accent-amber)",
                      }}
                    />
                  </span>
                  <span className="traces-bar-value">
                    {durationBuckets.slow}
                  </span>
                </div>
                <div className="traces-bar-row">
                  <span className="traces-bar-label">&gt;10s</span>
                  <span className="traces-bar-track">
                    <span
                      className="traces-bar-fill"
                      style={{
                        width: `${(durationBuckets.verySlow / maxBucket) * 100}%`,
                        backgroundColor: "var(--accent-red)",
                      }}
                    />
                  </span>
                  <span className="traces-bar-value">
                    {durationBuckets.verySlow}
                  </span>
                </div>
              </div>
            </div>

            {byDay.length > 0 && (
              <div className="traces-chart-panel">
                <div className="traces-chart-label">ACTIVITY // {byDay.length}D</div>
                <div
                  className="step-chart"
                  style={{ height: 60 }}
                >
                  {[...byDay].reverse().map((d) => (
                    <div
                      key={d.date}
                      className="step-bar"
                      style={{
                        height: `${(d.count / Math.max(...byDay.map((x) => x.count), 1)) * 100}%`,
                      }}
                      title={`${d.date}: ${d.count} calls`}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Search + Filters */}
          <div className="traces-toolbar">
            <div className="traces-search-wrapper">
              <span className="traces-search-prefix">&gt;_</span>
              <input
                type="text"
                className="traces-search-input"
                placeholder="SEARCH TRACES..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
              {searchQuery && (
                <button
                  className="traces-search-clear"
                  onClick={() => setSearchQuery("")}
                  type="button"
                >
                  CLR
                </button>
              )}
            </div>

            <div className="traces-filter-group">
              <button
                className={`traces-filter-btn ${statusFilter === "all" ? "active" : ""}`}
                onClick={() => setStatusFilter("all")}
                type="button"
              >
                ALL
              </button>
              <button
                className={`traces-filter-btn ${statusFilter === "tool" ? "active" : ""}`}
                onClick={() => setStatusFilter("tool")}
                type="button"
              >
                TOOLS
              </button>
              <button
                className={`traces-filter-btn ${statusFilter === "mnemo" ? "active" : ""}`}
                onClick={() => setStatusFilter("mnemo")}
                type="button"
              >
                MNEMO
              </button>
            </div>

            <div className="traces-results-count">
              SHOWING {filteredCalls.length}
              {filteredCalls.length !== initialCalls.length &&
                ` / ${initialCalls.length}`}
            </div>
          </div>

          {/* Session-grouped timeline */}
          <div className="traces-sessions">
            {sessionGroups.map((group) => {
              const isExpanded = expandedSessions.has(group.sessionId);
              return (
                <div key={group.sessionId} className="traces-session">
                  <button
                    className="traces-session-header"
                    onClick={() => toggleSession(group.sessionId)}
                    type="button"
                  >
                    <span className="traces-session-arrow">
                      {isExpanded ? "\u25BE" : "\u25B8"}
                    </span>
                    <span className="traces-session-label">SESSION</span>
                    <a
                      href={`/traces/${group.sessionId}`}
                      className="traces-session-id"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {group.sessionId.slice(0, 16)}...
                    </a>
                    {group.project && (
                      <span className="traces-session-project">
                        {group.project}
                      </span>
                    )}
                    <span className="traces-session-meta">
                      {group.calls.length} calls
                    </span>
                    <span className="traces-session-meta">
                      {formatDurationTotal(group.totalDuration)}
                    </span>
                    <span className="traces-session-time">
                      {formatTime(group.startTime)}
                    </span>
                  </button>

                  {isExpanded && (
                    <div className="traces-timeline">
                      {group.calls.map((tc, idx) => (
                        <div
                          key={tc.id}
                          className="traces-timeline-item"
                        >
                          <div className="traces-timeline-connector">
                            <span
                              className="traces-timeline-dot"
                              style={{
                                backgroundColor: toolColor(tc.tool_name),
                              }}
                            />
                            {idx < group.calls.length - 1 && (
                              <span className="traces-timeline-line" />
                            )}
                          </div>

                          <button
                            className="traces-timeline-content"
                            onClick={() => toggleTrace(tc.id)}
                            type="button"
                          >
                            <span className="traces-timeline-time">
                              {formatTimeShort(tc.occurred_at)}
                            </span>
                            <span
                              className={`badge ${toolBadge(tc.tool_name)}`}
                            >
                              {tc.tool_name}
                            </span>
                            <span className="traces-timeline-agent">
                              {tc.agent}
                            </span>
                            <span className="traces-timeline-dur">
                              {tc.duration_ms != null
                                ? formatDuration(tc.duration_ms)
                                : "--"}
                            </span>
                            {tc.is_mnemo_legacy && (
                              <span className="badge badge-green">MNEMO</span>
                            )}
                          </button>

                          {expandedTraces.has(tc.id) && (
                            <div className="traces-timeline-detail">
                              {tc.input_json &&
                                tc.input_json !== "null" &&
                                tc.input_json !== "{}" && (
                                  <>
                                    <div className="section-label">INPUT</div>
                                    <pre className="traces-detail-pre">
                                      {tc.input_json}
                                    </pre>
                                  </>
                                )}
                              {tc.output_text && (
                                <>
                                  <div className="section-label">OUTPUT</div>
                                  <pre className="traces-detail-pre">
                                    {tc.output_text.length > 2000
                                      ? tc.output_text.slice(0, 2000) +
                                        "\n[truncated]"
                                      : tc.output_text}
                                  </pre>
                                </>
                              )}
                              {!tc.input_json &&
                                !tc.output_text && (
                                  <div className="traces-detail-empty">
                                    NO DETAIL DATA
                                  </div>
                                )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {sessionGroups.length === 0 && (
            <div className="empty-state">
              <div className="empty-label">NO MATCHING TRACES</div>
              <p
                style={{
                  color: "var(--text-dim)",
                  fontSize: "var(--font-size-sm)",
                }}
              >
                {searchQuery
                  ? `No results for "${searchQuery}". Try a different query.`
                  : "No traces match the current filters."}
              </p>
            </div>
          )}
        </>
      ) : (
        <div className="empty-state" style={{ paddingTop: "var(--space-8)" }}>
          <div className="empty-label">NO TRACES YET</div>
          <p
            style={{
              color: "var(--text-dim)",
              fontSize: "var(--font-size-sm)",
              maxWidth: 480,
              margin: "0 auto",
            }}
          >
            Traces will appear when OpenCode executes tool calls. Each tool
            invocation is logged with timing, input/output, and session context.
          </p>
        </div>
      )}
    </>
  );
}
