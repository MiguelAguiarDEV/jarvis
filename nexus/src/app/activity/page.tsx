import { engramFetch, type ActivityEntry } from "@/lib/engram";
import ActivityClient from "./activity-client";

export const dynamic = "force-dynamic";

export default async function ActivityPage() {
  let entries: ActivityEntry[] = [];

  try {
    const data = await engramFetch<{ entries: ActivityEntry[] }>("/api/activity");
    entries = data.entries ?? [];
  } catch {
    // Client will handle empty state and allow refresh
  }

  // Sort by most recent first
  entries.sort(
    (a, b) => new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime(),
  );

  return <ActivityClient initialEntries={entries} />;
}
