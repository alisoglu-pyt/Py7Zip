"""Normalised archive entry model and folder-tree helpers."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field


def normalize_name(name: str) -> str:
    """Normalise an archive member path to forward slashes without a prefix."""
    text = (name or "").replace("\\", "/")
    text = text.lstrip("/")
    while text.startswith("./"):
        text = text[2:]
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if parts and parts[0] == "..":
        parts = [part for part in parts if part != ".."]
    return "/".join(parts)


def parent_of(name: str) -> str:
    name = normalize_name(name)
    if "/" not in name:
        return ""
    return name.rsplit("/", 1)[0]


def basename_of(name: str) -> str:
    return normalize_name(name).rsplit("/", 1)[-1]


@dataclass
class Entry:
    """A single file/folder inside an archive."""

    name: str
    is_dir: bool = False
    size: int = 0
    packed: int = 0
    mtime: float | None = None
    crc: str | None = None
    method: str = ""
    is_symlink: bool = False
    encrypted: bool = False
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = normalize_name(self.name)
        if self.name.endswith("/") and not self.is_dir:
            self.is_dir = True
            self.name = self.name.rstrip("/")
        if self.name == "" and not self.is_dir:
            # Root marker - callers generally ignore it.
            self.is_dir = True

    @property
    def basename(self) -> str:
        return basename_of(self.name)

    @property
    def parent(self) -> str:
        return parent_of(self.name)

    @property
    def depth(self) -> int:
        return self.name.count("/")

    def key(self) -> tuple[str, bool]:
        return (self.name, self.is_dir)


def _make_dir_entry(name: str) -> Entry:
    return Entry(name=name, is_dir=True, size=0, packed=0)


def child_entries(entries: list[Entry], prefix: str = "") -> list[Entry]:
    """Return the direct children of *prefix*, synthesising missing folders."""
    prefix = normalize_name(prefix)
    result: dict[str, Entry] = {}

    for entry in entries:
        name = entry.name
        if not name:
            continue
        if prefix:
            marker = prefix + "/"
            if name == prefix:
                continue
            if not name.startswith(marker):
                continue
            relative = name[len(marker):]
        else:
            relative = name
        relative = relative.strip("/")
        if not relative:
            continue

        if "/" in relative:
            child_name = relative.split("/", 1)[0]
            if child_name not in result:
                result[child_name] = _make_dir_entry(
                    f"{prefix}/{child_name}" if prefix else child_name
                )
            continue

        # Direct child: an explicit entry always wins over a synthetic folder.
        existing = result.get(relative)
        if existing is None or not entry.is_dir or existing.is_dir:
            result[relative] = entry

    return list(result.values())


def entry_in_subtree(entry: Entry, folder: str) -> bool:
    folder = normalize_name(folder)
    if not folder:
        return True
    return entry.name == folder or entry.name.startswith(folder + "/")


def selected_member_names(
    entries: list[Entry], selected_names: set[str], recursive: bool = True
) -> list[str]:
    """Expand a selection (which may contain folders) into member names."""
    if not selected_names:
        return []
    normalized = {normalize_name(n) for n in selected_names}
    if not recursive:
        return [e.name for e in entries if e.name in normalized]

    result: list[str] = []
    for entry in entries:
        name = entry.name
        if name in normalized:
            result.append(name)
            continue
        for chosen in normalized:
            if name.startswith(chosen + "/"):
                result.append(name)
                break
    return result


def search_entries(
    entries: list[Entry], prefix: str, query: str
) -> list[Entry]:
    """Filter entries below *prefix* whose name contains *query*."""
    query = query.casefold().strip()
    if not query:
        return []
    prefix = normalize_name(prefix)
    results: list[Entry] = []
    for entry in entries:
        if not entry_in_subtree(entry, prefix):
            continue
        if query in entry.name.casefold():
            results.append(entry)
    return results


def total_unpacked(entries: list[Entry]) -> int:
    return sum(e.size for e in entries if not e.is_dir)


def total_packed(entries: list[Entry]) -> int:
    return sum(e.packed for e in entries if not e.is_dir)


def join_archive_path(folder: str, name: str) -> str:
    folder = normalize_name(folder)
    name = normalize_name(name)
    if not folder:
        return name
    if not name:
        return folder
    return posixpath.join(folder, name)
