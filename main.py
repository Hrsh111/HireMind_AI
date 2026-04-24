#!/usr/bin/env python3
"""DSA Interview Bot — Entry point."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import GROQ_API_KEY, GROQ_MODEL, OLLAMA_MODEL, OLLAMA_URL
from llm import LLMClient
from voice import VoicePipeline
from watcher import FileWatcher
from interviewer import Interviewer
import ui


def parse_args():
    parser = argparse.ArgumentParser(
        description="Algo — AI-powered DSA Interview Bot (Groq-powered, voice-enabled)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python main.py                                  Start (uses Groq if GROQ_API_KEY set)
  GROQ_API_KEY=gsk_... python main.py             Pass API key inline
  python main.py --jd-path ./jd.txt --resume-path ./resume.txt
  python main.py --watch ../solution.cpp           Watch a file
  python main.py --no-voice                        Text-only mode
  python main.py --local                           Force Ollama (local, slower)
        """,
    )
    parser.add_argument("--topic", type=str, help="Optional preferred topic to append into context")
    parser.add_argument("--diff", choices=["easy", "medium", "hard"], default="medium", help="Preferred difficulty hint")
    parser.add_argument("--watch", type=str, help="File or directory to watch for code changes")
    parser.add_argument("--no-voice", action="store_true", help="Disable voice (text-only mode)")
    parser.add_argument("--local", action="store_true", help="Force local Ollama instead of Groq")
    parser.add_argument("--model", type=str, help="Override model name")
    parser.add_argument("--jd-path", type=str, help="Path to job description text file")
    parser.add_argument("--resume-path", type=str, help="Path to resume text file")
    return parser.parse_args()


def read_text_file(path: str | None, label: str) -> str:
    if not path:
        return ""
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        ui.print_error(f"{label} file does not exist: {file_path}")
        sys.exit(1)
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception as exc:
        ui.print_error(f"Could not read {label} file {file_path}: {exc}")
        sys.exit(1)


def check_ollama(url: str, model: str) -> bool:
    import requests
    try:
        resp = requests.get(f"{url}/api/tags", timeout=5)
        if resp.status_code != 200:
            return False
        models = [m["name"] for m in resp.json().get("models", [])]
        base_model = model.split(":")[0]
        return any(base_model in m for m in models)
    except Exception:
        return False


def main():
    args = parse_args()
    jd_text = read_text_file(args.jd_path, "Job description")
    resume_text = read_text_file(args.resume_path, "Resume")

    if args.topic:
        topic_hint = f"Candidate requested topic focus: {args.topic} ({args.diff})."
        jd_text = f"{jd_text}\n\n{topic_hint}".strip()
    elif args.diff:
        jd_text = f"{jd_text}\n\nPreferred interview difficulty: {args.diff}.".strip()

    api_key = "" if args.local else GROQ_API_KEY
    model = args.model or ""

    # Determine backend
    if api_key:
        ui.print_info(f"Using Groq API ({model or GROQ_MODEL}) — ultra-fast responses")
        llm = LLMClient(api_key=api_key, model=model)
    else:
        # Fallback to Ollama
        ollama_model = model or OLLAMA_MODEL
        if not check_ollama(OLLAMA_URL, ollama_model):
            ui.print_error("No LLM backend available!")
            ui.print_info("")
            ui.print_info("Option 1 (recommended): Set GROQ_API_KEY for free ultra-fast AI")
            ui.print_info("  Get your free key at: https://console.groq.com")
            ui.print_info("  Then run: GROQ_API_KEY=gsk_... python main.py")
            ui.print_info("")
            ui.print_info("Option 2: Start Ollama locally")
            ui.print_info(f"  ollama serve && ollama pull {ollama_model}")
            sys.exit(1)
        ui.print_info(f"Using Ollama ({ollama_model}) — local, slower")
        llm = LLMClient(model=model)

    voice = VoicePipeline(enabled=not args.no_voice)
    if not args.no_voice:
        ui.print_info("Voice ON — bot will speak aloud. Press Enter (empty) to speak via mic.")

    # File watcher
    watcher = None
    if args.watch:
        watch_path = Path(args.watch).resolve()
        if not watch_path.exists():
            ui.print_error(f"Watch path does not exist: {watch_path}")
            sys.exit(1)
        watcher = FileWatcher(str(watch_path), lambda fp, c: None)
        ui.print_info(f"Watching: {watch_path}")

    # Create and run interviewer
    interviewer = Interviewer(
        llm=llm,
        voice=voice,
        watcher=watcher,
        jd_text=jd_text,
        resume_text=resume_text,
    )

    if watcher:
        watcher.callback = interviewer.on_code_change
        watcher.start()

    try:
        interviewer.run()
    except KeyboardInterrupt:
        ui.print_info("\nSession ended. Keep practicing!")
    finally:
        if watcher:
            watcher.stop()


if __name__ == "__main__":
    main()
