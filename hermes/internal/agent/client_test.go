package agent

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestCreateSessionSendsEmptyJSONObject(t *testing.T) {
	t.Helper()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Fatalf("expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/session" {
			t.Fatalf("expected /session, got %s", r.URL.Path)
		}
		body, err := io.ReadAll(r.Body)
		if err != nil {
			t.Fatalf("read body: %v", err)
		}
		defer r.Body.Close()
		if string(body) != "{}" {
			t.Fatalf("expected body {}, got %q", string(body))
		}
		var payload map[string]any
		if err := json.Unmarshal(body, &payload); err != nil {
			t.Fatalf("body is not valid JSON: %v", err)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"id":"sess-123"}`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "secret")
	session, err := client.CreateSession(context.Background())
	if err != nil {
		t.Fatalf("CreateSession returned error: %v", err)
	}
	if session.ID != "sess-123" {
		t.Fatalf("expected session ID sess-123, got %s", session.ID)
	}
}

func TestSendMessageAccepts204NoContent(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Fatalf("expected POST, got %s", r.Method)
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	client := NewClient(server.URL, "secret")
	err := client.SendMessage(context.Background(), "sess-123", "hello")
	if err != nil {
		t.Fatalf("SendMessage should accept 204, got error: %v", err)
	}
}

func TestSendMessageStillAccepts200And202(t *testing.T) {
	for _, code := range []int{http.StatusOK, http.StatusAccepted} {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(code)
		}))

		client := NewClient(server.URL, "secret")
		err := client.SendMessage(context.Background(), "sess-123", "hello")
		server.Close()
		if err != nil {
			t.Fatalf("SendMessage should accept %d, got error: %v", code, err)
		}
	}
}

func TestMessageDeserializationMatchesOpenCodeWireFormat(t *testing.T) {
	raw := `[
		{
			"info": {"role": "user", "time": {"created": 1774807656522}, "id": "msg_user1", "sessionID": "ses_123"},
			"parts": [{"type": "text", "text": "hola"}]
		},
		{
			"info": {"role": "assistant", "time": {"created": 1774807656530, "completed": 1774807663273}, "id": "msg_asst1", "sessionID": "ses_123"},
			"parts": [
				{"type": "step-start"},
				{"type": "text", "text": "¡Hola! 👋"},
				{"type": "step-finish"}
			]
		}
	]`
	var messages []Message
	if err := json.Unmarshal([]byte(raw), &messages); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if len(messages) != 2 {
		t.Fatalf("expected 2 messages, got %d", len(messages))
	}

	user := messages[0]
	if user.GetRole() != "user" {
		t.Fatalf("user role: expected 'user', got %q", user.GetRole())
	}
	if user.GetText() != "hola" {
		t.Fatalf("user text: expected 'hola', got %q", user.GetText())
	}

	asst := messages[1]
	if asst.GetRole() != "assistant" {
		t.Fatalf("assistant role: expected 'assistant', got %q", asst.GetRole())
	}
	if !asst.IsComplete() {
		t.Fatalf("assistant should be complete")
	}
	if asst.GetText() != "¡Hola! 👋" {
		t.Fatalf("assistant text: expected '¡Hola! 👋', got %q", asst.GetText())
	}

	text, inProgress := extractAssistantReply(messages, 0)
	if text != "¡Hola! 👋" || inProgress {
		t.Fatalf("extractAssistantReply(0): expected ('¡Hola! 👋', false), got (%q, %v)", text, inProgress)
	}

	text, inProgress = extractAssistantReply(messages, 2)
	if text != "" || inProgress {
		t.Fatalf("extractAssistantReply(2): expected ('', false), got (%q, %v)", text, inProgress)
	}
}

func TestExtractAssistantReplyInProgressToolUse(t *testing.T) {
	// Simulate an in-progress assistant message during tool execution:
	// completed == 0, has a tool-invocation part with running state.
	raw := `[
		{
			"info": {"role": "user", "time": {"created": 100}, "id": "msg_u1", "sessionID": "ses_1"},
			"parts": [{"type": "text", "text": "list files"}]
		},
		{
			"info": {"role": "assistant", "time": {"created": 200, "completed": 0}, "id": "msg_a1", "sessionID": "ses_1"},
			"parts": [
				{"type": "step-start"},
				{"type": "tool-invocation", "tool": {"name": "bash"}, "state": {"status": "running"}}
			]
		}
	]`
	var messages []Message
	if err := json.Unmarshal([]byte(raw), &messages); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	asst := messages[1]
	if asst.IsComplete() {
		t.Fatal("in-progress assistant should not be complete")
	}
	if !asst.HasToolUse() {
		t.Fatal("should detect tool-use")
	}
	if !asst.HasRunningTool() {
		t.Fatal("should detect running tool")
	}

	// extractAssistantReply should return ("", true) — in-progress
	text, inProgress := extractAssistantReply(messages, 0)
	if text != "" {
		t.Fatalf("expected empty text during tool-use, got %q", text)
	}
	if !inProgress {
		t.Fatal("expected inProgress=true for in-progress assistant message")
	}
}

func TestExtractAssistantReplyToolUseCompleted(t *testing.T) {
	// Tool execution finished, message now has completed time and text.
	raw := `[
		{
			"info": {"role": "user", "time": {"created": 100}, "id": "msg_u1", "sessionID": "ses_1"},
			"parts": [{"type": "text", "text": "list files"}]
		},
		{
			"info": {"role": "assistant", "time": {"created": 200, "completed": 500}, "id": "msg_a1", "sessionID": "ses_1"},
			"parts": [
				{"type": "step-start"},
				{"type": "tool-invocation", "tool": {"name": "bash"}, "state": {"status": "completed"}},
				{"type": "tool-result"},
				{"type": "text", "text": "Here are the files:\n- main.go\n- go.mod"},
				{"type": "step-finish"}
			]
		}
	]`
	var messages []Message
	if err := json.Unmarshal([]byte(raw), &messages); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	asst := messages[1]
	if !asst.IsComplete() {
		t.Fatal("completed assistant should be complete")
	}
	if !asst.HasToolUse() {
		t.Fatal("should detect tool-use")
	}
	if asst.HasRunningTool() {
		t.Fatal("completed assistant should not have running tool")
	}

	text, inProgress := extractAssistantReply(messages, 0)
	if text != "Here are the files:\n- main.go\n- go.mod" {
		t.Fatalf("expected file listing text, got %q", text)
	}
	if inProgress {
		t.Fatal("completed message should not be in-progress")
	}
}

func TestExtractAssistantReplyNoAssistantMessage(t *testing.T) {
	// Only user messages — no assistant response yet.
	raw := `[
		{
			"info": {"role": "user", "time": {"created": 100}, "id": "msg_u1", "sessionID": "ses_1"},
			"parts": [{"type": "text", "text": "hello"}]
		}
	]`
	var messages []Message
	if err := json.Unmarshal([]byte(raw), &messages); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	text, inProgress := extractAssistantReply(messages, 0)
	if text != "" || inProgress {
		t.Fatalf("expected ('', false) when no assistant message, got (%q, %v)", text, inProgress)
	}
}
