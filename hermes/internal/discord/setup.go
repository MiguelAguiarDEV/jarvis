package discord

import (
	"context"
	"fmt"
	"strings"

	"github.com/bwmarrin/discordgo"

	"jarvis-discord-bot/internal/observability"
)

const (
	bootstrapCategory = "jarvis"
	bootstrapChannel  = "chat"
)

func EnsureBootstrap(s *discordgo.Session, guildID string) error {
	ctx := observability.WithFields(observability.WithTrace(context.Background(), observability.NewTraceID()), observability.Fields{"component": "discord_bootstrap", "guild_id": guildID})
	if guildID == "" {
		observability.Warn(ctx, "discord_bootstrap_skipped", observability.Fields{"reason": "missing_guild_id"})
		return nil
	}

	channels, err := s.GuildChannels(guildID)
	if err != nil {
		observability.Error(ctx, "discord_guild_channels_failed", observability.Fields{"error_class": "guild_channels_failed", "error": err.Error()})
		return fmt.Errorf("list guild channels: %w", err)
	}

	categoryID := findChannelID(channels, bootstrapCategory, discordgo.ChannelTypeGuildCategory, "")
	if categoryID == "" {
		created, err := s.GuildChannelCreateComplex(guildID, discordgo.GuildChannelCreateData{
			Name: bootstrapCategory,
			Type: discordgo.ChannelTypeGuildCategory,
		})
		if err != nil {
			observability.Error(ctx, "discord_create_category_failed", observability.Fields{"error_class": "create_category_failed", "error": err.Error()})
			return fmt.Errorf("create category: %w", err)
		}
		categoryID = created.ID
		observability.Info(ctx, "discord_category_created", observability.Fields{"category_id": categoryID})
	}

	if findChannelID(channels, bootstrapChannel, discordgo.ChannelTypeGuildText, categoryID) == "" {
		_, err := s.GuildChannelCreateComplex(guildID, discordgo.GuildChannelCreateData{
			Name:     bootstrapChannel,
			Type:     discordgo.ChannelTypeGuildText,
			ParentID: categoryID,
			Topic:    "Start agent sessions with /chat",
		})
		if err != nil {
			observability.Error(ctx, "discord_create_chat_channel_failed", observability.Fields{"error_class": "create_chat_channel_failed", "error": err.Error()})
			return fmt.Errorf("create chat channel: %w", err)
		}
		observability.Info(ctx, "discord_chat_channel_created", observability.Fields{"category_id": categoryID, "channel_name": bootstrapChannel})
	}

	return nil
}

func findChannelID(channels []*discordgo.Channel, name string, channelType discordgo.ChannelType, parentID string) string {
	for _, channel := range channels {
		if channel.Type != channelType {
			continue
		}
		if strings.EqualFold(channel.Name, name) && (parentID == "" || channel.ParentID == parentID) {
			return channel.ID
		}
	}
	return ""
}
