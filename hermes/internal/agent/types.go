package agent

import "encoding/json"

type SessionResponse struct {
	ID string `json:"id"`
}

type SessionState struct {
	ID       string    `json:"id"`
	Messages []Message `json:"messages"`
}

// MessagePart represents a part in an OpenCode message.
// Parts can be text, tool invocations, step markers, reasoning, etc.
// We keep the raw JSON for tool-specific fields and only extract what we need.
type MessagePart struct {
	Type string `json:"type"`
	Text string `json:"text,omitempty"`

	// Tool-use fields (present when type == "tool-invocation" or "tool-result")
	Tool  json.RawMessage `json:"tool,omitempty"`
	State json.RawMessage `json:"state,omitempty"`
}

// ToolState extracts the status string from a part's "state" field if present.
// Returns "" if state is missing or unparseable.
func (p MessagePart) ToolStatus() string {
	if len(p.State) == 0 {
		return ""
	}
	var state struct {
		Status string `json:"status"`
	}
	if json.Unmarshal(p.State, &state) == nil {
		return state.Status
	}
	return ""
}

// ToolName extracts the tool name from a tool-invocation part.
// The "tool" field is typically {"name":"bash","input":{...}} or just a string.
func (p MessagePart) ToolName() string {
	if len(p.Tool) == 0 {
		return ""
	}
	// Try as object with "name" field.
	var obj struct {
		Name string `json:"name"`
	}
	if json.Unmarshal(p.Tool, &obj) == nil && obj.Name != "" {
		return obj.Name
	}
	// Try as plain string.
	var s string
	if json.Unmarshal(p.Tool, &s) == nil {
		return s
	}
	return ""
}

// ActiveToolName returns the name of the currently running tool in an
// in-progress assistant message, or "" if none is found.
func (m Message) ActiveToolName() string {
	if m.GetRole() != "assistant" {
		return ""
	}
	// Scan backwards — the last tool-invocation is the most recent.
	for i := len(m.Parts) - 1; i >= 0; i-- {
		p := m.Parts[i]
		if p.Type == "tool-invocation" || p.Type == "tool" {
			status := p.ToolStatus()
			if status == "" || status == "running" || status == "pending" {
				if name := p.ToolName(); name != "" {
					return name
				}
			}
		}
	}
	return ""
}

// MessageInfo holds the metadata envelope that OpenCode nests under "info".
type MessageInfo struct {
	ID        string      `json:"id"`
	SessionID string      `json:"sessionID"`
	Role      string      `json:"role"`
	Time      MessageTime `json:"time"`
}

// MessageTime matches OpenCode's time object: "created" and "completed".
type MessageTime struct {
	Created   int64 `json:"created"`
	Completed int64 `json:"completed"`
}

// Message is the wire format returned by GET /session/{id}/message.
// OpenCode nests role/time/id under "info"; parts are top-level.
type Message struct {
	Info  MessageInfo   `json:"info"`
	Parts []MessagePart `json:"parts"`
}

type PromptRequest struct {
	Parts   []MessagePart `json:"parts,omitempty"`
	Content []MessagePart `json:"content,omitempty"`
}

func (m Message) IsComplete() bool {
	return m.Info.Time.Completed > 0
}

func (m Message) GetRole() string {
	return m.Info.Role
}

func (m Message) GetText() string {
	var text string
	for _, p := range m.Parts {
		if p.Type == "text" {
			text += p.Text
		}
	}
	return text
}

// HasToolUse returns true if any part is a tool-related type.
func (m Message) HasToolUse() bool {
	for _, p := range m.Parts {
		switch p.Type {
		case "tool-invocation", "tool-result", "tool":
			return true
		}
	}
	return false
}

// HasRunningTool returns true if any tool part has state.status == "running"
// or if the message is an incomplete assistant message with tool parts.
func (m Message) HasRunningTool() bool {
	if m.GetRole() != "assistant" || m.IsComplete() {
		return false
	}
	for _, p := range m.Parts {
		switch p.Type {
		case "tool-invocation", "tool-result", "tool":
			status := p.ToolStatus()
			if status == "" || status == "running" || status == "pending" {
				return true
			}
		}
	}
	return false
}
