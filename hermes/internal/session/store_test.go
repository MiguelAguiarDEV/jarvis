package session

import (
	"path/filepath"
	"testing"
	"time"
)

func TestStoreSaveLoadRoundTrip(t *testing.T) {
	store := NewStore(filepath.Join(t.TempDir(), "sessions.json"))
	now := time.Now().UTC()
	input := map[string]*Session{
		"thread-1": {
			ID:                "session-1",
			OpenCodeSessionID: "session-1",
			TransportThreadID: "thread-1",
			UserID:            "user-1",
			Topic:             "debug nginx",
			TurnCount:         2,
			Status:            StatusActive,
			CreatedAt:         now,
			LastActive:        now,
		},
	}
	if err := store.Save(input); err != nil {
		t.Fatalf("save: %v", err)
	}
	loaded, err := store.Load()
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	if len(loaded) != 1 || loaded["thread-1"] == nil {
		t.Fatalf("unexpected loaded sessions: %#v", loaded)
	}
	if loaded["thread-1"].Topic != "debug nginx" {
		t.Fatalf("unexpected topic: %s", loaded["thread-1"].Topic)
	}
}
