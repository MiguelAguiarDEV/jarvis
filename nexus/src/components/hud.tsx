// HUD components for the jarvis dashboard terminal aesthetic

// ─── HUD Panel ─────────────────────────────────────────────────────────────
// Bordered frame with top-left label, like the reference images
export function HudPanel({
  label,
  children,
  className = "",
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`hud-panel ${className}`}>
      <div className="hud-panel-label">{label}</div>
      <div className="hud-panel-body">{children}</div>
    </div>
  );
}

// ─── Terminal Progress Bar ─────────────────────────────────────────────────
// CPU ████████░░░░ 67%
export function TerminalBar({
  label,
  value,
  max = 100,
  unit = "%",
}: {
  label: string;
  value: number;
  max?: number;
  unit?: string;
}) {
  const pct = Math.min((value / max) * 100, 100);
  const filled = Math.round(pct / 5);
  const empty = 20 - filled;
  const bar = "█".repeat(filled) + "░".repeat(empty);
  return (
    <div className="terminal-bar">
      <span className="terminal-bar-label">{label}</span>
      <span className="terminal-bar-fill">{bar}</span>
      <span className="terminal-bar-value">
        {typeof value === "number" ? value.toFixed(1) : value}
        {unit}
      </span>
    </div>
  );
}

// ─── Hex Stream ────────────────────────────────────────────────────────────
// Semi-cryptic data strings like BD32 CP67 V68-871 TOX 539 V02
export function HexStream({ seed = 0 }: { seed?: number }) {
  const chunks: string[] = [];
  let s = seed || Date.now();
  for (let i = 0; i < 8; i++) {
    s = ((s * 1103515245 + 12345) & 0x7fffffff) >>> 0;
    const hex = s.toString(16).toUpperCase().slice(-4);
    chunks.push(hex);
  }
  return (
    <div className="hex-stream">
      {chunks.map((h, i) => (
        <span key={i}>{h}</span>
      ))}
    </div>
  );
}

// ─── Data Matrix ───────────────────────────────────────────────────────────
// Grid of dots/squares like the reference decorative patterns
export function DataMatrix({
  rows = 4,
  cols = 16,
  seed = 42,
}: {
  rows?: number;
  cols?: number;
  seed?: number;
}) {
  let s = seed;
  const cells: boolean[][] = [];
  for (let r = 0; r < rows; r++) {
    const row: boolean[] = [];
    for (let c = 0; c < cols; c++) {
      s = ((s * 1103515245 + 12345) & 0x7fffffff) >>> 0;
      row.push(s % 3 !== 0);
    }
    cells.push(row);
  }
  return (
    <div className="data-matrix">
      {cells.map((row, r) => (
        <div key={r} className="data-matrix-row">
          {row.map((on, c) => (
            <span key={c} className={`matrix-cell ${on ? "on" : "off"}`} />
          ))}
        </div>
      ))}
    </div>
  );
}

// ─── Waveform ──────────────────────────────────────────────────────────────
// CSS-based oscilloscope wave visualization
export function Waveform({
  points = 40,
  height = 40,
  seed = 0,
}: {
  points?: number;
  height?: number;
  seed?: number;
}) {
  let s = seed || 7;
  const values: number[] = [];
  for (let i = 0; i < points; i++) {
    s = ((s * 1103515245 + 12345) & 0x7fffffff) >>> 0;
    values.push(0.2 + (s % 1000) / 1500);
  }
  return (
    <div className="waveform" style={{ height }}>
      {values.map((v, i) => (
        <div
          key={i}
          className="waveform-bar"
          style={{
            height: `${v * 100}%`,
            opacity: 0.4 + v * 0.6,
          }}
        />
      ))}
    </div>
  );
}

// ─── Equalizer ─────────────────────────────────────────────────────────────
// Vertical bar array like audio equalizers from the references
export function Equalizer({
  bars = 20,
  data,
  maxVal,
}: {
  bars?: number;
  data?: number[];
  maxVal?: number;
}) {
  let s = 13;
  const values =
    data ??
    Array.from({ length: bars }, () => {
      s = ((s * 1103515245 + 12345) & 0x7fffffff) >>> 0;
      return s % 100;
    });
  const max = maxVal ?? Math.max(...values, 1);
  return (
    <div className="equalizer">
      {values.map((v, i) => (
        <div
          key={i}
          className="eq-bar"
          style={{ height: `${(v / max) * 100}%` }}
        />
      ))}
    </div>
  );
}

// ─── Status Line ───────────────────────────────────────────────────────────
// ACTIVE: ENGRAM  |  03.x  |  SYNC: READY
export function StatusLine({ items }: { items: [string, string][] }) {
  return (
    <div className="status-line-row">
      {items.map(([k, v], i) => (
        <span key={i} className="status-item">
          <span className="status-key">{k}:</span> {v}
        </span>
      ))}
    </div>
  );
}

// ─── Metric Block ──────────────────────────────────────────────────────────
// Compact metric with label above
export function Metric({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="metric-block">
      <div className="metric-block-label">{label}</div>
      <div className="metric-block-value">{value}</div>
      {sub && <div className="metric-block-sub">{sub}</div>}
    </div>
  );
}
