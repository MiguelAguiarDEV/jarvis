# Design: Gateway Pattern for Multi-Channel JARVIS

> Date: 2026-04-03
> Status: proposal
> Scope: ATHENA internal refactor + new channel implementations
> Estimated effort: 2-3 sessions

## 1. Problem

JARVIS has two hardcoded channels:

1. **Web chat (NEXUS)**: HTTP POST to `/api/chat`, SSE response stream. Lives in `athena/internal/cloud/cloudserver/chat.go`.
2. **Discord (HERMES)**: Separate Go binary (`hermes/`), uses `discordgo`, calls ATHENA's `/api/chat` endpoint as an HTTP client via `MnemoChatClient`.

Adding WhatsApp, Voice, Telegram, or CLI requires either:
- (A) Building another standalone bot (like Hermes) for each channel -- duplicates session management, auth, formatting.
- (B) Adding more hardcoded handlers inside ATHENA -- violates separation, gets messy fast.

**Neither scales.** We need a **Channel abstraction** with a **Gateway router** inside ATHENA that normalizes messages from any source and routes them to the orchestrator.

## 2. Channel Interface (Go)

```go
package gateway

import "context"

// Channel represents a message transport (Discord, WhatsApp, Web, etc.).
type Channel interface {
    // Name returns the channel identifier (e.g. "discord", "whatsapp", "web").
    Name() string

    // Receive returns a channel of incoming messages. Blocks until ctx is cancelled.
    Receive(ctx context.Context) (<-chan IncomingMessage, error)

    // Send delivers a message to the channel.
    Send(ctx context.Context, msg OutgoingMessage) error

    // Start initializes the channel (connect to API, open webhooks, etc.).
    Start(ctx context.Context) error

    // Stop gracefully shuts down the channel.
    Stop() error
}

// IncomingMessage is a normalized message from any channel.
type IncomingMessage struct {
    ChannelName string            // "discord", "whatsapp", "web", "voice"
    SenderID    string            // channel-specific user identifier
    Text        string            // plain text content
    Attachments []Attachment      // images, files, voice notes
    ReplyTo     string            // thread/reply context (channel-specific)
    Metadata    map[string]string // channel-specific extras (guild_id, phone, etc.)
}

// OutgoingMessage is a normalized response to send to any channel.
type OutgoingMessage struct {
    ChannelName string        // target channel
    RecipientID string        // channel-specific recipient
    Text        string        // response content (markdown)
    Format      MessageFormat // how to render the text
    ReplyTo     string        // thread/reply context
}

// MessageFormat controls how text is rendered per channel.
type MessageFormat int

const (
    FormatMarkdown MessageFormat = iota // full markdown (web)
    FormatPlain                         // plain text (voice, SMS)
    FormatHTML                          // HTML (Telegram)
)

// Attachment represents a file or media attachment.
type Attachment struct {
    Type     string // "image", "audio", "file"
    URL      string // download URL or local path
    MimeType string
    Name     string
}
```

### Why this interface

- **`Receive` returns a Go channel**: Each channel implementation runs its own event loop (webhook server, WebSocket listener, polling). The Gateway reads from all channels uniformly via `select`.
- **`Send` is synchronous**: The orchestrator calls Send after processing. Channel handles formatting internally.
- **`Start`/`Stop`**: Lifecycle management. Some channels need webhook registration (WhatsApp), WebSocket connections (Discord), or HTTP servers (web).

## 3. Gateway Architecture

```
Channels                    Gateway (in ATHENA)              Orchestrator
                            ┌─────────────────────┐
├── WebChat (SSE)           │  Message Router      │         ├── Chat()
├── Discord (embed) ──────► │  Session Resolver    │ ──────► ├── Tools
├── WhatsApp (future)       │  Format Converter    │         ├── Skills
├── Telegram (future)       │  Auth Middleware      │         └── Memory
├── Voice (future)          └─────────────────────┘
└── CLI (future)
```

### Gateway Components

| Component | Responsibility |
|-----------|---------------|
| **Message Router** | Reads from all channel `Receive()` channels via `select`. Dispatches to orchestrator. Routes responses back to source channel via `Send()`. |
| **Session Resolver** | Maps `(channelName, senderID)` to a JARVIS conversation. Creates conversations on first contact. Maintains mapping in PostgreSQL. |
| **Format Converter** | Converts orchestrator markdown output to channel-appropriate format before calling `Send()`. |
| **Auth Middleware** | Per-channel auth. Web: API key/JWT. Discord: `ALLOWED_USER_IDS`. WhatsApp: webhook verification token. Voice: caller ID allowlist. |

### Gateway Core (pseudo-code)

```go
type Gateway struct {
    channels    map[string]Channel
    orchestrator *jarvis.Orchestrator
    sessions    *SessionResolver
    formatter   *FormatConverter
}

func (g *Gateway) Run(ctx context.Context) error {
    // Start all channels
    for _, ch := range g.channels {
        ch.Start(ctx)
    }

    // Multiplex all incoming messages
    merged := g.mergeReceiveChannels(ctx)

    for msg := range merged {
        go g.handleMessage(ctx, msg)
    }
    return nil
}

func (g *Gateway) handleMessage(ctx context.Context, msg IncomingMessage) {
    // 1. Resolve session (channel+sender -> conversation_id)
    convID := g.sessions.Resolve(msg.ChannelName, msg.SenderID)

    // 2. Call orchestrator
    var response strings.Builder
    g.orchestrator.Chat(msg.SenderID, convID, msg.Text, func(token string) {
        response.WriteString(token)
    })

    // 3. Format for target channel
    formatted := g.formatter.Convert(response.String(), msg.ChannelName)

    // 4. Send response
    g.channels[msg.ChannelName].Send(ctx, OutgoingMessage{
        ChannelName: msg.ChannelName,
        RecipientID: msg.SenderID,
        Text:        formatted,
        ReplyTo:     msg.ReplyTo,
    })
}
```

## 4. Format Conversion

Each channel supports different markup:

| Channel | Bold | Italic | Code | Code Block | Tables | Headers | Links | Quotes |
|---------|------|--------|------|------------|--------|---------|-------|--------|
| Web (NEXUS) | `**x**` | `*x*` | `` `x` `` | ` ```x``` ` | yes | yes | yes | yes |
| Discord | `**x**` | `*x*` | `` `x` `` | ` ```x``` ` | no | no (in DMs) | yes | `> x` |
| WhatsApp | `*x*` | `_x_` | `` `x` `` | ` ```x``` ` | no | no | no | `> x` |
| Telegram | `**x**` or `<b>` | `*x*` or `<i>` | `` `x` `` | ` ```x``` ` | no | no | `[t](u)` | no |
| Voice | plain text | plain text | read aloud | skip or summarize | skip | read aloud | read URL | read aloud |
| CLI | ANSI colors | ANSI | ANSI | ANSI | yes | yes | underline | indent |

### Converter Strategy

```go
type FormatConverter struct {
    converters map[string]func(markdown string) string
}
```

Each channel registers a converter function. Default is pass-through (markdown). The converter:
1. Parses markdown AST (use `goldmark` or simple regex for common patterns).
2. Transforms unsupported elements (e.g., tables to bullet lists for Discord/WhatsApp).
3. Truncates if channel has message length limits (Discord: 2000 chars, WhatsApp: 4096 chars).

**Voice special case**: Strip all formatting, simplify for TTS. Long responses get summarized (ask LLM to condense if > 500 chars).

## 5. Where Gateway Lives

| Option | Pros | Cons |
|--------|------|------|
| **Inside ATHENA** (recommended) | No extra service, direct access to orchestrator, simpler deployment | ATHENA grows slightly larger |
| Separate service | Isolation, independent scaling | Extra container, HTTP overhead, needs orchestrator API changes |
| Sidecar per channel | Maximum isolation | Operational nightmare for homelab |

**Decision: Inside ATHENA.**

- JARVIS is a homelab project, not a microservices platform.
- The Gateway is ~500 lines of Go. Not worth a separate service.
- Direct access to the orchestrator avoids HTTP round-trips and SSE complexity.
- New package: `athena/internal/gateway/`

### Package Structure

```
athena/internal/gateway/
    gateway.go          // Gateway struct, Run(), message routing
    channel.go          // Channel interface, message types
    session_resolver.go // (channelName, senderID) -> conversation_id mapping
    format.go           // FormatConverter + per-channel converters
    web_channel.go      // WebChat channel (wraps existing SSE handler)
    discord_channel.go  // Discord channel (embeds discordgo, replaces Hermes)
    whatsapp_channel.go // WhatsApp channel (Meta Cloud API)
    telegram_channel.go // Telegram channel (Bot API)
    voice_channel.go    // Voice channel (Vapi or Telnyx)
```

## 6. Migration Path

### Phase 1: Interface + Gateway Router (session 1)
1. Create `athena/internal/gateway/` package with `Channel` interface and `Gateway` struct.
2. Implement `WebChannel` wrapping the existing SSE chat handler. The current `handleChatSSE` in `cloudserver/chat.go` becomes a thin HTTP adapter that creates an `IncomingMessage` and feeds it to the Gateway.
3. All existing tests pass. Web chat works exactly as before.

### Phase 2: Discord Channel (session 1-2)
1. Implement `DiscordChannel` inside ATHENA using `discordgo`. Port the relevant logic from Hermes (`internal/discord/adapter.go`, `dm.go`, `messages.go`, `format.go`).
2. Discord bot runs inside ATHENA's process -- no separate container.
3. Keep Hermes container running in parallel during transition.
4. Once validated, remove Hermes from `docker-compose.yml`.

### Phase 3: WhatsApp Channel (session 2)
1. Implement `WhatsAppChannel` using Meta Cloud API.
2. Webhook receiver endpoint in ATHENA for incoming messages.
3. REST client for outgoing messages.
4. Format converter: markdown to WhatsApp markup.

### Phase 4: Voice Channel (session 3)
1. Implement `VoiceChannel` using chosen provider.
2. STT pipeline for incoming audio.
3. TTS pipeline for outgoing text.
4. Format converter: strip markdown, simplify for speech.

### Phase 5: Cleanup
1. Remove Hermes as standalone service.
2. Update `docker-compose.yml`.
3. Update ARCHITECTURE.md.

## 7. Session Resolution

The Gateway needs to map `(channelName, senderID)` to a JARVIS conversation ID.

### Schema Addition

```sql
CREATE TABLE channel_sessions (
    id            BIGSERIAL PRIMARY KEY,
    channel_name  TEXT NOT NULL,          -- "discord", "whatsapp", "web"
    sender_id     TEXT NOT NULL,          -- channel-specific user ID
    conversation_id BIGINT NOT NULL REFERENCES conversations(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(channel_name, sender_id)
);

CREATE INDEX idx_channel_sessions_lookup ON channel_sessions(channel_name, sender_id);
```

### Resolution Logic

1. Look up `(channel_name, sender_id)` in `channel_sessions`.
2. If found and `last_active` < 24h: reuse `conversation_id`.
3. If found but stale (> 24h): create new conversation, update mapping.
4. If not found: create conversation + mapping.

The 24h window is configurable per channel. Discord users might want longer sessions; WhatsApp users might expect fresh context.

## 8. WhatsApp Specifics

### Requirements
- **Meta Business Account** (free to create)
- **WhatsApp Business API access** via Meta Cloud API
- **Phone number** (dedicated, not personal)
- **Webhook URL** (ATHENA must be reachable from Meta servers -- via Cloudflare Tunnel)

### Architecture

```
Meta Cloud API
     │
     ├── Webhook POST /api/whatsapp/webhook ──► WhatsAppChannel.Receive()
     │                                              │
     │                                         Gateway.handleMessage()
     │                                              │
     └── REST API (send message) ◄────────── WhatsAppChannel.Send()
```

### Key Considerations
- **Webhook verification**: Meta sends a GET with `hub.verify_token` on setup. Must respond with `hub.challenge`.
- **Message types**: text, image, audio (voice notes), document, location, contacts.
- **Voice notes**: Receive as audio attachment, run through Whisper STT, treat as text.
- **Rate limits**: 1000 messages/day on free tier (test phone). Paid: 100K+/day.
- **Cost**: Free for development. Production: ~$0.005-0.08 per message depending on region.
- **24-hour window**: WhatsApp requires user to message first. Business-initiated messages after 24h require approved templates.

### WhatsApp Format Converter
```
Markdown                    WhatsApp
**bold**          →         *bold*
*italic*          →         _italic_
`code`            →         `code`
```code```        →         ```code```
> quote           →         > quote
[link](url)       →         url (plain, no markdown links)
| tables |        →         bullet list fallback
# Header          →         *Header* (bold as substitute)
```

## 9. Voice Specifics

### Option A: Vapi (recommended for MVP)
- **What**: Hosted voice AI platform. Handles STT + TTS + phone number.
- **Pros**: Fast to integrate, no infra to manage, good quality.
- **Cons**: Vendor lock-in, cost per minute (~$0.05/min), data leaves homelab.
- **Integration**: Vapi calls a webhook with transcribed text, expects text response. Perfect fit for Gateway pattern.

### Option B: Telnyx (more control)
- **What**: Telecom API. Real phone number, SIP, WebRTC.
- **Pros**: Real phone number, more control, can self-host STT/TTS.
- **Cons**: More complex setup, need to handle audio streams.
- **Integration**: SIP/WebRTC for audio, self-hosted Whisper for STT, ElevenLabs or Piper for TTS.

### Option C: Self-hosted (maximum control, most effort)
- **STT**: `whisper.cpp` running on homelab (GPU recommended).
- **TTS**: `piper` (local, fast, decent quality) or ElevenLabs API (best quality, paid).
- **Phone**: Telnyx or Twilio for the actual phone number + SIP trunk.

### Recommendation
Start with **Vapi** for MVP (session 3). Evaluate self-hosted later if cost or privacy becomes a concern.

### Voice Format Converter
```
Markdown                    Voice (TTS input)
**bold**          →         (strip, read normally)
*italic*          →         (strip, read normally)
`code`            →         "code: [content]"
```code block```  →         "Here's the code: [first 3 lines]. The full code has N lines."
> quote           →         (read normally)
[link](url)       →         "link to [text]"
| tables |        →         "The table shows: [row 1], [row 2]..."
# Header          →         (read as section intro)
Long response     →         Summarize via LLM if > 500 chars for TTS
```

## 10. Auth Per Channel

| Channel | Auth Mechanism | Implementation |
|---------|---------------|----------------|
| Web (NEXUS) | JWT + API key (existing) | No change |
| Discord | `ALLOWED_USER_IDS` env var | Port from Hermes |
| WhatsApp | Webhook verify token + phone allowlist | New: `WHATSAPP_ALLOWED_PHONES` |
| Telegram | Chat ID allowlist | New: `TELEGRAM_ALLOWED_CHAT_IDS` |
| Voice | Caller ID allowlist | New: `VOICE_ALLOWED_CALLERS` |
| CLI | Local only (stdin/stdout) | No auth needed |

All allowlists are environment variables, injected via 1Password `op run`.

## 11. Configuration

```yaml
# In .env.tpl (1Password references)
GATEWAY_CHANNELS=web,discord              # comma-separated enabled channels

# Discord (existing)
DISCORD_TOKEN=op://Desarrollo/jarvis-discord/token
DISCORD_ALLOWED_USER_IDS=op://Desarrollo/jarvis-discord/allowed_users

# WhatsApp (future)
WHATSAPP_VERIFY_TOKEN=op://Desarrollo/jarvis-whatsapp/verify_token
WHATSAPP_ACCESS_TOKEN=op://Desarrollo/jarvis-whatsapp/access_token
WHATSAPP_PHONE_NUMBER_ID=op://Desarrollo/jarvis-whatsapp/phone_number_id
WHATSAPP_ALLOWED_PHONES=op://Desarrollo/jarvis-whatsapp/allowed_phones

# Voice (future)
VAPI_API_KEY=op://Desarrollo/jarvis-voice/vapi_api_key
VOICE_ALLOWED_CALLERS=op://Desarrollo/jarvis-voice/allowed_callers
```

Channels are opt-in. If env vars for a channel are missing, that channel is not started. No crash, just a warning log.

## 12. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Discord migration breaks existing bot | Users lose access | Run Hermes in parallel during transition. Feature-flag new Discord channel. |
| WhatsApp 24h window limits proactive messages | Can't notify user after 24h | Use approved message templates for notifications. |
| Voice quality is poor | Bad UX | Start with Vapi (proven quality). Add fallback to text summary. |
| Gateway adds latency | Slower responses | Gateway is in-process (no network hop). Overhead is negligible. |
| Single process = single point of failure | All channels down if ATHENA crashes | Already the case. ATHENA has health checks + `unless-stopped` restart policy. |
| Cloudflare Tunnel needed for webhooks | WhatsApp/Voice won't work without it | Already have Cloudflare Tunnel for NEXUS. Add routes for webhook endpoints. |

## 13. Open Questions

1. **Should Discord stay as a separate service (Hermes) or be absorbed into ATHENA?** Recommendation: absorb. Hermes is thin (~500 lines of real logic). Removes a container and simplifies deployment.
2. **Streaming for non-web channels?** Discord and WhatsApp don't support SSE. Options: (a) buffer full response then send, (b) send typing indicator while processing, then send complete message. Recommend (b).
3. **Multi-message responses?** If response exceeds channel limit (Discord: 2000 chars), split into multiple messages. Need a splitter that respects code blocks and sentence boundaries.

## 14. Success Criteria

- [ ] `Channel` interface defined and tested
- [ ] `Gateway` routes messages from web channel to orchestrator (existing behavior preserved)
- [ ] Discord channel works through Gateway (Hermes removed from docker-compose)
- [ ] WhatsApp channel receives and responds to messages
- [ ] Voice channel handles a phone call end-to-end
- [ ] Format conversion works correctly for each channel
- [ ] Session resolution creates/reuses conversations correctly
- [ ] All channels respect auth allowlists
- [ ] No secrets in code or logs
