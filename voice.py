"""Voice pipeline: Text-to-Speech and Speech-to-Text."""

import subprocess
import threading
import tempfile
import wave
import io
import numpy as np
from config import TTS_RATE, STT_MODEL, RECORD_SAMPLE_RATE, SILENCE_THRESHOLD, SILENCE_DURATION


class TTS:
    """Text-to-Speech using macOS native `say` command."""

    def __init__(self):
        self._speaking = False
        self._process = None

    def speak(self, text: str):
        """Speak text aloud. Blocks until done."""
        if not text or text.strip() == "...":
            return
        clean = text.replace("`", "").replace("*", "").replace("#", "")
        self._speaking = True
        try:
            self._process = subprocess.Popen(
                ["say", "-r", str(TTS_RATE), clean],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            self._process.kill()
        except Exception:
            pass
        finally:
            self._speaking = False
            self._process = None

    def speak_async(self, text: str):
        """Speak text in a background thread."""
        t = threading.Thread(target=self.speak, args=(text,), daemon=True)
        t.start()
        return t

    def speak_streamed(self, text_generator):
        """Speak chunks as they arrive from LLM streaming. Returns full text.

        Buffers text by sentence, then speaks each sentence while
        the next one is being generated — feels real-time.
        """
        full_text = ""
        sentence_buf = ""
        sentence_enders = {".","!","?","\n"}
        threads = []

        for chunk in text_generator:
            full_text += chunk
            sentence_buf += chunk

            # When we hit end of sentence, speak it async
            if any(sentence_buf.rstrip().endswith(e) for e in sentence_enders) and len(sentence_buf.strip()) > 5:
                t = self.speak_async(sentence_buf.strip())
                if t:
                    threads.append(t)
                sentence_buf = ""

        # Speak any remaining text
        if sentence_buf.strip():
            t = self.speak_async(sentence_buf.strip())
            if t:
                threads.append(t)

        # Wait for all speech to finish
        for t in threads:
            t.join(timeout=30)

        return full_text

    def stop(self):
        self._speaking = False
        if self._process:
            try:
                self._process.kill()
            except Exception:
                pass

    @property
    def is_speaking(self) -> bool:
        return self._speaking


class STT:
    """Speech-to-Text using faster-whisper (local, fast)."""

    def __init__(self):
        self._model = None
        self._available = False
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(STT_MODEL, device="cpu", compute_type="int8")
            self._available = True
        except ImportError:
            print("[voice] faster-whisper not installed. Voice input disabled.")
            print("        Install with: pip install faster-whisper")
        except Exception as e:
            print(f"[voice] Could not load Whisper model: {e}")

    @property
    def available(self) -> bool:
        return self._available

    def listen(self) -> str:
        """Record audio until silence, then transcribe."""
        if not self._available:
            return ""

        try:
            import sounddevice as sd
        except ImportError:
            print("[voice] sounddevice not installed. Install: pip install sounddevice")
            return ""

        print("\n  [Listening... speak now, stay silent to stop]\n")

        frames = []
        silence_frames = 0
        max_silence = int(SILENCE_DURATION * RECORD_SAMPLE_RATE / 1024)
        max_duration_frames = int(30 * RECORD_SAMPLE_RATE / 1024)

        try:
            stream = sd.InputStream(
                samplerate=RECORD_SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=1024,
            )
            stream.start()

            for _ in range(max_duration_frames):
                data, _ = stream.read(1024)
                frames.append(data.copy())

                volume = np.abs(data).mean()
                if volume < SILENCE_THRESHOLD:
                    silence_frames += 1
                else:
                    silence_frames = 0

                if silence_frames >= max_silence and len(frames) > max_silence:
                    break

            stream.stop()
            stream.close()

        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"[voice] Recording error: {e}")
            return ""

        if not frames:
            return ""

        audio = np.concatenate(frames, axis=0).flatten()
        audio_int16 = (audio * 32767).astype(np.int16)

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(RECORD_SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_buffer.getvalue())
            tmp_path = f.name

        try:
            segments, _ = self._model.transcribe(tmp_path, beam_size=3)
            text = " ".join(seg.text for seg in segments).strip()
            return text
        except Exception as e:
            print(f"[voice] Transcription error: {e}")
            return ""
        finally:
            import os
            os.unlink(tmp_path)


class VoicePipeline:
    """Combined TTS + STT with mode toggle."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.tts = TTS() if enabled else None
        self.stt = STT() if enabled else None

    def speak(self, text: str):
        if self.enabled and self.tts:
            self.tts.speak(text)

    def speak_async(self, text: str) -> threading.Thread | None:
        if self.enabled and self.tts:
            return self.tts.speak_async(text)
        return None

    def speak_streamed(self, text_generator):
        """Speak LLM output in real-time as it streams. Returns full text."""
        if self.enabled and self.tts:
            return self.tts.speak_streamed(text_generator)
        # If voice disabled, just consume the generator
        full = ""
        for chunk in text_generator:
            full += chunk
        return full

    def listen(self) -> str:
        if self.enabled and self.stt and self.stt.available:
            return self.stt.listen()
        return ""

    def stop_speaking(self):
        if self.tts:
            self.tts.stop()

    @property
    def stt_available(self) -> bool:
        return self.enabled and self.stt is not None and self.stt.available
