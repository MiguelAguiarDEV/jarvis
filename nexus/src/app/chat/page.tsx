"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import { HudPanel, HexStream, Metric, StatusLine } from "@/components/hud";
import type { Conversation, Message } from "@/lib/engram";
import { streamChat } from "@/lib/engram";

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatCost(usd?: number): string {
  if (!usd && usd !== 0) return "--";
  return `$${Number(usd).toFixed(4)}`;
}

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConv, setActiveConv] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamBuffer, setStreamBuffer] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [thinkingStart, setThinkingStart] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [thinkingStatus, setThinkingStatus] = useState("Connecting to model");
  const [thinkingDetail, setThinkingDetail] = useState("");
  const [responseInfo, setResponseInfo] = useState<{ model?: string; tokens_in?: number; tokens_out?: number } | null>(null);
  const [editingConvId, setEditingConvId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Elapsed time counter while streaming
  useEffect(() => {
    if (!thinkingStart) {
      setElapsed(0);
      return;
    }
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - thinkingStart) / 1000));
    }, 100);
    return () => clearInterval(interval);
  }, [thinkingStart]);

  // Fetch conversations
  useEffect(() => {
    fetch("/api/conversations")
      .then((r) => r.json())
      .then((data) => {
        const convs = data.conversations ?? data ?? [];
        setConversations(Array.isArray(convs) ? convs : []);
      })
      .catch(() => setConversations([]));
  }, []);

  // Fetch messages when conversation changes
  useEffect(() => {
    if (activeConv === null) {
      setMessages([]);
      return;
    }
    fetch(`/api/conversations/${activeConv}/messages`)
      .then((r) => r.json())
      .then((data) => {
        const msgs = data.messages ?? data ?? [];
        setMessages(Array.isArray(msgs) ? msgs : []);
      })
      .catch(() => setMessages([]));
  }, [activeConv]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamBuffer]);

  const createConversation = useCallback(async () => {
    try {
      const res = await fetch("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: `Session ${new Date().toISOString().slice(0, 16)}` }),
      });
      const conv = await res.json();
      setConversations((prev) => [conv, ...prev]);
      setActiveConv(conv.id);
      setMessages([]);
    } catch {
      setError("Failed to create conversation");
    }
  }, []);

  const renameConversation = useCallback(async (id: number, title: string) => {
    try {
      await fetch(`/api/conversations/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title } : c))
      );
    } catch {
      setError("Failed to rename conversation");
    } finally {
      setEditingConvId(null);
    }
  }, []);

  const deleteConversation = useCallback(async (id: number) => {
    if (!confirm("Delete this session and all its messages?")) return;
    try {
      await fetch(`/api/conversations/${id}`, { method: "DELETE" });
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConv === id) {
        setActiveConv(null);
        setMessages([]);
      }
    } catch {
      setError("Failed to delete conversation");
    }
  }, [activeConv]);

  const sendMessage = useCallback(async () => {
    if (!input.trim() || streaming) return;
    if (activeConv === null) {
      setError("Select or create a conversation first");
      return;
    }

    const userMsg: Message = {
      id: Date.now(),
      conversation_id: activeConv,
      role: "user",
      content: input.trim(),
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);
    setStreamBuffer("");
    setError(null);
    setThinkingStart(Date.now());
    setThinkingStatus("Connecting to model");
    setThinkingDetail("");
    setResponseInfo(null);

    let accumulated = "";

    try {
      await streamChat(
        activeConv,
        userMsg.content,
        (token) => {
          if (token.startsWith("__STATUS__")) {
            try {
              const s = JSON.parse(token.slice(10));
              if (s.status === "reasoning") {
                setThinkingStatus("Reasoning");
                setThinkingDetail(s.detail || "");
              } else if (s.status === "complete") {
                setResponseInfo({ model: s.model, tokens_in: s.tokens_in, tokens_out: s.tokens_out });
              }
            } catch { /* skip */ }
            return;
          }
          accumulated += token;
          setStreamBuffer(accumulated);
        },
        () => {
          // done — add the assistant message from accumulated tokens
          if (accumulated) {
            setMessages((prev) => [
              ...prev,
              {
                id: Date.now(),
                conversation_id: activeConv,
                role: "assistant",
                content: accumulated,
                created_at: new Date().toISOString(),
              },
            ]);
          }
          setStreamBuffer("");
          setStreaming(false);
          setThinkingStart(null);
        },
        (err) => {
          setError(err.message);
          setStreamBuffer("");
          setStreaming(false);
          setThinkingStart(null);
        },
      );
    } catch {
      if (accumulated) {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            conversation_id: activeConv,
            role: "assistant",
            content: accumulated,
            created_at: new Date().toISOString(),
          },
        ]);
      }
    } finally {
      setStreamBuffer("");
      setStreaming(false);
      setThinkingStart(null);
    }
  }, [input, streaming, activeConv]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const totalTokensIn = messages.reduce((s, m) => s + (m.tokens_in ?? 0), 0);
  const totalTokensOut = messages.reduce((s, m) => s + (m.tokens_out ?? 0), 0);
  const totalCost = messages.reduce((s, m) => s + (Number(m.cost_usd) || 0), 0);

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-kicker">COMMS // CONVERSATIONAL INTERFACE</div>
          <h2 className="page-title">Chat</h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          {streaming && <span className="live-dot" />}
          <span className="badge badge-amber">
            {messages.filter((m) => m.role === "user").length} MESSAGES
          </span>
        </div>
      </div>

      {/* Mobile session selector — visible only on small screens */}
      <div className="mobile-only" style={{ display: "none" }}>
        <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
          <select
            value={activeConv ?? ""}
            onChange={(e) => setActiveConv(e.target.value ? Number(e.target.value) : null)}
            className="filter-select"
            style={{ flex: 1 }}
          >
            <option value="">Select session...</option>
            {conversations.map((c) => (
              <option key={c.id} value={c.id}>{c.title || `Conv #${c.id}`}</option>
            ))}
          </select>
          {activeConv !== null && (
            <button
              onClick={() => deleteConversation(activeConv)}
              title="Delete session"
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
                color: "var(--accent-red, #f87171)",
                fontFamily: "var(--font-mono)",
                fontSize: "var(--font-size-xs)",
                padding: "var(--space-2) var(--space-3)",
                cursor: "pointer",
              }}
            >
              DEL
            </button>
          )}
          <button
            onClick={createConversation}
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              color: "var(--accent-amber)",
              fontFamily: "var(--font-mono)",
              fontSize: "var(--font-size-xs)",
              padding: "var(--space-2) var(--space-3)",
              cursor: "pointer",
            }}
          >
            + NEW
          </button>
        </div>
      </div>

      <div style={{ display: "flex", gap: "1px", flex: 1, minHeight: 0, background: "var(--border-subtle)" }}>
        {/* Conversation sidebar — desktop only */}
        <HudPanel label="CONVERSATIONS" className="chat-sidebar">
          <button
            onClick={createConversation}
            style={{
              width: "100%",
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              color: "var(--accent-amber)",
              fontFamily: "var(--font-mono)",
              fontSize: "var(--font-size-xs)",
              padding: "var(--space-2) var(--space-3)",
              cursor: "pointer",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              marginBottom: "var(--space-2)",
            }}
          >
            + NEW SESSION
          </button>

          <div style={{ display: "flex", flexDirection: "column", gap: "1px" }}>
            {conversations.map((conv) => (
              <div
                key={conv.id}
                style={{
                  background: activeConv === conv.id ? "var(--bg-active)" : "var(--bg-panel)",
                  border: `1px solid ${activeConv === conv.id ? "var(--accent-amber)" : "transparent"}`,
                  display: "flex",
                  alignItems: "center",
                  gap: "2px",
                }}
              >
                {editingConvId === conv.id ? (
                  <div style={{ flex: 1, display: "flex", alignItems: "center", padding: "var(--space-2) var(--space-3)", gap: "4px" }}>
                    <input
                      autoFocus
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") renameConversation(conv.id, editTitle);
                        if (e.key === "Escape") setEditingConvId(null);
                      }}
                      onBlur={() => renameConversation(conv.id, editTitle)}
                      style={{
                        flex: 1,
                        background: "var(--bg-surface)",
                        border: "1px solid var(--accent-amber)",
                        color: "var(--text-primary)",
                        fontFamily: "var(--font-mono)",
                        fontSize: "var(--font-size-xs)",
                        padding: "2px 4px",
                        outline: "none",
                        minWidth: 0,
                      }}
                    />
                  </div>
                ) : (
                  <button
                    onClick={() => setActiveConv(conv.id)}
                    style={{
                      flex: 1,
                      background: "transparent",
                      border: "none",
                      color: activeConv === conv.id ? "var(--accent-amber)" : "var(--text-secondary)",
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--font-size-xs)",
                      padding: "var(--space-2) var(--space-3)",
                      cursor: "pointer",
                      textAlign: "left",
                      minWidth: 0,
                    }}
                  >
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {conv.title || `Conv #${conv.id}`}
                    </div>
                    <div style={{ color: "var(--text-dim)", fontSize: "var(--font-size-xs)" }}>
                      {formatTime(conv.created_at)}
                    </div>
                  </button>
                )}
                {editingConvId !== conv.id && (
                  <div style={{ display: "flex", flexShrink: 0, gap: "1px", paddingRight: "var(--space-2)" }}>
                    <button
                      title="Rename session"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingConvId(conv.id);
                        setEditTitle(conv.title || `Conv #${conv.id}`);
                      }}
                      style={{
                        background: "transparent",
                        border: "none",
                        color: "var(--text-dim)",
                        fontFamily: "var(--font-mono)",
                        fontSize: "var(--font-size-xs)",
                        cursor: "pointer",
                        padding: "2px 4px",
                        lineHeight: 1,
                      }}
                    >
                      &#x270E;
                    </button>
                    <button
                      title="Delete session"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteConversation(conv.id);
                      }}
                      style={{
                        background: "transparent",
                        border: "none",
                        color: "var(--text-dim)",
                        fontFamily: "var(--font-mono)",
                        fontSize: "var(--font-size-xs)",
                        cursor: "pointer",
                        padding: "2px 4px",
                        lineHeight: 1,
                      }}
                    >
                      &#xD7;
                    </button>
                  </div>
                )}
              </div>
            ))}
            {conversations.length === 0 && (
              <div className="empty-state">
                <div className="empty-label">NO SESSIONS</div>
              </div>
            )}
          </div>
        </HudPanel>

        {/* Chat area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          {/* Stats bar */}
          <div style={{ background: "var(--bg-panel)", borderBottom: "1px solid var(--border-subtle)", padding: "var(--space-2) var(--space-3)" }}>
            <StatusLine
              items={[
                ["TOKENS IN", String(totalTokensIn)],
                ["TOKENS OUT", String(totalTokensOut)],
                ["COST", formatCost(totalCost)],
                ["CONV", activeConv ? `#${activeConv}` : "--"],
              ]}
            />
          </div>

          {/* Messages */}
          <div
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "var(--space-4)",
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-3)",
            }}
          >
            {activeConv === null ? (
              <div className="empty-state" style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
                <HexStream seed={42} />
                <div className="empty-label" style={{ marginTop: "var(--space-4)" }}>SELECT OR CREATE A SESSION</div>
              </div>
            ) : messages.length === 0 && !streaming ? (
              <div className="empty-state" style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
                <div className="empty-label">AWAITING INPUT</div>
              </div>
            ) : (
              <>
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    style={{
                      background: msg.role === "user" ? "var(--bg-surface)" : "var(--bg-panel)",
                      border: `1px solid ${msg.role === "user" ? "var(--border)" : "var(--border-subtle)"}`,
                      padding: "var(--space-3)",
                    }}
                  >
                    <div style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "var(--space-2)",
                    }}>
                      <span
                        className={`badge ${msg.role === "user" ? "badge-blue" : "badge-amber"}`}
                      >
                        {msg.role === "user" ? "USER" : "JARVIS"}
                      </span>
                      <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center" }}>
                        {msg.model && (
                          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-dim)" }}>
                            {msg.model}
                          </span>
                        )}
                        {msg.tokens_in != null && (
                          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-dim)" }}>
                            {msg.tokens_in}/{msg.tokens_out}t
                          </span>
                        )}
                        {msg.cost_usd != null && (
                          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-dim)" }}>
                            {formatCost(msg.cost_usd)}
                          </span>
                        )}
                        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-dim)" }}>
                          {formatTime(msg.created_at)}
                        </span>
                      </div>
                    </div>
                    <div style={{
                      fontSize: "var(--font-size-sm)",
                      color: "var(--text-primary)",
                      whiteSpace: msg.role === "user" ? "pre-wrap" : undefined,
                      wordBreak: "break-word",
                    }}>
                      {msg.role === "assistant" ? (
                        <div className="chat-markdown" suppressHydrationWarning>
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                      ) : (
                        msg.content
                      )}
                    </div>
                  </div>
                ))}

                {/* Thinking indicator — shown while waiting for response */}
                {streaming && !streamBuffer && (
                  <div
                    style={{
                      background: "var(--bg-panel)",
                      border: "1px solid var(--border)",
                      padding: "var(--space-3)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                      <span className="live-dot" />
                      <span className="badge badge-amber">JARVIS</span>
                    </div>
                    <div style={{
                      fontSize: "var(--font-size-sm)",
                      color: "var(--text-dim)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "var(--space-1)",
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                        <span style={{ color: "var(--text-muted)", letterSpacing: "0.1em", fontSize: "var(--font-size-xs)", textTransform: "uppercase" }}>
                          {thinkingStatus}
                        </span>
                        <span style={{ color: "var(--accent-amber)", animation: "blink 1s infinite" }}>...</span>
                      </div>
                      {thinkingDetail && (
                        <div style={{ fontSize: "var(--font-size-xs)", color: "var(--text-dim)", fontStyle: "italic", marginTop: "var(--space-1)" }}>
                          {thinkingDetail.length > 100 ? thinkingDetail.slice(0, 100) + "..." : thinkingDetail}
                        </div>
                      )}
                      <div style={{ display: "flex", gap: "var(--space-4)", fontSize: "var(--font-size-xs)", color: "var(--text-dim)", marginTop: "var(--space-1)" }}>
                        <span style={{ fontVariantNumeric: "tabular-nums" }}>{elapsed}s elapsed</span>
                        <span>via OpenCode serve</span>
                        {responseInfo?.model && <span>model: {responseInfo.model}</span>}
                      </div>
                    </div>
                  </div>
                )}

                {/* Streaming buffer — shown while tokens arrive */}
                {streaming && streamBuffer && (
                  <div
                    style={{
                      background: "var(--bg-panel)",
                      border: "1px solid var(--accent-amber)",
                      padding: "var(--space-3)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                      <span className="live-dot" />
                      <span className="badge badge-amber">JARVIS</span>
                      <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-dim)", fontVariantNumeric: "tabular-nums" }}>
                        {elapsed}s
                      </span>
                    </div>
                    <div style={{
                      fontSize: "var(--font-size-sm)",
                      color: "var(--text-primary)",
                      wordBreak: "break-word",
                    }}>
                      <div className="chat-markdown" suppressHydrationWarning>
                        <ReactMarkdown>{streamBuffer}</ReactMarkdown>
                      </div>
                      <span style={{ color: "var(--accent-amber)", animation: "blink 1s infinite" }}>_</span>
                    </div>
                  </div>
                )}
              </>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Error */}
          {error && (
            <div style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--accent-red)",
              padding: "var(--space-2) var(--space-3)",
              fontSize: "var(--font-size-xs)",
              color: "var(--accent-red)",
            }}>
              ERROR: {error}
            </div>
          )}

          {/* Input area */}
          <div style={{
            background: "var(--bg-panel)",
            borderTop: "1px solid var(--border)",
            padding: "var(--space-3)",
            display: "flex",
            gap: "var(--space-2)",
          }}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={activeConv ? "Enter message... (Enter to send, Shift+Enter for newline)" : "Select a session first"}
              disabled={activeConv === null || streaming}
              rows={2}
              style={{
                flex: 1,
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
                color: "var(--text-primary)",
                fontFamily: "var(--font-mono)",
                fontSize: "var(--font-size-sm)",
                padding: "var(--space-2) var(--space-3)",
                resize: "none",
                outline: "none",
              }}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || streaming || activeConv === null}
              style={{
                background: streaming ? "var(--bg-surface)" : "var(--accent-amber)",
                border: "1px solid var(--accent-amber)",
                color: streaming ? "var(--text-dim)" : "var(--bg-root)",
                fontFamily: "var(--font-mono)",
                fontSize: "var(--font-size-xs)",
                padding: "var(--space-2) var(--space-4)",
                cursor: streaming ? "not-allowed" : "pointer",
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                fontWeight: 600,
                alignSelf: "stretch",
              }}
            >
              {streaming ? "..." : "SEND"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
