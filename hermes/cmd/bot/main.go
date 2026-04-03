package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"jarvis-discord-bot/internal/agent"
	"jarvis-discord-bot/internal/config"
	"jarvis-discord-bot/internal/discord"
	"jarvis-discord-bot/internal/observability"
	"jarvis-discord-bot/internal/session"
)

func main() {
	cfg := config.Load()
	bootCtx := observability.WithFields(observability.WithTrace(context.Background(), "startup"), observability.Fields{
		"component":         "main",
		"session_file_path": cfg.SessionFilePath,
		"metrics_addr":      cfg.MetricsAddr,
		"diagnostics_dir":   cfg.DiagnosticsDir,
		"opencode_enabled":  cfg.OpenCodeURL != "" && cfg.OpenCodePassword != "",
		"engram_enabled":    cfg.EngramURL != "" && cfg.EngramUser != "",
	})

	if err := observability.Setup(bootCtx, cfg.MetricsAddr, cfg.DiagnosticsDir, func() map[string]any {
		return map[string]any{
			"session_file_path": cfg.SessionFilePath,
			"diagnostics_dir":   cfg.DiagnosticsDir,
			"opencode_url":      cfg.OpenCodeURL,
			"engram_url":        cfg.EngramURL,
		}
	}); err != nil {
		log.Fatalf("Error starting observability: %v", err)
	}
	defer func() {
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = observability.Shutdown(shutdownCtx)
	}()
	observability.Info(bootCtx, "bot_starting", nil)

	// Engram authentication
	if cfg.EngramURL != "" && cfg.EngramUser != "" {
		if err := discord.EngramLogin(cfg); err != nil {
			observability.Warn(bootCtx, "engram_login_failed", observability.Fields{"error_class": "engram_login_failed", "error": err.Error()})
		} else {
			observability.Info(bootCtx, "engram_authenticated", nil)
			go func() {
				for {
					time.Sleep(50 * time.Minute)
					if err := discord.EngramLogin(cfg); err != nil {
						observability.Warn(bootCtx, "engram_jwt_refresh_failed", observability.Fields{"error_class": "engram_jwt_refresh_failed", "error": err.Error()})
					}
				}
			}()
		}
	}

	// Create OpenCode client
	var agentClient *agent.Client
	if cfg.OpenCodeURL != "" && cfg.OpenCodePassword != "" {
		agentClient = agent.NewClient(cfg.OpenCodeURL, cfg.OpenCodePassword)
		observability.Info(bootCtx, "opencode_client_configured", observability.Fields{"opencode_url": cfg.OpenCodeURL})
	} else {
		observability.Warn(bootCtx, "opencode_not_configured", nil)
		agentClient = agent.NewClient("", "")
	}

	// Create session manager
	store := session.NewStore(cfg.SessionFilePath)
	mgr, err := session.NewManager(agentClient, store)
	if err != nil {
		log.Fatalf("Error creating session manager: %v", err)
	}

	// Create and start Discord adapter
	adapter, err := discord.NewTransportAdapter(cfg, mgr)
	if err != nil {
		log.Fatalf("Error creating Discord adapter: %v", err)
	}

	if err := adapter.Start(); err != nil {
		log.Fatalf("Error starting Discord adapter: %v", err)
	}
	defer adapter.Stop()

	observability.Info(bootCtx, "bot_running", nil)
	sc := make(chan os.Signal, 1)
	signal.Notify(sc, syscall.SIGINT, syscall.SIGTERM)
	<-sc

	observability.Info(bootCtx, "bot_shutting_down", nil)
}
