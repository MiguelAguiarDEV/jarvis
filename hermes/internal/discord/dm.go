package discord

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/bwmarrin/discordgo"

	"jarvis-discord-bot/internal/agent"
	"jarvis-discord-bot/internal/config"
	"jarvis-discord-bot/internal/observability"
)

// dmConversation tracks the mnemo conversation for a DM channel.
type dmConversation struct {
	ConversationID int64
	ChannelID      string
	UserID         string
	CreatedAt      time.Time
	TurnCount      int
}

// DMRouter handles Discord DM messages by routing them to ATHENA via
// the mnemo-cloud /api/chat SSE endpoint.
type DMRouter struct {
	mu            sync.RWMutex
	conversations map[string]*dmConversation // channelID -> conversation
	chatClient    *agent.MnemoChatClient
	cfg           *config.Config
}

// NewDMRouter creates a new DM router.
func NewDMRouter(cfg *config.Config) *DMRouter {
	var chatClient *agent.MnemoChatClient
	if cfg.MnemoURL != "" && cfg.MnemoAPIKey != "" {
		chatClient = agent.NewMnemoChatClient(cfg.MnemoURL, cfg.MnemoAPIKey)
	}
	return &DMRouter{
		conversations: make(map[string]*dmConversation),
		chatClient:    chatClient,
		cfg:           cfg,
	}
}

// HandleDM processes a DM message. Returns true if the message was a DM
// and was handled (or should be ignored), false if not a DM.
func (d *DMRouter) HandleDM(s *discordgo.Session, m *discordgo.MessageCreate) bool {
	// Only handle DMs (GuildID is empty for DMs).
	if m.GuildID != "" {
		return false
	}

	ctx := observability.WithFields(
		observability.WithTrace(context.Background(), observability.NewTraceID()),
		observability.Fields{
			"component":  "dm_router",
			"channel_id": m.ChannelID,
			"author_id":  m.Author.ID,
		},
	)

	// Guard: nil author, bot messages, or uninitialized gateway state.
	if m.Author == nil || m.Author.Bot {
		return true
	}
	if s.State == nil || s.State.User == nil {
		return true
	}
	if m.Author.ID == s.State.User.ID {
		return true
	}
	if strings.TrimSpace(m.Content) == "" {
		return true
	}

	ctx = observability.WithFields(ctx, observability.MessageSummary(m.Content))

	// Auth check.
	if !d.cfg.IsUserAllowed(m.Author.ID) {
		observability.Inc("jarvis_dm_ignored_total", "Ignored DM messages by reason.", map[string]string{"reason": "unauthorized_user"})
		observability.Warn(ctx, "dm_unauthorized", nil)
		_, _ = s.ChannelMessageSend(m.ChannelID, "Not authorized.")
		return true
	}

	// Check if chat client is configured.
	if d.chatClient == nil {
		observability.Warn(ctx, "dm_chat_unavailable", observability.Fields{"reason": "no_api_key"})
		_, _ = s.ChannelMessageSend(m.ChannelID, "Chat not configured. Set MNEMO_API_KEY.")
		return true
	}

	observability.Info(ctx, "dm_received", nil)
	go d.relayDM(ctx, s, m)
	return true
}

// relayDM sends the DM to ATHENA via mnemo chat and posts the response.
func (d *DMRouter) relayDM(ctx context.Context, s *discordgo.Session, m *discordgo.MessageCreate) {
	started := time.Now()
	var relayErr error
	defer func() {
		observability.ObserveOperation(ctx, "dm_relay", started,
			map[string]string{"component": "dm_router"}, relayErr)
	}()

	_ = s.ChannelTyping(m.ChannelID)
	placeholder, err := s.ChannelMessageSend(m.ChannelID, "Thinking...")
	if err != nil {
		relayErr = err
		observability.Error(ctx, "dm_placeholder_failed", observability.Fields{
			"error_class": "placeholder_failed", "error": err.Error(),
		})
		return
	}

	// Get or create conversation for this DM channel.
	conv, err := d.getOrCreateConversation(ctx, m.ChannelID, m.Author.ID)
	if err != nil {
		relayErr = err
		observability.Error(ctx, "dm_conversation_failed", observability.Fields{
			"error_class": "conversation_create_failed", "error": err.Error(),
		})
		_, _ = s.ChannelMessageEdit(m.ChannelID, placeholder.ID, "Failed to start conversation. Try again later.")
		return
	}
	ctx = observability.WithFields(ctx, observability.Fields{"conversation_id": conv.ConversationID})

	// Stream response from ATHENA.
	lastUpdate := time.Now()
	tokenCount := 0
	onToken := func(token string) {
		tokenCount++
		// Update placeholder periodically to show progress.
		if time.Since(lastUpdate) > 3*time.Second {
			_, _ = s.ChannelMessageEdit(m.ChannelID, placeholder.ID,
				fmt.Sprintf("Thinking... (%ds)", int(time.Since(started).Seconds())))
			lastUpdate = time.Now()
		}
	}

	response, err := d.chatClient.ChatSSE(ctx, conv.ConversationID, m.Content, onToken)
	if err != nil {
		relayErr = err
		observability.Error(ctx, "dm_chat_failed", observability.Fields{
			"error_class": "chat_sse_failed", "error": err.Error(),
		})
		errMsg := "Something went wrong. Try again."
		if strings.Contains(err.Error(), "conversation not found") {
			// Conversation was deleted server-side; reset and retry.
			d.mu.Lock()
			delete(d.conversations, m.ChannelID)
			d.mu.Unlock()
			errMsg = "Conversation expired. Send your message again to start a new one."
		}
		_, _ = s.ChannelMessageEdit(m.ChannelID, placeholder.ID, errMsg)
		return
	}

	if strings.TrimSpace(response) == "" {
		_, _ = s.ChannelMessageEdit(m.ChannelID, placeholder.ID, "Agent returned an empty response.")
		return
	}

	// Update turn count.
	d.mu.Lock()
	conv.TurnCount++
	d.mu.Unlock()

	// Split and send response.
	chunks := SplitResponse(response, 1800)
	_, _ = s.ChannelMessageEdit(m.ChannelID, placeholder.ID, chunks[0])
	for _, chunk := range chunks[1:] {
		_, _ = s.ChannelMessageSend(m.ChannelID, chunk)
	}
	observability.Info(ctx, "dm_relay_completed", observability.Fields{
		"response_length": len(response),
		"chunk_count":     len(chunks),
		"turn_count":      conv.TurnCount,
		"latency_ms":      time.Since(started).Milliseconds(),
	})
}

// getOrCreateConversation returns the existing conversation for a DM channel
// or creates a new one via the mnemo API.
func (d *DMRouter) getOrCreateConversation(ctx context.Context, channelID, userID string) (*dmConversation, error) {
	d.mu.RLock()
	conv, ok := d.conversations[channelID]
	d.mu.RUnlock()
	if ok {
		return conv, nil
	}

	title := fmt.Sprintf("Discord DM %s", time.Now().Format("2006-01-02 15:04"))
	conversationID, err := d.chatClient.CreateConversation(ctx, title)
	if err != nil {
		return nil, err
	}

	conv = &dmConversation{
		ConversationID: conversationID,
		ChannelID:      channelID,
		UserID:         userID,
		CreatedAt:      time.Now(),
	}
	d.mu.Lock()
	d.conversations[channelID] = conv
	d.mu.Unlock()

	observability.Info(ctx, "dm_conversation_created", observability.Fields{
		"conversation_id": conversationID,
		"channel_id":      channelID,
	})
	return conv, nil
}
