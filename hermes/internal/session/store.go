package session

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"jarvis-discord-bot/internal/observability"
)

type Store struct {
	filePath string
	mu       sync.Mutex
}

func NewStore(filePath string) *Store {
	return &Store{filePath: filePath}
}

func (s *Store) Load() (map[string]*Session, error) {
	ctx := observability.WithFields(observability.WithTrace(context.Background(), observability.NewTraceID()), observability.Fields{"component": "session_store", "file_path": s.filePath})
	started := time.Now()
	var loadErr error
	defer func() {
		observability.ObserveOperation(ctx, "session_store_load", started, map[string]string{"component": "session_store"}, loadErr)
	}()
	s.mu.Lock()
	defer s.mu.Unlock()

	data, err := os.ReadFile(s.filePath)
	if err != nil {
		if os.IsNotExist(err) {
			observability.Info(ctx, "session_store_load_empty", observability.Fields{"reason": "file_not_found"})
			return map[string]*Session{}, nil
		}
		loadErr = fmt.Errorf("read session file: %w", err)
		return nil, loadErr
	}
	if len(data) == 0 {
		observability.Info(ctx, "session_store_load_empty", observability.Fields{"reason": "file_empty"})
		return map[string]*Session{}, nil
	}

	var list []*Session
	if err := json.Unmarshal(data, &list); err != nil {
		loadErr = fmt.Errorf("parse session file: %w", err)
		return nil, loadErr
	}
	out := make(map[string]*Session, len(list))
	for _, item := range list {
		if item != nil && item.TransportThreadID != "" {
			out[item.TransportThreadID] = item
		}
	}
	observability.Set("jarvis_session_store_records", "Persisted session records.", nil, float64(len(out)))
	observability.Info(ctx, "session_store_loaded", observability.Fields{"session_count": len(out), "bytes": len(data)})
	return out, nil
}

func (s *Store) Save(sessions map[string]*Session) error {
	ctx := observability.WithFields(observability.WithTrace(context.Background(), observability.NewTraceID()), observability.Fields{"component": "session_store", "file_path": s.filePath, "session_count": len(sessions)})
	started := time.Now()
	var saveErr error
	defer func() {
		observability.ObserveOperation(ctx, "session_store_save", started, map[string]string{"component": "session_store"}, saveErr)
	}()
	s.mu.Lock()
	defer s.mu.Unlock()

	list := make([]*Session, 0, len(sessions))
	for _, item := range sessions {
		if item != nil {
			list = append(list, item)
		}
	}

	data, err := json.MarshalIndent(list, "", "  ")
	if err != nil {
		saveErr = fmt.Errorf("marshal sessions: %w", err)
		return saveErr
	}

	if err := os.MkdirAll(filepath.Dir(s.filePath), 0755); err != nil {
		saveErr = fmt.Errorf("mkdir session dir: %w", err)
		return saveErr
	}

	tmpPath := s.filePath + ".tmp"
	if err := os.WriteFile(tmpPath, data, 0644); err != nil {
		saveErr = fmt.Errorf("write temp session file: %w", err)
		return saveErr
	}
	if err := os.Rename(tmpPath, s.filePath); err != nil {
		saveErr = fmt.Errorf("replace session file: %w", err)
		return saveErr
	}
	observability.Set("jarvis_session_store_records", "Persisted session records.", nil, float64(len(list)))
	observability.Info(ctx, "session_store_saved", observability.Fields{"bytes": len(data)})
	return nil
}
