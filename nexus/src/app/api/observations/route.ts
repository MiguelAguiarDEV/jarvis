import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.ENGRAM_API_URL!;
const API_KEY = process.env.ENGRAM_API_KEY!;

/**
 * GET /api/observations?q=<search>&type=<filter>&project=<filter>&limit=<n>
 *
 * Proxies to the engram cloud search endpoint.
 * When no query is provided, runs a broad search to list all observations.
 */
export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const q = sp.get("q") || "";
  const type = sp.get("type") || "";
  const project = sp.get("project") || "";
  const limit = sp.get("limit") || "100";

  // The engram search API requires a non-empty query.
  // When the user hasn't typed a search query, we run multiple broad queries
  // to collect all observations, mirroring what the original server page did.
  if (!q) {
    const queries = [
      "architecture", "decision", "bug", "config",
      "discovery", "pattern", "fix", "setup",
      "preference", "learning", "deploy", "test",
    ];
    const seen = new Set<number>();
    const all: any[] = [];

    for (const query of queries) {
      try {
        const params = new URLSearchParams({ q: query, limit });
        if (type) params.set("type", type);
        if (project) params.set("project", project);

        const res = await fetch(`${API_URL}/sync/search?${params.toString()}`, {
          headers: {
            Authorization: `Bearer ${API_KEY}`,
            "Content-Type": "application/json",
          },
          next: { revalidate: 0 },
        });
        if (!res.ok) continue;
        const data = await res.json();
        for (const r of data.results ?? []) {
          if (!seen.has(r.id)) {
            seen.add(r.id);
            all.push(r);
          }
        }
      } catch {
        // skip failed queries
      }
    }

    return NextResponse.json({ results: all });
  }

  // Direct search with user query
  const params = new URLSearchParams({ q, limit });
  if (type) params.set("type", type);
  if (project) params.set("project", project);

  try {
    const res = await fetch(`${API_URL}/sync/search?${params.toString()}`, {
      headers: {
        Authorization: `Bearer ${API_KEY}`,
        "Content-Type": "application/json",
      },
      next: { revalidate: 0 },
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: `Upstream ${res.status}` },
        { status: res.status },
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { error: "Failed to fetch observations" },
      { status: 502 },
    );
  }
}
