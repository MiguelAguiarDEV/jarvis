package session

import "time"

const (
	StatusActive = "active"
	StatusEnded  = "ended"
	StatusFailed = "failed"
)

type Session struct {
	ID                string    `json:"id"`
	OpenCodeSessionID string    `json:"opencode_session_id"`
	TransportThreadID string    `json:"transport_thread_id"`
	UserID            string    `json:"user_id"`
	Topic             string    `json:"topic"`
	TurnCount         int       `json:"turn_count"`
	Status            string    `json:"status"`
	LastError         string    `json:"last_error,omitempty"`
	CreatedAt         time.Time `json:"created_at"`
	LastActive        time.Time `json:"last_active"`
}

func (s *Session) IsActive() bool {
	return s != nil && s.Status == StatusActive
}

func (s *Session) IsFailed() bool {
	return s != nil && s.Status == StatusFailed
}

func (s *Session) IsEnded() bool {
	return s != nil && s.Status == StatusEnded
}
