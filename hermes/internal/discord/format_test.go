package discord

import (
	"strings"
	"testing"
)

func TestSplitResponseKeepsChunksWithinLimit(t *testing.T) {
	text := strings.Repeat("alpha beta gamma\n\n", 120)
	chunks := SplitResponse(text, 180)
	if len(chunks) < 2 {
		t.Fatalf("expected multiple chunks, got %d", len(chunks))
	}
	for _, chunk := range chunks {
		if len(chunk) > 180 {
			t.Fatalf("chunk too large: %d", len(chunk))
		}
	}
}

func TestSplitResponseReopensCodeFence(t *testing.T) {
	text := "```go\n" + strings.Repeat("fmt.Println(\"x\")\n", 30) + "```"
	chunks := SplitResponse(text, 90)
	if len(chunks) < 2 {
		t.Fatalf("expected multiple chunks, got %d", len(chunks))
	}
	for i, chunk := range chunks {
		if strings.Count(chunk, "```")%2 != 0 {
			t.Fatalf("chunk %d leaves code fence unbalanced", i)
		}
	}
}
