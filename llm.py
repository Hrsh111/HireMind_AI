"""LLM client — Groq (ultra-fast, free) with Ollama fallback."""

import json
import requests
from config import GROQ_API_KEY, GROQ_MODEL, OLLAMA_URL, OLLAMA_MODEL


class LLMClient:
    def __init__(self, api_key: str = "", model: str = ""):
        self.history: list[dict] = []

        # Determine backend
        self._api_key = api_key or GROQ_API_KEY
        if self._api_key:
            self._backend = "groq"
            self._model = model or GROQ_MODEL
        else:
            self._backend = "ollama"
            self._model = model or OLLAMA_MODEL

    @property
    def backend_name(self) -> str:
        return f"{self._backend} ({self._model})"

    def set_system_prompt(self, prompt: str):
        self.history = [{"role": "system", "content": prompt}]

    def chat(self, user_message: str, stream: bool = False) -> str:
        """Send a message and get a response. Returns full text."""
        self.history.append({"role": "user", "content": user_message})

        if self._backend == "groq":
            full_response = self._groq_chat(stream=False)
        else:
            full_response = self._ollama_chat(stream=False)

        self.history.append({"role": "assistant", "content": full_response})
        self._trim_history()
        return full_response

    def chat_stream(self, user_message: str):
        """Generator that yields response chunks for real-time display + TTS."""
        self.history.append({"role": "user", "content": user_message})

        full_response = ""
        if self._backend == "groq":
            for chunk in self._groq_stream():
                full_response += chunk
                yield chunk
        else:
            for chunk in self._ollama_stream():
                full_response += chunk
                yield chunk

        self.history.append({"role": "assistant", "content": full_response})
        self._trim_history()

    def inject_context(self, context: str):
        self.history.append({"role": "system", "content": context})

    # ── Groq backend ──────────────────────────────────────────────

    def _groq_chat(self, stream: bool = False) -> str:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": self.history,
                    "stream": False,
                    "temperature": 0.7,
                    "max_tokens": 1024,
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except requests.HTTPError as e:
            return f"Groq API error: {e.response.status_code} — {e.response.text[:200]}"
        except Exception as e:
            return f"Groq error: {e}"

    def _groq_stream(self):
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": self.history,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 1024,
                },
                stream=True,
                timeout=30,
            )
            resp.raise_for_status()

            for line in resp.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8")
                if not line_str.startswith("data: "):
                    continue
                data_str = line_str[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    delta = data["choices"][0].get("delta", {})
                    chunk = delta.get("content", "")
                    if chunk:
                        yield chunk
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

        except requests.HTTPError as e:
            yield f"Groq API error: {e.response.status_code}"
        except Exception as e:
            yield f"Groq error: {e}"

    # ── Ollama backend (fallback) ─────────────────────────────────

    def _ollama_chat(self, stream: bool = False) -> str:
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={"model": self._model, "messages": self.history, "stream": False},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "")
        except requests.ConnectionError:
            return "Can't reach Ollama. Run: ollama serve"
        except Exception as e:
            return f"Ollama error: {e}"

    def _ollama_stream(self):
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={"model": self._model, "messages": self.history, "stream": True},
                stream=True,
                timeout=120,
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        break
        except requests.ConnectionError:
            yield "Can't reach Ollama. Run: ollama serve"
        except Exception as e:
            yield f"Ollama error: {e}"

    def _trim_history(self):
        if len(self.history) > 42:
            self.history = self.history[:1] + self.history[-40:]
