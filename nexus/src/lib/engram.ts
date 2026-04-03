const API_URL = process.env.ENGRAM_API_URL!;
const API_KEY = process.env.ENGRAM_API_KEY!;

export async function engramFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
      ...init?.headers,
    },
    next: { revalidate: 30 },
  });
  if (!res.ok) throw new Error(`Engram API ${res.status}: ${await res.text()}`);
  return res.json();
}

// --- Types ---

export interface ToolCall {
  id: number;
  user_id: string;
  session_id: string;
  project?: string;
  agent: string;
  tool_name: string;
  input_json?: string;
  output_text?: string;
  duration_ms?: number;
  tokens_in?: number;
  tokens_out?: number;
  model?: string;
  cost_usd?: string;
  is_engram: boolean;
  occurred_at: string;
}

export interface TraceStats {
  total_calls: number;
  unique_tools: number;
  total_duration_ms: number;
  by_tool: { tool_name: string; count: number; avg_duration_ms: number }[];
  by_session: { session_id: string; project: string; count: number }[];
  by_day: { date: string; count: number }[];
}

export interface SessionToolCalls {
  session_id: string;
  tool_calls: ToolCall[];
  total: number;
}

export interface SearchResult {
  id: number;
  session_id: string;
  type: string;
  title: string;
  content: string;
  project?: string;
  topic_key?: string;
  created_at: string;
  updated_at: string;
}

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  data?: Record<string, string>;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// --- JARVIS MVP Types ---

export interface Task {
  id: number;
  user_id: string;
  parent_id?: number;
  title: string;
  description?: string;
  status: string;
  priority: string;
  assignee_type: string;
  assignee?: string;
  source: string;
  project?: string;
  tags?: string[];
  due_at?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  children?: Task[];
}

export interface Conversation {
  id: number;
  user_id: string;
  title?: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  role: string;
  content: string;
  model?: string;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
  created_at: string;
}

export interface ActivityEntry {
  type: string;
  id: number;
  project: string;
  summary: string;
  occurred_at: string;
  data?: any;
}

// --- SSE Client Helper ---

export function createEventSource(
  url: string,
  onEvent: (event: MessageEvent) => void,
  onError?: (event: Event) => void,
): EventSource {
  const es = new EventSource(url);
  es.onmessage = onEvent;
  es.onerror = onError ?? (() => {});
  return es;
}

// --- Chat Streaming Helper ---

export async function streamChat(
  conversationId: number,
  message: string,
  onToken: (token: string) => void,
  onDone: (msg: Message) => void,
  onError?: (err: Error) => void,
): Promise<void> {
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, message }),
    });

    if (!res.ok) {
      // The proxy now returns SSE even for errors, but in case it doesn't:
      const text = await res.text();
      const msg = text.includes("<!DOCTYPE") || text.includes("<html")
        ? `Connection timeout (${res.status}). Try again.`
        : `Chat API ${res.status}: ${text.slice(0, 200)}`;
      throw new Error(msg);
    }

    const reader = res.body?.getReader();
    if (!reader) throw new Error("No response body");

    const decoder = new TextDecoder();
    let buffer = "";
    let doneSignaled = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data === "[DONE]") continue;
          try {
            const parsed = JSON.parse(data);
            if (parsed.status) {
              // Real status event from the orchestrator
              onToken("__STATUS__" + JSON.stringify(parsed));
            } else if (parsed.token) {
              onToken(parsed.token);
            } else if (parsed.done) {
              doneSignaled = true;
              onDone({
                id: Date.now(),
                conversation_id: conversationId,
                role: "assistant",
                content: "",
                created_at: new Date().toISOString(),
              });
            } else if (parsed.message) {
              doneSignaled = true;
              onDone(parsed.message);
            } else if (parsed.error) {
              onError?.(new Error(parsed.error));
              return;
            }
          } catch {
            // partial JSON, skip
          }
        }
      }
    }
    // Safety: if stream ended without a done event, signal completion
    if (!doneSignaled) {
      onDone({
        id: Date.now(),
        conversation_id: conversationId,
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
      });
    }
  } catch (err) {
    try {
      onError?.(err instanceof Error ? err : new Error(String(err)));
    } catch {
      // Prevent onError callback from throwing unhandled
    }
  }
}
