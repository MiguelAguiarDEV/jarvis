"use client";

import { useState, useEffect, useCallback } from "react";
import { HudPanel, TerminalBar, HexStream, Metric, StatusLine } from "@/components/hud";

// ─── Types ──────────────────────────────────────────────────────────────────

interface ModelCost {
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  calls: number;
}

interface DayCost {
  date: string;
  cost_usd: number;
  calls: number;
}

interface BudgetReport {
  claude_used: number;
  claude_budget: number;
  openai_used: number;
  openai_budget: number;
  claude_pct: number;
  openai_pct: number;
}

interface CostSummary {
  total_cost: number;
  period: string;
  by_model: ModelCost[];
  by_day: DayCost[];
  budget: BudgetReport | null;
}

interface SessionCost {
  session_id: string;
  project: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  calls: number;
  first_call: string;
  last_call: string;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatUSD(v: number): string {
  return `$${v.toFixed(4)}`;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatDate(iso: string): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
  });
}

function formatDateTime(iso: string): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function truncateSessionID(id: string): string {
  if (id.length <= 12) return id;
  return id.slice(0, 6) + ".." + id.slice(-4);
}

// ─── Budget Bar Component ───────────────────────────────────────────────────

function BudgetBar({
  label,
  used,
  budget,
  pct,
}: {
  label: string;
  used: number;
  budget: number;
  pct: number;
}) {
  const barWidth = 30;
  const filled = Math.min(Math.round((pct / 100) * barWidth), barWidth);
  const empty = barWidth - filled;

  const isWarning = pct >= 80;
  const isCritical = pct >= 95;

  const barChar = isCritical ? "#" : "=";
  const bar = barChar.repeat(filled) + " ".repeat(empty);

  return (
    <div
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: "var(--font-size-sm)",
        lineHeight: 1.6,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: "var(--space-1)",
        }}
      >
        <span style={{ color: "var(--text-secondary)" }}>{label}</span>
        <span
          style={{
            color: isCritical
              ? "var(--accent-red)"
              : isWarning
                ? "var(--accent-amber)"
                : "var(--accent-green)",
          }}
        >
          {pct.toFixed(1)}%
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <span style={{ color: "var(--text-dim)" }}>[</span>
        <span
          style={{
            color: isCritical
              ? "var(--accent-red)"
              : isWarning
                ? "var(--accent-amber)"
                : "var(--accent-green)",
            letterSpacing: "0.05em",
          }}
        >
          {bar}
        </span>
        <span style={{ color: "var(--text-dim)" }}>]</span>
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: "var(--font-size-xs)",
          color: "var(--text-dim)",
          marginTop: "var(--space-1)",
        }}
      >
        <span>USED: ${used.toFixed(2)}</span>
        <span>LIMIT: ${budget.toFixed(0)}</span>
        <span>REMAINING: ${(budget - used).toFixed(2)}</span>
      </div>
      {isWarning && (
        <div
          style={{
            fontSize: "var(--font-size-xs)",
            color: isCritical ? "var(--accent-red)" : "var(--accent-amber)",
            marginTop: "var(--space-1)",
          }}
        >
          {isCritical ? "!! CRITICAL: BUDGET NEARLY EXHAUSTED" : "! WARNING: BUDGET >80%"}
        </div>
      )}
    </div>
  );
}

// ─── Sparkline Component (ASCII) ────────────────────────────────────────────

function Sparkline({ values, width = 30 }: { values: number[]; width?: number }) {
  if (values.length === 0) return <span style={{ color: "var(--text-dim)" }}>--</span>;

  const max = Math.max(...values, 0.01);
  const chars = [" ", "\u2581", "\u2582", "\u2583", "\u2584", "\u2585", "\u2586", "\u2587", "\u2588"];

  // Sample or pad to width
  const sampled =
    values.length >= width
      ? values.slice(-width)
      : [...Array(width - values.length).fill(0), ...values];

  const line = sampled
    .map((v) => {
      const idx = Math.min(Math.floor((v / max) * (chars.length - 1)), chars.length - 1);
      return chars[idx];
    })
    .join("");

  return (
    <span
      style={{
        fontFamily: "var(--font-mono)",
        color: "var(--accent-green)",
        letterSpacing: "0",
      }}
    >
      {line}
    </span>
  );
}

// ─── Page ───────────────────────────────────────────────────────────────────

type Period = "day" | "week" | "month";

export default function CostsPage() {
  const [summary, setSummary] = useState<CostSummary | null>(null);
  const [sessions, setSessions] = useState<SessionCost[]>([]);
  const [period, setPeriod] = useState<Period>("month");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [costRes, sessRes] = await Promise.all([
        fetch(`/api/costs?period=${period}`),
        fetch(`/api/costs/sessions?period=${period}&limit=30`),
      ]);
      const costData = await costRes.json();
      const sessData = await sessRes.json();
      setSummary(costData);
      setSessions(sessData.sessions ?? []);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const totalCost = summary?.total_cost ?? 0;
  const budget = summary?.budget;
  const totalBudget = (budget?.claude_budget ?? 200) + (budget?.openai_budget ?? 200);
  const totalUsed = (budget?.claude_used ?? 0) + (budget?.openai_used ?? 0);

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-kicker">ANALYTICS // COST TRACKING</div>
          <h2 className="page-title">Costs</h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          {/* Period selector */}
          {(["day", "week", "month"] as Period[]).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              style={{
                background: p === period ? "var(--bg-surface)" : "transparent",
                border:
                  p === period
                    ? "1px solid var(--accent-green)"
                    : "1px solid var(--border-subtle)",
                color: p === period ? "var(--accent-green)" : "var(--text-dim)",
                fontFamily: "var(--font-mono)",
                fontSize: "var(--font-size-xs)",
                padding: "var(--space-1) var(--space-3)",
                cursor: "pointer",
                textTransform: "uppercase",
                letterSpacing: "0.1em",
              }}
            >
              {p}
            </button>
          ))}
          <button
            onClick={fetchData}
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
              fontFamily: "var(--font-mono)",
              fontSize: "var(--font-size-xs)",
              padding: "var(--space-1) var(--space-3)",
              cursor: "pointer",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
            }}
          >
            REFRESH
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--accent-red)",
            padding: "var(--space-2) var(--space-3)",
            fontSize: "var(--font-size-xs)",
            color: "var(--accent-red)",
          }}
        >
          ERROR: {error}
        </div>
      )}

      {loading ? (
        <div className="empty-state">
          <div className="empty-label">LOADING COST DATA...</div>
        </div>
      ) : (
        <>
          {/* Top metrics row */}
          <div className="hud-grid-4">
            <HudPanel label="TOTAL COST">
              <Metric
                label={period.toUpperCase()}
                value={`$${totalCost.toFixed(2)}`}
                sub={`${summary?.by_model?.length ?? 0} models`}
              />
            </HudPanel>
            <HudPanel label="BUDGET USED">
              <Metric
                label="COMBINED"
                value={`${((totalUsed / totalBudget) * 100).toFixed(1)}%`}
                sub={`$${totalUsed.toFixed(2)} / $${totalBudget.toFixed(0)}`}
              />
            </HudPanel>
            <HudPanel label="TOTAL SESSIONS">
              <Metric
                label="THIS PERIOD"
                value={sessions.length}
                sub={`${summary?.by_day?.length ?? 0} active days`}
              />
            </HudPanel>
            <HudPanel label="DAILY TREND">
              <Sparkline
                values={
                  summary?.by_day
                    ? [...summary.by_day].reverse().map((d) => d.cost_usd)
                    : []
                }
              />
            </HudPanel>
          </div>

          {/* Budget bars */}
          {budget && (
            <HudPanel label="BUDGET STATUS">
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
                <BudgetBar
                  label="CLAUDE (ANTHROPIC)"
                  used={budget.claude_used}
                  budget={budget.claude_budget}
                  pct={budget.claude_pct}
                />
                {budget.openai_budget > 0 && budget.openai_used > 0 && (
                  <BudgetBar
                    label="OPENAI"
                    used={budget.openai_used}
                    budget={budget.openai_budget}
                    pct={budget.openai_pct}
                  />
                )}
              </div>
            </HudPanel>
          )}

          {/* Cost by model table */}
          <HudPanel label="COST BY MODEL">
            {summary?.by_model && summary.by_model.length > 0 ? (
              <div style={{ overflowX: "auto" }}>
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    fontFamily: "var(--font-mono)",
                    fontSize: "var(--font-size-xs)",
                  }}
                >
                  <thead>
                    <tr
                      style={{
                        borderBottom: "1px solid var(--border-subtle)",
                        color: "var(--text-dim)",
                        textTransform: "uppercase",
                        letterSpacing: "0.1em",
                      }}
                    >
                      <th style={{ textAlign: "left", padding: "var(--space-2)" }}>MODEL</th>
                      <th style={{ textAlign: "right", padding: "var(--space-2)" }}>COST</th>
                      <th style={{ textAlign: "right", padding: "var(--space-2)" }}>INPUT TOK</th>
                      <th style={{ textAlign: "right", padding: "var(--space-2)" }}>OUTPUT TOK</th>
                      <th style={{ textAlign: "right", padding: "var(--space-2)" }}>CALLS</th>
                      <th style={{ textAlign: "left", padding: "var(--space-2)", width: "120px" }}>
                        SHARE
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.by_model.map((m) => {
                      const pct = totalCost > 0 ? (m.cost / totalCost) * 100 : 0;
                      const barLen = Math.round(pct / 5);
                      return (
                        <tr
                          key={m.model}
                          style={{
                            borderBottom: "1px solid var(--border-subtle)",
                            color: "var(--text-secondary)",
                          }}
                        >
                          <td style={{ padding: "var(--space-2)" }}>
                            <span style={{ color: "var(--accent-blue)" }}>{m.model}</span>
                          </td>
                          <td
                            style={{
                              textAlign: "right",
                              padding: "var(--space-2)",
                              color: "var(--accent-green)",
                            }}
                          >
                            {formatUSD(m.cost)}
                          </td>
                          <td style={{ textAlign: "right", padding: "var(--space-2)" }}>
                            {formatTokens(m.input_tokens)}
                          </td>
                          <td style={{ textAlign: "right", padding: "var(--space-2)" }}>
                            {formatTokens(m.output_tokens)}
                          </td>
                          <td style={{ textAlign: "right", padding: "var(--space-2)" }}>
                            {m.calls}
                          </td>
                          <td style={{ padding: "var(--space-2)" }}>
                            <span style={{ color: "var(--accent-amber)" }}>
                              {"=".repeat(barLen)}
                            </span>
                            <span style={{ color: "var(--text-dim)" }}>
                              {" "}
                              {pct.toFixed(0)}%
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-label">NO MODEL DATA</div>
              </div>
            )}
          </HudPanel>

          {/* Cost by day table */}
          <HudPanel label="COST BY DAY">
            {summary?.by_day && summary.by_day.length > 0 ? (
              <div style={{ overflowX: "auto" }}>
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    fontFamily: "var(--font-mono)",
                    fontSize: "var(--font-size-xs)",
                  }}
                >
                  <thead>
                    <tr
                      style={{
                        borderBottom: "1px solid var(--border-subtle)",
                        color: "var(--text-dim)",
                        textTransform: "uppercase",
                        letterSpacing: "0.1em",
                      }}
                    >
                      <th style={{ textAlign: "left", padding: "var(--space-2)" }}>DATE</th>
                      <th style={{ textAlign: "right", padding: "var(--space-2)" }}>COST</th>
                      <th style={{ textAlign: "right", padding: "var(--space-2)" }}>CALLS</th>
                      <th style={{ textAlign: "left", padding: "var(--space-2)", width: "200px" }}>
                        VOLUME
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.by_day.map((d) => {
                      const maxDayCost = Math.max(
                        ...summary.by_day.map((x) => x.cost_usd),
                        0.01,
                      );
                      const barLen = Math.round((d.cost_usd / maxDayCost) * 20);
                      return (
                        <tr
                          key={d.date}
                          style={{
                            borderBottom: "1px solid var(--border-subtle)",
                            color: "var(--text-secondary)",
                          }}
                        >
                          <td style={{ padding: "var(--space-2)" }}>{formatDate(d.date)}</td>
                          <td
                            style={{
                              textAlign: "right",
                              padding: "var(--space-2)",
                              color: "var(--accent-green)",
                            }}
                          >
                            {formatUSD(d.cost_usd)}
                          </td>
                          <td style={{ textAlign: "right", padding: "var(--space-2)" }}>
                            {d.calls}
                          </td>
                          <td style={{ padding: "var(--space-2)" }}>
                            <span style={{ color: "var(--accent-green)" }}>
                              {"\u2588".repeat(barLen)}
                            </span>
                            <span style={{ color: "var(--border-subtle)" }}>
                              {"\u2591".repeat(20 - barLen)}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-label">NO DAILY DATA</div>
              </div>
            )}
          </HudPanel>

          {/* Per-session breakdown */}
          <HudPanel label="SESSION BREAKDOWN">
            {sessions.length > 0 ? (
              <div style={{ overflowX: "auto" }}>
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    fontFamily: "var(--font-mono)",
                    fontSize: "var(--font-size-xs)",
                  }}
                >
                  <thead>
                    <tr
                      style={{
                        borderBottom: "1px solid var(--border-subtle)",
                        color: "var(--text-dim)",
                        textTransform: "uppercase",
                        letterSpacing: "0.1em",
                      }}
                    >
                      <th style={{ textAlign: "left", padding: "var(--space-2)" }}>SESSION</th>
                      <th style={{ textAlign: "left", padding: "var(--space-2)" }}>PROJECT</th>
                      <th style={{ textAlign: "left", padding: "var(--space-2)" }}>MODEL</th>
                      <th style={{ textAlign: "right", padding: "var(--space-2)" }}>TOKENS</th>
                      <th style={{ textAlign: "right", padding: "var(--space-2)" }}>COST</th>
                      <th style={{ textAlign: "right", padding: "var(--space-2)" }}>CALLS</th>
                      <th style={{ textAlign: "left", padding: "var(--space-2)" }}>LAST ACTIVE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.map((s, i) => (
                      <tr
                        key={`${s.session_id}-${s.model}-${i}`}
                        style={{
                          borderBottom: "1px solid var(--border-subtle)",
                          color: "var(--text-secondary)",
                        }}
                      >
                        <td
                          style={{
                            padding: "var(--space-2)",
                            color: "var(--text-muted)",
                          }}
                          title={s.session_id}
                        >
                          {truncateSessionID(s.session_id)}
                        </td>
                        <td style={{ padding: "var(--space-2)" }}>
                          <span className="badge badge-blue">
                            {s.project || "unknown"}
                          </span>
                        </td>
                        <td
                          style={{
                            padding: "var(--space-2)",
                            color: "var(--accent-blue)",
                          }}
                        >
                          {s.model}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: "var(--space-2)",
                            fontSize: "var(--font-size-xs)",
                          }}
                        >
                          <span style={{ color: "var(--text-dim)" }}>
                            {formatTokens(s.input_tokens)}
                          </span>
                          <span style={{ color: "var(--border)" }}> / </span>
                          <span style={{ color: "var(--text-dim)" }}>
                            {formatTokens(s.output_tokens)}
                          </span>
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: "var(--space-2)",
                            color: "var(--accent-green)",
                          }}
                        >
                          {formatUSD(s.cost)}
                        </td>
                        <td style={{ textAlign: "right", padding: "var(--space-2)" }}>
                          {s.calls}
                        </td>
                        <td
                          style={{
                            padding: "var(--space-2)",
                            color: "var(--text-dim)",
                          }}
                        >
                          {formatDateTime(s.last_call)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-label">NO SESSION DATA</div>
              </div>
            )}
          </HudPanel>

          {/* Status line */}
          <StatusLine
            items={[
              ["PERIOD", period.toUpperCase()],
              ["MODELS", String(summary?.by_model?.length ?? 0)],
              ["SESSIONS", String(sessions.length)],
              ["TOTAL", `$${totalCost.toFixed(2)}`],
            ]}
          />

          <div style={{ display: "flex", gap: "var(--space-4)" }}>
            <HexStream seed={70} />
            <HexStream seed={71} />
          </div>
        </>
      )}
    </>
  );
}
