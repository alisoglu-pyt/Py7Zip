"""Shared helpers used by the UI and the archive engine."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")


def human_size(size: int | float | None) -> str:
    """Return a compact human readable size (e.g. ``1.4 MB``)."""
    if size is None:
        return "—"
    try:
        value = float(size)
    except (TypeError, ValueError):
        return "—"
    if value < 0:
        return "—"
    index = 0
    while value >= 1024.0 and index < len(_UNITS) - 1:
        value /= 1024.0
        index += 1
    if index == 0:
        return f"{int(value)} {_UNITS[index]}"
    if value >= 100:
        return f"{value:.0f} {_UNITS[index]}"
    if value >= 10:
        return f"{value:.1f} {_UNITS[index]}"
    return f"{value:.2f} {_UNITS[index]}"


def format_timestamp(timestamp: float | None) -> str:
    """Format a POSIX timestamp for display."""
    if not timestamp:
        return "—"
    import datetime as _dt

    try:
        return _dt.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return "—"


def ratio_text(unpacked: int, packed: int) -> str:
    """Compression ratio as a percentage of the original size."""
    if not unpacked:
        return "—"
    if not packed:
        return "0%"
    value = packed / unpacked * 100.0
    if value < 0.1:
        return "<0.1%"
    return f"{value:.1f}%"


def crc_hex(value: int | None) -> str | None:
    if value is None:
        return None
    try:
        return f"{int(value) & 0xFFFFFFFF:08X}"
    except (TypeError, ValueError):
        return None


def safe_filename(name: str, fallback: str = "output") -> str:
    """Turn an arbitrary string into a portable file name."""
    name = (name or "").strip().replace("\x00", "")
    for char in '<>:"/\\|?*':
        name = name.replace(char, "_")
    name = name.strip(" .")
    return name or fallback


def is_probably_text(data: bytes) -> bool:
    """Cheap heuristic to decide whether bytes look like UTF-8/ASCII text."""
    if not data:
        return True
    if b"\x00" in data:
        return False
    sample = data[:4096]
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        # Fall back to a printable-character ratio for legacy encodings.
        printable = sum(1 for b in sample if 9 <= b <= 13 or 32 <= b <= 126)
        return printable / max(len(sample), 1) > 0.90


TEXT_EXTENSIONS = {
    ".txt", ".md", ".rst", ".log", ".ini", ".cfg", ".conf", ".json", ".xml",
    ".yaml", ".yml", ".toml", ".csv", ".tsv", ".py", ".pyw", ".js", ".ts",
    ".tsx", ".jsx", ".html", ".htm", ".css", ".scss", ".c", ".h", ".cpp",
    ".hpp", ".cc", ".cs", ".java", ".kt", ".go", ".rs", ".rb", ".php", ".sh",
    ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".sql", ".svg", ".gitignore",
    ".env", ".properties", ".gradle", ".cmake", ".mak", ".mk", ".dockerfile",
}

IMAGE_EXTENSIONS = {
    ".png", ".gif", ".ppm", ".pgm", ".pbm", ".bmp", ".ico", ".tga",
}


def is_text_name(name: str) -> bool:
    return Path(name).suffix.lower() in TEXT_EXTENSIONS


def is_image_name(name: str) -> bool:
    return Path(name).suffix.lower() in IMAGE_EXTENSIONS


def open_with_default(path: str | Path) -> None:
    """Open a file or folder with the operating system's default handler."""
    target = str(path)
    if sys.platform == "win32":
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])


def reveal_in_file_manager(path: str | Path) -> None:
    target = Path(path)
    if sys.platform == "win32":
        if target.is_file():
            subprocess.Popen(["explorer", "/select,", str(target)])
        else:
            os.startfile(str(target))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(target)])
    else:
        folder = target if target.is_dir() else target.parent
        subprocess.Popen(["xdg-open", str(folder)])


def make_temp_dir(prefix: str = "py7zip-") -> str:
    return tempfile.mkdtemp(prefix=prefix)


def remove_tree(path: str | Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def common_parent(paths: list[str]) -> str:
    """Return the deepest common parent folder of a set of paths."""
    if not paths:
        return os.getcwd()
    if len(paths) == 1:
        # Use the parent even for a single folder so the folder itself is
        # stored inside the archive rather than flattened.
        return os.path.dirname(os.path.abspath(paths[0]))
    try:
        return os.path.commonpath([os.path.abspath(p) for p in paths])
    except ValueError:
        return os.path.dirname(os.path.abspath(paths[0]))


def shorten_path(path: str, limit: int = 64) -> str:
    if len(path) <= limit:
        return path
    head = max(8, limit // 3)
    tail = max(8, limit - head - 3)
    return f"{path[:head]}…{path[-tail:]}"


def file_icon_name(name: str, is_dir: bool = False) -> str:
    """Return a portable emoji-ish glyph for the item type."""
    if is_dir:
        return "📁"
    ext = Path(name).suffix.lower()
    if ext in {".7z", ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".txz",
               ".tbz2", ".rar", ".iso", ".jar"}:
        return "🗜"
    if ext in IMAGE_EXTENSIONS:
        return "🖼"
    if ext in TEXT_EXTENSIONS:
        return "📄"
    if ext in {".mp3", ".wav", ".flac", ".ogg", ".m4a"}:
        return "🎵"
    if ext in {".mp4", ".mkv", ".avi", ".mov", ".webm"}:
        return "🎬"
    if ext in {".exe", ".msi", ".dll", ".so", ".app"}:
        return "⚙"
    return "📄"
