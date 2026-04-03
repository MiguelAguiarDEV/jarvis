package discord

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/bwmarrin/discordgo"

	"jarvis-discord-bot/internal/agent"
	"jarvis-discord-bot/internal/config"
	"jarvis-discord-bot/internal/observability"
	"jarvis-discord-bot/internal/session"
)

func MessageHandler(cfg *config.Config, mgr session.SessionManager, dmRouter *DMRouter) func(*discordgo.Session, *discordgo.MessageCreate) {
	return func(s *discordgo.Session, m *discordgo.MessageCreate) {
		ctx := observability.WithFields(observability.WithTrace(context.Background(), observability.NewTraceID()), observability.Fields{"component": "discord_message", "channel_id": m.ChannelID})

		// Guard: nil author, bot messages, or uninitialized gateway state.
		if m.Author == nil || m.Author.Bot {
			observability.Inc("jarvis_ignored_messages_total", "Ignored Discord messages by reason.", map[string]string{"reason": "bot_or_nil_author"})
			return
		}
		if s.State == nil || s.State.User == nil {
			observability.Inc("jarvis_ignored_messages_total", "Ignored Discord messages by reason.", map[string]string{"reason": "gateway_not_ready"})
			observability.Warn(ctx, "message_ignored", observability.Fields{"reason": "gateway_not_ready"})
			return
		}
		ctx = observability.WithFields(ctx, observability.Fields{"author_id": m.Author.ID, "guild_id": m.GuildID})

		// Skip the bot's own messages.
		if m.Author.ID == s.State.User.ID {
			return
		}
		// Skip empty messages (embeds, attachments only).
		if strings.TrimSpace(m.Content) == "" {
			observability.Inc("jarvis_ignored_messages_total", "Ignored Discord messages by reason.", map[string]string{"reason": "empty_message"})
			return
		}

		// Route DMs to ATHENA via mnemo chat (before checking guild sessions).
		if dmRouter != nil && dmRouter.HandleDM(s, m) {
			return
		}

		ctx = observability.WithFields(ctx, observability.MessageSummary(m.Content))

		sess, ok := mgr.Get(m.ChannelID)
		if !ok {
			// No session for this channel — not a session thread. Silently ignore.
			return
		}

		// Auto-recover failed sessions: create a new OpenCode session for this thread.
		if sess.IsFailed() {
			observability.Info(ctx, "session_auto_recover_start", observability.Fields{
				"last_error": sess.LastError,
			})
			recovered, err := mgr.Recover(ctx, m.ChannelID)
			if err != nil {
				observability.Error(ctx, "session_auto_recover_failed", observability.Fields{
					"error_class": "auto_recover_failed",
					"error":       err.Error(),
				})
				_, _ = s.ChannelMessageSend(m.ChannelID, "Session recovery failed. Use /end and /chat to start fresh.")
				return
			}
			observability.Info(ctx, "session_auto_recovered", observability.Fields{
				"new_opencode_session_id": recovered.OpenCodeSessionID,
			})
			_, _ = s.ChannelMessageSend(m.ChannelID, "♻️ Session recovered. Processing your message...")
			sess = recovered
		}

		if !sess.IsActive() {
			observability.Inc("jarvis_ignored_messages_total", "Ignored Discord messages by reason.", map[string]string{"reason": "session_not_active"})
			observability.Info(ctx, "message_ignored", observability.Fields{"reason": "session_not_active", "status": sess.Status})
			return
		}

		ctx = observability.WithFields(ctx, observability.Fields{"opencode_session_id": sess.OpenCodeSessionID, "session_user_id": sess.UserID})

		if !cfg.IsUserAllowed(m.Author.ID) {
			observability.Inc("jarvis_ignored_messages_total", "Ignored Discord messages by reason.", map[string]string{"reason": "unauthorized_user"})
			observability.Warn(ctx, "message_ignored", observability.Fields{"reason": "unauthorized_user"})
			_, _ = s.ChannelMessageSend(m.ChannelID, "Not authorized")
			return
		}

		go relayMessage(ctx, s, m.ChannelID, m.Content, mgr, cfg)
	}
}

func relayMessage(ctx context.Context, s *discordgo.Session, channelID, text string, mgr session.SessionManager, cfg *config.Config) {
	ctx = observability.WithFields(observability.WithTrace(ctx, observability.TraceID(ctx)), observability.Fields{"component": "discord_relay", "channel_id": channelID})
	ctx = observability.WithFields(ctx, observability.MessageSummary(text))
	started := time.Now()
	var relayErr error
	defer func() {
		observability.ObserveOperation(ctx, "discord_relay_message", started, map[string]string{"component": "discord_relay"}, relayErr)
	}()
	observability.Info(ctx, "relay_started", nil)
	_ = s.ChannelTyping(channelID)
	placeholder, err := s.ChannelMessageSend(channelID, "⏳ Thinking...")
	if err != nil {
		relayErr = err
		observability.Error(ctx, "relay_placeholder_failed", observability.Fields{"error_class": "placeholder_failed", "error": err.Error()})
		return
	}
	ctx = observability.WithFields(ctx, observability.Fields{"placeholder_message_id": placeholder.ID})

	// Build progress callback that updates the Discord placeholder.
	onProgress := func(_ context.Context, p agent.PollProgress) {
		var msg string
		elapsed := int(p.Elapsed.Seconds())
		if p.ActiveToolName != "" {
			msg = fmt.Sprintf("🔧 Running %s... (%ds)", formatToolName(p.ActiveToolName), elapsed)
		} else if p.ToolUseDetected {
			msg = fmt.Sprintf("🔧 Running tools... (%ds)", elapsed)
		} else {
			msg = fmt.Sprintf("⏳ Thinking... (%ds)", elapsed)
		}
		_, _ = s.ChannelMessageEdit(channelID, placeholder.ID, msg)
	}

	opts := agent.PollOptions{
		Timeout:      cfg.PollTimeout,
		TimeoutTools: cfg.PollTimeoutTools,
		OnProgress:   onProgress,
	}

	response, err := mgr.SendAndWait(ctx, channelID, text, opts)
	if err != nil {
		relayErr = err
		observability.Error(ctx, "relay_manager_failed", observability.Fields{"error_class": "send_and_wait_failed", "error": err.Error()})

		// If session was marked failed, tell the user they can retry.
		if errors.Is(err, session.ErrSessionFailed) {
			_, _ = s.ChannelMessageEdit(channelID, placeholder.ID, "Session failed. Send your message again to auto-recover, or /end and /chat to start fresh.")
		} else if errors.Is(err, agent.ErrPollTimeout) {
			_, _ = s.ChannelMessageEdit(channelID, placeholder.ID, "⏰ The agent is still working but took too long. Try a simpler question or check back later.")
		} else {
			_, _ = s.ChannelMessageEdit(channelID, placeholder.ID, mapRelayError(err))
		}
		return
	}

	chunks := SplitResponse(response, 1800)
	if len(chunks) == 0 {
		relayErr = context.DeadlineExceeded
		observability.Warn(ctx, "relay_empty_response", observability.Fields{"reason": "empty_chunks"})
		_, _ = s.ChannelMessageEdit(channelID, placeholder.ID, "Agent returned an empty response.")
		return
	}

	_, _ = s.ChannelMessageEdit(channelID, placeholder.ID, chunks[0])
	observability.Info(ctx, "relay_first_chunk_sent", observability.Fields{"chunk_count": len(chunks), "response_length": len(response)})
	for _, chunk := range chunks[1:] {
		if _, err := s.ChannelMessageSend(channelID, chunk); err != nil {
			relayErr = err
			observability.Error(ctx, "relay_chunk_send_failed", observability.Fields{"error_class": "chunk_send_failed", "error": err.Error()})
			return
		}
	}
	observability.Info(ctx, "relay_completed", observability.Fields{"latency_ms": time.Since(started).Milliseconds()})
}

// formatToolName makes tool names more user-friendly for Discord display.
func formatToolName(name string) string {
	// Shorten common long names.
	switch {
	case strings.HasPrefix(name, "mcp_"):
		// e.g. "mcp_bash" -> "bash", "mcp_playwright_navigate" -> "playwright navigate"
		short := strings.TrimPrefix(name, "mcp_")
		return strings.ReplaceAll(short, "_", " ")
	default:
		return strings.ReplaceAll(name, "_", " ")
	}
}
