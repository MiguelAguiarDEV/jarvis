package session

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"jarvis-discord-bot/internal/agent"
	"jarvis-discord-bot/internal/observability"
)

type AgentClient interface {
	CreateSession(ctx context.Context) (*agent.SessionResponse, error)
	SendMessage(ctx context.Context, sessionID, text string) error
	GetMessages(ctx context.Context, sessionID string) ([]agent.Message, error)
	PollForResponse(ctx context.Context, sessionID string, knownCount int, opts agent.PollOptions) (string, error)
	AbortSession(ctx context.Context, sessionID string) error
}

type SessionManager interface {
	Create(ctx context.Context, userID, transportThreadID, topic string) (*Session, error)
	Get(transportThreadID string) (*Session, bool)
	SendAndWait(ctx context.Context, transportThreadID, text string, opts agent.PollOptions) (string, error)
	End(ctx context.Context, transportThreadID string) (*Session, error)
	Recover(ctx context.Context, transportThreadID string) (*Session, error)
	ActiveSessions() []*Session
}

type Manager struct {
	mu       sync.RWMutex
	sessions map[string]*Session
	store    *Store
	agent    AgentClient
}

func NewManager(agentClient AgentClient, store *Store) (*Manager, error) {
	loaded, err := store.Load()
	if err != nil {
		return nil, err
	}
	observability.Info(observability.WithTrace(context.Background(), observability.NewTraceID()), "session_manager_initialized", observability.Fields{"loaded_sessions": len(loaded)})
	return &Manager{sessions: loaded, store: store, agent: agentClient}, nil
}

func (m *Manager) Create(ctx context.Context, userID, transportThreadID, topic string) (*Session, error) {
	ctx = observability.WithTrace(ctx, observability.TraceID(ctx))
	ctx = observability.WithFields(ctx, observability.Fields{"component": "session_manager", "user_id": userID, "transport_thread_id": transportThreadID, "topic": topic})
	started := time.Now()
	var opErr error
	defer func() {
		observability.ObserveOperation(ctx, "session_create", started, map[string]string{"component": "session_manager"}, opErr)
	}()
	created, err := m.agent.CreateSession(ctx)
	if err != nil {
		opErr = fmt.Errorf("create opencode session: %w", err)
		return nil, opErr
	}

	now := time.Now().UTC()
	sess := &Session{
		ID:                created.ID,
		OpenCodeSessionID: created.ID,
		TransportThreadID: transportThreadID,
		UserID:            userID,
		Topic:             topic,
		Status:            StatusActive,
		CreatedAt:         now,
		LastActive:        now,
	}

	m.mu.Lock()
	m.sessions[transportThreadID] = sess
	m.mu.Unlock()

	if err := m.persist(); err != nil {
		opErr = err
		return nil, err
	}
	observability.Info(ctx, "session_created", observability.Fields{"opencode_session_id": sess.OpenCodeSessionID})
	return sess, nil
}

func (m *Manager) Get(transportThreadID string) (*Session, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	sess, ok := m.sessions[transportThreadID]
	return sess, ok
}

func (m *Manager) SendAndWait(ctx context.Context, transportThreadID, text string, opts agent.PollOptions) (string, error) {
	ctx = observability.WithTrace(ctx, observability.TraceID(ctx))
	ctx = observability.WithFields(ctx, observability.Fields{"component": "session_manager", "transport_thread_id": transportThreadID})
	ctx = observability.WithFields(ctx, observability.MessageSummary(text))
	started := time.Now()
	var opErr error
	defer func() {
		observability.ObserveOperation(ctx, "session_send_and_wait", started, map[string]string{"component": "session_manager"}, opErr)
	}()
	sess, ok := m.Get(transportThreadID)
	if !ok {
		observability.Inc("jarvis_session_thread_mismatch_total", "Session thread mismatches or missing sessions.", map[string]string{"reason": "no_session"})
		opErr = fmt.Errorf("no session for thread %s", transportThreadID)
		observability.Warn(ctx, "session_thread_mismatch", observability.Fields{"reason": "no_session"})
		return "", opErr
	}
	if sess.IsFailed() {
		observability.Inc("jarvis_session_thread_mismatch_total", "Session thread mismatches or missing sessions.", map[string]string{"reason": "session_failed"})
		opErr = ErrSessionFailed
		observability.Warn(ctx, "session_send_failed_session", observability.Fields{"reason": "session_failed", "last_error": sess.LastError})
		return "", opErr
	}
	if !sess.IsActive() {
		observability.Inc("jarvis_session_thread_mismatch_total", "Session thread mismatches or missing sessions.", map[string]string{"reason": "no_active_session"})
		opErr = fmt.Errorf("no active session for thread %s", transportThreadID)
		observability.Warn(ctx, "session_thread_mismatch", observability.Fields{"reason": "no_active_session", "status": sess.Status})
		return "", opErr
	}
	ctx = observability.WithFields(ctx, observability.Fields{"opencode_session_id": sess.OpenCodeSessionID, "user_id": sess.UserID, "turn_count": sess.TurnCount})

	messages, err := m.agent.GetMessages(ctx, sess.OpenCodeSessionID)
	if err != nil {
		opErr = err
		return "", err
	}
	baseline := len(messages)
	observability.Info(ctx, "session_send_baseline_loaded", observability.Fields{"baseline_messages": baseline})

	if err := m.agent.SendMessage(ctx, sess.OpenCodeSessionID, text); err != nil {
		opErr = err
		return "", err
	}

	response, err := m.agent.PollForResponse(ctx, sess.OpenCodeSessionID, baseline, opts)
	if err != nil {
		// Mark session as failed on poll timeout so subsequent messages don't
		// keep hitting a dead session.
		if errors.Is(err, agent.ErrPollTimeout) {
			m.markFailed(sess, err.Error())
		}
		opErr = err
		return "", err
	}

	m.mu.Lock()
	sess.TurnCount++
	sess.LastActive = time.Now().UTC()
	m.mu.Unlock()

	if err := m.persist(); err != nil {
		observability.Warn(ctx, "session_persist_warning", observability.Fields{"error_class": "persist_warning", "error": err.Error()})
	}
	observability.Info(ctx, "session_response_ready", observability.Fields{"response_length": len(response)})
	return response, nil
}

// Recover creates a new OpenCode session for an existing thread, replacing
// a failed or timed-out session. Returns the new session.
func (m *Manager) Recover(ctx context.Context, transportThreadID string) (*Session, error) {
	ctx = observability.WithTrace(ctx, observability.TraceID(ctx))
	ctx = observability.WithFields(ctx, observability.Fields{"component": "session_manager", "transport_thread_id": transportThreadID})
	started := time.Now()
	var opErr error
	defer func() {
		observability.ObserveOperation(ctx, "session_recover", started, map[string]string{"component": "session_manager"}, opErr)
	}()

	old, ok := m.Get(transportThreadID)
	if !ok {
		opErr = fmt.Errorf("no session to recover for thread %s", transportThreadID)
		return nil, opErr
	}

	observability.Info(ctx, "session_recover_start", observability.Fields{
		"old_status":              old.Status,
		"old_opencode_session_id": old.OpenCodeSessionID,
		"old_turn_count":          old.TurnCount,
		"old_last_error":          old.LastError,
	})

	// Try to abort the old OpenCode session (best-effort)
	_ = m.agent.AbortSession(ctx, old.OpenCodeSessionID)

	// Create a new OpenCode session
	created, err := m.agent.CreateSession(ctx)
	if err != nil {
		opErr = fmt.Errorf("recover: create opencode session: %w", err)
		return nil, opErr
	}

	now := time.Now().UTC()
	m.mu.Lock()
	old.OpenCodeSessionID = created.ID
	old.Status = StatusActive
	old.LastError = ""
	old.LastActive = now
	// Keep TurnCount, UserID, Topic from old session for continuity
	m.mu.Unlock()

	if err := m.persist(); err != nil {
		opErr = err
		return nil, err
	}
	observability.Info(ctx, "session_recovered", observability.Fields{
		"new_opencode_session_id": created.ID,
		"turn_count":              old.TurnCount,
	})
	return old, nil
}

func (m *Manager) End(ctx context.Context, transportThreadID string) (*Session, error) {
	ctx = observability.WithTrace(ctx, observability.TraceID(ctx))
	ctx = observability.WithFields(ctx, observability.Fields{"component": "session_manager", "transport_thread_id": transportThreadID})
	started := time.Now()
	var opErr error
	defer func() {
		observability.ObserveOperation(ctx, "session_end", started, map[string]string{"component": "session_manager"}, opErr)
	}()
	sess, ok := m.Get(transportThreadID)
	if !ok {
		observability.Inc("jarvis_session_thread_mismatch_total", "Session thread mismatches or missing sessions.", map[string]string{"reason": "end_missing_session"})
		opErr = fmt.Errorf("no session for thread %s", transportThreadID)
		observability.Warn(ctx, "session_end_missing", observability.Fields{"reason": "end_missing_session"})
		return nil, opErr
	}
	if sess.IsEnded() {
		// Already ended — return it without error so /end is idempotent.
		observability.Info(ctx, "session_already_ended", observability.Fields{"turn_count": sess.TurnCount})
		return sess, nil
	}
	ctx = observability.WithFields(ctx, observability.Fields{"opencode_session_id": sess.OpenCodeSessionID, "user_id": sess.UserID})

	// Only abort if the session was active (not already failed/ended).
	if sess.IsActive() {
		if err := m.agent.AbortSession(ctx, sess.OpenCodeSessionID); err != nil && err != agent.ErrUnavailable {
			observability.Warn(ctx, "session_abort_warning", observability.Fields{"error_class": "abort_warning", "error": err.Error()})
		}
	}

	m.mu.Lock()
	sess.Status = StatusEnded
	sess.LastActive = time.Now().UTC()
	m.mu.Unlock()

	if err := m.persist(); err != nil {
		opErr = err
		return nil, err
	}
	observability.Info(ctx, "session_ended", observability.Fields{"turn_count": sess.TurnCount})
	return sess, nil
}

func (m *Manager) ActiveSessions() []*Session {
	m.mu.RLock()
	defer m.mu.RUnlock()
	out := make([]*Session, 0, len(m.sessions))
	for _, sess := range m.sessions {
		if sess.IsActive() {
			out = append(out, sess)
		}
	}
	return out
}

func (m *Manager) markFailed(sess *Session, reason string) {
	m.mu.Lock()
	sess.Status = StatusFailed
	sess.LastError = reason
	sess.LastActive = time.Now().UTC()
	m.mu.Unlock()
	observability.Warn(observability.WithTrace(context.Background(), observability.NewTraceID()), "session_marked_failed", observability.Fields{
		"component":           "session_manager",
		"transport_thread_id": sess.TransportThreadID,
		"opencode_session_id": sess.OpenCodeSessionID,
		"reason":              reason,
	})
	_ = m.persist()
}

func (m *Manager) persist() error {
	m.mu.RLock()
	copyMap := make(map[string]*Session, len(m.sessions))
	for key, value := range m.sessions {
		copyMap[key] = value
	}
	m.mu.RUnlock()
	return m.store.Save(copyMap)
}

// ErrSessionFailed is returned when a message is sent to a failed session.
var ErrSessionFailed = errors.New("session failed: use /end and /chat to start a new session, or send another message to auto-recover")
