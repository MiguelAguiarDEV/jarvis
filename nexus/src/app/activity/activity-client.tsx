"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { HudPanel, HexStream, Metric, StatusLine, DataMatrix, Waveform } from "@/components/hud";
import type { ActivityEntry } from "@/lib/engram";

// ── Date/time helpers ────────────────────────────────────────────────

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function formatDateKey(iso: string): string {
  const d = new Date(iso);
  return d.toISOString().slice(0, 10);
}

function formatDateLabel(dateKey: string): string {
  const d = new Date(dateKey + "T00:00:00");
  const now = new Date();
  const today = now.toISOString().slice(0, 10);
  const yesterday = new Date(now.getTime() - 86400000).toISOString().slice(0, 10);
  if (dateKey === today) return "TODAY";
  if (dateKey === yesterday) return "YESTERDAY";
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "2-digit",
  }).toUpperCase();
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ── Type config ──────────────────────────────────────────────────────

const TYPE_CONFIG: Record<string, { badge: string; icon: string; label: string }> = {
  tool_call:    { badge: "badge-amber",  icon: "\u2699", label: "TOOL CALL" },
  observation:  { badge: "badge-green",  icon: "\u25C6", label: "OBSERVATION" },
  session:      { badge: "badge-blue",   icon: "\u25B6", label: "SESSION" },
  task_update:  { badge: "badge-purple", icon: "\u2611", label: "TASK" },
  budget_alert: { badge: "badge-red",    icon: "\u26A0", label: "ALERT" },
};

const ALL_TYPES = ["tool_call", "observation", "session", "task_update"];

// ── Heatmap Component ────────────────────────────────────────────────

function ActivityHeatmap({ entries }: { entries: ActivityEntry[] }) {
  // Build day -> count map for last 90 days
  const now = new Date();
  const dayMap = new Map<string, number>();

  // Init last 90 days
  for (let i = 89; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 86400000);
    const key = d.toISOString().slice(0, 10);
    dayMap.set(key, 0);
  }

  for (const e of entries) {
    const key = formatDateKey(e.occurred_at);
    if (dayMap.has(key)) {
      dayMap.set(key, (dayMap.get(key) ?? 0) + 1);
    }
  }

  const days = Array.from(dayMap.entries());
  const maxCount = Math.max(...days.map(([, c]) => c), 1);

  // Compute intensity level 0-4
  function level(count: number): number {
    if (count === 0) return 0;
    const ratio = count / maxCount;
    if (ratio < 0.25) return 1;
    if (ratio < 0.5) return 2;
    if (ratio < 0.75) return 3;
    return 4;
  }

  // Group into weeks (columns of 7)
  const weeks: { key: string; count: number; lvl: number }[][] = [];
  // Pad start so first day aligns to its weekday
  const firstDate = new Date(days[0][0] + "T00:00:00");
  const startDow = firstDate.getDay(); // 0=Sun
  const padded: { key: string; count: number; lvl: number }[] = [];
  for (let i = 0; i < startDow; i++) {
    padded.push({ key: "", count: -1, lvl: -1 });
  }
  for (const [key, count] of days) {
    padded.push({ key, count, lvl: level(count) });
  }
  for (let i = 0; i < padded.length; i += 7) {
    weeks.push(padded.slice(i, i + 7));
  }

  // Month labels
  const monthLabels: { col: number; label: string }[] = [];
  let lastMonth = -1;
  for (let w = 0; w < weeks.length; w++) {
    for (const cell of weeks[w]) {
      if (cell.key) {
        const m = new Date(cell.key + "T00:00:00").getMonth();
        if (m !== lastMonth) {
          lastMonth = m;
          monthLabels.push({
            col: w,
            label: new Date(cell.key + "T00:00:00").toLocaleDateString("en-US", { month: "short" }).toUpperCase(),
          });
        }
        break;
      }
    }
  }

  const dayLabels = ["", "MON", "", "WED", "", "FRI", ""];

  return (
    <div className="activity-heatmap">
      <div className="heatmap-month-labels">
        <div className="heatmap-day-spacer" />
        {monthLabels.map((m, i) => (
          <span
            key={i}
            className="heatmap-month"
            style={{ gridColumn: m.col + 2 }}
          >
            {m.label}
          </span>
        ))}
      </div>
      <div className="heatmap-grid">
        <div className="heatmap-day-labels">
          {dayLabels.map((l, i) => (
            <span key={i} className="heatmap-day-label">{l}</span>
          ))}
        </div>
        <div className="heatmap-cells">
          {weeks.map((week, wi) => (
            <div key={wi} className="heatmap-col">
              {week.map((cell, di) => (
                <div
                  key={di}
                  className={`heatmap-cell ${cell.lvl >= 0 ? `heatmap-lvl-${cell.lvl}` : "heatmap-empty"}`}
                  title={cell.key ? `${cell.key}: ${cell.count} events` : ""}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="heatmap-legend">
        <span>LESS</span>
        <div className="heatmap-cell heatmap-lvl-0" />
        <div className="heatmap-cell heatmap-lvl-1" />
        <div className="heatmap-cell heatmap-lvl-2" />
        <div className="heatmap-cell heatmap-lvl-3" />
        <div className="heatmap-cell heatmap-lvl-4" />
        <span>MORE</span>
      </div>
    </div>
  );
}

// ── Compact Event Row ────────────────────────────────────────────────

function CompactEvent({ entry }: { entry: ActivityEntry }) {
  const config = TYPE_CONFIG[entry.type] ?? { badge: "badge-muted", icon: "\u2022", label: entry.type.toUpperCase() };
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`activity-event ${expanded ? "activity-event-expanded" : ""}`}
      onClick={() => setExpanded(!expanded)}
    >
      <span className="activity-event-time">{formatTime(entry.occurred_at)}</span>
      <span className={`badge ${config.badge} activity-event-badge`}>{config.label}</span>
      <span className="activity-event-summary">{entry.summary}</span>
      {entry.project && (
        <span className="activity-event-project">{entry.project}</span>
      )}
      <span className="activity-event-rel">{relativeTime(entry.occurred_at)}</span>
      {entry.data && (
        <span className="activity-event-expand">{expanded ? "\u25BE" : "\u25B8"}</span>
      )}
      {expanded && entry.data && (
        <div className="activity-event-detail" onClick={(e) => e.stopPropagation()}>
          <pre>{JSON.stringify(entry.data, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

// ── Props ────────────────────────────────────────────────────────────

interface ActivityClientProps {
  initialEntries: ActivityEntry[];
}

export default function ActivityClient({ initialEntries }: ActivityClientProps) {
  const [entries, setEntries] = useState<ActivityEntry[]>(initialEntries);
  const [liveEntries, setLiveEntries] = useState<ActivityEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState(false);
  const [filterProject, setFilterProject] = useState("");
  const [filterType, setFilterType] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [collapsedDays, setCollapsedDays] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  // ── Fetch activity ─────────────────────────────────────────────────
  const fetchActivity = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filterProject) params.set("project", filterProject);

    try {
      const res = await fetch(`/api/activity?${params.toString()}`);
      const data = await res.json();
      const list = data.entries ?? data ?? [];
      setEntries(Array.isArray(list) ? list : []);
      setError(null);
    } catch (err) {
      setError(String(err));
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [filterProject]);

  useEffect(() => {
    fetchActivity();
  }, [fetchActivity]);

  // ── SSE connection ─────────────────────────────────────────────────
  useEffect(() => {
    if (esRef.current) {
      esRef.current.close();
    }

    const params = new URLSearchParams();
    if (filterProject) params.set("project", filterProject);

    const es = new EventSource(`/api/events?${params.toString()}`);
    esRef.current = es;

    es.onopen = () => setConnected(true);

    es.onmessage = (event) => {
      try {
        const entry = JSON.parse(event.data) as ActivityEntry;
        setLiveEntries((prev) => [entry, ...prev]);
      } catch {
        // ignore non-JSON events
      }
    };

    es.onerror = () => {
      setConnected(false);
    };

    return () => {
      es.close();
      setConnected(false);
    };
  }, [filterProject]);

  // ── Computed data ──────────────────────────────────────────────────
  const allEntries = useMemo(() => [...liveEntries, ...entries], [liveEntries, entries]);

  // Stats
  const stats = useMemo(() => {
    const byType: Record<string, number> = {};
    const byProject: Record<string, number> = {};
    const byDay: Record<string, number> = {};

    for (const e of allEntries) {
      byType[e.type] = (byType[e.type] ?? 0) + 1;
      if (e.project) {
        byProject[e.project] = (byProject[e.project] ?? 0) + 1;
      }
      const dayKey = formatDateKey(e.occurred_at);
      byDay[dayKey] = (byDay[dayKey] ?? 0) + 1;
    }

    const activeDays = Object.keys(byDay).length;
    const today = new Date().toISOString().slice(0, 10);
    const eventsToday = byDay[today] ?? 0;

    // Most active day
    let mostActiveDay = "";
    let mostActiveDayCount = 0;
    for (const [day, count] of Object.entries(byDay)) {
      if (count > mostActiveDayCount) {
        mostActiveDayCount = count;
        mostActiveDay = day;
      }
    }

    return {
      total: allEntries.length,
      byType,
      byProject,
      activeDays,
      eventsToday,
      mostActiveDay,
      mostActiveDayCount,
    };
  }, [allEntries]);

  const projects = useMemo(
    () =>
      Object.entries(stats.byProject)
        .sort((a, b) => b[1] - a[1]),
    [stats.byProject],
  );

  // ── Filtered + grouped entries ─────────────────────────────────────
  const groupedEntries = useMemo(() => {
    let filtered = allEntries;

    // Type filter
    if (filterType.size > 0) {
      filtered = filtered.filter((e) => filterType.has(e.type));
    }

    // Search filter
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (e) =>
          e.summary.toLowerCase().includes(q) ||
          (e.project && e.project.toLowerCase().includes(q)) ||
          e.type.toLowerCase().includes(q),
      );
    }

    // Group by date
    const groups = new Map<string, ActivityEntry[]>();
    for (const e of filtered) {
      const key = formatDateKey(e.occurred_at);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(e);
    }

    // Sort groups by date descending, entries within each group by time descending
    const sorted = Array.from(groups.entries())
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([date, items]) => ({
        date,
        label: formatDateLabel(date),
        entries: items.sort(
          (a, b) => new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime(),
        ),
      }));

    return sorted;
  }, [allEntries, filterType, searchQuery]);

  const filteredCount = groupedEntries.reduce((sum, g) => sum + g.entries.length, 0);

  // ── Toggle helpers ─────────────────────────────────────────────────
  const toggleType = (type: string) => {
    setFilterType((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const toggleDay = (date: string) => {
    setCollapsedDays((prev) => {
      const next = new Set(prev);
      if (next.has(date)) next.delete(date);
      else next.add(date);
      return next;
    });
  };

  // ── Type distribution bars ─────────────────────────────────────────
  const typeDistribution = useMemo(() => {
    return ALL_TYPES
      .map((type) => ({
        type,
        count: stats.byType[type] ?? 0,
        config: TYPE_CONFIG[type] ?? { badge: "badge-muted", icon: "\u2022", label: type },
      }))
      .sort((a, b) => b.count - a.count);
  }, [stats.byType]);

  const maxTypeCount = Math.max(...typeDistribution.map((t) => t.count), 1);

  return (
    <>
      {/* Page header */}
      <div className="page-header">
        <div>
          <div className="page-kicker">FEED // ACTIVITY TIMELINE</div>
          <h2 className="page-title">Activity</h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          {connected ? (
            <>
              <span className="live-dot" />
              <span style={{ fontSize: "var(--font-size-xs)", color: "var(--accent-green)" }}>
                SSE CONNECTED
              </span>
            </>
          ) : (
            <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-dim)" }}>
              POLLING MODE
            </span>
          )}
          {loading && <span className="memory-loading">SCANNING...</span>}
        </div>
      </div>

      {/* Stats header */}
      <div className="activity-stats-bar">
        <div className="activity-stat">
          <span className="activity-stat-label">TOTAL EVENTS</span>
          <span className="activity-stat-value">{stats.total}</span>
        </div>
        <div className="activity-stat">
          <span className="activity-stat-label">ACTIVE DAYS</span>
          <span className="activity-stat-value">{stats.activeDays}</span>
        </div>
        <div className="activity-stat">
          <span className="activity-stat-label">EVENTS TODAY</span>
          <span className="activity-stat-value">{stats.eventsToday}</span>
        </div>
        <div className="activity-stat">
          <span className="activity-stat-label">MOST ACTIVE</span>
          <span className="activity-stat-value">{stats.mostActiveDayCount}</span>
          {stats.mostActiveDay && (
            <span className="activity-stat-sub">{stats.mostActiveDay}</span>
          )}
        </div>
        <div className="activity-stat-types">
          {typeDistribution.map((t) => (
            <span key={t.type} className={`badge ${t.config.badge}`}>
              {t.config.label} ({t.count})
            </span>
          ))}
        </div>
      </div>

      {/* Heatmap + Type Distribution + Project Breakdown */}
      <div className="activity-panels-row">
        <HudPanel label="ACTIVITY HEATMAP // 90 DAYS" className="activity-heatmap-panel">
          <ActivityHeatmap entries={allEntries} />
        </HudPanel>
        <HudPanel label="TYPE DISTRIBUTION">
          <div className="activity-type-dist">
            {typeDistribution.map((t) => (
              <div key={t.type} className="activity-dist-row">
                <span className={`badge ${t.config.badge} activity-dist-badge`}>{t.config.label}</span>
                <div className="activity-dist-track">
                  <div
                    className="activity-dist-fill"
                    style={{ width: `${(t.count / maxTypeCount) * 100}%` }}
                  />
                </div>
                <span className="activity-dist-count">{t.count}</span>
              </div>
            ))}
          </div>
        </HudPanel>
        <HudPanel label="PROJECT BREAKDOWN">
          <div className="activity-project-list">
            {projects.length > 0 ? (
              projects.map(([proj, count]) => (
                <div key={proj} className="activity-project-row">
                  <span className="activity-project-name">{proj}</span>
                  <span className="activity-project-count">{count}</span>
                </div>
              ))
            ) : (
              <span className="activity-no-data">NO PROJECT DATA</span>
            )}
          </div>
        </HudPanel>
      </div>

      {/* Search + Type Filters + Controls */}
      <div className="activity-toolbar">
        <div className="activity-search-wrapper">
          <span className="activity-search-prefix">&gt;_</span>
          <input
            type="text"
            className="activity-search-input"
            placeholder="SEARCH EVENTS..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          {searchQuery && (
            <button
              className="activity-search-clear"
              onClick={() => setSearchQuery("")}
              type="button"
            >
              CLR
            </button>
          )}
        </div>

        <div className="activity-type-filters">
          {ALL_TYPES.map((type) => {
            const config = TYPE_CONFIG[type];
            const count = stats.byType[type] ?? 0;
            const active = filterType.has(type);
            return (
              <button
                key={type}
                className={`activity-type-btn ${active ? "active" : ""} ${count === 0 ? "empty" : ""}`}
                onClick={() => toggleType(type)}
                type="button"
              >
                {config?.label ?? type}
                {count > 0 && <span className="activity-type-count">{count}</span>}
              </button>
            );
          })}
        </div>

        <div className="activity-controls">
          <select
            className="activity-project-select"
            value={filterProject}
            onChange={(e) => setFilterProject(e.target.value)}
          >
            <option value="">ALL PROJECTS</option>
            {projects.map(([proj, count]) => (
              <option key={proj} value={proj}>
                {proj.toUpperCase()} ({count})
              </option>
            ))}
          </select>
          <button className="activity-ctrl-btn" onClick={fetchActivity} type="button">
            REFRESH
          </button>
          <button className="activity-ctrl-btn" onClick={() => setLiveEntries([])} type="button">
            CLEAR LIVE
          </button>
        </div>
      </div>

      {/* Results line */}
      <div className="activity-results-line">
        <span>
          SHOWING {filteredCount}
          {(filterType.size > 0 || searchQuery) && ` (FILTERED FROM ${stats.total})`}
        </span>
        <StatusLine
          items={[
            ["PROJECTS", String(projects.length)],
            ["LIVE", String(liveEntries.length)],
            ["SSE", connected ? "CONNECTED" : "OFF"],
          ]}
        />
      </div>

      {/* Error */}
      {error && (
        <div className="activity-error">
          ERROR: {error}
        </div>
      )}

      {/* Live entries banner */}
      {liveEntries.length > 0 && (
        <div className="activity-live-banner">
          <span className="live-dot" />
          {liveEntries.length} NEW LIVE EVENT{liveEntries.length > 1 ? "S" : ""}
        </div>
      )}

      {/* Grouped timeline */}
      <div className="activity-timeline">
        {groupedEntries.length > 0 ? (
          groupedEntries.map((group) => {
            const isCollapsed = collapsedDays.has(group.date);
            return (
              <div key={group.date} className="activity-day-group">
                <div
                  className="activity-day-header"
                  onClick={() => toggleDay(group.date)}
                >
                  <span className="activity-day-toggle">
                    {isCollapsed ? "\u25B8" : "\u25BE"}
                  </span>
                  <span className="activity-day-label">{group.label}</span>
                  <span className="activity-day-date">{group.date}</span>
                  <span className="activity-day-count">
                    {group.entries.length} EVENT{group.entries.length !== 1 ? "S" : ""}
                  </span>
                  <div className="activity-day-line" />
                </div>
                {!isCollapsed && (
                  <div className="activity-day-entries">
                    {group.entries.map((entry, i) => (
                      <CompactEvent key={`${entry.type}-${entry.id}-${i}`} entry={entry} />
                    ))}
                  </div>
                )}
              </div>
            );
          })
        ) : (
          <HudPanel label="TIMELINE">
            <Waveform points={60} height={40} seed={99} />
            <DataMatrix rows={4} cols={24} seed={55} />
            <HexStream seed={77} />
            <div className="empty-state">
              <div className="empty-label">NO ACTIVITY</div>
              <p style={{ fontSize: "var(--font-size-xs)" }}>
                {searchQuery
                  ? `No results for "${searchQuery}". Try a different query.`
                  : "Awaiting system events..."}
              </p>
            </div>
          </HudPanel>
        )}
      </div>

      <div style={{ display: "flex", gap: "var(--space-4)" }}>
        <HexStream seed={50} />
        <HexStream seed={51} />
      </div>
    </>
  );
}
