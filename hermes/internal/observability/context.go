package observability

import (
	"context"
	"crypto/rand"
	"encoding/hex"
)

type contextKey string

const (
	traceIDKey       contextKey = "trace_id"
	correlationIDKey contextKey = "correlation_id"
	fieldsKey        contextKey = "fields"
)

type Fields map[string]any

func NewTraceID() string {
	buf := make([]byte, 8)
	if _, err := rand.Read(buf); err != nil {
		return "trace-unavailable"
	}
	return hex.EncodeToString(buf)
}

func WithTrace(ctx context.Context, traceID string) context.Context {
	if traceID == "" {
		traceID = NewTraceID()
	}
	ctx = context.WithValue(ctx, traceIDKey, traceID)
	if CorrelationID(ctx) == "" {
		ctx = context.WithValue(ctx, correlationIDKey, traceID)
	}
	return ctx
}

func WithCorrelation(ctx context.Context, correlationID string) context.Context {
	if correlationID == "" {
		return ctx
	}
	return context.WithValue(ctx, correlationIDKey, correlationID)
}

func WithFields(ctx context.Context, fields Fields) context.Context {
	if len(fields) == 0 {
		return ctx
	}
	merged := Fields{}
	if existing, ok := ctx.Value(fieldsKey).(Fields); ok {
		for key, value := range existing {
			merged[key] = value
		}
	}
	for key, value := range fields {
		merged[key] = value
	}
	return context.WithValue(ctx, fieldsKey, merged)
}

func TraceID(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	if value, ok := ctx.Value(traceIDKey).(string); ok {
		return value
	}
	return ""
}

func CorrelationID(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	if value, ok := ctx.Value(correlationIDKey).(string); ok {
		return value
	}
	return ""
}

func ContextFields(ctx context.Context) Fields {
	if ctx == nil {
		return Fields{}
	}
	if value, ok := ctx.Value(fieldsKey).(Fields); ok {
		copy := Fields{}
		for key, item := range value {
			copy[key] = item
		}
		return copy
	}
	return Fields{}
}
