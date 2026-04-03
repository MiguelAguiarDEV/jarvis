import { NextRequest, NextResponse } from "next/server";
import { mnemoFetch } from "@/lib/mnemo";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const claudeBudget =
    req.nextUrl.searchParams.get("claude_budget") || "200";
  const openAIBudget =
    req.nextUrl.searchParams.get("openai_budget") || "200";
  try {
    const data = await mnemoFetch(
      `/api/costs/budget?claude_budget=${claudeBudget}&openai_budget=${openAIBudget}`,
    );
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({
      monthly_budget_usd: 0,
      spent_this_month: 0,
      remaining: 0,
      percent_used: 0,
      projected_monthly: 0,
    });
  }
}
