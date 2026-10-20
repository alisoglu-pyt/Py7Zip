"""Self test bundled with the application (used to validate frozen builds).

Run from source with ``python -m py7zip --selftest`` or from the packaged
executable with ``Py7Zip.exe --selftest``.  The exit code is 0 on success and
1 on failure; a detailed log is written to the temporary directory as well.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import traceback
from pathlib import Path

from .engine import (
    ArchiveEngine,
    PasswordRequiredError,
    split_part_paths,
)
from .i18n import I18N, LANGUAGES


def _write_log(lines: list[str]) -> str:
    path = os.path.join(tempfile.gettempdir(), "py7zip-selftest.log")
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError:
        pass
    return path


def run_selftest() -> int:
    lines: list[str] = ["Py7-Zip self test"]
    failures = 0
    work = Path(tempfile.mkdtemp(prefix="py7zip-selftest-"))
    try:
        source = work / "source"
        (source / "sub").mkdir(parents=True)
        (source / "hello.txt").write_text("hello world\n" * 100, encoding="utf-8")
        (source / "sub" / "data.bin").write_bytes(bytes(range(256)) * 20)

        engine = ArchiveEngine()
        formats = {
            "7z": "sample.7z",
            "zip": "sample.zip",
            "tar": "sample.tar",
            "tar.gz": "sample.tar.gz",
            "gz": "single.txt.gz",
        }
        for fmt, filename in formats.items():
            archive = work / filename
            try:
                items = (
                    [str(source / "hello.txt")]
                    if fmt == "gz"
                    else [str(source / "hello.txt"), str(source / "sub")]
                )
                engine.create_archive(
                    str(archive),
                    items,
                    fmt_key=fmt,
                    arc_root=str(source),
                    level=5,
                    method="LZMA2" if fmt == "7z" else "Deflate",
                )
                entries = engine.list_archive(str(archive))
                assert entries, f"{fmt}: empty listing"
                if fmt != "gz":
                    engine.add_to_archive(
                        str(archive),
                        [str(source / "sub" / "data.bin")],
                        arc_root=str(work),
                    )
                    engine.delete_from_archive(
                        str(archive), ["data.bin"]
                    )
                dest = work / f"out-{fmt.replace('.', '_')}"
                engine.extract_archive(str(archive), str(dest))
                engine.test_archive(str(archive))
                lines.append(f"[OK]   {fmt}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                lines.append(f"[FAIL] {fmt}: {exc}")
                lines.append(traceback.format_exc())

        # Encrypted 7z round-trip.
        try:
            secret = work / "secret.7z"
            engine.create_archive(
                str(secret),
                [str(source / "hello.txt")],
                fmt_key="7z",
                arc_root=str(source),
                password="s3cret",
                encrypt_header=True,
            )
            try:
                engine.list_archive(str(secret))
            except PasswordRequiredError:
                pass
            else:
                raise AssertionError("encrypted archive was listed without a password")
            entries = engine.list_archive(str(secret), password="s3cret")
            assert entries, "encrypted listing empty"
            out = work / "secret-out"
            engine.extract_archive(str(secret), str(out), password="s3cret")
            assert (out / "hello.txt").read_text(encoding="utf-8").startswith("hello")
            engine.test_archive(str(secret), password="s3cret")
            lines.append("[OK]   7z AES-256 encryption")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            lines.append(f"[FAIL] 7z encryption: {exc}")
            lines.append(traceback.format_exc())

        # Split volumes.
        try:
            split_source = work / "split-source"
            split_source.mkdir()
            (split_source / "large.bin").write_bytes(os.urandom(2_200_000))
            split_archive = work / "split.7z"
            engine.create_archive(
                str(split_archive),
                [str(split_source)],
                fmt_key="7z",
                arc_root=str(work),
                method="Copy",
                part_size=1024 * 1024,
            )
            parts = split_part_paths(str(split_archive))
            assert len(parts) >= 2, f"only {len(parts)} split parts"
            assert not split_archive.exists(), "unsplit archive was not removed"
            engine.test_archive(parts[0])
            names = [
                entry.name for entry in engine.list_archive(parts[0])
            ]
            assert any(name.endswith("large.bin") for name in names)
            lines.append(f"[OK]   split volumes ({len(parts)} parts)")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            lines.append(f"[FAIL] split volumes: {exc}")
            lines.append(traceback.format_exc())

        # All bundled languages load and expose core labels.
        try:
            for code in LANGUAGES:
                translator = I18N(code)
                assert translator.language == code
                for key in ("menu.file", "toolbar.open", "col.name", "btn.ok"):
                    value = translator.t(key)
                    assert value and value != key, (code, key)
            lines.append(f"[OK]   languages ({len(LANGUAGES)})")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            lines.append(f"[FAIL] languages: {exc}")
            lines.append(traceback.format_exc())

        # Byte-based progress reporting used by the progress window.
        try:
            progress_events: list[tuple[int, int, str]] = []
            progress_archive = work / "progress.7z"
            engine.create_archive(
                str(progress_archive),
                [str(source)],
                fmt_key="7z",
                arc_root=str(work),
                progress=lambda current, total, message: progress_events.append(
                    (current, total, message)
                ),
            )
            assert progress_events, "no progress events"
            total = progress_events[-1][1]
            assert total > 0, "zero progress total"
            assert progress_events[-1][0] >= total, "progress did not finish"
            assert len({event[0] for event in progress_events}) >= 2, (
                "progress was too coarse"
            )
            engine.test_archive(str(progress_archive))
            lines.append("[OK]   progress reporting")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            lines.append(f"[FAIL] progress reporting: {exc}")
            lines.append(traceback.format_exc())

        # Archive created inside its own source folder must not include
        # itself (this used to corrupt the 7z header).
        try:
            folder = work / "self-inclusion"
            folder.mkdir()
            (folder / "one.txt").write_text("one\n" * 500, encoding="utf-8")
            archive = folder / "inside.7z"
            for _attempt in (1, 2):
                engine.create_archive(
                    str(archive), [str(folder)], fmt_key="7z",
                    arc_root=str(work),
                )
                names = [
                    entry.name for entry in engine.list_archive(str(archive))
                ]
                assert not any(
                    name.endswith("inside.7z") for name in names
                ), f"archive included itself: {names}"
                engine.test_archive(str(archive))
            lines.append("[OK]   self-inclusion safety")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            lines.append(f"[FAIL] self-inclusion: {exc}")
            lines.append(traceback.format_exc())

        # Make sure the optional codec modules were bundled correctly.
        for module in (
            "bcj", "inflate64", "pyppmd", "brotli", "multivolumefile",
            "Cryptodome",
        ):
            try:
                __import__(module)
                lines.append(f"[OK]   module {module}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                lines.append(f"[FAIL] module {module}: {exc}")

        lines.append("")
        lines.append(
            "RESULT: all self tests passed" if failures == 0
            else f"RESULT: {failures} failure(s)"
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)

    log_path = _write_log(lines)
    text = "\n".join(lines)
    try:
        print(text)
    except Exception:
        pass
    try:
        print(f"Log: {log_path}")
    except Exception:
        pass
    return 0 if failures == 0 else 1
