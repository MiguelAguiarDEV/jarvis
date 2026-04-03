package discord

import "strings"

func SplitResponse(text string, maxLen int) []string {
	text = strings.TrimSpace(text)
	if text == "" {
		return nil
	}
	if len(text) <= maxLen {
		return []string{text}
	}

	var chunks []string
	remaining := text
	for len(remaining) > 0 {
		if len(remaining) <= maxLen {
			chunks = append(chunks, remaining)
			break
		}

		cut := chooseSplitPoint(remaining, maxLen)
		chunk := strings.TrimSpace(remaining[:cut])
		remaining = strings.TrimSpace(remaining[cut:])

		if strings.Count(chunk, "```")%2 != 0 {
			chunk += "\n```"
			remaining = "```\n" + remaining
		}
		chunks = append(chunks, chunk)
	}
	return chunks
}

func chooseSplitPoint(text string, maxLen int) int {
	window := text[:maxLen]
	for _, sep := range []string{"\n\n", "\n", " "} {
		if idx := strings.LastIndex(window, sep); idx > maxLen/2 {
			return idx + len(sep)
		}
	}
	return maxLen
}

func FormatContainers(raw string) string {
	lines := strings.Split(raw, "\n")
	var sb strings.Builder
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		switch {
		case strings.Contains(line, "healthy"):
			sb.WriteString("✅ " + line + "\n")
		case strings.Contains(line, "unhealthy"), strings.Contains(line, "restarting"):
			sb.WriteString("❌ " + line + "\n")
		default:
			sb.WriteString("🔵 " + line + "\n")
		}
	}
	return sb.String()
}
