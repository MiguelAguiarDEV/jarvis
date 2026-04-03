package observability

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"time"
)

type Logger struct {
	mu  sync.Mutex
	out *os.File
}

func NewLogger() *Logger {
	return &Logger{out: os.Stdout}
}

func (l *Logger) log(ctx context.Context, level, message string, fields Fields) {
	entry := map[string]any{
		"ts":    time.Now().UTC().Format(time.RFC3339Nano),
		"level": level,
		"msg":   message,
	}
	if traceID := TraceID(ctx); traceID != "" {
		entry["trace_id"] = traceID
	}
	if correlationID := CorrelationID(ctx); correlationID != "" {
		entry["correlation_id"] = correlationID
	}
	for key, value := range ContextFields(ctx) {
		entry[key] = value
	}
	for key, value := range fields {
		entry[key] = value
	}
	encoded, err := json.Marshal(entry)
	if err != nil {
		encoded = []byte(fmt.Sprintf(`{"ts":"%s","level":"error","msg":"log_marshal_failed","marshal_error":%q}`, time.Now().UTC().Format(time.RFC3339Nano), err.Error()))
	}
	l.mu.Lock()
	defer l.mu.Unlock()
	_, _ = l.out.Write(append(encoded, '\n'))
	if current != nil {
		current.diagnostics.WriteEvent(context.Background(), "log", Fields{"level": level, "message": message})
	}
}

func (l *Logger) Info(ctx context.Context, message string, fields Fields) {
	l.log(ctx, "info", message, fields)
}

func (l *Logger) Warn(ctx context.Context, message string, fields Fields) {
	l.log(ctx, "warn", message, fields)
}

func (l *Logger) Error(ctx context.Context, message string, fields Fields) {
	l.log(ctx, "error", message, fields)
}
