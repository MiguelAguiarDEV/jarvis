# JARVIS

Personal AI voice assistant with multi-LLM support and tool execution.

## Architecture

```
Mic → Wake Word → VAD → STT (GPU) → LLM Router → Tool Router → TTS (CPU) → Speaker
       (CPU)     (CPU)  (on-demand)  (Claude/GPT/  (system_info)  (Kokoro)
                                      Qwen)
```

### Pipeline States
```
IDLE → [wake word] → LISTENING → [speech end] → TRANSCRIBING → THINKING → SPEAKING → IDLE
```

### LLM Providers (fallback chain)
| Priority | Provider | Auth | Device |
|----------|----------|------|--------|
| 1 | Claude | setup-token | Cloud |
| 2 | ChatGPT | OAuth PKCE | Cloud |
| 3 | Qwen 3.5-9B | None (local) | CPU via Ollama |

### VRAM Budget (RTX 4060, 8GB)
| Component | VRAM | Notes |
|-----------|------|-------|
| STT (faster-whisper) | ~4GB | On-demand: loaded only during transcription, then unloaded |
| TTS (Kokoro-82M) | 0GB | CPU only, ~300MB RAM |
| VAD (Silero) | 0GB | CPU only, ~2MB |
| Wake Word (openWakeWord) | 0GB | CPU only |
| Qwen fallback | 0GB | CPU via Ollama, uses RAM |

## Requirements

- **OS:** Windows 10/11 (native execution)
- **Python:** 3.12+
- **GPU:** NVIDIA GPU with CUDA 12.x (for STT)
- **RAM:** 16GB+ recommended (32GB for Qwen fallback)
- **Microphone:** Any USB/integrated mic
- **Speakers:** Any audio output device

### Optional
- **Ollama:** For Qwen fallback (`ollama pull qwen3.5:9b`)
- **Claude token:** From `claude setup-token` CLI
- **ChatGPT:** OAuth PKCE flow (configured via `.env`)

## Setup

```bash
# Clone
git clone https://github.com/MiguelAguiarDEV/jarvis.git
cd jarvis

# Install dependencies
uv sync --extra dev          # Dev tools (pytest, ruff, mypy)
uv sync --extra audio        # PyAudio (requires portaudio system library)

# Download TTS models (~340MB total)
curl -L -o models/kokoro-v1.0.onnx \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -L -o models/voices-v1.0.bin \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

# Configure
cp .env.example .env
# Edit .env with your credentials (Claude token, etc.)

# Verify components work
uv run python scripts/smoke_test.py

# Run JARVIS
uv run python -m jarvis
```

## Development

Development from WSL, execution on Windows native.

```bash
# Run tests (211 tests, ~5s)
uv run pytest -v

# Run tests with coverage
uv run pytest --cov=jarvis --cov-report=term-missing

# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run mypy src/

# Smoke test (real models, no hardware needed)
uv run python scripts/smoke_test.py
```

## Project Structure

```
src/jarvis/
├── __main__.py            # Entry point (python -m jarvis)
├── config.py              # Settings via env vars (pydantic-settings)
├── logging.py             # Structured logging, sensitive data filtering
├── audio/
│   ├── capture.py         # Async mic input (PyAudio)
│   ├── playback.py        # Async speaker output (PyAudio)
│   ├── vad.py             # Voice Activity Detection (Silero)
│   └── wake_word.py       # Wake word detection (openWakeWord)
├── stt/
│   └── whisper_stt.py     # STT with VRAM management (faster-whisper)
├── tts/
│   └── kokoro_tts.py      # TTS, sync + streaming (Kokoro-82M)
├── llm/
│   ├── base.py            # Abstract LLMProvider + data types
│   ├── claude_provider.py # Anthropic Claude
│   ├── chatgpt_provider.py# OpenAI ChatGPT
│   ├── qwen_provider.py   # Qwen via Ollama
│   ├── router.py          # Fallback chain router
│   └── auth/
│       └── oauth_pkce.py  # RFC 7636 PKCE flow
├── tools/
│   ├── base.py            # Tool abstractions
│   ├── system_info.py     # Time, date, OS info tool
│   └── router.py          # Tool registry + executor
└── pipeline/
    └── main_loop.py       # Async state machine orchestrator
```

## Security

- The LLM is a **decision-maker**, not an executor
- It decides WHAT tool to call and with WHAT parameters
- The tool router executes with real credentials from config
- **The LLM never sees tokens, API keys, or sensitive credentials**
- All credentials are filtered from logs (`***REDACTED***`)
- Structured logging with request correlation for debugging

## License

MIT
