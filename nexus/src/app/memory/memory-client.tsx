"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import type { SearchResult } from "@/lib/engram";

// ── Type badge color mapping ──────────────────────────────────────────
function typeBadge(type: string): string {
  switch (type) {
    case "decision":
    case "architecture":
      return "badge-green";
    case "bugfix":
      return "badge-red";
    case "discovery":
    case "learning":
      return "badge-amber";
    case "pattern":
    case "config":
      return "badge-blue";
    case "preference":
      return "badge-purple";
    default:
      return "badge-muted";
  }
}

// ── All known observation types ───────────────────────────────────────
const ALL_TYPES = [
  "discovery",
  "decision",
  "architecture",
  "bugfix",
  "pattern",
  "config",
  "preference",
];

// ── Date formatting ───────────────────────────────────────────────────
function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
  });
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

// ── Sort helpers ──────────────────────────────────────────────────────
type SortMode = "date" | "title";

function sortObservations(
  obs: SearchResult[],
  mode: SortMode,
): SearchResult[] {
  const sorted = [...obs];
  if (mode === "title") {
    sorted.sort((a, b) => a.title.localeCompare(b.title));
  } else {
    sorted.sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  }
  return sorted;
}

// ── Props ─────────────────────────────────────────────────────────────
interface MemoryClientProps {
  initialObservations: SearchResult[];
}

export default function MemoryClient({
  initialObservations,
}: MemoryClientProps) {
  const [observations, setObservations] =
    useState<SearchResult[]>(initialObservations);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set());
  const [activeProject, setActiveProject] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("date");
  const [expandedCards, setExpandedCards] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Fetch observations from API ───────────────────────────────────
  const fetchObservations = useCallback(
    async (query: string) => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (query) params.set("q", query);
        if (activeProject) params.set("project", activeProject);
        // type filter is applied client-side since multi-select
        params.set("limit", "100");

        const res = await fetch(`/api/observations?${params.toString()}`);
        if (!res.ok) throw new Error(`${res.status}`);
        const data = await res.json();
        setObservations(data.results ?? []);
      } catch {
        // keep existing data on error
      } finally {
        setLoading(false);
      }
    },
    [activeProject],
  );

  // ── Debounced search ──────────────────────────────────────────────
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetchObservations(searchQuery);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [searchQuery, fetchObservations]);

  // ── Re-fetch when project filter changes ──────────────────────────
  useEffect(() => {
    fetchObservations(searchQuery);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeProject]);

  // ── Compute derived data ──────────────────────────────────────────
  const byType = new Map<string, number>();
  const byProject = new Map<string, number>();
  for (const o of observations) {
    byType.set(o.type, (byType.get(o.type) ?? 0) + 1);
    if (o.project) byProject.set(o.project, (byProject.get(o.project) ?? 0) + 1);
  }

  const typeEntries = Array.from(byType.entries()).sort((a, b) => b[1] - a[1]);
  const projectEntries = Array.from(byProject.entries()).sort(
    (a, b) => b[1] - a[1],
  );
  const topicCount = new Set(
    observations.filter((o) => o.topic_key).map((o) => o.topic_key),
  ).size;

  // ── Apply client-side filters + sort ──────────────────────────────
  let filtered = observations;
  if (activeTypes.size > 0) {
    filtered = filtered.filter((o) => activeTypes.has(o.type));
  }
  filtered = sortObservations(filtered, sortMode);

  // ── Toggle type filter ────────────────────────────────────────────
  const toggleType = (type: string) => {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  // ── Toggle card expansion ─────────────────────────────────────────
  const toggleExpand = (id: number) => {
    setExpandedCards((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  return (
    <>
      {/* Page header */}
      <div className="page-header">
        <div>
          <div className="page-kicker">MEMORY // KNOWLEDGE INDEX</div>
          <h2 className="page-title">Memory Browser</h2>
        </div>
        <span className="badge badge-amber">
          {observations.length} OBSERVATIONS
        </span>
      </div>

      {/* Stats bar */}
      <div className="memory-stats-bar">
        <div className="memory-stat">
          <span className="memory-stat-label">TOTAL</span>
          <span className="memory-stat-value">{observations.length}</span>
        </div>
        <div className="memory-stat">
          <span className="memory-stat-label">TYPES</span>
          <span className="memory-stat-value">{byType.size}</span>
        </div>
        <div className="memory-stat">
          <span className="memory-stat-label">PROJECTS</span>
          <span className="memory-stat-value">{byProject.size}</span>
        </div>
        <div className="memory-stat">
          <span className="memory-stat-label">TOPICS</span>
          <span className="memory-stat-value">{topicCount}</span>
        </div>
        <div className="memory-stat-types">
          {typeEntries.map(([type, count]) => (
            <span key={type} className={`badge ${typeBadge(type)}`}>
              {type} ({count})
            </span>
          ))}
        </div>
        {loading && (
          <span className="memory-loading">SCANNING...</span>
        )}
      </div>

      {/* Search + Filters */}
      <div className="memory-toolbar">
        <div className="memory-search-wrapper">
          <span className="memory-search-prefix">&gt;_</span>
          <input
            type="text"
            className="memory-search-input"
            placeholder="SEARCH OBSERVATIONS..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          {searchQuery && (
            <button
              className="memory-search-clear"
              onClick={() => setSearchQuery("")}
              type="button"
            >
              CLR
            </button>
          )}
        </div>

        <div className="memory-type-filters">
          {ALL_TYPES.map((type) => {
            const count = byType.get(type) ?? 0;
            const active = activeTypes.has(type);
            return (
              <button
                key={type}
                className={`memory-type-btn ${active ? "active" : ""} ${count === 0 ? "empty" : ""}`}
                onClick={() => toggleType(type)}
                type="button"
              >
                {type}
                {count > 0 && <span className="memory-type-count">{count}</span>}
              </button>
            );
          })}
        </div>

        <div className="memory-controls">
          <select
            className="memory-project-select"
            value={activeProject}
            onChange={(e) => setActiveProject(e.target.value)}
          >
            <option value="">ALL PROJECTS</option>
            {projectEntries.map(([proj, count]) => (
              <option key={proj} value={proj}>
                {proj.toUpperCase()} ({count})
              </option>
            ))}
          </select>

          <div className="memory-sort-group">
            <button
              className={`memory-sort-btn ${sortMode === "date" ? "active" : ""}`}
              onClick={() => setSortMode("date")}
              type="button"
            >
              DATE
            </button>
            <button
              className={`memory-sort-btn ${sortMode === "title" ? "active" : ""}`}
              onClick={() => setSortMode("title")}
              type="button"
            >
              A-Z
            </button>
          </div>
        </div>
      </div>

      {/* Results count */}
      <div className="memory-results-line">
        <span>
          SHOWING {filtered.length}
          {activeTypes.size > 0 && ` (FILTERED FROM ${observations.length})`}
        </span>
        {searchQuery && (
          <span className="memory-query-echo">
            QUERY: &quot;{searchQuery}&quot;
          </span>
        )}
      </div>

      {/* Knowledge cards grid */}
      <div className="knowledge-grid memory-grid">
        {filtered.map((obs) => {
          const expanded = expandedCards.has(obs.id);
          return (
            <div
              key={obs.id}
              className={`knowledge-card memory-card ${expanded ? "expanded" : ""}`}
              onClick={() => toggleExpand(obs.id)}
            >
              <div className="memory-card-header">
                <span className={`badge ${typeBadge(obs.type)}`}>
                  {obs.type}
                </span>
                <span className="memory-card-date">
                  {formatDate(obs.created_at)}
                </span>
              </div>

              <div className="card-title">{obs.title}</div>

              <div
                className={`card-preview ${expanded ? "card-preview-expanded" : ""}`}
              >
                {expanded ? obs.content : obs.content.length > 150 ? obs.content.slice(0, 150) + "..." : obs.content}
              </div>

              <div className="card-meta">
                {obs.project && (
                  <span className="memory-project-badge">{obs.project}</span>
                )}
                {obs.topic_key && (
                  <span className="memory-topic-key">{obs.topic_key}</span>
                )}
                <span className="memory-card-timestamp">
                  {formatTimestamp(obs.created_at)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="empty-state">
          <div className="empty-label">NO OBSERVATIONS FOUND</div>
          <p style={{ color: "var(--text-dim)", fontSize: "var(--font-size-sm)" }}>
            {searchQuery
              ? `No results for "${searchQuery}". Try a different query.`
              : "No observations match the current filters."}
          </p>
        </div>
      )}
    </>
  );
}
