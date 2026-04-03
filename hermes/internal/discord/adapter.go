package discord

import (
	"context"

	"github.com/bwmarrin/discordgo"

	"jarvis-discord-bot/internal/config"
	"jarvis-discord-bot/internal/observability"
	"jarvis-discord-bot/internal/session"
)

type TransportAdapter struct {
	session  *discordgo.Session
	cfg      *config.Config
	mgr      session.SessionManager
	dmRouter *DMRouter
}

func NewTransportAdapter(cfg *config.Config, mgr session.SessionManager) (*TransportAdapter, error) {
	dg, err := discordgo.New("Bot " + cfg.DiscordToken)
	if err != nil {
		return nil, err
	}
	dg.Identify.Intents = discordgo.IntentsGuilds | discordgo.IntentsGuildMessages | discordgo.IntentsMessageContent | discordgo.IntentsDirectMessages
	dmRouter := NewDMRouter(cfg)
	return &TransportAdapter{session: dg, cfg: cfg, mgr: mgr, dmRouter: dmRouter}, nil
}

func (a *TransportAdapter) Start() error {
	a.session.AddHandler(func(s *discordgo.Session, r *discordgo.Ready) {
		ctx := observability.WithFields(observability.WithTrace(context.Background(), observability.NewTraceID()), observability.Fields{"component": "discord_adapter", "discord_user_id": r.User.ID})
		observability.Info(ctx, "discord_ready", observability.Fields{"username": r.User.Username, "discriminator": r.User.Discriminator})
	})
	a.session.AddHandler(InteractionHandler(a.cfg, a.mgr))
	a.session.AddHandler(MessageHandler(a.cfg, a.mgr, a.dmRouter))

	if err := a.session.Open(); err != nil {
		observability.Error(observability.WithTrace(context.Background(), observability.NewTraceID()), "discord_open_failed", observability.Fields{"component": "discord_adapter", "error_class": "discord_open_failed", "error": err.Error()})
		return err
	}

	if err := EnsureBootstrap(a.session, a.cfg.GuildID); err != nil {
		observability.Warn(observability.WithTrace(context.Background(), observability.NewTraceID()), "discord_bootstrap_warning", observability.Fields{"component": "discord_adapter", "error_class": "bootstrap_warning", "error": err.Error()})
	}
	RegisterCommands(a.session, a.cfg.GuildID)
	return nil
}

func (a *TransportAdapter) Stop() error {
	return a.session.Close()
}
