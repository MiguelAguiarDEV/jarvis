package observability

import (
	"context"
	"encoding/json"
	"net/http"
	"time"
)

type HealthProvider func() map[string]any

type Server struct {
	addr           string
	metrics        *Metrics
	diagnostics    *Diagnostics
	logger         *Logger
	healthProvider HealthProvider
	httpServer     *http.Server
	startedAt      time.Time
}

func NewServer(addr string, metrics *Metrics, diagnostics *Diagnostics, logger *Logger, healthProvider HealthProvider) *Server {
	mux := http.NewServeMux()
	server := &Server{
		addr:           addr,
		metrics:        metrics,
		diagnostics:    diagnostics,
		logger:         logger,
		healthProvider: healthProvider,
		startedAt:      time.Now().UTC(),
	}
	mux.HandleFunc("/healthz", server.handleHealth)
	mux.HandleFunc("/metrics", server.handleMetrics)
	server.httpServer = &http.Server{Addr: addr, Handler: mux}
	return server
}

func (s *Server) Start(ctx context.Context) error {
	if s == nil || s.addr == "" {
		return nil
	}
	go func() {
		s.logger.Info(ctx, "observability_server_start", Fields{"listen_addr": s.addr})
		if err := s.httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			s.logger.Error(ctx, "observability_server_failed", Fields{"error_class": classifyError(err), "error": err.Error()})
			s.metrics.Inc("jarvis_observability_http_failures_total", "Observability HTTP server failures.", map[string]string{"component": "server"})
		}
	}()
	return nil
}

func (s *Server) Shutdown(ctx context.Context) error {
	if s == nil || s.httpServer == nil {
		return nil
	}
	return s.httpServer.Shutdown(ctx)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	ctx := WithTrace(r.Context(), r.Header.Get("X-Trace-Id"))
	payload := map[string]any{
		"status":     "ok",
		"uptime_sec": time.Since(s.startedAt).Seconds(),
	}
	if s.healthProvider != nil {
		for key, value := range s.healthProvider() {
			payload[key] = value
		}
	}
	s.metrics.Inc("jarvis_healthz_requests_total", "Health endpoint requests.", nil)
	s.diagnostics.WriteSnapshot("healthz.json", payload)
	encoded, _ := json.Marshal(payload)
	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write(encoded)
	s.logger.Info(ctx, "healthz_served", Fields{"remote_addr": r.RemoteAddr})
}

func (s *Server) handleMetrics(w http.ResponseWriter, r *http.Request) {
	ctx := WithTrace(r.Context(), r.Header.Get("X-Trace-Id"))
	s.metrics.Inc("jarvis_metrics_requests_total", "Metrics endpoint requests.", nil)
	s.diagnostics.WriteSnapshot("metrics.prom", s.metrics.Render())
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	_, _ = w.Write([]byte(s.metrics.Render()))
	s.logger.Info(ctx, "metrics_served", Fields{"remote_addr": r.RemoteAddr})
}
