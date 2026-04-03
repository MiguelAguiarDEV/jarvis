"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div style={{ padding: "var(--space-6)" }}>
      <div style={{
        border: "1px solid var(--accent-red)",
        background: "var(--bg-panel)",
        padding: "var(--space-4)",
      }}>
        <div style={{
          fontSize: "var(--font-size-xs)",
          color: "var(--accent-red)",
          letterSpacing: "0.15em",
          textTransform: "uppercase",
          marginBottom: "var(--space-2)",
        }}>
          SYSTEM ERROR
        </div>
        <div style={{
          fontSize: "var(--font-size-sm)",
          color: "var(--text-secondary)",
          marginBottom: "var(--space-3)",
          fontFamily: "var(--font-mono)",
        }}>
          {error.message}
        </div>
        <button
          onClick={reset}
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--accent-red)",
            color: "var(--accent-red)",
            fontFamily: "var(--font-mono)",
            fontSize: "var(--font-size-xs)",
            padding: "var(--space-2) var(--space-3)",
            cursor: "pointer",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
          }}
        >
          RETRY
        </button>
      </div>
    </div>
  );
}
