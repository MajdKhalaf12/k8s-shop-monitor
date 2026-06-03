from __future__ import annotations

import os
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from classifier.config import settings
from classifier.engine import ClassificationEngine
from classifier import metrics


class LogTailHandler(FileSystemEventHandler):
    def __init__(self, engine: ClassificationEngine) -> None:
        self._engine = engine
        self._path = settings.log_path
        self._offset = 0
        self._inode: int | None = None

    def _open_and_tail_existing(self) -> None:
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8", errors="replace") as f:
            st = os.fstat(f.fileno())
            self._inode = st.st_ino
            f.seek(self._offset)
            for line in f:
                self._process_line(line)
            self._offset = f.tell()

    def _process_line(self, line: str) -> None:
        from classifier.parser import parse_line

        entry = parse_line(line)
        if entry:
            self._engine.process(entry)

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        if os.path.abspath(event.src_path) != os.path.abspath(self._path):
            return
        self._read_new_lines()

    def _read_new_lines(self) -> None:
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8", errors="replace") as f:
            st = os.fstat(f.fileno())
            if self._inode is not None and st.st_ino != self._inode:
                self._offset = 0
            self._inode = st.st_ino
            f.seek(self._offset)
            for line in f:
                self._process_line(line)
            self._offset = f.tell()

    def run_poll_loop(self, interval: float = 0.5) -> None:
        while True:
            self._read_new_lines()
            time.sleep(interval)


def main() -> None:
    metrics.start_metrics_server(settings.metrics_port)
    engine = ClassificationEngine()
    handler = LogTailHandler(engine)
    handler._open_and_tail_existing()

    log_dir = os.path.dirname(settings.log_path) or "/logs"
    os.makedirs(log_dir, exist_ok=True)

    observer = Observer()
    observer.schedule(handler, log_dir, recursive=False)
    observer.start()
    try:
        handler.run_poll_loop()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
