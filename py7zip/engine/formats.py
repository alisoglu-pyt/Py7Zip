"""Archive format registry and filename-based detection."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

_SPLIT_PART_RE = re.compile(r"^(?P<base>.+)\.(?P<number>\d{3,})$")


@dataclass(frozen=True)
class ArchiveFormat:
    key: str
    label: str
    ext: str
    kind: str  # 7z | zip | tar | gzip | bzip2 | xz
    extensions: tuple[str, ...] = field(default_factory=tuple)
    can_create: bool = True
    can_extract: bool = True
    single_file: bool = False
    tar_mode: str = ""

    @property
    def all_extensions(self) -> tuple[str, ...]:
        if self.extensions:
            return self.extensions
        return (self.ext,) if self.ext else ()


ARCHIVE_FORMATS: dict[str, ArchiveFormat] = {
    "7z": ArchiveFormat(
        key="7z", label="7z", ext=".7z", kind="7z",
        extensions=(".7z",),
    ),
    "zip": ArchiveFormat(
        key="zip", label="Zip", ext=".zip", kind="zip",
        extensions=(".zip", ".jar", ".apk", ".docx", ".xlsx", ".pptx", ".epub"),
    ),
    "tar": ArchiveFormat(
        key="tar", label="Tar", ext=".tar", kind="tar", tar_mode="w",
        extensions=(".tar",),
    ),
    "tar.gz": ArchiveFormat(
        key="tar.gz", label="Tar + Gzip", ext=".tar.gz", kind="tar",
        tar_mode="w:gz", extensions=(".tar.gz", ".tgz"),
    ),
    "tar.bz2": ArchiveFormat(
        key="tar.bz2", label="Tar + Bzip2", ext=".tar.bz2", kind="tar",
        tar_mode="w:bz2", extensions=(".tar.bz2", ".tbz2", ".tbz"),
    ),
    "tar.xz": ArchiveFormat(
        key="tar.xz", label="Tar + Xz", ext=".tar.xz", kind="tar",
        tar_mode="w:xz", extensions=(".tar.xz", ".txz"),
    ),
    "gz": ArchiveFormat(
        key="gz", label="Gzip", ext=".gz", kind="gzip",
        extensions=(".gz",), single_file=True,
    ),
    "bz2": ArchiveFormat(
        key="bz2", label="Bzip2", ext=".bz2", kind="bzip2",
        extensions=(".bz2",), single_file=True,
    ),
    "xz": ArchiveFormat(
        key="xz", label="Xz", ext=".xz", kind="xz",
        extensions=(".xz",), single_file=True,
    ),
}

CREATE_FORMATS: tuple[str, ...] = (
    "7z",
    "zip",
    "tar",
    "tar.gz",
    "tar.bz2",
    "tar.xz",
    "gz",
    "bz2",
    "xz",
)

# Longest extensions first so that ".tar.gz" wins over ".gz".
_SORTED_FORMATS = sorted(
    ARCHIVE_FORMATS.values(),
    key=lambda fmt: max(len(ext) for ext in fmt.all_extensions),
    reverse=True,
)


def _detect_format_direct(path: str | os.PathLike[str]) -> str | None:
    name = os.fspath(path).lower()
    for fmt in _SORTED_FORMATS:
        for ext in fmt.all_extensions:
            if name.endswith(ext):
                return fmt.key
    return None


def split_base_path(path: str | os.PathLike[str]) -> str | None:
    """Return the base archive path for ``archive.7z.001`` style parts."""
    text = os.fspath(path)
    match = _SPLIT_PART_RE.match(text)
    if not match:
        return None
    base = match.group("base")
    if _detect_format_direct(base):
        return base
    return None


def split_part_paths(base: str) -> list[str]:
    """Return all existing ``base.NNN`` volumes sorted by number."""
    directory = os.path.dirname(os.path.abspath(base)) or "."
    prefix = os.path.basename(base)
    pattern = re.compile(r"^" + re.escape(prefix) + r"\.(\d{3,})$")
    found: list[tuple[int, str]] = []
    try:
        with os.scandir(directory) as iterator:
            for entry in iterator:
                match = pattern.match(entry.name)
                if match:
                    found.append((int(match.group(1)), entry.path))
    except OSError:
        return []
    found.sort(key=lambda item: item[0])
    return [path for _number, path in found]


def detect_format(path: str | os.PathLike[str]) -> str | None:
    """Return the format key for *path* (by extension) or ``None``.

    Split volumes such as ``archive.7z.001`` report the format of their
    base archive (``7z``).
    """
    base = split_base_path(path)
    if base is not None:
        return _detect_format_direct(base)
    return _detect_format_direct(path)


def format_for(path: str | os.PathLike[str]) -> ArchiveFormat | None:
    key = detect_format(path)
    return ARCHIVE_FORMATS.get(key) if key else None


def is_archive_path(path: str | os.PathLike[str]) -> bool:
    return detect_format(path) is not None


def format_extension(fmt_key: str) -> str:
    fmt = ARCHIVE_FORMATS.get(fmt_key)
    return fmt.ext if fmt else ""


def strip_archive_suffix(path: str | os.PathLike[str]) -> str:
    """Remove a known archive suffix (``archive.tar.gz`` -> ``archive``).

    Split volume suffixes are removed first (``a.7z.001`` -> ``a``).
    """
    text = os.fspath(path)
    match = _SPLIT_PART_RE.match(text)
    if match and _detect_format_direct(match.group("base")):
        text = match.group("base")
    lower = text.lower()
    for fmt in _SORTED_FORMATS:
        for ext in sorted(fmt.all_extensions, key=len, reverse=True):
            if lower.endswith(ext):
                return text[: -len(ext)]
    return text


def base_name_for_extract(path: str | os.PathLike[str]) -> str:
    """Name used for the auto-created extraction sub-folder."""
    name = Path(strip_archive_suffix(path)).name
    return name or "extracted"


def suggest_archive_path(folder: str, base: str, fmt_key: str) -> str:
    extension = format_extension(fmt_key)
    candidate = os.path.join(folder, base + extension)
    if not os.path.exists(candidate):
        return candidate
    index = 2
    while True:
        candidate = os.path.join(folder, f"{base} ({index}){extension}")
        if not os.path.exists(candidate):
            return candidate
        index += 1
