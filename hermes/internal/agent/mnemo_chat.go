package agent

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"jarvis-discord-bot/internal/observability"
)

// MnemoChatClient talks to the mnemo-cloud /api/chat SSE endpoint
// and /api/conversations REST endpoints.
type MnemoChatClient struct {
	BaseURL    string
	APIKey     string
	HTTPClient *http.Client
}

// NewMnemoChatClient creates a client for the mnemo chat API.
func NewMnemoChatClient(baseURL, apiKey string) *MnemoChatClient {
	return &MnemoChatClient{
		BaseURL:    strings.TrimRight(baseURL, "/"),
		APIKey:     apiKey,
		HTTPClient: &http.Client{Timeout: 120 * time.Second},
	}
}

// CreateConversation creates a new conversation and returns its ID.
func (c *MnemoChatClient) CreateConversation(ctx context.Context, title string) (int64, error) {
	ctx = observability.WithFields(ctx, observability.Fields{
		"component": "mnemo_chat", "operation": "create_conversation",
	})
	started := time.Now()
	var opErr error
	defer func() {
		observability.ObserveOperation(ctx, "mnemo_create_conversation", started,
			map[string]string{"component": "mnemo_chat"}, opErr)
	}()

	body, _ := json.Marshal(map[string]string{"title": title})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+"/api/conversations", bytes.NewReader(body))
	if err != nil {
		opErr = fmt.Errorf("create request: %w", err)
		return 0, opErr
	}
	req.Header.Set("Authorization", "Bearer "+c.APIKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		opErr = fmt.Errorf("mnemo conversation create: %w", err)
		return 0, opErr
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated && resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		opErr = fmt.Errorf("mnemo conversation create: status %d: %s", resp.StatusCode, string(respBody))
		return 0, opErr
	}

	var result struct {
		ID int64 `json:"id"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		opErr = fmt.Errorf("decode conversation response: %w", err)
		return 0, opErr
	}
	observability.Info(ctx, "mnemo_conversation_created", observability.Fields{"conversation_id": result.ID})
	return result.ID, nil
}

// ChatSSE sends a message to the mnemo chat SSE endpoint and collects
// the full streamed response. It calls onToken for each token received.
// Returns the complete assembled response.
func (c *MnemoChatClient) ChatSSE(ctx context.Context, conversationID int64, message string, onToken func(string)) (string, error) {
	ctx = observability.WithFields(ctx, observability.Fields{
		"component":       "mnemo_chat",
		"operation":       "chat_sse",
		"conversation_id": conversationID,
	})
	ctx = observability.WithFields(ctx, observability.MessageSummary(message))
	started := time.Now()
	var opErr error
	defer func() {
		observability.ObserveOperation(ctx, "mnemo_chat_sse", started,
			map[string]string{"component": "mnemo_chat"}, opErr)
	}()

	body, _ := json.Marshal(map[string]any{
		"conversation_id": conversationID,
		"message":         message,
	})

	// Use a longer timeout client for SSE streaming.
	sseClient := &http.Client{Timeout: 5 * time.Minute}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+"/api/chat", bytes.NewReader(body))
	if err != nil {
		opErr = fmt.Errorf("create request: %w", err)
		return "", opErr
	}
	req.Header.Set("Authorization", "Bearer "+c.APIKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "text/event-stream")

	observability.Info(ctx, "mnemo_chat_request_start", nil)
	resp, err := sseClient.Do(req)
	if err != nil {
		opErr = fmt.Errorf("mnemo chat: %w", err)
		return "", opErr
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		opErr = fmt.Errorf("mnemo chat: status %d: %s", resp.StatusCode, string(respBody))
		return "", opErr
	}

	// Parse SSE stream.
	var sb strings.Builder
	scanner := bufio.NewScanner(resp.Body)
	for scanner.Scan() {
		line := scanner.Text()
		if !strings.HasPrefix(line, "data: ") {
			continue
		}
		data := line[6:] // strip "data: " prefix

		var event map[string]any
		if err := json.Unmarshal([]byte(data), &event); err != nil {
			continue
		}

		// Check for error event.
		if errMsg, ok := event["error"].(string); ok {
			opErr = fmt.Errorf("mnemo chat error: %s", errMsg)
			return sb.String(), opErr
		}

		// Check for done event.
		if done, ok := event["done"].(bool); ok && done {
			break
		}

		// Token event.
		if token, ok := event["token"].(string); ok {
			sb.WriteString(token)
			if onToken != nil {
				onToken(token)
			}
		}
	}

	if err := scanner.Err(); err != nil {
		opErr = fmt.Errorf("sse read error: %w", err)
		return sb.String(), opErr
	}

	result := sb.String()
	observability.Info(ctx, "mnemo_chat_completed", observability.Fields{
		"response_length": len(result),
		"elapsed_ms":      time.Since(started).Milliseconds(),
	})
	return result, nil
}
