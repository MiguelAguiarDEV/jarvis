package observability

import "testing"

func TestMessageSummaryDoesNotExposeRawText(t *testing.T) {
	fields := MessageSummary("hello world")
	if got := fields["message_length"]; got != 11 {
		t.Fatalf("expected length 11, got %v", got)
	}
	if _, ok := fields["message_hash_prefix"]; !ok {
		t.Fatalf("expected hash prefix")
	}
	if _, ok := fields["text"]; ok {
		t.Fatalf("raw text should not be present")
	}
}
