# JARVIS

Personal AI voice assistant with multi-LLM support and tool execution.

## Architecture

```
Wake Word → VAD → STT (GPU) → LLM Router → Tool Router → TTS (CPU) → Speaker
```

### LLM Providers
- **Claude** (primary) — Anthropic API via setup-token
- **ChatGPT** (secondary) — OpenAI API via OAuth PKCE
- **Qwen 3.5-9B** (fallback) — Local via Ollama (CPU)

### VRAM Budget (RTX 4060, 8GB)
- STT (faster-whisper): ~4GB on-demand (loaded only during transcription)
- TTS (Kokoro): 0GB (CPU)
- Qwen fallback: 0GB (CPU via Ollama)

## Requirements

- **OS:** Windows 10/11 (native execution)
- **Python:** 3.12+
- **GPU:** NVIDIA GPU with CUDA 12.x (for STT)
- **RAM:** 16GB+ recommended (32GB for Qwen fallback)
- **Ollama:** Required for Qwen fallback (`ollama pull qwen3.5:9b`)

## Setup

```bash
# Clone
git clone https://github.com/MiguelAguiarDEV/jarvis.git
cd jarvis

# Install dependencies (requires uv)
uv sync --all-extras

# Configure
cp .env.example .env
# Edit .env with your credentials

# Download TTS models
# Place kokoro-v1.0.onnx and voices-v1.0.bin in models/

# Run
uv run python -m jarvis
```

## Development

Development is done from WSL, execution on Windows native.

```bash
# Run tests
uv run pytest --cov=jarvis --cov-report=term-missing

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Type check
uv run mypy src/
```

## Project Structure

```
src/jarvis/
├── config.py          # Settings (pydantic-settings)
├── audio/             # Mic capture, speaker playback, VAD, wake word
├── stt/               # Speech-to-text (faster-whisper, GPU)
├── tts/               # Text-to-speech (Kokoro, CPU)
├── llm/               # Multi-provider LLM abstraction
│   └── auth/          # OAuth PKCE flow
├── tools/             # Tool system (system_info, etc.)
└── pipeline/          # Main async orchestration loop
```

## Security

The LLM is a decision-maker, not an executor. It decides WHAT tool to call and with WHAT parameters. The tool router executes with real credentials. **The LLM never sees tokens, API keys, or sensitive credentials.**

## License

MIT
