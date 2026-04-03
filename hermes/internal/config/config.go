package config

import (
	"log"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	DiscordToken     string
	GuildID          string
	AllowedUserIDs   []string
	OpenCodeURL      string
	OpenCodePassword string
	EngramURL        string
	EngramUser       string
	EngramPass       string
	EngramAPIKey     string
	SessionFilePath  string
	MetricsAddr      string
	DiagnosticsDir   string
	PollTimeout      time.Duration
	PollTimeoutTools time.Duration
}

func Load() *Config {
	token := os.Getenv("DISCORD_TOKEN")
	if token == "" {
		log.Fatal("DISCORD_TOKEN not set")
	}

	allowedRaw := firstNonEmpty(os.Getenv("ALLOWED_USER_IDS"), os.Getenv("DISCORD_USER_ID"))
	sessionPath := firstNonEmpty(os.Getenv("SESSION_FILE_PATH"), "/data/sessions.json")

	return &Config{
		DiscordToken:     token,
		GuildID:          os.Getenv("DISCORD_GUILD_ID"),
		AllowedUserIDs:   splitCSV(allowedRaw),
		OpenCodeURL:      strings.TrimRight(os.Getenv("OPENCODE_SERVER_URL"), "/"),
		OpenCodePassword: os.Getenv("OPENCODE_SERVER_PASSWORD"),
		EngramURL:        strings.TrimRight(os.Getenv("ENGRAM_URL"), "/"),
		EngramUser:       os.Getenv("ENGRAM_USER"),
		EngramPass:       firstNonEmpty(os.Getenv("ENGRAM_PASS"), os.Getenv("ENGRAM_PASSWORD")),
		EngramAPIKey:     os.Getenv("ENGRAM_API_KEY"),
		SessionFilePath:  sessionPath,
		MetricsAddr:      firstNonEmpty(os.Getenv("METRICS_ADDR"), "127.0.0.1:9090"),
		DiagnosticsDir:   firstNonEmpty(os.Getenv("DIAGNOSTICS_DIR"), "/data/diagnostics"),
		PollTimeout:      parseDurationSec(os.Getenv("POLL_TIMEOUT_SEC"), 120),
		PollTimeoutTools: parseDurationSec(os.Getenv("POLL_TIMEOUT_TOOLS_SEC"), 600),
	}
}

func (c *Config) IsUserAllowed(userID string) bool {
	if len(c.AllowedUserIDs) == 0 {
		return true
	}
	for _, id := range c.AllowedUserIDs {
		if id == userID {
			return true
		}
	}
	return false
}

func splitCSV(raw string) []string {
	if raw == "" {
		return nil
	}
	parts := strings.Split(raw, ",")
	out := make([]string, 0, len(parts))
	for _, part := range parts {
		trimmed := strings.TrimSpace(part)
		if trimmed != "" {
			out = append(out, trimmed)
		}
	}
	return out
}

func parseDurationSec(raw string, defaultSec int) time.Duration {
	if raw == "" {
		return time.Duration(defaultSec) * time.Second
	}
	n, err := strconv.Atoi(raw)
	if err != nil || n <= 0 {
		return time.Duration(defaultSec) * time.Second
	}
	return time.Duration(n) * time.Second
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}
