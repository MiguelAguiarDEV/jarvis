import { mnemoFetch, type SearchResult } from "@/lib/mnemo";
import MemoryClient from "./memory-client";

export const dynamic = "force-dynamic";

export default async function MemoryPage() {
  let observations: SearchResult[] = [];
  const queries = [
    "architecture", "decision", "bug", "config",
    "discovery", "pattern", "fix", "setup",
    "preference", "learning", "deploy", "test",
  ];
  const seen = new Set<number>();

  for (const q of queries) {
    try {
      const res = await mnemoFetch<{ results: SearchResult[] }>(
        `/sync/search?q=${encodeURIComponent(q)}&limit=20`
      );
      for (const r of res.results ?? []) {
        if (!seen.has(r.id)) {
          seen.add(r.id);
          observations.push(r);
        }
      }
    } catch {}
  }

  observations.sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return <MemoryClient initialObservations={observations} />;
}
