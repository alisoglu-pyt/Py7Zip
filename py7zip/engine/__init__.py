"""Archive engine package (pure Python implementation)."""

from .archive import (
    ArchiveEngine,
    ArchiveError,
    OperationCancelled,
    PasswordRequiredError,
)
from .entries import Entry
from .formats import (
    ARCHIVE_FORMATS,
    CREATE_FORMATS,
    detect_format,
    format_extension,
    is_archive_path,
    split_base_path,
    split_part_paths,
    strip_archive_suffix,
)

__all__ = [
    "ArchiveEngine",
    "ArchiveError",
    "OperationCancelled",
    "PasswordRequiredError",
    "Entry",
    "ARCHIVE_FORMATS",
    "CREATE_FORMATS",
    "detect_format",
    "format_extension",
    "is_archive_path",
    "split_base_path",
    "split_part_paths",
    "strip_archive_suffix",
]
