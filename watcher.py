"""File watcher — monitors code changes in real-time."""

import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from config import WATCH_DEBOUNCE_SEC, WATCH_EXTENSIONS


class CodeChangeHandler(FileSystemEventHandler):
    """Handles file change events with debouncing."""

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self._last_modified = 0
        self._last_path = ""

    def on_modified(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix not in WATCH_EXTENSIONS:
            return

        now = time.time()
        # Debounce: ignore rapid changes to the same file
        if path.name == self._last_path and (now - self._last_modified) < WATCH_DEBOUNCE_SEC:
            return

        self._last_modified = now
        self._last_path = path.name

        try:
            content = path.read_text(errors="replace")
            self.callback(str(path), content)
        except Exception:
            pass

    def on_created(self, event):
        self.on_modified(event)


class FileWatcher:
    """Watches a file or directory for code changes."""

    def __init__(self, path: str, callback):
        """
        Args:
            path: File or directory path to watch.
            callback: Function called with (filepath, content) on changes.
        """
        self.path = Path(path).resolve()
        self.callback = callback
        self.observer = Observer()
        self._running = False
        self._current_code = ""
        self._current_file = ""

    def start(self):
        handler = CodeChangeHandler(self._on_change)

        if self.path.is_file():
            watch_dir = str(self.path.parent)
        else:
            watch_dir = str(self.path)

        self.observer.schedule(handler, watch_dir, recursive=True)
        self.observer.daemon = True
        self.observer.start()
        self._running = True

    def _on_change(self, filepath: str, content: str):
        self._current_file = filepath
        self._current_code = content
        self.callback(filepath, content)

    def stop(self):
        if self._running:
            self.observer.stop()
            self.observer.join(timeout=2)
            self._running = False

    @property
    def current_code(self) -> str:
        return self._current_code

    @property
    def current_file(self) -> str:
        return self._current_file

    def read_initial(self) -> str:
        """Read the watched file's current content (if it's a single file)."""
        if self.path.is_file():
            try:
                self._current_file = str(self.path)
                self._current_code = self.path.read_text(errors="replace")
                return self._current_code
            except Exception:
                pass
        return ""
