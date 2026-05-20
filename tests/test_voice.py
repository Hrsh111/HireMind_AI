import voice
from voice import TTS, _detect_tts_engine


def test_detect_macos(monkeypatch):
    monkeypatch.setattr(voice.sys, "platform", "darwin")
    monkeypatch.setattr(voice.shutil, "which", lambda c: "/usr/bin/say" if c == "say" else None)
    assert _detect_tts_engine() == "say"


def test_detect_linux_espeak(monkeypatch):
    monkeypatch.setattr(voice.sys, "platform", "linux")
    monkeypatch.setattr(voice.shutil, "which", lambda c: "/usr/bin/espeak-ng" if c == "espeak-ng" else None)
    assert _detect_tts_engine() == "espeak-ng"


def test_detect_none(monkeypatch):
    monkeypatch.setattr(voice.sys, "platform", "linux")
    monkeypatch.setattr(voice.shutil, "which", lambda c: None)
    assert _detect_tts_engine() is None


def test_build_command_say(monkeypatch):
    monkeypatch.setattr(voice, "_detect_tts_engine", lambda: "say")
    cmd = TTS()._build_command("hello")
    assert cmd[0] == "say"
    assert "hello" in cmd


def test_build_command_espeak(monkeypatch):
    monkeypatch.setattr(voice, "_detect_tts_engine", lambda: "espeak-ng")
    cmd = TTS()._build_command("hello")
    assert cmd[0] == "espeak-ng"
    assert cmd[-1] == "hello"


def test_powershell_escapes_quotes(monkeypatch):
    monkeypatch.setattr(voice, "_detect_tts_engine", lambda: "powershell")
    cmd = TTS()._build_command("it's me")
    assert "''" in cmd[-1]


def test_no_engine_speak_is_noop(monkeypatch):
    monkeypatch.setattr(voice, "_detect_tts_engine", lambda: None)
    t = TTS()
    assert t.available is False
    t.speak("anything")  # must not raise
