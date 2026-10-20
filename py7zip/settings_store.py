"""Persistent application settings.

Settings are stored as JSON in the platform's per-user configuration
directory (``%APPDATA%`` on Windows, ``$XDG_CONFIG_HOME`` on Linux).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from . import APP_ID

DEFAULTS: dict[str, Any] = {
    "language": "tr",
    "theme": "light",
    "last_dir": "",
    "last_archive_dir": "",
    "extract_dir": "",
    "show_hidden": False,
    "confirm_delete": True,
    "preview_enabled": False,
    "sidebar_visible": False,
    "window_geometry": "",
    "sash_position": 220,
    "sort_column": "name",
    "sort_reverse": False,
    "compression_level": 5,
    "compression_method": "LZMA2",
    "recent_files": [],
}


def config_dir() -> Path:
    """Return the per-user configuration directory."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "Py7Zip"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_ID


class Settings:
    """Small dictionary-like wrapper with atomic persistence."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config_dir() / "settings.json")
        self._data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    # -- dictionary helpers -------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def update(self, **values: Any) -> None:
        self._data.update(values)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    # -- persistence --------------------------------------------------------
    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self._data.update(data)
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            # Corrupted settings should never prevent the app from starting.
            pass

    def save(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                prefix="settings-", suffix=".json", dir=str(self.path.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(self._data, fh, ensure_ascii=False, indent=2)
                os.replace(tmp_name, self.path)
            finally:
                if os.path.exists(tmp_name):
                    try:
                        os.unlink(tmp_name)
                    except OSError:
                        pass
            return True
        except OSError:
            return False

    def add_recent(self, path: str, limit: int = 12) -> None:
        recent = [p for p in self._data.get("recent_files", []) if p != path]
        recent.insert(0, path)
        self._data["recent_files"] = recent[:limit]

    def clear_recent(self) -> None:
        self._data["recent_files"] = []
