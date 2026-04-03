package agent

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"jarvis-discord-bot/internal/observability"
)

var (
	ErrPollTimeout  = errors.New("opencode: polling timeout exceeded")
	ErrUnavailable  = errors.New("opencode: server unavailable")
	ErrUnauthorized = errors.New("opencode: authentication failed")
)

type Client struct {
	BaseURL    string
	Password   string
	HTTPClient *http.Client
}

func NewClient(baseURL, password string) *Client {
	return &Client{
		BaseURL:    strings.TrimRight(baseURL, "/"),
		Password:   password,
		HTTPClient: &http.Client{Timeout: 130 * time.Second},
	}
}

func (c *Client) CreateSession(ctx context.Context) (*SessionResponse, error) {
	ctx = observability.WithFields(observability.WithTrace(ctx, observability.TraceID(ctx)), observability.Fields{"component": "opencode_client"})
	var session SessionResponse
	if err := c.doJSON(ctx, http.MethodPost, c.BaseURL+"/session", map[string]any{}, &session, http.StatusOK, http.StatusCreated); err != nil {
		return nil, err
	}
	observability.Info(ctx, "opencode_session_created", observability.Fields{"opencode_session_id": session.ID})
	return &session, nil
}

func (c *Client) SendMessage(ctx context.Context, sessionID, text string) error {
	ctx = observability.WithFields(observability.WithTrace(ctx, observability.TraceID(ctx)), observability.Fields{"component": "opencode_client", "opencode_session_id": sessionID})
	ctx = observability.WithFields(ctx, observability.MessageSummary(text))
	payload := PromptRequest{
		Parts:   []MessagePart{{Type: "text", Text: text}},
		Content: []MessagePart{{Type: "text", Text: text}},
	}
	return c.doJSON(ctx, http.MethodPost, c.BaseURL+"/session/"+sessionID+"/prompt_async", payload, nil, http.StatusOK, http.StatusAccepted, http.StatusNoContent)
}

func (c *Client) GetMessages(ctx context.Context, sessionID string) ([]Message, error) {
	ctx = observability.WithFields(observability.WithTrace(ctx, observability.TraceID(ctx)), observability.Fields{"component": "opencode_client", "opencode_session_id": sessionID})
	var state SessionState
	err := c.doJSON(ctx, http.MethodGet, c.BaseURL+"/session/"+sessionID, nil, &state, http.StatusOK)
	if err == nil && len(state.Messages) > 0 {
		observability.Info(ctx, "opencode_messages_loaded", observability.Fields{"message_count": len(state.Messages), "mode": "session_state"})
		return state.Messages, nil
	}

	var messages []Message
	legacyErr := c.doJSON(ctx, http.MethodGet, c.BaseURL+"/session/"+sessionID+"/message", nil, &messages, http.StatusOK)
	if legacyErr == nil {
		observability.Info(ctx, "opencode_messages_loaded", observability.Fields{"message_count": len(messages), "mode": "legacy_messages"})
		return messages, nil
	}
	if err != nil {
		return nil, err
	}
	return messages, legacyErr
}

func (c *Client) AbortSession(ctx context.Context, sessionID string) error {
	ctx = observability.WithFields(observability.WithTrace(ctx, observability.TraceID(ctx)), observability.Fields{"component": "opencode_client", "opencode_session_id": sessionID})
	return c.doJSON(ctx, http.MethodPost, c.BaseURL+"/session/"+sessionID+"/abort", nil, nil, http.StatusOK, http.StatusAccepted, http.StatusNoContent)
}

func (c *Client) doJSON(ctx context.Context, method, url string, payload any, out any, success ...int) error {
	ctx = observability.WithTrace(ctx, observability.TraceID(ctx))
	ctx = observability.WithFields(ctx, observability.Fields{"component": "opencode_client", "http_method": method, "url_path": sanitizeURLPath(url)})
	started := time.Now()
	var opErr error
	statusCode := 0
	defer func() {
		labels := map[string]string{"component": "opencode_client", "method": method, "path": sanitizeURLPath(url)}
		if statusCode > 0 {
			labels["status_code"] = fmt.Sprintf("%d", statusCode)
		}
		observability.ObserveOperation(ctx, "opencode_request", started, labels, opErr)
	}()
	if c.BaseURL == "" || c.Password == "" {
		opErr = ErrUnavailable
		return opErr
	}

	var body io.Reader
	if payload != nil {
		encoded, err := json.Marshal(payload)
		if err != nil {
			opErr = fmt.Errorf("marshal request: %w", err)
			return opErr
		}
		body = bytes.NewReader(encoded)
	}

	req, err := http.NewRequestWithContext(ctx, method, url, body)
	if err != nil {
		opErr = fmt.Errorf("create request: %w", err)
		return opErr
	}
	req.Header.Set("Authorization", c.basicAuthHeader())
	req.Header.Set("Content-Type", "application/json")
	observability.Info(ctx, "opencode_request_start", nil)

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		opErr = fmt.Errorf("%w: %v", ErrUnavailable, err)
		return opErr
	}
	defer resp.Body.Close()
	statusCode = resp.StatusCode

	responseBody, _ := io.ReadAll(resp.Body)
	if !containsStatus(resp.StatusCode, success) {
		switch resp.StatusCode {
		case http.StatusUnauthorized, http.StatusForbidden:
			opErr = ErrUnauthorized
			return opErr
		case http.StatusBadGateway, http.StatusServiceUnavailable, http.StatusGatewayTimeout:
			opErr = fmt.Errorf("%w: status %d", ErrUnavailable, resp.StatusCode)
			return opErr
		default:
			opErr = fmt.Errorf("opencode: status %d: %s", resp.StatusCode, strings.TrimSpace(string(responseBody)))
			return opErr
		}
	}

	if out != nil && len(responseBody) > 0 {
		if err := json.Unmarshal(responseBody, out); err != nil {
			opErr = fmt.Errorf("decode response: %w", err)
			return opErr
		}
	}
	observability.Info(ctx, "opencode_request_end", observability.Fields{"status_code": resp.StatusCode, "latency_ms": time.Since(started).Milliseconds()})
	return nil
}

func sanitizeURLPath(url string) string {
	trimmed := strings.TrimSpace(url)
	if trimmed == "" {
		return ""
	}
	parts := strings.SplitN(trimmed, "://", 2)
	if len(parts) == 2 {
		trimmed = parts[1]
	}
	idx := strings.Index(trimmed, "/")
	if idx == -1 {
		return "/"
	}
	return trimmed[idx:]
}

func (c *Client) basicAuthHeader() string {
	creds := "opencode:" + c.Password
	return "Basic " + base64.StdEncoding.EncodeToString([]byte(creds))
}

func containsStatus(code int, success []int) bool {
	for _, want := range success {
		if code == want {
			return true
		}
	}
	return false
}
