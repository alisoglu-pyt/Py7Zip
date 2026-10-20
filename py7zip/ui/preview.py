"""Right-hand preview panel (text, images and metadata)."""

from __future__ import annotations

import base64
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

from ..utils import (
    format_timestamp,
    human_size,
    is_image_name,
    is_probably_text,
    is_text_name,
)

TEXT_LIMIT = 512 * 1024
IMAGE_LIMIT = 24 * 1024 * 1024


class PreviewPanel(ttk.Frame):
    """Displays metadata and a best-effort preview of a file/archive entry."""

    def __init__(
        self,
        master,
        i18n,
        theme,
        on_open: Callable[[object], None] | None = None,
        on_extract: Callable[[object], None] | None = None,
    ) -> None:
        super().__init__(master, style="Card.TFrame", padding=(8, 6))
        self.i18n = i18n
        self.theme = theme
        self.on_open = on_open
        self.on_extract = on_extract
        self._context = None
        self._token = 0
        self._photo = None
        self._results: queue.Queue = queue.Queue()
        self.after(50, self._poll_results)

        header = ttk.Frame(self, style="Card.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        self.title_label = ttk.Label(
            header, text=self.i18n.t("preview.title"), style="Section.TLabel"
        )
        self.title_label.grid(row=0, column=0, sticky="w")
        self.open_button = ttk.Button(
            header,
            text="↗",
            style="Link.TButton",
            width=3,
            command=self._open_clicked,
            state="disabled",
        )
        self.open_button.grid(row=0, column=1, padx=(4, 0))
        self.extract_button = ttk.Button(
            header,
            text="⤓",
            style="Link.TButton",
            width=3,
            command=self._extract_clicked,
            state="disabled",
        )
        self.extract_button.grid(row=0, column=2, padx=(2, 0))

        self.meta = ttk.Frame(self, style="Card.TFrame", padding=(0, 8))
        self.meta.grid(row=1, column=0, sticky="ew")
        self.meta.columnconfigure(1, weight=1)
        self._meta_vars = {
            "name": tk.StringVar(value=""),
            "size": tk.StringVar(value=""),
            "modified": tk.StringVar(value=""),
            "extra": tk.StringVar(value=""),
        }
        rows = (
            ("dlg.properties.name", "name"),
            ("dlg.properties.size", "size"),
            ("dlg.properties.modified", "modified"),
            ("dlg.properties.methods", "extra"),
        )
        self._meta_labels: dict[str, ttk.Label] = {}
        for index, (key, name) in enumerate(rows):
            label = ttk.Label(
                self.meta, text=self.i18n.t(key), style="MutedCard.TLabel"
            )
            label.grid(row=index, column=0, sticky="nw", padx=(0, 8), pady=1)
            value = ttk.Label(
                self.meta,
                textvariable=self._meta_vars[name],
                style="Card.TLabel",
                wraplength=185,
                justify="left",
            )
            value.grid(row=index, column=1, sticky="nw", pady=1)
            self._meta_labels[name] = label

        container = ttk.Frame(self, style="Card.TFrame")
        container.grid(row=2, column=0, sticky="nsew")
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.text = tk.Text(
            container,
            wrap="none",
            font=theme.font_mono,
            padx=8,
            pady=8,
            height=12,
            width=22,
            **theme.text_options(),
        )
        self.text_scroll_y = ttk.Scrollbar(
            container, orient="vertical", command=self.text.yview
        )
        self.text_scroll_x = ttk.Scrollbar(
            container, orient="horizontal", command=self.text.xview
        )
        self.text.configure(
            yscrollcommand=self.text_scroll_y.set,
            xscrollcommand=self.text_scroll_x.set,
            state="disabled",
        )
        self.text.grid(row=0, column=0, sticky="nsew")
        self.text_scroll_y.grid(row=0, column=1, sticky="ns")
        self.text_scroll_x.grid(row=1, column=0, sticky="ew")

        self.image_label = tk.Label(container, **theme.label_options())
        self.image_label.grid(row=0, column=0, sticky="nsew")
        self.image_label.grid_remove()

        self.message = ttk.Label(
            container,
            text=self.i18n.t("preview.no_selection"),
            style="MutedCard.TLabel",
            anchor="center",
            justify="center",
            wraplength=200,
        )
        self.message.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self._show_message(self.i18n.t("preview.no_selection"))

    # ------------------------------------------------------------------
    def retranslate(self) -> None:
        self.title_label.configure(text=self.i18n.t("preview.title"))
        self._meta_labels["name"].configure(text=self.i18n.t("dlg.properties.name"))
        self._meta_labels["size"].configure(text=self.i18n.t("dlg.properties.size"))
        self._meta_labels["modified"].configure(
            text=self.i18n.t("dlg.properties.modified")
        )
        self._meta_labels["extra"].configure(
            text=self.i18n.t("dlg.properties.methods")
        )
        if self._context is None:
            self.message.configure(text=self.i18n.t("preview.no_selection"))

    def apply_theme(self) -> None:
        self.text.configure(**self.theme.text_options())
        self.image_label.configure(**self.theme.label_options())

    # ------------------------------------------------------------------
    def clear(self) -> None:
        self._token += 1
        self._context = None
        self._photo = None
        self.open_button.configure(state="disabled")
        self.extract_button.configure(state="disabled")
        for variable in self._meta_vars.values():
            variable.set("")
        self._show_message(self.i18n.t("preview.no_selection"))

    def _show_message(self, text: str) -> None:
        self.text.grid_remove()
        self.text_scroll_x.grid_remove()
        self.text_scroll_y.grid_remove()
        self.image_label.grid_remove()
        self.message.configure(text=text)
        self.message.grid()

    def _show_text(self, content: str) -> None:
        self.message.grid_remove()
        self.image_label.grid_remove()
        self.text.grid()
        self.text_scroll_x.grid()
        self.text_scroll_y.grid()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)
        self.text.xview_moveto(0)

    def _show_image(self, data: bytes, name: str) -> bool:
        photo = None
        try:
            from PIL import Image, ImageTk  # type: ignore

            import io

            image = Image.open(io.BytesIO(data))
            image.thumbnail((420, 420))
            photo = ImageTk.PhotoImage(image, master=self)
        except Exception:
            photo = None
        if photo is None:
            try:
                encoded = base64.b64encode(data)
                photo = tk.PhotoImage(data=encoded, master=self)
                width = photo.width()
                height = photo.height()
                factor = max(1, -(-width // 420), -(-height // 420))
                if factor > 1:
                    photo = photo.subsample(factor, factor)
            except Exception:
                photo = None
        if photo is None:
            return False
        self._photo = photo
        self.message.grid_remove()
        self.text.grid_remove()
        self.text_scroll_x.grid_remove()
        self.text_scroll_y.grid_remove()
        self.image_label.configure(image=photo)
        self.image_label.grid()
        return True

    # ------------------------------------------------------------------
    def _set_meta(self, name: str, size: int | None, mtime: float | None,
                  extra: str = "") -> None:
        self._meta_vars["name"].set(name)
        self._meta_vars["size"].set(human_size(size))
        self._meta_vars["modified"].set(format_timestamp(mtime))
        self._meta_vars["extra"].set(extra)

    def show_path(self, path: str) -> None:
        """Preview a file from the local filesystem."""
        self._token += 1
        token = self._token
        self._context = ("fs", path)
        try:
            stat = os.stat(path)
        except OSError:
            self.clear()
            return
        self._set_meta(os.path.basename(path), stat.st_size, stat.st_mtime, "")
        if os.path.isdir(path):
            self._show_message(self.i18n.t("type.folder"))
            self._context = None
            self.open_button.configure(state="normal")
            self.extract_button.configure(state="disabled")
            return
        self.open_button.configure(state="normal")
        self.extract_button.configure(state="disabled")
        if is_image_name(path):
            limit = IMAGE_LIMIT
        else:
            limit = TEXT_LIMIT

        def worker() -> None:
            try:
                with open(path, "rb") as handle:
                    data = handle.read(limit)
            except OSError as exc:
                self._deliver(token, lambda: self._show_message(str(exc)))
                return
            self._deliver(
                token,
                lambda: self._display(data, path, stat.st_size),
            )

        threading.Thread(target=worker, daemon=True).start()

    def show_archive_entry(
        self,
        engine,
        archive_path: str,
        entry,
        password: str | None = None,
    ) -> None:
        """Preview one entry from an open archive."""
        self._token += 1
        token = self._token
        self._context = ("archive", archive_path, entry, password)
        method = entry.method or ""
        self._set_meta(entry.name, entry.size, entry.mtime, method)
        if entry.is_dir:
            self._show_message(self.i18n.t("type.folder"))
            self._context = None
            self.open_button.configure(state="disabled")
            self.extract_button.configure(state="disabled")
            return
        self.open_button.configure(state="normal")
        self.extract_button.configure(state="normal")
        limit = IMAGE_LIMIT if is_image_name(entry.name) else TEXT_LIMIT

        def worker() -> None:
            try:
                data = engine.read_member(
                    archive_path, entry.name, password=password, limit=limit
                )
            except Exception as exc:  # noqa: BLE001 - shown to the user
                self._deliver(token, lambda: self._show_message(str(exc)))
                return
            self._deliver(
                token,
                lambda: self._display(data, entry.name, entry.size),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _deliver(self, token: int, callback: Callable[[], None]) -> None:
        # Workers only enqueue; the main thread drains the queue in
        # ``_poll_results`` so Tk is never touched from another thread.
        self._results.put((token, callback))

    def _poll_results(self) -> None:
        try:
            while True:
                token, callback = self._results.get_nowait()
                if token != self._token:
                    continue
                try:
                    if self.winfo_exists():
                        callback()
                except tk.TclError:
                    pass
        except queue.Empty:
            pass
        try:
            self.after(50, self._poll_results)
        except tk.TclError:
            pass

    def _display(self, data: bytes, name: str, full_size: int) -> None:
        if not data:
            self._show_message(self.i18n.t("msg.preview_binary"))
            return
        if is_image_name(name) and self._show_image(data, name):
            return
        if is_text_name(name) or is_probably_text(data):
            text = data.decode("utf-8", errors="replace")
            if full_size > len(data):
                text += (
                    "\n\n… " + self.i18n.t("msg.preview_too_large",
                                           size=human_size(full_size))
                )
            self._show_text(text)
            return
        self._show_message(self.i18n.t("msg.preview_binary"))

    # ------------------------------------------------------------------
    def _open_clicked(self) -> None:
        if self._context and self.on_open:
            self.on_open(self._context)

    def _extract_clicked(self) -> None:
        if self._context and self.on_extract:
            self.on_extract(self._context)
