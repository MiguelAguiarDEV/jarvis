"use client";

import { useState, useEffect, useCallback } from "react";
import { HudPanel, HexStream, Metric, StatusLine, DataMatrix } from "@/components/hud";
import type { Task } from "@/lib/mnemo";

// ── Helpers ──────────────────────────────────────────────────────────────

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
  });
}

function daysAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "1d ago";
  return `${days}d ago`;
}

// ── Constants ────────────────────────────────────────────────────────────

const STATUS_ORDER = ["open", "in_progress", "done"] as const;

const STATUS_CONFIG: Record<string, { label: string; badge: string; color: string }> = {
  open: { label: "PENDING", badge: "badge-blue", color: "var(--accent-blue)" },
  in_progress: { label: "IN PROGRESS", badge: "badge-amber", color: "var(--accent-amber)" },
  done: { label: "DONE", badge: "badge-green", color: "var(--accent-green)" },
  blocked: { label: "BLOCKED", badge: "badge-red", color: "var(--accent-red)" },
  cancelled: { label: "CANCELLED", badge: "badge-muted", color: "var(--text-dim)" },
};

const PRIORITY_CONFIG: Record<string, { badge: string; color: string }> = {
  critical: { badge: "badge-red", color: "var(--accent-red)" },
  high: { badge: "badge-red", color: "var(--accent-red)" },
  medium: { badge: "badge-amber", color: "var(--accent-amber)" },
  low: { badge: "badge-green", color: "var(--accent-green)" },
};

const STATUS_CYCLE: Record<string, string> = {
  open: "in_progress",
  in_progress: "done",
};

// ── Task Card ────────────────────────────────────────────────────────────

function TaskCard({
  task,
  onStatusChange,
  onDelete,
}: {
  task: Task;
  onStatusChange: (id: number, status: string) => void;
  onDelete: (id: number) => void;
}) {
  const [showConfirm, setShowConfirm] = useState(false);
  const statusCfg = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.open;
  const priorityCfg = PRIORITY_CONFIG[task.priority] ?? PRIORITY_CONFIG.medium;
  const nextStatus = STATUS_CYCLE[task.status];
  const hasChildren = task.children && task.children.length > 0;

  return (
    <div className="task-card">
      <div className="task-card-header">
        <span
          className={`badge ${priorityCfg.badge}`}
          style={{ fontSize: "0.6rem" }}
        >
          {task.priority.toUpperCase()}
        </span>
        <span className="task-card-date">{daysAgo(task.created_at)}</span>
      </div>

      <div className="task-card-title">{task.title}</div>

      {task.description && (
        <div className="task-card-desc">
          {task.description.length > 100
            ? task.description.slice(0, 100) + "..."
            : task.description}
        </div>
      )}

      <div className="task-card-footer">
        <div className="task-card-meta">
          {task.project && (
            <span className="task-card-project">{task.project}</span>
          )}
          {hasChildren && (
            <span className="task-card-subtasks">
              {task.children!.length} subtask{task.children!.length > 1 ? "s" : ""}
            </span>
          )}
        </div>

        <div className="task-card-actions">
          {nextStatus && (
            <button
              className="task-action-btn task-action-cycle"
              onClick={() => onStatusChange(task.id, nextStatus)}
              title={`Move to ${STATUS_CONFIG[nextStatus]?.label}`}
            >
              {task.status === "open" ? "\u25B6" : "\u2713"}
            </button>
          )}
          {!showConfirm ? (
            <button
              className="task-action-btn task-action-delete"
              onClick={() => setShowConfirm(true)}
              title="Delete task"
            >
              \u2715
            </button>
          ) : (
            <button
              className="task-action-btn task-action-confirm"
              onClick={() => {
                onDelete(task.id);
                setShowConfirm(false);
              }}
              title="Confirm delete"
            >
              DEL?
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Progress Summary Bar ─────────────────────────────────────────────────

function ProgressBar({
  counts,
  total,
}: {
  counts: { open: number; in_progress: number; done: number };
  total: number;
}) {
  if (total === 0) return null;
  const pctOpen = (counts.open / total) * 100;
  const pctProgress = (counts.in_progress / total) * 100;
  const pctDone = (counts.done / total) * 100;
  const completionRate = Math.round((counts.done / total) * 100);

  return (
    <div className="task-progress-bar">
      <div className="task-progress-label">
        <span>COMPLETION</span>
        <span className="task-progress-pct">{completionRate}%</span>
        <span className="task-progress-fraction">
          {counts.done}/{total}
        </span>
      </div>
      <div className="task-progress-track">
        {pctDone > 0 && (
          <div
            className="task-progress-fill task-progress-done"
            style={{ width: `${pctDone}%` }}
          />
        )}
        {pctProgress > 0 && (
          <div
            className="task-progress-fill task-progress-active"
            style={{ width: `${pctProgress}%` }}
          />
        )}
        {pctOpen > 0 && (
          <div
            className="task-progress-fill task-progress-pending"
            style={{ width: `${pctOpen}%` }}
          />
        )}
      </div>
      <div className="task-progress-legend">
        <span>
          <span className="task-legend-dot" style={{ background: "var(--accent-green)" }} />
          DONE {counts.done}
        </span>
        <span>
          <span className="task-legend-dot" style={{ background: "var(--accent-amber)" }} />
          ACTIVE {counts.in_progress}
        </span>
        <span>
          <span className="task-legend-dot" style={{ background: "var(--accent-blue)" }} />
          PENDING {counts.open}
        </span>
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [filterProject, setFilterProject] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterPriority, setFilterPriority] = useState("");

  // Inline create
  const [newTitle, setNewTitle] = useState("");
  const [newPriority, setNewPriority] = useState("medium");
  const [creating, setCreating] = useState(false);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filterProject) params.set("project", filterProject);
    if (filterStatus) params.set("status", filterStatus);
    if (filterPriority) params.set("priority", filterPriority);

    try {
      const res = await fetch(`/api/tasks?${params.toString()}`);
      const data = await res.json();
      const list = data.tasks ?? data ?? [];
      setTasks(Array.isArray(list) ? list : []);
      setError(null);
    } catch (err) {
      setError(String(err));
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, [filterProject, filterStatus, filterPriority]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // ── Handlers ───────────────────────────────────────────────────────

  const handleStatusChange = async (id: number, status: string) => {
    try {
      await fetch("/api/tasks", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, status }),
      });
      fetchTasks();
    } catch (err) {
      setError(String(err));
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await fetch("/api/tasks", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
      });
      fetchTasks();
    } catch (err) {
      setError(String(err));
    }
  };

  const handleInlineCreate = async () => {
    if (!newTitle.trim() || creating) return;
    setCreating(true);
    try {
      await fetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: newTitle.trim(),
          priority: newPriority,
          status: "open",
          source: "dashboard",
          assignee_type: "user",
        }),
      });
      setNewTitle("");
      setNewPriority("medium");
      fetchTasks();
    } catch (err) {
      setError(String(err));
    } finally {
      setCreating(false);
    }
  };

  // ── Computed stats ─────────────────────────────────────────────────

  const allTasks = tasks;
  const openCount = allTasks.filter((t) => t.status === "open").length;
  const progressCount = allTasks.filter((t) => t.status === "in_progress").length;
  const doneCount = allTasks.filter((t) => t.status === "done").length;
  const blockedCount = allTasks.filter((t) => t.status === "blocked").length;
  const totalActive = openCount + progressCount + doneCount;
  const completionRate = totalActive > 0 ? Math.round((doneCount / totalActive) * 100) : 0;

  // Tasks created in last 7 days
  const weekAgo = Date.now() - 7 * 86400000;
  const thisWeek = allTasks.filter((t) => new Date(t.created_at).getTime() > weekAgo).length;

  // Unique projects
  const projects = Array.from(new Set(allTasks.map((t) => t.project).filter(Boolean))) as string[];

  // Group by status for kanban
  const byStatus: Record<string, Task[]> = { open: [], in_progress: [], done: [] };
  for (const t of allTasks) {
    if (byStatus[t.status]) {
      byStatus[t.status].push(t);
    }
  }

  return (
    <>
      {/* Page header */}
      <div className="page-header">
        <div>
          <div className="page-kicker">OPS // TASK ENGINE</div>
          <h2 className="page-title">Tasks</h2>
        </div>
        <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
          {loading && (
            <span style={{
              fontSize: "var(--font-size-xs)",
              color: "var(--accent-amber)",
              letterSpacing: "0.15em",
              animation: "blink 1s step-end infinite",
            }}>
              LOADING...
            </span>
          )}
          <button
            onClick={fetchTasks}
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
              fontFamily: "var(--font-mono)",
              fontSize: "var(--font-size-xs)",
              padding: "var(--space-2) var(--space-3)",
              cursor: "pointer",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
            }}
          >
            REFRESH
          </button>
        </div>
      </div>

      {/* Inline create - terminal style */}
      <div className="task-inline-create">
        <span className="task-create-prefix">&gt;_</span>
        <input
          type="text"
          className="task-create-input"
          placeholder="NEW TASK..."
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleInlineCreate();
          }}
          autoComplete="off"
          spellCheck={false}
          disabled={creating}
        />
        <div className="task-create-priority">
          {(["low", "medium", "high"] as const).map((p) => (
            <button
              key={p}
              className={`task-priority-btn ${newPriority === p ? "active" : ""}`}
              onClick={() => setNewPriority(p)}
              style={{
                color: newPriority === p
                  ? PRIORITY_CONFIG[p]?.color
                  : "var(--text-dim)",
                borderColor: newPriority === p
                  ? PRIORITY_CONFIG[p]?.color
                  : "var(--border)",
              }}
              type="button"
            >
              {p[0].toUpperCase()}
            </button>
          ))}
        </div>
        <button
          className="task-create-submit"
          onClick={handleInlineCreate}
          disabled={!newTitle.trim() || creating}
          type="button"
        >
          {creating ? "..." : "ADD"}
        </button>
      </div>

      {/* Stats strip */}
      <div className="task-stats-bar">
        <div className="task-stat">
          <span className="task-stat-label">TOTAL</span>
          <span className="task-stat-value">{allTasks.length}</span>
        </div>
        <div className="task-stat">
          <span className="task-stat-label">DONE</span>
          <span className="task-stat-value" style={{ color: "var(--accent-green)" }}>{doneCount}</span>
        </div>
        <div className="task-stat">
          <span className="task-stat-label">ACTIVE</span>
          <span className="task-stat-value" style={{ color: "var(--accent-amber)" }}>{progressCount}</span>
        </div>
        <div className="task-stat">
          <span className="task-stat-label">PENDING</span>
          <span className="task-stat-value" style={{ color: "var(--accent-blue)" }}>{openCount}</span>
        </div>
        {blockedCount > 0 && (
          <div className="task-stat">
            <span className="task-stat-label">BLOCKED</span>
            <span className="task-stat-value" style={{ color: "var(--accent-red)" }}>{blockedCount}</span>
          </div>
        )}
        <div className="task-stat-sep" />
        <div className="task-stat">
          <span className="task-stat-label">RATE</span>
          <span className="task-stat-value">{completionRate}%</span>
        </div>
        <div className="task-stat">
          <span className="task-stat-label">THIS WEEK</span>
          <span className="task-stat-value">{thisWeek}</span>
        </div>
      </div>

      {/* Progress bar */}
      <ProgressBar
        counts={{ open: openCount, in_progress: progressCount, done: doneCount }}
        total={totalActive}
      />

      {/* Error */}
      {error && (
        <div style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--accent-red)",
          padding: "var(--space-2) var(--space-3)",
          fontSize: "var(--font-size-xs)",
          color: "var(--accent-red)",
        }}>
          ERROR: {error}
        </div>
      )}

      {/* Filters */}
      <div className="task-filter-row">
        <select
          className="filter-select"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
        >
          <option value="">ALL STATUS</option>
          <option value="open">PENDING</option>
          <option value="in_progress">IN PROGRESS</option>
          <option value="done">DONE</option>
          <option value="blocked">BLOCKED</option>
          <option value="cancelled">CANCELLED</option>
        </select>
        <select
          className="filter-select"
          value={filterPriority}
          onChange={(e) => setFilterPriority(e.target.value)}
        >
          <option value="">ALL PRIORITY</option>
          <option value="high">HIGH</option>
          <option value="medium">MEDIUM</option>
          <option value="low">LOW</option>
        </select>
        <input
          className="filter-input"
          placeholder="PROJECT FILTER"
          value={filterProject}
          onChange={(e) => setFilterProject(e.target.value)}
        />
        <StatusLine
          items={[
            ["SHOWING", String(allTasks.length)],
            ["PROJECTS", String(projects.length)],
          ]}
        />
      </div>

      {/* Kanban columns */}
      {!filterStatus && (
        <div className="task-kanban">
          {STATUS_ORDER.map((status) => {
            const cfg = STATUS_CONFIG[status];
            const statusTasks = byStatus[status] ?? [];
            return (
              <div key={status} className="task-kanban-col">
                <div className="task-kanban-header">
                  <span className="task-kanban-title" style={{ color: cfg.color }}>
                    {cfg.label}
                  </span>
                  <span className="task-kanban-count">{statusTasks.length}</span>
                </div>
                <div className="task-kanban-cards">
                  {statusTasks.length > 0 ? (
                    statusTasks.map((task) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        onStatusChange={handleStatusChange}
                        onDelete={handleDelete}
                      />
                    ))
                  ) : (
                    <div className="task-kanban-empty">
                      <DataMatrix rows={2} cols={16} seed={status.length * 17} />
                      <span>NO TASKS</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Filtered list view - shows when a status filter is active */}
      {filterStatus && (
        <HudPanel label={`TASK LIST // ${STATUS_CONFIG[filterStatus]?.label ?? filterStatus.toUpperCase()}`}>
          {loading ? (
            <div className="empty-state">
              <div className="empty-label">LOADING...</div>
            </div>
          ) : allTasks.length > 0 ? (
            <div className="task-list-filtered">
              {allTasks.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  onStatusChange={handleStatusChange}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          ) : (
            <>
              <DataMatrix rows={4} cols={24} seed={55} />
              <HexStream seed={77} />
              <div className="empty-state">
                <div className="empty-label">NO TASKS</div>
                <p style={{ fontSize: "var(--font-size-xs)" }}>
                  Adjust filters or create a task
                </p>
              </div>
            </>
          )}
        </HudPanel>
      )}

      <div style={{ display: "flex", gap: "var(--space-4)" }}>
        <HexStream seed={30} />
        <HexStream seed={31} />
      </div>
    </>
  );
}
