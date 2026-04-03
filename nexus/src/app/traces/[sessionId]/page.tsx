import { engramFetch, type SessionToolCalls } from "@/lib/engram";

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

export default async function SessionTracePage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  let data: SessionToolCalls | null = null;

  try {
    data = await engramFetch<SessionToolCalls>(
      `/traces/session/${encodeURIComponent(sessionId)}?limit=500`
    );
  } catch {
    // API unavailable
  }

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-kicker">TRACE // SESSION DETAIL</div>
          <h2 className="page-title">
            {sessionId.slice(0, 20)}
            {sessionId.length > 20 ? "..." : ""}
          </h2>
        </div>
        <span className="badge badge-amber">{data?.total ?? 0} CALLS</span>
      </div>

      <div style={{ fontSize: "var(--font-size-xs)", color: "var(--text-dim)" }}>
        <a href="/traces" style={{ color: "var(--text-muted)" }}>
          ALL TRACES
        </a>{" "}
        / {sessionId.slice(0, 16)}
      </div>

      {data?.tool_calls && data.tool_calls.length > 0 ? (
        <div className="hud-frame" data-label="CHRONOLOGICAL">
          <div className="hud-frame-body" style={{ padding: 0 }}>
            {data.tool_calls.map((tc) => (
              <details key={tc.id} className="trace-detail">
                <summary>
                  <span
                    style={{
                      color: "var(--text-dim)",
                      fontSize: "var(--font-size-xs)",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {formatTime(tc.occurred_at)}
                  </span>
                  <strong style={{ color: "var(--text-primary)" }}>
                    {tc.tool_name}
                  </strong>
                  {tc.duration_ms != null && (
                    <span className="badge badge-muted">{tc.duration_ms}ms</span>
                  )}
                  {tc.is_engram && (
                    <span className="badge badge-green">ENGRAM</span>
                  )}
                </summary>
                <div className="trace-body">
                  {tc.input_json && tc.input_json !== "null" && (
                    <>
                      <div className="section-label">INPUT</div>
                      <pre>{tc.input_json}</pre>
                    </>
                  )}
                  {tc.output_text && (
                    <>
                      <div className="section-label">OUTPUT</div>
                      <pre>
                        {tc.output_text.length > 2000
                          ? tc.output_text.slice(0, 2000) + "\n[truncated]"
                          : tc.output_text}
                      </pre>
                    </>
                  )}
                </div>
              </details>
            ))}
          </div>
        </div>
      ) : (
        <div className="empty-state">
          <div className="empty-label">NO TRACES</div>
          <p>No tool calls found for this session.</p>
        </div>
      )}
    </>
  );
}
