"""Application entry point."""

from __future__ import annotations

import argparse
import os
import sys


def _enable_high_dpi() -> None:
    """Make the window crisp on Windows high-DPI displays."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def build_parser() -> argparse.ArgumentParser:
    from . import APP_NAME, __version__
    from .i18n import LANGUAGES

    parser = argparse.ArgumentParser(
        prog="py7zip",
        description=f"{APP_NAME} - modern archive manager (7z, zip, tar, gz, bz2, xz)",
    )
    parser.add_argument("path", nargs="?", help="Archive or folder to open on startup")
    parser.add_argument(
        "--lang",
        choices=tuple(LANGUAGES.keys()),
        help="Interface language (" + "/".join(LANGUAGES.keys()) + ")",
    )
    parser.add_argument(
        "--theme", choices=("dark", "light"), help="Colour theme (dark/light)"
    )
    parser.add_argument(
        "--version", action="version", version=f"{APP_NAME} {__version__}"
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Run the bundled archive-engine self test and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.selftest:
        from .selftest import run_selftest

        return run_selftest()

    _enable_high_dpi()

    try:
        import tkinter as tk
    except ImportError:  # pragma: no cover - depends on the interpreter build
        sys.stderr.write(
            "Tkinter is not available. Install the python3-tk package "
            "(Linux) or use the official python.org installer (Windows).\n"
        )
        return 1

    from .ui.main_window import MainWindow

    try:
        root = tk.Tk()
    except tk.TclError as exc:  # no display / remote session
        sys.stderr.write(f"Cannot start the graphical interface: {exc}\n")
        return 1

    initial = args.path
    if initial and not os.path.isabs(initial):
        initial = os.path.abspath(initial)

    MainWindow(
        root,
        initial_path=initial,
        lang_override=args.lang,
        theme_override=args.theme,
    )
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
