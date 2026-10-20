"""Pure-Python archive engine.

The engine hides the differences between py7zr and the standard library
(``zipfile``, ``tarfile``, ``gzip``, ``bz2``, ``lzma``) behind a single,
synchronous API.  The GUI runs these calls in worker threads.

Supported formats
-----------------
* 7z                  (read/write, AES-256 password + header encryption)
* zip                 (read/write; password-protected zip can be read)
* tar                 (read/write)
* tar.gz / tar.bz2 / tar.xz (read/write)
* gz / bz2 / xz       (single-file compression / decompression)
"""

from __future__ import annotations

import bz2
import gzip
import io
import lzma
import os
import shutil
import tarfile
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Callable, Iterable

import py7zr

from .entries import Entry, normalize_name, selected_member_names
from .formats import (
    ARCHIVE_FORMATS,
    base_name_for_extract,
    detect_format,
    format_for,
    split_base_path,
    split_part_paths,
)

ProgressFn = Callable[[int, int, str], None]


def _noop_progress(current: int, total: int, message: str) -> None:
    return None


class ArchiveError(Exception):
    """A recoverable archive operation error."""


class PasswordRequiredError(ArchiveError):
    """The archive needs a password (or the supplied one is wrong)."""


class OperationCancelled(ArchiveError):
    """The user cancelled a running operation."""


def _check_cancel(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise OperationCancelled("Operation cancelled by the user")


def _report(progress: ProgressFn | None, current: int, total: int, message: str) -> None:
    if progress is not None:
        try:
            progress(current, total, message)
        except Exception:
            pass


def _chunked_copy(
    source,
    target,
    total_bytes: int = 0,
    progress: ProgressFn | None = None,
    cancel: threading.Event | None = None,
    message: str = "",
    offset: int = 0,
    grand_total: int = 0,
) -> int:
    """Copy a stream while reporting progress and honouring cancellation."""
    chunk_size = 1024 * 1024
    written = 0
    while True:
        _check_cancel(cancel)
        block = source.read(chunk_size)
        if not block:
            break
        target.write(block)
        written += len(block)
        if progress is not None and total_bytes > 0:
            if grand_total:
                _report(progress, offset + written, grand_total, message)
            else:
                _report(progress, written, total_bytes, message)
    return written


def _safe_target(destination: str, member: str) -> str:
    """Join an archive member name to a destination, blocking traversal."""
    member = normalize_name(member)
    if not member:
        return destination
    parts = member.split("/")
    if any(part in ("..", "") for part in parts):
        raise ArchiveError(f"Unsafe archive path: {member!r}")
    target = os.path.join(destination, *parts)
    real_dest = os.path.realpath(destination)
    real_target = os.path.realpath(target)
    try:
        if os.path.commonpath([real_dest, real_target]) != real_dest:
            raise ArchiveError(f"Unsafe archive path: {member!r}")
    except ValueError as exc:
        raise ArchiveError(f"Unsafe archive path: {member!r}") from exc
    return target


def _arcname(path: str, root: str) -> str:
    relative = os.path.relpath(path, root)
    if relative in (".", ""):
        relative = os.path.basename(path)
    return relative.replace("\\", "/").lstrip("/")


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _is_within(path: str, base: str) -> bool:
    """True when *path* is inside (or equals) the *base* directory."""
    try:
        if _norm(path) == _norm(base):
            return True
        return os.path.commonpath([_norm(path), _norm(base)]) == _norm(base)
    except ValueError:
        return False


def _walk_items(
    items: Iterable[str], arc_root: str, exclude: set[str] | None = None
):
    """Yield ``(absolute_path, archive_name, is_dir)`` for every item.

    ``exclude`` prevents the target archive (or its staging file) from being
    added to itself when the destination lives inside a selected folder.
    """
    excluded = {_norm(path) for path in (exclude or ())}
    for item in items:
        absolute = os.path.abspath(item)
        if not os.path.exists(absolute) or _norm(absolute) in excluded:
            continue
        name = _arcname(absolute, arc_root)
        if os.path.isdir(absolute):
            yield absolute, name, True
            for root, dirs, files in os.walk(absolute):
                dirs.sort()
                files.sort()
                for directory in dirs:
                    path = os.path.join(root, directory)
                    if _norm(path) in excluded:
                        continue
                    yield path, _arcname(path, arc_root), True
                for filename in files:
                    path = os.path.join(root, filename)
                    if _norm(path) in excluded:
                        continue
                    yield path, _arcname(path, arc_root), False
        else:
            yield absolute, name, False


def _count_files(items: Iterable[str]) -> int:
    total = 0
    for item in items:
        if os.path.isdir(item):
            for _root, _dirs, files in os.walk(item):
                total += len(files)
        elif os.path.exists(item):
            total += 1
    return total


def _count_bytes(items: Iterable[str]) -> int:
    total = 0
    for item in items:
        if os.path.isdir(item):
            for root, _dirs, files in os.walk(item):
                for filename in files:
                    try:
                        total += os.path.getsize(os.path.join(root, filename))
                    except OSError:
                        pass
        elif os.path.isfile(item):
            try:
                total += os.path.getsize(item)
            except OSError:
                pass
    return total


try:  # py7zr helper used to keep source timestamps with ``writef``.
    from py7zr.helpers import ArchiveTimestamp as _ArchiveTimestamp
except Exception:  # pragma: no cover - defensive across py7zr versions
    _ArchiveTimestamp = None


class _ProgressReader(io.BufferedIOBase):
    """File wrapper that reports consumed bytes back to the UI."""

    def __init__(self, handle, callback) -> None:
        self._handle = handle
        self._callback = callback
        self.name = getattr(handle, "name", "")

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._handle.tell()

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        return self._handle.seek(offset, whence)

    def read(self, size: int = -1) -> bytes:
        data = self._handle.read(size)
        if data:
            self._callback(len(data))
        return data

    def readinto(self, buffer) -> int:
        data = self._handle.read(len(buffer))
        buffer[:len(data)] = data
        if data:
            self._callback(len(data))
        return len(data)

    def close(self) -> None:
        try:
            self._handle.close()
        finally:
            super().close()


def _map_error(exc: Exception) -> ArchiveError:
    if isinstance(exc, ArchiveError):
        return exc
    if isinstance(exc, OperationCancelled):
        return exc
    password_errors = (py7zr.exceptions.PasswordRequired,)
    if isinstance(exc, password_errors):
        return PasswordRequiredError(str(exc) or "Password required")
    message = str(exc)
    lowered = message.lower()
    if "password" in lowered or "encrypted" in lowered:
        return PasswordRequiredError(message)
    return ArchiveError(message or exc.__class__.__name__)


# ---------------------------------------------------------------------------
# py7zr progress bridge
# ---------------------------------------------------------------------------
try:  # pragma: no cover - import shim across py7zr versions
    from py7zr.callbacks import ExtractCallback as _ExtractCallback
except Exception:  # pragma: no cover
    class _ExtractCallback:  # type: ignore[no-redef]
        pass


class _SevenZipProgress(_ExtractCallback):  # type: ignore[misc]
    def __init__(
        self,
        total: int,
        progress: ProgressFn | None,
        cancel: threading.Event | None,
    ) -> None:
        self.total = max(total, 1)
        self.current = 0
        self.progress = progress
        self.cancel = cancel

    def report_start_preparation(self) -> None:
        _report(self.progress, 0, self.total, "")

    def report_start(self, processing_file_path: str, processing_bytes: str) -> None:
        _check_cancel(self.cancel)
        _report(
            self.progress,
            self.current,
            self.total,
            os.path.basename(processing_file_path or ""),
        )

    def report_update(self, decompressed_bytes: str) -> None:
        _check_cancel(self.cancel)

    def report_end(self, processing_file_path: str, wrote_bytes: str) -> None:
        self.current += 1
        _report(
            self.progress,
            min(self.current, self.total),
            self.total,
            os.path.basename(processing_file_path or ""),
        )

    def report_warning(self, message: str) -> None:
        return None

    def report_postprocess(self) -> None:
        return None


class ArchiveEngine:
    """Stateless facade over the supported archive formats."""

    # ------------------------------------------------------------------
    # Split-volume helpers
    # ------------------------------------------------------------------
    def _materialize_split(self, path: str) -> tuple[str, str] | None:
        """Reassemble ``archive.7z.001`` style volumes into a temp file."""
        base = split_base_path(path)
        if not base:
            return None
        parts = split_part_paths(base)
        if not parts:
            raise ArchiveError(f"Split volumes not found: {base}.001")
        if not parts[0].lower().endswith(".001"):
            raise ArchiveError("The first volume (.001) is missing")
        temp_dir = tempfile.mkdtemp(prefix="py7zip-vol-")
        full_path = os.path.join(temp_dir, os.path.basename(base))
        try:
            with open(full_path, "wb") as target:
                for part in parts:
                    with open(part, "rb") as source:
                        shutil.copyfileobj(source, target, 1024 * 1024)
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        return full_path, temp_dir

    @staticmethod
    def _cleanup_split(temp_dir: str) -> None:
        shutil.rmtree(temp_dir, ignore_errors=True)

    def _split_archive(
        self,
        path: str,
        part_size: int,
        progress: ProgressFn | None = None,
        cancel: threading.Event | None = None,
    ) -> None:
        total = os.path.getsize(path)
        if part_size <= 0 or total <= part_size:
            return
        count = max(1, (total + part_size - 1) // part_size)
        width = max(3, len(str(count)))
        created: list[str] = []
        try:
            with open(path, "rb") as source:
                written = 0
                index = 1
                while True:
                    _check_cancel(cancel)
                    chunk = source.read(part_size)
                    if not chunk:
                        break
                    part = f"{path}.{index:0{width}d}"
                    with open(part, "wb") as target:
                        target.write(chunk)
                    created.append(part)
                    written += len(chunk)
                    _report(progress, written, total, "split")
                    index += 1
            os.remove(path)
            # Remove stale volumes from a previous, larger split set.
            new_set = {_norm(item) for item in created}
            for old in split_part_paths(path):
                if _norm(old) not in new_set:
                    try:
                        os.remove(old)
                    except OSError:
                        pass
        except Exception:
            for part in created:
                try:
                    os.remove(part)
                except OSError:
                    pass
            raise

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------
    def list_archive(
        self, path: str, password: str | None = None
    ) -> list[Entry]:
        resolved = self._materialize_split(path)
        if resolved:
            full, temp = resolved
            try:
                return self.list_archive(full, password=password)
            finally:
                self._cleanup_split(temp)
        fmt_key = detect_format(path)
        if not fmt_key:
            raise ArchiveError(f"Unsupported archive format: {path}")
        fmt = ARCHIVE_FORMATS[fmt_key]
        try:
            if fmt.kind == "7z":
                return self._list_7z(path, password)
            if fmt.kind == "zip":
                return self._list_zip(path)
            if fmt.kind == "tar":
                return self._list_tar(path)
            return self._list_single(path, fmt_key)
        except Exception as exc:  # noqa: BLE001 - normalised for the UI
            raise _map_error(exc) from exc

    def _list_7z(self, path: str, password: str | None) -> list[Entry]:
        entries: list[Entry] = []
        with py7zr.SevenZipFile(path, "r", password=password or None) as archive:
            for info in archive.list():
                name = normalize_name(info.filename)
                timestamp = None
                if info.creationtime is not None:
                    try:
                        timestamp = info.creationtime.timestamp()
                    except (OSError, ValueError, OverflowError):
                        timestamp = None
                entries.append(
                    Entry(
                        name=name,
                        is_dir=bool(info.is_directory),
                        size=int(info.uncompressed or 0),
                        packed=int(info.compressed or 0),
                        mtime=timestamp,
                        crc=(f"{int(info.crc32) & 0xFFFFFFFF:08X}"
                             if info.crc32 is not None else None),
                        is_symlink=bool(getattr(info, "is_symlink", False)),
                        encrypted=bool(archive.needs_password()),
                    )
                )
        return entries

    def _list_zip(self, path: str) -> list[Entry]:
        entries: list[Entry] = []
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                timestamp = None
                try:
                    timestamp = time.mktime(info.date_time + (0, 0, -1))
                except (OverflowError, ValueError):
                    timestamp = None
                entries.append(
                    Entry(
                        name=normalize_name(info.filename),
                        is_dir=info.is_dir(),
                        size=int(info.file_size),
                        packed=int(info.compress_size),
                        mtime=timestamp,
                        crc=f"{info.CRC & 0xFFFFFFFF:08X}",
                        method=_zip_method_name(info.compress_type),
                        encrypted=bool(info.flag_bits & 0x1),
                    )
                )
        return entries

    def _list_tar(self, path: str) -> list[Entry]:
        entries: list[Entry] = []
        with tarfile.open(path, "r:*") as archive:
            for member in archive.getmembers():
                entries.append(
                    Entry(
                        name=normalize_name(member.name),
                        is_dir=member.isdir(),
                        size=int(member.size) if member.isfile() else 0,
                        packed=int(member.size) if member.isfile() else 0,
                        mtime=float(member.mtime or 0) or None,
                        is_symlink=member.issym() or member.islnk(),
                    )
                )
        return entries

    def _list_single(self, path: str, fmt_key: str) -> list[Entry]:
        name = os.path.basename(base_name_for_extract(path))
        stat = os.stat(path)
        return [
            Entry(
                name=name,
                is_dir=False,
                size=int(stat.st_size),
                packed=int(stat.st_size),
                mtime=stat.st_mtime,
                method=fmt_key,
            )
        ]

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    def create_archive(
        self,
        archive_path: str,
        items: list[str],
        fmt_key: str | None = None,
        arc_root: str | None = None,
        password: str | None = None,
        level: int = 5,
        method: str = "LZMA2",
        encrypt_header: bool = False,
        progress: ProgressFn | None = None,
        cancel: threading.Event | None = None,
        part_size: int | None = None,
    ) -> None:
        if part_size is not None and part_size > 0:
            if part_size < 1024 * 1024:
                raise ArchiveError("Part size must be at least 1 MB")
        fmt_key = fmt_key or detect_format(archive_path)
        if not fmt_key or fmt_key not in ARCHIVE_FORMATS:
            raise ArchiveError(f"Unsupported archive format: {archive_path}")
        fmt = ARCHIVE_FORMATS[fmt_key]
        if not fmt.can_create:
            raise ArchiveError(f"Format {fmt.label} cannot be created")
        if not items:
            raise ArchiveError("No items selected")

        final_path = os.path.abspath(archive_path)
        cleaned: list[str] = []
        for item in items:
            absolute = os.path.abspath(item)
            if not os.path.exists(absolute):
                continue
            if _norm(absolute) == _norm(final_path):
                # The user selected the archive that is about to be written.
                continue
            cleaned.append(absolute)
        if not cleaned:
            raise ArchiveError("No items selected")
        items = cleaned

        arc_root = arc_root or os.path.dirname(items[0])
        level = max(0, min(9, int(level)))

        directory = os.path.dirname(final_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        if os.path.isdir(final_path):
            raise ArchiveError("Destination path is a directory")

        # Never write the archive inside a folder that is being archived.
        # Otherwise py7zr reads the growing archive itself, which can hang
        # or produce an archive with an invalid header.
        staging_dir: str | None = None
        target_path = final_path
        backup_path: str | None = None
        inside_sources = any(
            os.path.isdir(item) and _is_within(final_path, item)
            for item in items
        )
        if inside_sources:
            # Prefer a temporary folder on the same volume but outside the
            # source tree: the old archive can then be moved with a fast
            # rename instead of being copied to another drive.
            staging_parent = tempfile.gettempdir()
            current = directory or os.getcwd()
            while current:
                if not any(
                    os.path.isdir(item) and _is_within(current, item)
                    for item in items
                ):
                    staging_parent = current
                    break
                parent = os.path.dirname(current)
                if parent == current:
                    break
                current = parent
            try:
                staging_dir = tempfile.mkdtemp(
                    prefix="py7zip-create-", dir=staging_parent
                )
            except OSError:
                staging_dir = tempfile.mkdtemp(prefix="py7zip-create-")
            target_path = os.path.join(
                staging_dir, os.path.basename(final_path)
            )
            # Move a previous archive out of the source tree so it is not
            # added to the new archive when overwriting.
            if os.path.isfile(final_path):
                backup_path = os.path.join(
                    staging_dir, "previous-archive.bak"
                )
                shutil.move(final_path, backup_path)

        def restore_backup() -> None:
            if backup_path and os.path.exists(backup_path):
                try:
                    os.makedirs(directory, exist_ok=True)
                    shutil.move(backup_path, final_path)
                except OSError:
                    pass

        try:
            if fmt.kind == "7z":
                self._create_7z(
                    target_path, items, arc_root, password, level, method,
                    encrypt_header, progress, cancel,
                )
            elif fmt.kind == "zip":
                self._create_zip(
                    target_path, items, arc_root, level, method, progress,
                    cancel, exclude={final_path, target_path},
                )
            elif fmt.kind == "tar":
                self._create_tar(
                    target_path, items, arc_root, fmt.tar_mode, progress,
                    cancel, exclude={final_path, target_path},
                )
            else:
                self._create_single(
                    target_path, items, fmt.kind, level, progress, cancel
                )
        except Exception as exc:  # noqa: BLE001
            try:
                if os.path.exists(target_path) and os.path.getsize(target_path) == 0:
                    os.remove(target_path)
            except OSError:
                pass
            restore_backup()
            if staging_dir:
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise _map_error(exc) from exc

        if staging_dir:
            try:
                os.makedirs(directory, exist_ok=True)
                if os.path.exists(final_path):
                    os.remove(final_path)
                shutil.move(target_path, final_path)
            except Exception as exc:  # noqa: BLE001
                restore_backup()
                raise _map_error(exc) from exc
            finally:
                shutil.rmtree(staging_dir, ignore_errors=True)

        if part_size and part_size > 0:
            self._split_archive(final_path, int(part_size), progress, cancel)
        if os.path.exists(final_path):
            # A previous split volume set is stale now that a full archive
            # (or a single small volume) has been written.
            for old in split_part_paths(final_path):
                try:
                    os.remove(old)
                except OSError:
                    pass

    def _create_7z(
        self,
        archive_path: str,
        items: list[str],
        arc_root: str,
        password: str | None,
        level: int,
        method: str,
        encrypt_header: bool,
        progress: ProgressFn | None,
        cancel: threading.Event | None,
    ) -> None:
        # ``py7zr`` exposes the codec IDs as module constants, but the exact
        # set differs between releases, so resolve them defensively.
        # Brotli/Zstd are py7zr extensions that mainline 7-Zip cannot read.
        # Keep archives interoperable by falling back to LZMA2.
        if method in ("Brotli", "Zstd"):
            method = "LZMA2"

        method_names = {
            "LZMA2": "FILTER_LZMA2",
            "LZMA": "FILTER_LZMA",
            "Deflate": "FILTER_DEFLATE",
            "BZip2": "FILTER_BZIP2",
            "PPMD": "FILTER_PPMD",
            "Copy": "FILTER_COPY",
            "Brotli": "FILTER_BROTLI",
            "Zstd": "FILTER_ZSTD",
            # 7z has no standalone XZ codec; LZMA2 is the closest equivalent.
            "XZ": "FILTER_LZMA2",
        }
        constant = method_names.get(method, "FILTER_LZMA2")
        filter_id = getattr(py7zr, constant, py7zr.FILTER_LZMA2)
        if constant == "FILTER_COPY":
            filters = [{"id": filter_id}]
        else:
            filters = [{"id": filter_id, "preset": level}]

        kwargs: dict = {"password": password or None}
        if password and encrypt_header:
            kwargs["header_encryption"] = True

        total_bytes = max(_count_bytes(items), 1)
        processed = 0

        with py7zr.SevenZipFile(
            archive_path, "w", filters=filters, **kwargs
        ) as archive:
            for absolute, name, is_dir in _walk_items(
                items, arc_root, exclude={archive_path}
            ):
                _check_cancel(cancel)
                if is_dir:
                    archive.write(absolute, name)
                    continue

                label = os.path.basename(absolute)
                _report(
                    progress, min(processed, total_bytes), total_bytes, label
                )

                if progress is None:
                    # No UI callback: ``write`` preserves all metadata.
                    archive.write(absolute, name)
                    continue

                stat = os.stat(absolute)
                if os.path.islink(absolute):
                    archive.write(absolute, name)
                    processed += int(stat.st_size)
                    _report(
                        progress, min(processed, total_bytes),
                        total_bytes, label,
                    )
                    continue

                def on_read(count: int, _label: str = label) -> None:
                    nonlocal processed
                    # Allows the Cancel button to abort a single large file.
                    _check_cancel(cancel)
                    processed += count
                    _report(
                        progress, min(processed, total_bytes),
                        total_bytes, _label,
                    )

                with open(absolute, "rb") as handle:
                    archive.writef(_ProgressReader(handle, on_read), name)

                # ``writef`` uses "now" for timestamps; restore the source
                # metadata on the file-info entry it just appended.
                if _ArchiveTimestamp is not None:
                    try:
                        info = archive.header.files_info.files[-1]
                        info["lastwritetime"] = _ArchiveTimestamp.from_datetime(
                            stat.st_mtime
                        )
                        info["creationtime"] = _ArchiveTimestamp.from_datetime(
                            stat.st_ctime
                        )
                        info["lastaccesstime"] = _ArchiveTimestamp.from_datetime(
                            stat.st_atime
                        )
                    except Exception:
                        pass

            _report(progress, total_bytes, total_bytes, "done")

    def _create_zip(
        self,
        archive_path: str,
        items: list[str],
        arc_root: str,
        level: int,
        method: str,
        progress: ProgressFn | None,
        cancel: threading.Event | None,
        exclude: set[str] | None = None,
    ) -> None:
        compression_map = {
            "Deflate": zipfile.ZIP_DEFLATED,
            "Store": zipfile.ZIP_STORED,
            "Copy": zipfile.ZIP_STORED,
            "BZip2": zipfile.ZIP_BZIP2,
            "LZMA": zipfile.ZIP_LZMA,
        }
        compression = compression_map.get(method, zipfile.ZIP_DEFLATED)
        total = max(_count_files(items), 1)
        current = 0
        kwargs = {"compression": compression}
        if compression in (zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2):
            kwargs["compresslevel"] = max(0, min(9, level))
        with zipfile.ZipFile(archive_path, "w", **kwargs) as archive:
            for absolute, name, is_dir in _walk_items(items, arc_root, exclude):
                _check_cancel(cancel)
                if is_dir:
                    archive.writestr(name.rstrip("/") + "/", b"")
                    continue
                archive.write(absolute, name)
                current += 1
                _report(progress, current, total, os.path.basename(absolute))

    def _create_tar(
        self,
        archive_path: str,
        items: list[str],
        arc_root: str,
        tar_mode: str,
        progress: ProgressFn | None,
        cancel: threading.Event | None,
        exclude: set[str] | None = None,
    ) -> None:
        total = max(_count_files(items), 1)
        current = 0
        with tarfile.open(archive_path, tar_mode) as archive:
            for absolute, name, is_dir in _walk_items(items, arc_root, exclude):
                _check_cancel(cancel)
                archive.add(absolute, arcname=name, recursive=False)
                if not is_dir:
                    current += 1
                    _report(progress, current, total, os.path.basename(absolute))

    def _create_single(
        self,
        archive_path: str,
        items: list[str],
        kind: str,
        level: int,
        progress: ProgressFn | None,
        cancel: threading.Event | None,
    ) -> None:
        if len(items) != 1 or not os.path.isfile(items[0]):
            raise ArchiveError("This format can only compress a single file")
        source = items[0]
        total = os.path.getsize(source)
        if kind == "gzip":
            opener = lambda: gzip.open(archive_path, "wb", compresslevel=max(1, level))
        elif kind == "bzip2":
            opener = lambda: bz2.open(archive_path, "wb", compresslevel=max(1, min(9, level)))
        elif kind == "xz":
            opener = lambda: lzma.open(archive_path, "wb", preset=max(0, min(9, level)))
        else:  # pragma: no cover - defensive
            raise ArchiveError(f"Unsupported single-file format: {kind}")

        with open(source, "rb") as src, opener() as dst:
            _chunked_copy(
                src, dst, total, progress, cancel,
                message=os.path.basename(source),
            )

    # ------------------------------------------------------------------
    # Extract
    # ------------------------------------------------------------------
    def extract_archive(
        self,
        archive_path: str,
        destination: str,
        members: list[str] | None = None,
        password: str | None = None,
        overwrite: bool = True,
        progress: ProgressFn | None = None,
        cancel: threading.Event | None = None,
    ) -> None:
        resolved = self._materialize_split(archive_path)
        if resolved:
            full, temp = resolved
            try:
                self.extract_archive(
                    full, destination, members, password, overwrite,
                    progress, cancel,
                )
                return
            finally:
                self._cleanup_split(temp)
        fmt_key = detect_format(archive_path)
        if not fmt_key:
            raise ArchiveError(f"Unsupported archive format: {archive_path}")
        fmt = ARCHIVE_FORMATS[fmt_key]
        os.makedirs(destination, exist_ok=True)
        try:
            if fmt.kind == "7z":
                self._extract_7z(
                    archive_path, destination, members, password, progress, cancel
                )
            elif fmt.kind == "zip":
                self._extract_zip(
                    archive_path, destination, members, password, overwrite,
                    progress, cancel,
                )
            elif fmt.kind == "tar":
                self._extract_tar(
                    archive_path, destination, members, overwrite, progress, cancel
                )
            else:
                self._extract_single(
                    archive_path, destination, overwrite, progress, cancel
                )
        except Exception as exc:  # noqa: BLE001
            raise _map_error(exc) from exc

    def _extract_7z(
        self,
        archive_path: str,
        destination: str,
        members: list[str] | None,
        password: str | None,
        progress: ProgressFn | None,
        cancel: threading.Event | None,
    ) -> None:
        with py7zr.SevenZipFile(
            archive_path, "r", password=password or None
        ) as archive:
            all_entries = archive.list()
            file_names = [
                normalize_name(e.filename)
                for e in all_entries
                if e.is_file
            ]
            if members:
                wanted = {normalize_name(m) for m in members}
                targets = [name for name in file_names if name in wanted]
            else:
                targets = None
            total = len(targets) if targets is not None else len(file_names)
            callback = _SevenZipProgress(max(total, 1), progress, cancel)
            if targets is None:
                archive.extractall(path=destination, callback=callback)
            elif targets:
                archive.extract(
                    path=destination, targets=targets, callback=callback
                )

    def _extract_zip(
        self,
        archive_path: str,
        destination: str,
        members: list[str] | None,
        password: str | None,
        overwrite: bool,
        progress: ProgressFn | None,
        cancel: threading.Event | None,
    ) -> None:
        selected = {normalize_name(m) for m in members} if members else None
        pwd = password.encode("utf-8") if password else None
        with zipfile.ZipFile(archive_path) as archive:
            infos = [
                info for info in archive.infolist()
                if _member_selected(normalize_name(info.filename).rstrip("/"),
                                    info.is_dir(), selected)
            ]
            total = max(len(infos), 1)
            for index, info in enumerate(infos):
                _check_cancel(cancel)
                name = normalize_name(info.filename)
                target = _safe_target(destination, name)
                if info.is_dir():
                    os.makedirs(target, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target) or destination, exist_ok=True)
                    if not overwrite and os.path.exists(target):
                        continue
                    with archive.open(info, pwd=pwd) as source, open(target, "wb") as out:
                        _chunked_copy(source, out, info.file_size)
                _report(progress, index + 1, total, os.path.basename(name))

    def _extract_tar(
        self,
        archive_path: str,
        destination: str,
        members: list[str] | None,
        overwrite: bool,
        progress: ProgressFn | None,
        cancel: threading.Event | None,
    ) -> None:
        selected = {normalize_name(m) for m in members} if members else None
        with tarfile.open(archive_path, "r:*") as archive:
            all_members = archive.getmembers()
            chosen = [
                member for member in all_members
                if _member_selected(
                    normalize_name(member.name).rstrip("/"),
                    member.isdir(), selected,
                )
            ]
            total = max(len([m for m in chosen if m.isfile()]), 1)
            current = 0
            for member in chosen:
                _check_cancel(cancel)
                name = normalize_name(member.name)
                target = _safe_target(destination, name)
                if not overwrite and os.path.exists(target) and not member.isdir():
                    continue
                _tar_extract_member(archive, member, destination)
                if member.isfile():
                    current += 1
                _report(progress, current, total, os.path.basename(name))

    def _extract_single(
        self,
        archive_path: str,
        destination: str,
        overwrite: bool,
        progress: ProgressFn | None,
        cancel: threading.Event | None,
    ) -> None:
        output_name = os.path.basename(base_name_for_extract(archive_path)) or "output"
        target = os.path.join(destination, output_name)
        if not overwrite and os.path.exists(target):
            return
        fmt_key = detect_format(archive_path)
        opener = {"gz": gzip.open, "bz2": bz2.open, "xz": lzma.open}.get(fmt_key or "")
        if opener is None:
            raise ArchiveError(f"Unsupported format: {archive_path}")
        total = os.path.getsize(archive_path)
        with opener(archive_path, "rb") as source, open(target, "wb") as out:
            _chunked_copy(
                source, out, total, progress, cancel,
                message=os.path.basename(target),
            )

    # ------------------------------------------------------------------
    # Add / delete / test
    # ------------------------------------------------------------------
    def add_to_archive(
        self,
        archive_path: str,
        items: list[str],
        arc_root: str | None = None,
        password: str | None = None,
        level: int = 5,
        method: str = "LZMA2",
        progress: ProgressFn | None = None,
        cancel: threading.Event | None = None,
    ) -> None:
        if split_base_path(archive_path):
            raise ArchiveError(
                "Modifying split archives is not supported; join the parts first"
            )
        if not items:
            raise ArchiveError("No items selected")
        fmt_key = detect_format(archive_path)
        fmt = ARCHIVE_FORMATS.get(fmt_key or "")
        if not fmt:
            raise ArchiveError(f"Unsupported archive format: {archive_path}")
        arc_root = arc_root or os.path.dirname(os.path.abspath(items[0]))
        try:
            if fmt.kind == "7z":
                # py7zr's append mode can corrupt archives in some releases,
                # so the 7z backend rebuilds the archive safely instead.
                self._rebuild_7z(
                    archive_path,
                    add_items=items,
                    arc_root=arc_root,
                    remove_members=[],
                    password=password,
                    level=level,
                    method=method,
                    progress=progress,
                    cancel=cancel,
                )
            elif fmt.kind == "zip":
                total = max(_count_files(items), 1)
                current = 0
                with zipfile.ZipFile(
                    archive_path, "a", compression=zipfile.ZIP_DEFLATED,
                    compresslevel=max(0, min(9, level)),
                ) as archive:
                    for absolute, name, is_dir in _walk_items(
                        items, arc_root, exclude={archive_path}
                    ):
                        _check_cancel(cancel)
                        if is_dir:
                            archive.writestr(name.rstrip("/") + "/", b"")
                            continue
                        archive.write(absolute, name)
                        current += 1
                        _report(progress, current, total, os.path.basename(absolute))
            elif fmt.kind == "tar":
                self._add_tar(
                    archive_path, items, arc_root, fmt.tar_mode, progress, cancel
                )
            else:
                raise ArchiveError(
                    "Adding files is not supported for single-file formats"
                )
        except Exception as exc:  # noqa: BLE001
            raise _map_error(exc) from exc

    def _add_tar(
        self,
        archive_path: str,
        items: list[str],
        arc_root: str,
        tar_mode: str,
        progress: ProgressFn | None,
        cancel: threading.Event | None,
    ) -> None:
        temporary = archive_path + ".py7zip-tmp"
        total = max(_count_files(items), 1)
        current = 0
        try:
            with tarfile.open(archive_path, "r:*") as source, \
                    tarfile.open(temporary, tar_mode) as target:
                for member in source.getmembers():
                    _check_cancel(cancel)
                    fileobj = source.extractfile(member) if member.isfile() else None
                    target.addfile(member, fileobj)
                for absolute, name, is_dir in _walk_items(
                    items, arc_root, exclude={archive_path, temporary}
                ):
                    _check_cancel(cancel)
                    target.add(absolute, arcname=name, recursive=False)
                    if not is_dir:
                        current += 1
                        _report(progress, current, total, os.path.basename(absolute))
            os.replace(temporary, archive_path)
        finally:
            if os.path.exists(temporary):
                try:
                    os.remove(temporary)
                except OSError:
                    pass

    def delete_from_archive(
        self,
        archive_path: str,
        members: list[str],
        password: str | None = None,
        progress: ProgressFn | None = None,
        cancel: threading.Event | None = None,
    ) -> None:
        if split_base_path(archive_path):
            raise ArchiveError(
                "Modifying split archives is not supported; join the parts first"
            )
        if not members:
            return
        fmt_key = detect_format(archive_path)
        fmt = ARCHIVE_FORMATS.get(fmt_key or "")
        if not fmt:
            raise ArchiveError(f"Unsupported archive format: {archive_path}")
        try:
            if fmt.kind == "7z":
                self._delete_7z(
                    archive_path, members, password, progress, cancel
                )
            elif fmt.kind == "zip":
                self._delete_zip(archive_path, members, progress, cancel)
            elif fmt.kind == "tar":
                self._delete_tar(
                    archive_path, members, fmt.tar_mode, progress, cancel
                )
            else:
                raise ArchiveError(
                    "Deleting entries is not supported for single-file formats"
                )
        except Exception as exc:  # noqa: BLE001
            raise _map_error(exc) from exc

    def _delete_7z(
        self,
        archive_path: str,
        members: list[str],
        password: str | None,
        progress: ProgressFn | None,
        cancel: threading.Event | None,
    ) -> None:
        self._rebuild_7z(
            archive_path,
            add_items=[],
            arc_root=None,
            remove_members=members,
            password=password,
            level=5,
            method="LZMA2",
            progress=progress,
            cancel=cancel,
        )

    def _rebuild_7z(
        self,
        archive_path: str,
        add_items: list[str],
        arc_root: str | None,
        remove_members: list[str],
        password: str | None,
        level: int,
        method: str,
        progress: ProgressFn | None,
        cancel: threading.Event | None,
    ) -> None:
        """Extract, modify and re-create a 7z archive (safe update path).

        py7zr cannot reliably delete members and its append mode is not
        trustworthy on every release, therefore updates are performed by
        unpacking into a temporary folder, applying the changes and writing
        a fresh archive.
        """
        temp_dir = tempfile.mkdtemp(prefix="py7zip-rebuild-")
        temporary_archive = archive_path + ".py7zip-tmp"
        try:
            _report(progress, 0, 3, "extract")
            self.extract_archive(
                archive_path, temp_dir, password=password, cancel=cancel
            )
            _check_cancel(cancel)

            _report(progress, 1, 3, "delete")
            for member in {normalize_name(m) for m in remove_members}:
                target = _safe_target(temp_dir, member)
                if os.path.isdir(target):
                    shutil.rmtree(target, ignore_errors=True)
                elif os.path.exists(target):
                    try:
                        os.remove(target)
                    except OSError:
                        pass

            _report(progress, 2, 3, "add")
            if add_items:
                root = arc_root or os.path.dirname(os.path.abspath(add_items[0]))
                for absolute, name, is_dir in _walk_items(add_items, root):
                    _check_cancel(cancel)
                    target = _safe_target(temp_dir, name)
                    if is_dir:
                        os.makedirs(target, exist_ok=True)
                    else:
                        os.makedirs(
                            os.path.dirname(target) or temp_dir, exist_ok=True
                        )
                        shutil.copy2(absolute, target)

            _check_cancel(cancel)
            _report(progress, 3, 4, "rebuild")
            tops = [
                os.path.join(temp_dir, name)
                for name in sorted(os.listdir(temp_dir))
            ]
            if tops:
                self.create_archive(
                    temporary_archive,
                    tops,
                    fmt_key="7z",
                    arc_root=temp_dir,
                    password=password,
                    level=level,
                    method=method,
                    encrypt_header=bool(password),
                    progress=None,
                    cancel=cancel,
                )
            else:
                kwargs: dict = {"password": password or None}
                if password:
                    kwargs["header_encryption"] = True
                with py7zr.SevenZipFile(temporary_archive, "w", **kwargs):
                    pass
            os.replace(temporary_archive, archive_path)
            _report(progress, 4, 4, "done")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            if os.path.exists(temporary_archive):
                try:
                    os.remove(temporary_archive)
                except OSError:
                    pass

    def _delete_zip(
        self,
        archive_path: str,
        members: list[str],
        progress: ProgressFn | None,
        cancel: threading.Event | None,
    ) -> None:
        remove = {normalize_name(m) for m in members}
        temporary = archive_path + ".py7zip-tmp"
        try:
            with zipfile.ZipFile(archive_path) as source, \
                    zipfile.ZipFile(temporary, "w") as target:
                infos = source.infolist()
                total = max(len(infos), 1)
                for index, info in enumerate(infos):
                    _check_cancel(cancel)
                    name = normalize_name(info.filename).rstrip("/")
                    if _is_removed(name, remove):
                        _report(progress, index + 1, total, name)
                        continue
                    if info.is_dir():
                        target.writestr(info, b"")
                    else:
                        with source.open(info) as src, \
                                target.open(info, "w") as dst:
                            _chunked_copy(src, dst, info.file_size)
                    _report(progress, index + 1, total, name)
            os.replace(temporary, archive_path)
        finally:
            if os.path.exists(temporary):
                try:
                    os.remove(temporary)
                except OSError:
                    pass

    def _delete_tar(
        self,
        archive_path: str,
        members: list[str],
        tar_mode: str,
        progress: ProgressFn | None,
        cancel: threading.Event | None,
    ) -> None:
        remove = {normalize_name(m) for m in members}
        temporary = archive_path + ".py7zip-tmp"
        try:
            with tarfile.open(archive_path, "r:*") as source, \
                    tarfile.open(temporary, tar_mode) as target:
                all_members = source.getmembers()
                total = max(len(all_members), 1)
                for index, member in enumerate(all_members):
                    _check_cancel(cancel)
                    name = normalize_name(member.name).rstrip("/")
                    if _is_removed(name, remove):
                        _report(progress, index + 1, total, name)
                        continue
                    fileobj = source.extractfile(member) if member.isfile() else None
                    target.addfile(member, fileobj)
                    _report(progress, index + 1, total, name)
            os.replace(temporary, archive_path)
        finally:
            if os.path.exists(temporary):
                try:
                    os.remove(temporary)
                except OSError:
                    pass

    def test_archive(
        self,
        archive_path: str,
        password: str | None = None,
        progress: ProgressFn | None = None,
        cancel: threading.Event | None = None,
    ) -> None:
        resolved = self._materialize_split(archive_path)
        if resolved:
            full, temp = resolved
            try:
                self.test_archive(full, password, progress, cancel)
                return
            finally:
                self._cleanup_split(temp)
        fmt_key = detect_format(archive_path)
        fmt = ARCHIVE_FORMATS.get(fmt_key or "")
        if not fmt:
            raise ArchiveError(f"Unsupported archive format: {archive_path}")
        try:
            if fmt.kind == "7z":
                with py7zr.SevenZipFile(
                    archive_path, "r", password=password or None
                ) as archive:
                    entries = archive.list()
                    result = archive.test()
                if result is False:
                    raise ArchiveError("Archive integrity check failed")
                _report(progress, len(entries), max(len(entries), 1), "done")
            elif fmt.kind == "zip":
                with zipfile.ZipFile(archive_path) as archive:
                    bad = archive.testzip()
                    if bad:
                        raise ArchiveError(f"CRC error in: {bad}")
                    count = len(archive.infolist())
                _report(progress, count, max(count, 1), "done")
            elif fmt.kind == "tar":
                with tarfile.open(archive_path, "r:*") as archive:
                    members = [m for m in archive.getmembers() if m.isfile()]
                    total = max(len(members), 1)
                    for index, member in enumerate(members):
                        _check_cancel(cancel)
                        fileobj = archive.extractfile(member)
                        if fileobj is None:
                            raise ArchiveError(f"Cannot read: {member.name}")
                        while True:
                            _check_cancel(cancel)
                            block = fileobj.read(1024 * 1024)
                            if not block:
                                break
                        _report(progress, index + 1, total, member.name)
            else:
                fmt_key_inner = detect_format(archive_path)
                opener = {"gz": gzip.open, "bz2": bz2.open, "xz": lzma.open}.get(
                    fmt_key_inner or ""
                )
                if opener is None:
                    raise ArchiveError("Unsupported format")
                with opener(archive_path, "rb") as source:
                    while True:
                        _check_cancel(cancel)
                        if not source.read(1024 * 1024):
                            break
                _report(progress, 1, 1, "done")
        except Exception as exc:  # noqa: BLE001
            raise _map_error(exc) from exc

    # ------------------------------------------------------------------
    # Reading a single member (preview)
    # ------------------------------------------------------------------
    def read_member(
        self,
        archive_path: str,
        member: str,
        password: str | None = None,
        limit: int = 1024 * 1024,
    ) -> bytes:
        resolved = self._materialize_split(archive_path)
        if resolved:
            full, temp = resolved
            try:
                return self.read_member(full, member, password, limit)
            finally:
                self._cleanup_split(temp)
        fmt_key = detect_format(archive_path)
        fmt = ARCHIVE_FORMATS.get(fmt_key or "")
        if not fmt:
            raise ArchiveError(f"Unsupported archive format: {archive_path}")
        try:
            if fmt.kind == "7z":
                temp_dir = tempfile.mkdtemp(prefix="py7zip-read-")
                try:
                    with py7zr.SevenZipFile(
                        archive_path, "r", password=password or None
                    ) as archive:
                        archive.extract(
                            path=temp_dir, targets=[normalize_name(member)]
                        )
                    target = _safe_target(temp_dir, member)
                    with open(target, "rb") as fh:
                        return fh.read(limit)
                finally:
                    shutil.rmtree(temp_dir, ignore_errors=True)
            if fmt.kind == "zip":
                with zipfile.ZipFile(archive_path) as archive:
                    pwd = password.encode("utf-8") if password else None
                    with archive.open(normalize_name(member), pwd=pwd) as fh:
                        return fh.read(limit)
            if fmt.kind == "tar":
                with tarfile.open(archive_path, "r:*") as archive:
                    fh = archive.extractfile(normalize_name(member))
                    if fh is None:
                        raise ArchiveError(f"Cannot read: {member}")
                    return fh.read(limit)
            opener = {"gzip": gzip.open, "bzip2": bz2.open, "xz": lzma.open}.get(
                fmt.kind
            )
            if opener is None:
                raise ArchiveError("Unsupported format")
            with opener(archive_path, "rb") as fh:
                return fh.read(limit)
        except Exception as exc:  # noqa: BLE001
            raise _map_error(exc) from exc

    def extract_member(
        self,
        archive_path: str,
        member: str,
        destination: str,
        password: str | None = None,
    ) -> str:
        """Extract one member into *destination* and return its path."""
        resolved = self._materialize_split(archive_path)
        if resolved:
            full, temp = resolved
            try:
                return self.extract_member(
                    full, member, destination, password
                )
            finally:
                self._cleanup_split(temp)
        os.makedirs(destination, exist_ok=True)
        fmt_key = detect_format(archive_path)
        fmt = ARCHIVE_FORMATS.get(fmt_key or "")
        if not fmt:
            raise ArchiveError(f"Unsupported archive format: {archive_path}")
        try:
            if fmt.kind in ("7z", "tar"):
                if fmt.kind == "7z":
                    with py7zr.SevenZipFile(
                        archive_path, "r", password=password or None
                    ) as archive:
                        archive.extract(
                            path=destination, targets=[normalize_name(member)]
                        )
                else:
                    with tarfile.open(archive_path, "r:*") as archive:
                        info = archive.getmember(normalize_name(member))
                        fileobj = archive.extractfile(info)
                        target = _safe_target(destination, member)
                        os.makedirs(os.path.dirname(target) or destination, exist_ok=True)
                        with open(target, "wb") as out:
                            _chunked_copy(fileobj, out, info.size)
                        return target
                return _safe_target(destination, member)
            if fmt.kind == "zip":
                with zipfile.ZipFile(archive_path) as archive:
                    pwd = password.encode("utf-8") if password else None
                    info = archive.getinfo(normalize_name(member))
                    target = _safe_target(destination, member)
                    os.makedirs(os.path.dirname(target) or destination, exist_ok=True)
                    with archive.open(info, pwd=pwd) as src, open(target, "wb") as out:
                        _chunked_copy(src, out, info.file_size)
                    return target
            # Single-file formats.
            output = os.path.join(
                destination,
                os.path.basename(base_name_for_extract(archive_path)) or "output",
            )
            self._extract_single(archive_path, destination, True, None, None)
            return output
        except Exception as exc:  # noqa: BLE001
            raise _map_error(exc) from exc

    # ------------------------------------------------------------------
    # Informational helpers
    # ------------------------------------------------------------------
    def is_valid_archive(
        self, path: str, password: str | None = None
    ) -> bool:
        try:
            self.list_archive(path, password=password)
            return True
        except Exception:
            return False

    def needs_password(self, path: str) -> bool:
        resolved = self._materialize_split(path)
        if resolved:
            full, temp = resolved
            try:
                return self.needs_password(full)
            finally:
                self._cleanup_split(temp)
        fmt_key = detect_format(path)
        if fmt_key == "7z":
            try:
                with py7zr.SevenZipFile(path, "r") as archive:
                    return bool(archive.needs_password())
            except py7zr.exceptions.PasswordRequired:
                return True
            except Exception:
                return False
        if fmt_key == "zip":
            try:
                with zipfile.ZipFile(path) as archive:
                    return any(info.flag_bits & 0x1 for info in archive.infolist())
            except Exception:
                return False
        return False

    def archive_info(
        self, path: str, password: str | None = None
    ) -> dict:
        resolved = self._materialize_split(path)
        if resolved:
            full, temp = resolved
            try:
                info = self.archive_info(full, password=password)
                base = split_base_path(path) or path
                info["path"] = os.path.abspath(path)
                info["name"] = os.path.basename(base)
                info["split"] = True
                info["size_on_disk"] = sum(
                    os.path.getsize(part)
                    for part in split_part_paths(base)
                )
                return info
            finally:
                self._cleanup_split(temp)
        fmt_key = detect_format(path) or ""
        fmt = ARCHIVE_FORMATS.get(fmt_key)
        entries = self.list_archive(path, password=password)
        files = [e for e in entries if not e.is_dir]
        folders = [e for e in entries if e.is_dir]
        unpacked = sum(e.size for e in files)
        packed = sum(e.packed for e in files) or os.path.getsize(path)
        methods: list[str] = []
        if fmt and fmt.kind == "7z":
            try:
                with py7zr.SevenZipFile(
                    path, "r", password=password or None
                ) as archive:
                    info = archive.archiveinfo()
                    methods = list(info.method_names or [])
            except Exception:
                methods = []
        elif fmt and fmt.kind == "zip":
            seen: list[str] = []
            try:
                with zipfile.ZipFile(path) as archive:
                    for info in archive.infolist():
                        name = _zip_method_name(info.compress_type)
                        if name not in seen:
                            seen.append(name)
                methods = seen
            except Exception:
                methods = []
        elif fmt and fmt.kind == "tar":
            methods = ["Tar"]
            if fmt.tar_mode.endswith("gz"):
                methods.append("Gzip")
            elif fmt.tar_mode.endswith("bz2"):
                methods.append("Bzip2")
            elif fmt.tar_mode.endswith("xz"):
                methods.append("Xz")
        stat = os.stat(path)
        return {
            "path": os.path.abspath(path),
            "name": os.path.basename(path),
            "format": fmt.label if fmt else fmt_key,
            "format_key": fmt_key,
            "count": len(entries),
            "files": len(files),
            "folders": len(folders),
            "unpacked": unpacked,
            "packed": packed,
            "ratio": (packed / unpacked * 100.0) if unpacked else 0.0,
            "encrypted": self.needs_password(path) if password is None else True,
            "methods": methods,
            "mtime": stat.st_mtime,
            "size_on_disk": stat.st_size,
            "split": False,
        }


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------
def _zip_method_name(compress_type: int) -> str:
    return {
        zipfile.ZIP_STORED: "Store",
        zipfile.ZIP_DEFLATED: "Deflate",
        zipfile.ZIP_BZIP2: "BZip2",
        zipfile.ZIP_LZMA: "LZMA",
    }.get(compress_type, f"Method {compress_type}")


def _member_selected(name: str, is_dir: bool, selected: set[str] | None) -> bool:
    if selected is None:
        return True
    if name in selected:
        return True
    # Include directory entries that are parents of a selected member.
    for chosen in selected:
        if chosen.startswith(name + "/"):
            return True
    return False


def _is_removed(name: str, remove: set[str]) -> bool:
    if name in remove:
        return True
    for chosen in remove:
        if name.startswith(chosen + "/"):
            return True
    return False


def _tar_extract_member(
    archive: tarfile.TarFile, member: tarfile.TarInfo, destination: str
) -> None:
    """Extract a single tar member using the safest available filter."""
    try:
        archive.extract(member, path=destination, filter="data")
    except TypeError:  # Python < 3.12 has no filter parameter
        archive.extract(member, path=destination)


def expand_selection(entries: list[Entry], names: set[str]) -> list[str]:
    """Public helper used by the UI to expand folder selections."""
    return selected_member_names(entries, names, recursive=True)
