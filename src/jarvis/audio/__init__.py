"""Audio capture, playback, VAD, and wake word detection."""

from jarvis.audio.capture import AudioCapture, AudioCaptureError, pcm_bytes_to_float
from jarvis.audio.playback import AudioPlayback, AudioPlaybackError, float_to_pcm_bytes
from jarvis.audio.vad import SpeechEvent, VADError, VoiceActivityDetector
from jarvis.audio.wake_word import WakeWordDetector, WakeWordError

__all__ = [
    "AudioCapture",
    "AudioCaptureError",
    "AudioPlayback",
    "AudioPlaybackError",
    "SpeechEvent",
    "VADError",
    "VoiceActivityDetector",
    "WakeWordDetector",
    "WakeWordError",
    "float_to_pcm_bytes",
    "pcm_bytes_to_float",
]
