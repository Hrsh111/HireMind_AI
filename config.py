"""Configuration for the DSA Interview Bot."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
QUESTIONS_DIR = BASE_DIR / "questions"

# Groq API settings (FREE — get key at console.groq.com)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
GROQ_MODEL = "llama-3.3-70b-versatile"  # Fast & smart. Alt: "llama-3.1-8b-instant" (faster)

# Fallback: Ollama (local, slower)
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2:3b"

# Voice settings
VOICE_ENABLED = True
TTS_RATE = 190  # Words per minute for macOS say
STT_MODEL = "tiny"  # Whisper model: tiny (fastest), base, small
RECORD_SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.01
SILENCE_DURATION = 1.5  # Seconds of silence to stop recording

# File watcher settings
WATCH_DEBOUNCE_SEC = 0.5
WATCH_EXTENSIONS = {".cpp", ".c++", ".py", ".java", ".c", ".js", ".ts", ".go", ".rs"}

# Interview settings
IDLE_HINT_TIMEOUT = 180
MAX_HINTS = 3

DIFFICULTY_LEVELS = ["easy", "medium", "hard"]

TOPICS = [
    "arrays",
    "strings",
    "linked_list",
    "trees",
    "graphs",
    "dp",
    "binary_search",
    "backtracking",
    "stacks_queues",
    "heaps",
    "system_design",
]
