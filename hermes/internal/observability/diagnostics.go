package observability

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type Diagnostics struct {
	dir string
	mu  sync.Mutex
}

func NewDiagnostics(dir string) *Diagnostics {
	return &Diagnostics{dir: dir}
}

func (d *Diagnostics) Init() error {
	return os.MkdirAll(d.dir, 0o755)
}

func (d *Diagnostics) WriteEvent(ctx context.Context, kind string, fields Fields) {
	if d == nil || d.dir == "" {
		return
	}
	entry := map[string]any{
		"ts":   time.Now().UTC().Format(time.RFC3339Nano),
		"kind": kind,
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
	d.append("events.jsonl", entry)
}

func (d *Diagnostics) WriteSnapshot(name string, payload any) {
	if d == nil || d.dir == "" {
		return
	}
	var (
		encoded []byte
		err     error
	)
	switch value := payload.(type) {
	case string:
		encoded = []byte(value)
	case []byte:
		encoded = value
	default:
		encoded, err = json.MarshalIndent(payload, "", "  ")
		if err != nil {
			return
		}
	}
	d.mu.Lock()
	defer d.mu.Unlock()
	_ = os.WriteFile(filepath.Join(d.dir, name), encoded, 0o644)
}

func (d *Diagnostics) append(name string, payload any) {
	encoded, err := json.Marshal(payload)
	if err != nil {
		return
	}
	d.mu.Lock()
	defer d.mu.Unlock()
	path := filepath.Join(d.dir, name)
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return
	}
	defer f.Close()
	_, _ = fmt.Fprintln(f, string(encoded))
}
