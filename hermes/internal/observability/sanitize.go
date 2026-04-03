package observability

import (
	"crypto/sha256"
	"encoding/hex"
	"strings"
)

func MessageSummary(text string) Fields {
	hash := sha256.Sum256([]byte(text))
	prefix := hex.EncodeToString(hash[:])
	if len(prefix) > 12 {
		prefix = prefix[:12]
	}
	return Fields{
		"message_length":      len(text),
		"message_hash_prefix": prefix,
		"message_empty":       strings.TrimSpace(text) == "",
	}
}
