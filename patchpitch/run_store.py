"""Bounded JSON files, atomic checkpoints and crash-safe OS locks."""
import hashlib
import json
import os
import tempfile
from contextlib import AbstractContextManager
from pathlib import Path


class RunError(Exception):
    def __init__(self, code, message, exit_code=2):
        super().__init__(message)
        self.code, self.message, self.exit_code = code, message, exit_code

    def as_dict(self):
        return {"code": self.code, "message": self.message}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RunError("DUPLICATE_KEY", "Duplicate JSON keys are not allowed.")
        result[key] = value
    return result


def read_json(path, limit=32_000_000):
    try:
        with Path(path).open("rb") as handle:
            raw = handle.read(limit + 1)
        if len(raw) > limit:
            raise RunError("FILE_TOO_LARGE", "Input file exceeds its byte budget.")
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")))
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise RunError("INVALID_FILE", "Cannot read a valid, bounded UTF-8 JSON input.") from exc


def write_text(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".checkpoint-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


class FileLock(AbstractContextManager):
    """Hold a byte-range/flock lock; a killed process releases it automatically."""
    def __init__(self, path, code="RUN_BUSY"):
        self.path, self.code, self.handle = Path(path), code, None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                if self.handle.seek(0, 2) == 0:
                    self.handle.write(b"0")
                    self.handle.flush()
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.handle.close()
            self.handle = None
            raise RunError(self.code, "Another process holds the requested lock.", 3) from exc
        return self

    def __exit__(self, *args):
        if self.handle:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
        return False


def engine_lock():
    # tempfile is user-specific on Windows. Include the home identity on Unix.
    identity = hashlib.sha256(str(Path.home()).encode()).hexdigest()[:16]
    return FileLock(Path(tempfile.gettempdir()) / f"patchpitch-{identity}-engine.lock", "ENGINE_BUSY")
