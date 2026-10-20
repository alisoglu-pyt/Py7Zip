"""Allow ``python -m py7zip`` to launch the application."""

from .main import main

if __name__ == "__main__":
    raise SystemExit(main())
