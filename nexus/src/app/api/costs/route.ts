import { NextRequest, NextResponse } from "next/server";
import { mnemoFetch } from "@/lib/mnemo";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const period = req.nextUrl.searchParams.get("period") || "month";
  try {
    const data = await mnemoFetch(`/api/costs?period=${period}`);
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({
      total_cost: 0,
      period,
      by_model: [],
      by_day: [],
      budget: null,
    });
  }
}
