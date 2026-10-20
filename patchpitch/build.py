"""Identity of the local runtime sources, without Git or external processes."""
import hashlib
from pathlib import Path


def source_hash():
    root=Path(__file__).parent
    files=[p for p in root.rglob("*") if p.is_file() and p.suffix in {".py",".js",".html",".css",".json",".txt"} and "__pycache__" not in p.parts]
    content="\n".join(p.relative_to(root).as_posix()+":"+hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files))
    return hashlib.sha256(content.encode()).hexdigest()
