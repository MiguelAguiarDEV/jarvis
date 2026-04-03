package observability

import (
	"context"
	"strings"
	"time"
)

type Runtime struct {
	logger      *Logger
	metrics     *Metrics
	diagnostics *Diagnostics
	server      *Server
}

var current = &Runtime{}

func Setup(ctx context.Context, addr, diagnosticsDir string, healthProvider HealthProvider) error {
	logger := NewLogger()
	metrics := NewMetrics()
	diagnostics := NewDiagnostics(diagnosticsDir)
	if err := diagnostics.Init(); err != nil {
		return err
	}
	server := NewServer(addr, metrics, diagnostics, logger, healthProvider)
	current = &Runtime{logger: logger, metrics: metrics, diagnostics: diagnostics, server: server}
	metrics.Set("jarvis_process_up", "Whether the bot process is running.", nil, 1)
	diagnostics.WriteSnapshot("runtime.json", map[string]any{"metrics_addr": addr, "diagnostics_dir": diagnosticsDir})
	return server.Start(ctx)
}

func Shutdown(ctx context.Context) error {
	if current == nil {
		return nil
	}
	if current.metrics != nil {
		current.metrics.Set("jarvis_process_up", "Whether the bot process is running.", nil, 0)
	}
	if current.server != nil {
		return current.server.Shutdown(ctx)
	}
	return nil
}

func L() *Logger {
	if current.logger == nil {
		current.logger = NewLogger()
	}
	return current.logger
}

func M() *Metrics {
	if current.metrics == nil {
		current.metrics = NewMetrics()
	}
	return current.metrics
}

func D() *Diagnostics {
	if current.diagnostics == nil {
		current.diagnostics = NewDiagnostics("")
	}
	return current.diagnostics
}

func Info(ctx context.Context, message string, fields Fields) {
	L().Info(ctx, message, fields)
}

func Warn(ctx context.Context, message string, fields Fields) {
	L().Warn(ctx, message, fields)
}

func Error(ctx context.Context, message string, fields Fields) {
	L().Error(ctx, message, fields)
}

func Inc(name, help string, labels map[string]string) {
	M().Inc(name, help, labels)
}

func Set(name, help string, labels map[string]string, value float64) {
	M().Set(name, help, labels, value)
}

func ObserveOperation(ctx context.Context, name string, started time.Time, labels map[string]string, err error) {
	status := "ok"
	if err != nil {
		status = "error"
	}
	metricLabels := map[string]string{"operation": name, "status": status}
	for key, value := range labels {
		metricLabels[key] = value
	}
	M().Inc("jarvis_operations_total", "Operation totals by status.", metricLabels)
	M().Add("jarvis_operation_duration_ms_total", "Accumulated operation duration in milliseconds.", metricLabels, float64(time.Since(started).Milliseconds()))
	fields := Fields{"operation": name, "status": status, "duration_ms": time.Since(started).Milliseconds()}
	for key, value := range metricLabels {
		fields[key] = value
	}
	if err != nil {
		fields["error_class"] = classifyError(err)
		fields["error"] = err.Error()
		Error(ctx, "operation_failed", fields)
		D().WriteEvent(ctx, "operation_failed", fields)
		D().WriteSnapshot("last-error.json", fields)
		return
	}
	Info(ctx, "operation_completed", fields)
	D().WriteEvent(ctx, "operation_completed", fields)
}

func classifyError(err error) string {
	if err == nil {
		return ""
	}
	return strings.ReplaceAll(strings.ToLower(strings.TrimSpace(err.Error())), " ", "_")
}
