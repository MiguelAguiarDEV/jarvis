package discord

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/bwmarrin/discordgo"

	"jarvis-discord-bot/internal/agent"
	"jarvis-discord-bot/internal/config"
	"jarvis-discord-bot/internal/observability"
	"jarvis-discord-bot/internal/session"
)

var (
	jwtToken string
	jwtMu    sync.RWMutex
)

func RegisterCommands(s *discordgo.Session, guildID string) {
	commands := []*discordgo.ApplicationCommand{
		{Name: "status", Description: "Show homelab status: containers, disk, RAM, uptime"},
		{Name: "services", Description: "List running Docker services"},
		{Name: "search", Description: "Search Mnemo memory", Options: []*discordgo.ApplicationCommandOption{{Type: discordgo.ApplicationCommandOptionString, Name: "query", Description: "Search query", Required: true}}},
		{Name: "context", Description: "Get recent Mnemo context for a project", Options: []*discordgo.ApplicationCommandOption{{Type: discordgo.ApplicationCommandOptionString, Name: "project", Description: "Project name", Required: true}}},
		{Name: "chat", Description: "Start a new chat session with the AI agent", Options: []*discordgo.ApplicationCommandOption{{Type: discordgo.ApplicationCommandOptionString, Name: "topic", Description: "Session topic", Required: false}}},
		{Name: "end", Description: "End the current chat session"},
	}

	for _, cmd := range commands {
		if _, err := s.ApplicationCommandCreate(s.State.User.ID, guildID, cmd); err != nil {
			observability.Error(observability.WithTrace(context.Background(), observability.NewTraceID()), "discord_command_register_failed", observability.Fields{"component": "discord_commands", "command": cmd.Name, "error_class": "command_register_failed", "error": err.Error()})
			continue
		}
		observability.Info(observability.WithTrace(context.Background(), observability.NewTraceID()), "discord_command_registered", observability.Fields{"component": "discord_commands", "command": cmd.Name})
	}
}

func InteractionHandler(cfg *config.Config, mgr session.SessionManager) func(*discordgo.Session, *discordgo.InteractionCreate) {
	return func(s *discordgo.Session, i *discordgo.InteractionCreate) {
		commandName := ""
		if i.Type == discordgo.InteractionApplicationCommand {
			commandName = i.ApplicationCommandData().Name
		}
		ctx := observability.WithFields(observability.WithTrace(context.Background(), observability.NewTraceID()), observability.Fields{"component": "discord_interaction", "channel_id": i.ChannelID, "guild_id": i.GuildID, "command": commandName, "user_id": getUserID(i)})
		if i.Type != discordgo.InteractionApplicationCommand {
			observability.Inc("jarvis_ignored_interactions_total", "Ignored Discord interactions by reason.", map[string]string{"reason": "non_application_command"})
			observability.Info(ctx, "interaction_ignored", observability.Fields{"reason": "non_application_command"})
			return
		}

		userID := getUserID(i)
		if !cfg.IsUserAllowed(userID) {
			observability.Inc("jarvis_ignored_interactions_total", "Ignored Discord interactions by reason.", map[string]string{"reason": "unauthorized_user"})
			observability.Warn(ctx, "interaction_ignored", observability.Fields{"reason": "unauthorized_user"})
			respond(s, i, "Not authorized")
			return
		}
		observability.Info(ctx, "interaction_received", nil)

		switch i.ApplicationCommandData().Name {
		case "status":
			handleStatus(s, i)
		case "services":
			handleServices(s, i)
		case "search":
			handleSearch(s, i, cfg)
		case "context":
			handleContext(s, i, cfg)
		case "chat":
			handleChat(s, i, cfg, mgr)
		case "end":
			handleEnd(s, i, mgr)
		}
	}
}

func handleChat(s *discordgo.Session, i *discordgo.InteractionCreate, cfg *config.Config, mgr session.SessionManager) {
	ctx := observability.WithFields(observability.WithTrace(context.Background(), observability.NewTraceID()), observability.Fields{"component": "discord_chat", "channel_id": i.ChannelID, "guild_id": i.GuildID, "user_id": getUserID(i), "command": "chat"})
	if cfg.OpenCodeURL == "" || cfg.OpenCodePassword == "" {
		observability.Warn(ctx, "chat_unavailable", observability.Fields{"reason": "opencode_not_configured"})
		respond(s, i, "Agent unavailable. Try again later.")
		return
	}

	topic := ""
	for _, opt := range i.ApplicationCommandData().Options {
		if opt.Name == "topic" {
			topic = strings.TrimSpace(opt.StringValue())
		}
	}
	ctx = observability.WithFields(ctx, observability.Fields{"topic": topic})
	if topic != "" {
		ctx = observability.WithFields(ctx, observability.MessageSummary(topic))
	}

	if err := s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{Type: discordgo.InteractionResponseDeferredChannelMessageWithSource}); err != nil {
		observability.Error(ctx, "chat_defer_failed", observability.Fields{"error_class": "interaction_defer_failed", "error": err.Error()})
		return
	}
	observability.Info(ctx, "chat_deferred", nil)

	threadName := buildThreadName(topic)
	thread, err := createInteractionThread(s, i, threadName)
	if err != nil {
		observability.Error(ctx, "chat_thread_create_failed", observability.Fields{"error_class": "thread_create_failed", "error": err.Error()})
		msg := fmt.Sprintf("Failed to create thread: %v", err)
		_, _ = s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &msg})
		return
	}
	ctx = observability.WithCorrelation(ctx, thread.ID)
	ctx = observability.WithFields(ctx, observability.Fields{"thread_id": thread.ID, "thread_name": thread.Name})
	observability.Info(ctx, "chat_thread_created", nil)

	_, err = mgr.Create(ctx, getUserID(i), thread.ID, topic)
	if err != nil {
		observability.Error(ctx, "chat_session_create_failed", observability.Fields{"error_class": "session_create_failed", "error": err.Error()})
		msg := "Agent unavailable. Try again later."
		_, _ = s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &msg})
		return
	}

	ready := fmt.Sprintf("Session started in %s", thread.Mention())
	_, _ = s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &ready})
	observability.Info(ctx, "chat_session_started", nil)

	if topic == "" {
		_, _ = s.ChannelMessageSend(thread.ID, "Session ready. Send your first message.")
		observability.Info(ctx, "chat_waiting_for_first_message", nil)
		return
	}

	go relayMessage(ctx, s, thread.ID, topic, mgr, cfg)
}

func handleEnd(s *discordgo.Session, i *discordgo.InteractionCreate, mgr session.SessionManager) {
	ctx := observability.WithFields(observability.WithTrace(context.Background(), observability.NewTraceID()), observability.Fields{"component": "discord_end", "channel_id": i.ChannelID, "guild_id": i.GuildID, "user_id": getUserID(i), "command": "end"})
	if err := s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{Type: discordgo.InteractionResponseDeferredChannelMessageWithSource}); err != nil {
		observability.Error(ctx, "end_defer_failed", observability.Fields{"error_class": "interaction_defer_failed", "error": err.Error()})
		return
	}

	sess, err := mgr.End(ctx, i.ChannelID)
	if err != nil {
		observability.Warn(ctx, "end_without_session", observability.Fields{"error_class": "end_missing_session", "error": err.Error()})
		msg := "No active session in this thread."
		_, _ = s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &msg})
		return
	}

	msg := fmt.Sprintf("Session ended. %d turns.", sess.TurnCount)
	_, _ = s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &msg})
	_ = archiveThread(s, i.ChannelID)
	observability.Info(ctx, "end_completed", observability.Fields{"turn_count": sess.TurnCount})
}

func handleStatus(s *discordgo.Session, i *discordgo.InteractionCreate) {
	_ = s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{Type: discordgo.InteractionResponseDeferredChannelMessageWithSource})
	uptime := shellCmd("uptime -p")
	disk := shellCmd("df -h / | tail -1 | awk '{print \"Used: \" $3 \"/\" $2 \" (\" $5 \")\"}'")
	mem := shellCmd("free -h | awk '/Mem:/{print \"Used: \" $3 \"/\" $2}'")
	containers := shellCmd("docker ps --format '{{.Names}}: {{.Status}}' 2>/dev/null || echo 'Docker not available'")
	load := shellCmd("cat /proc/loadavg | awk '{print $1, $2, $3}'")
	msg := fmt.Sprintf("**Homelab Status**\n\n**Uptime:** %s\n**Disk:** %s\n**RAM:** %s\n**Load:** %s\n\n**Containers:**\n%s", uptime, disk, mem, load, FormatContainers(containers))
	_, _ = s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &msg})
}

func handleServices(s *discordgo.Session, i *discordgo.InteractionCreate) {
	_ = s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{Type: discordgo.InteractionResponseDeferredChannelMessageWithSource})
	out := shellCmd("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || echo 'Docker not available'")
	msg := fmt.Sprintf("**Docker Services**\n```\n%s\n```", out)
	_, _ = s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &msg})
}

func handleSearch(s *discordgo.Session, i *discordgo.InteractionCreate, cfg *config.Config) {
	ctx := observability.WithFields(observability.WithTrace(context.Background(), observability.NewTraceID()), observability.Fields{"component": "discord_search", "channel_id": i.ChannelID, "user_id": getUserID(i), "command": "search"})
	_ = s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{Type: discordgo.InteractionResponseDeferredChannelMessageWithSource})
	query := i.ApplicationCommandData().Options[0].StringValue()
	ctx = observability.WithFields(ctx, observability.MessageSummary(query))
	jwt := getJWT()
	if cfg.MnemoURL == "" || jwt == "" {
		observability.Warn(ctx, "search_unavailable", observability.Fields{"reason": "mnemo_not_connected"})
		msg := "Mnemo not connected"
		_, _ = s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &msg})
		return
	}

	url := fmt.Sprintf("%s/sync/search?q=%s&limit=5", cfg.MnemoURL, query)
	req, _ := http.NewRequest(http.MethodGet, url, nil)
	req.Header.Set("Authorization", "Bearer "+jwt)
	resp, err := (&http.Client{Timeout: 10 * time.Second}).Do(req)
	if err != nil {
		observability.Error(ctx, "search_request_failed", observability.Fields{"error_class": "mnemo_request_failed", "error": err.Error()})
		msg := fmt.Sprintf("Mnemo error: %v", err)
		_, _ = s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &msg})
		return
	}
	defer resp.Body.Close()

	var result struct {
		Results []struct {
			ID      int    `json:"id"`
			Title   string `json:"title"`
			Type    string `json:"type"`
			Project string `json:"project"`
			Content string `json:"content"`
		} `json:"results"`
	}
	_ = json.NewDecoder(resp.Body).Decode(&result)
	if len(result.Results) == 0 {
		observability.Info(ctx, "search_no_results", nil)
		msg := fmt.Sprintf("No results for: **%s**", query)
		_, _ = s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &msg})
		return
	}

	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("**Results for: %s**\n\n", query))
	for _, obs := range result.Results {
		content := obs.Content
		if len(content) > 150 {
			content = content[:150] + "..."
		}
		sb.WriteString(fmt.Sprintf("**#%d** [%s] %s _%s_\n%s\n\n", obs.ID, obs.Type, obs.Title, obs.Project, content))
	}
	msg := truncateForDiscord(sb.String())
	_, _ = s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &msg})
	observability.Info(ctx, "search_completed", observability.Fields{"result_count": len(result.Results)})
}

func handleContext(s *discordgo.Session, i *discordgo.InteractionCreate, cfg *config.Config) {
	ctx := observability.WithFields(observability.WithTrace(context.Background(), observability.NewTraceID()), observability.Fields{"component": "discord_context", "channel_id": i.ChannelID, "user_id": getUserID(i), "command": "context"})
	_ = s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{Type: discordgo.InteractionResponseDeferredChannelMessageWithSource})
	project := i.ApplicationCommandData().Options[0].StringValue()
	ctx = observability.WithFields(ctx, observability.MessageSummary(project))
	jwt := getJWT()
	if cfg.MnemoURL == "" || jwt == "" {
		observability.Warn(ctx, "context_unavailable", observability.Fields{"reason": "mnemo_not_connected"})
		msg := "Mnemo not connected"
		_, _ = s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &msg})
		return
	}

	url := fmt.Sprintf("%s/sync/context?project=%s&limit=5", cfg.MnemoURL, project)
	req, _ := http.NewRequest(http.MethodGet, url, nil)
	req.Header.Set("Authorization", "Bearer "+jwt)
	resp, err := (&http.Client{Timeout: 10 * time.Second}).Do(req)
	if err != nil {
		observability.Error(ctx, "context_request_failed", observability.Fields{"error_class": "mnemo_request_failed", "error": err.Error()})
		msg := fmt.Sprintf("Mnemo error: %v", err)
		_, _ = s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &msg})
		return
	}
	defer resp.Body.Close()

	var result struct {
		Context string `json:"context"`
	}
	_ = json.NewDecoder(resp.Body).Decode(&result)
	msg := result.Context
	if msg == "" {
		msg = fmt.Sprintf("No context for: **%s**", project)
	}
	msg = truncateForDiscord(msg)
	_, _ = s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &msg})
	observability.Info(ctx, "context_completed", observability.Fields{"context_empty": msg == ""})
}

func MnemoLogin(cfg *config.Config) error {
	ctx := observability.WithFields(observability.WithTrace(context.Background(), observability.NewTraceID()), observability.Fields{"component": "mnemo_auth", "mnemo_url": cfg.MnemoURL, "mnemo_user": cfg.MnemoUser})
	body, _ := json.Marshal(map[string]string{"username": cfg.MnemoUser, "password": cfg.MnemoPass})
	resp, err := http.Post(cfg.MnemoURL+"/auth/login", "application/json", bytes.NewReader(body))
	if err != nil {
		observability.Error(ctx, "mnemo_login_request_failed", observability.Fields{"error_class": "mnemo_login_failed", "error": err.Error()})
		return err
	}
	defer resp.Body.Close()
	var result struct {
		AccessToken string `json:"access_token"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		observability.Error(ctx, "mnemo_login_decode_failed", observability.Fields{"error_class": "mnemo_login_decode_failed", "error": err.Error()})
		return err
	}
	if result.AccessToken == "" {
		observability.Warn(ctx, "mnemo_login_empty_token", nil)
		return fmt.Errorf("no access_token in response")
	}
	jwtMu.Lock()
	jwtToken = result.AccessToken
	jwtMu.Unlock()
	observability.Info(ctx, "mnemo_login_succeeded", nil)
	return nil
}

func getJWT() string {
	jwtMu.RLock()
	defer jwtMu.RUnlock()
	return jwtToken
}

func getUserID(i *discordgo.InteractionCreate) string {
	if i.Member != nil {
		return i.Member.User.ID
	}
	if i.User != nil {
		return i.User.ID
	}
	return ""
}

func shellCmd(cmd string) string {
	out, err := exec.Command("sh", "-c", cmd).CombinedOutput()
	if err != nil {
		return fmt.Sprintf("error: %v", err)
	}
	return strings.TrimSpace(string(out))
}

func respond(s *discordgo.Session, i *discordgo.InteractionCreate, msg string) {
	_ = s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{Type: discordgo.InteractionResponseChannelMessageWithSource, Data: &discordgo.InteractionResponseData{Content: msg}})
}

func buildThreadName(topic string) string {
	stamp := time.Now().Format("15:04")
	if strings.TrimSpace(topic) == "" {
		return fmt.Sprintf("🤖 New session [%s]", stamp)
	}
	name := fmt.Sprintf("🤖 %s [%s]", strings.TrimSpace(topic), stamp)
	if len(name) > 100 {
		return name[:100]
	}
	return name
}

func createInteractionThread(s *discordgo.Session, i *discordgo.InteractionCreate, threadName string) (*discordgo.Channel, error) {
	ctx := observability.WithFields(observability.WithTrace(context.Background(), observability.NewTraceID()), observability.Fields{"component": "discord_thread", "channel_id": i.ChannelID, "thread_name": threadName})
	seed := "Creating session thread..."
	message, err := s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &seed})
	if err != nil {
		observability.Error(ctx, "thread_seed_message_failed", observability.Fields{"error_class": "thread_seed_message_failed", "error": err.Error()})
		return nil, err
	}
	thread, err := s.MessageThreadStartComplex(message.ChannelID, message.ID, &discordgo.ThreadStart{Name: threadName, AutoArchiveDuration: 1440})
	if err != nil {
		observability.Error(ctx, "thread_start_failed", observability.Fields{"error_class": "thread_start_failed", "error": err.Error()})
		return nil, err
	}
	observability.Info(ctx, "thread_started", observability.Fields{"thread_id": thread.ID})
	return thread, nil
}

func archiveThread(s *discordgo.Session, channelID string) error {
	ctx := observability.WithFields(observability.WithTrace(context.Background(), observability.NewTraceID()), observability.Fields{"component": "discord_thread", "channel_id": channelID})
	archived := true
	_, err := s.ChannelEditComplex(channelID, &discordgo.ChannelEdit{Archived: &archived})
	if err != nil {
		observability.Error(ctx, "thread_archive_failed", observability.Fields{"error_class": "thread_archive_failed", "error": err.Error()})
		return err
	}
	observability.Info(ctx, "thread_archived", nil)
	return err
}

func mapRelayError(err error) string {
	if err == nil {
		return ""
	}
	switch {
	case strings.Contains(err.Error(), agent.ErrPollTimeout.Error()):
		return "Response timed out. Try again or /end session."
	case strings.Contains(err.Error(), agent.ErrUnauthorized.Error()):
		return "Agent unavailable. Try again later."
	case strings.Contains(err.Error(), agent.ErrUnavailable.Error()):
		return "Agent unavailable. Try again later."
	default:
		return fmt.Sprintf("Agent error: %v", err)
	}
}

func truncateForDiscord(msg string) string {
	if len(msg) <= 2000 {
		return msg
	}
	return msg[:1997] + "..."
}
