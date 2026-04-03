package agent

import (
	"context"
	"errors"
	"fmt"
	"time"

	"jarvis-discord-bot/internal/observability"
)

const (
	pollInterval   = 1 * time.Second
	getMessagesTTL = 15 * time.Second
	maxRetries     = 3

	// progressUpdateInterval controls how often we invoke the progress callback.
	progressUpdateInterval = 20 * time.Second
)

// PollProgress describes the current state of a polling cycle.
type PollProgress struct {
	ToolUseDetected bool
	ActiveToolName  string
	Elapsed         time.Duration
}

// PollOptions configures polling behaviour.
type PollOptions struct {
	Timeout      time.Duration                             // base timeout (no tool-use)
	TimeoutTools time.Duration                             // extended timeout when tool-use detected
	OnProgress   func(ctx context.Context, p PollProgress) // optional; called periodically
}

// DefaultPollOptions returns sensible defaults (120s / 600s).
func DefaultPollOptions() PollOptions {
	return PollOptions{
		Timeout:      120 * time.Second,
		TimeoutTools: 600 * time.Second,
	}
}

func (c *Client) PollForResponse(ctx context.Context, sessionID string, knownCount int, opts PollOptions) (string, error) {
	parentCtx := ctx
	ctx = observability.WithFields(observability.WithTrace(parentCtx, observability.TraceID(parentCtx)), observability.Fields{
		"component":           "opencode_poller",
		"opencode_session_id": sessionID,
		"known_count":         knownCount,
	})

	if opts.Timeout == 0 {
		opts.Timeout = 120 * time.Second
	}
	if opts.TimeoutTools == 0 {
		opts.TimeoutTools = 600 * time.Second
	}

	started := time.Now()
	deadline := started.Add(opts.Timeout)
	var opErr error
	defer func() {
		observability.ObserveOperation(ctx, "opencode_poll_for_response", started, map[string]string{"component": "opencode_poller"}, opErr)
	}()

	ticker := time.NewTicker(pollInterval)
	defer ticker.Stop()

	retries := 0
	toolUseExtended := false
	lastProgressUpdate := time.Time{}
	observability.Info(ctx, "opencode_poll_started", nil)

	for {
		// Check deadline before each poll attempt.
		if time.Now().After(deadline) {
			opErr = ErrPollTimeout
			observability.Warn(ctx, "opencode_poll_timeout", observability.Fields{
				"tool_use_extended": toolUseExtended,
				"elapsed_ms":        time.Since(started).Milliseconds(),
			})
			return "", opErr
		}

		// Use a per-request timeout so a slow GetMessages doesn't consume the
		// entire poll budget.
		reqCtx, reqCancel := context.WithTimeout(ctx, getMessagesTTL)
		messages, err := c.GetMessages(reqCtx, sessionID)
		reqCancel()

		if err == nil {
			retries = 0
			text, inProgress := extractAssistantReply(messages, knownCount)
			if text != "" {
				observability.Info(ctx, "opencode_poll_response_ready", observability.Fields{
					"message_count":     len(messages),
					"response_length":   len(text),
					"tool_use_extended": toolUseExtended,
					"elapsed_ms":        time.Since(started).Milliseconds(),
				})
				return text, nil
			}

			if inProgress {
				if !toolUseExtended {
					// First detection of an in-progress assistant message.
					// Extend the deadline to accommodate tool execution.
					toolUseExtended = true
					deadline = started.Add(opts.TimeoutTools)

					observability.Info(ctx, "opencode_poll_tool_use_detected", observability.Fields{
						"message_count":   len(messages),
						"new_deadline_ms": time.Until(deadline).Milliseconds(),
						"elapsed_ms":      time.Since(started).Milliseconds(),
					})
				}

				// Fire progress callback periodically.
				if opts.OnProgress != nil && time.Since(lastProgressUpdate) >= progressUpdateInterval {
					toolName := activeToolFromMessages(messages, knownCount)
					opts.OnProgress(ctx, PollProgress{
						ToolUseDetected: true,
						ActiveToolName:  toolName,
						Elapsed:         time.Since(started),
					})
					lastProgressUpdate = time.Now()
				}
			}
		} else if errors.Is(err, ErrUnauthorized) {
			opErr = err
			return "", err
		} else {
			retries++
			observability.Warn(ctx, "opencode_poll_retry", observability.Fields{
				"retry":       retries,
				"error_class": "poll_retry_error",
				"error":       err.Error(),
			})
			if retries >= maxRetries {
				opErr = err
				return "", err
			}
			// Back off before retrying, but respect the deadline.
			select {
			case <-time.After(2 * time.Second):
			case <-parentCtx.Done():
				opErr = ErrPollTimeout
				return "", opErr
			}
			continue
		}

		// Wait for next tick, but respect the parent context cancellation.
		select {
		case <-parentCtx.Done():
			opErr = fmt.Errorf("opencode: polling canceled: %w", parentCtx.Err())
			return "", opErr
		case <-ticker.C:
		}
	}
}

// activeToolFromMessages finds the most recent running tool name from the
// in-progress assistant messages above knownCount.
func activeToolFromMessages(messages []Message, knownCount int) string {
	for idx := len(messages) - 1; idx >= knownCount; idx-- {
		msg := messages[idx]
		if msg.GetRole() != "assistant" || msg.IsComplete() {
			continue
		}
		if name := msg.ActiveToolName(); name != "" {
			return name
		}
	}
	return ""
}

// extractAssistantReply scans messages above knownCount for a completed assistant reply.
// Returns:
//   - (text, false) when a completed assistant message with text is found
//   - ("", true)    when an in-progress assistant message exists (tool-use or still generating)
//   - ("", false)   when no new assistant message exists at all
func extractAssistantReply(messages []Message, knownCount int) (string, bool) {
	if len(messages) <= knownCount {
		return "", false
	}
	inProgress := false
	for idx := len(messages) - 1; idx >= knownCount; idx-- {
		msg := messages[idx]
		if msg.GetRole() != "assistant" {
			continue
		}
		if msg.IsComplete() {
			if text := msg.GetText(); text != "" {
				return text, false
			}
			// Completed but no text — keep scanning older messages.
			continue
		}
		// Assistant message exists but is not yet complete.
		inProgress = true
	}
	return "", inProgress
}
