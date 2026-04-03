import { mnemoFetch, type TraceStats, type ToolCall } from "@/lib/mnemo";
import TracesClient from "./traces-client";

export const dynamic = "force-dynamic";

export default async function TracesPage() {
  let stats: TraceStats | null = null;
  const allCalls: ToolCall[] = [];

  try {
    stats = await mnemoFetch<TraceStats>("/traces/stats");
  } catch {}

  if (stats?.by_session) {
    for (const s of stats.by_session.slice(0, 10)) {
      try {
        const res = await mnemoFetch<{ tool_calls: ToolCall[] }>(
          `/traces/session/${encodeURIComponent(s.session_id)}?limit=100`,
        );
        if (res.tool_calls) allCalls.push(...res.tool_calls);
      } catch {}
    }
  }

  allCalls.sort(
    (a, b) =>
      new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime(),
  );

  return <TracesClient stats={stats} initialCalls={allCalls} />;
}
