"""Modal dialogs used by the main window."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from ..engine.formats import (
    ARCHIVE_FORMATS,
    CREATE_FORMATS,
    base_name_for_extract,
    detect_format,
    format_extension,
    strip_archive_suffix,
)
from ..i18n import LANGUAGES
from ..utils import common_parent

LEVEL_VALUES = (0, 1, 3, 5, 7, 9)
LEVEL_KEYS = {
    0: "level.0",
    1: "level.1",
    3: "level.3",
    5: "level.5",
    7: "level.7",
    9: "level.9",
}

METHODS_BY_KIND = {
    # Only methods that mainline 7-Zip can read.  py7zr's Brotli/Zstd
    # extensions are intentionally not offered because 7-Zip cannot open
    # such archives (often reported as "invalid header data").
    "7z": ["LZMA2", "LZMA", "Deflate", "BZip2", "PPMD", "Copy"],
    "zip": ["Deflate", "Store", "BZip2", "LZMA"],
    "tar": ["—"],
    "gzip": ["—"],
    "bzip2": ["—"],
    "xz": ["—"],
}


class BaseDialog(tk.Toplevel):
    def __init__(self, parent, i18n, theme, title: str) -> None:
        super().__init__(parent)
        self.withdraw()
        self.i18n = i18n
        self.theme = theme
        self.result: Any = None
        self.parent = parent
        self.title(title)
        self.configure(background=theme.palette["bg"])
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda _event: self.cancel())

        self.body = ttk.Frame(self, style="Card.TFrame", padding=14)
        self.body.pack(fill="both", expand=True)
        self.body.columnconfigure(1, weight=1)

        self.buttonbar = ttk.Frame(self, style="Toolbar.TFrame", padding=(12, 8))
        self.buttonbar.pack(fill="x")
        self.buttonbar.columnconfigure(0, weight=1)

        self._primary_button: ttk.Button | None = None

    # ------------------------------------------------------------------
    def add_buttons(
        self,
        ok_text: str,
        on_ok: Callable[[], None],
        cancel_text: str | None = None,
        extra: list[tuple[str, Callable[[], None]]] | None = None,
        show_cancel: bool = True,
    ) -> None:
        if extra:
            for index, (text, command) in enumerate(extra):
                ttk.Button(
                    self.buttonbar, text=text, style="TButton", command=command
                ).grid(row=0, column=1 + index, padx=(0, 8))
        if show_cancel:
            cancel = ttk.Button(
                self.buttonbar,
                text=cancel_text or self.i18n.t("btn.cancel"),
                style="TButton",
                command=self.cancel,
            )
            cancel.grid(row=0, column=10, padx=(0, 8))
        primary = ttk.Button(
            self.buttonbar,
            text=ok_text,
            style="Accent.TButton",
            command=on_ok,
        )
        primary.grid(row=0, column=11)
        self._primary_button = primary
        self.bind("<Return>", lambda _event: on_ok())

    def show(self) -> Any:
        self.update_idletasks()
        self._center()
        self.deiconify()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        if self._primary_button is not None:
            self._primary_button.focus_set()
        self.wait_window(self)
        return self.result

    def _center(self) -> None:
        try:
            width = self.winfo_reqwidth()
            height = self.winfo_reqheight()
            parent = self.parent
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + max(0, (pw - width) // 2)
            y = py + max(0, (ph - height) // 2)
            self.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

    def cancel(self) -> None:
        self.result = None
        self.destroy()

    def _close(self, result: Any) -> None:
        self.result = result
        self.destroy()

    # ------------------------------------------------------------------
    def label(self, parent, key: str, style: str = "Card.TLabel", **kwargs):
        widget = ttk.Label(parent, text=self.i18n.t(key), style=style, **kwargs)
        return widget

    def add_entry_row(
        self,
        parent,
        row: int,
        key: str,
        textvariable: tk.StringVar,
        browse: bool = False,
        show: str | None = None,
    ) -> ttk.Entry:
        label = self.label(parent, key)
        label.grid(row=row, column=0, sticky="w", padx=(0, 10), pady=(5, 1))
        entry = ttk.Entry(parent, textvariable=textvariable, show=show or "")
        entry.grid(row=row, column=1, sticky="ew", pady=(5, 1))
        if browse:
            button = ttk.Button(
                parent,
                text=self.i18n.t("btn.browse"),
                style="TButton",
                command=lambda: self._browse_into(textvariable),
            )
            button.grid(row=row, column=2, padx=(6, 0), pady=(5, 1))
        return entry

    def _browse_into(self, variable: tk.StringVar) -> None:
        initial = variable.get().strip() or os.path.expanduser("~")
        folder = filedialog.askdirectory(parent=self, initialdir=initial)
        if folder:
            variable.set(folder)

    def error(self, message: str) -> None:
        messagebox.showerror(
            self.i18n.t("msg.error"), message, parent=self
        )


# ---------------------------------------------------------------------------
# Create archive
# ---------------------------------------------------------------------------
class CreateArchiveDialog(BaseDialog):
    def __init__(
        self,
        parent,
        i18n,
        theme,
        sources: list[str],
        default_dir: str,
        default_name: str,
        default_format: str = "7z",
        default_level: int = 5,
        default_method: str = "LZMA2",
    ) -> None:
        super().__init__(parent, i18n, theme, i18n.t("dlg.create.title"))
        self.sources = list(sources)
        self._format_keys = list(CREATE_FORMATS)
        self._format_index = {
            key: index for index, key in enumerate(self._format_keys)
        }

        header = ttk.Label(
            self.body,
            text=i18n.t("dlg.create.header"),
            style="Card.TLabel",
            font=theme.font_title,
        )
        header.grid(row=0, column=0, columnspan=3, sticky="w")
        source_text = i18n.t("dlg.create.summary", count=len(sources))
        if sources:
            source_text += f"  ·  {os.path.basename(sources[0])}"
        ttk.Label(
            self.body, text=source_text, style="MutedCard.TLabel"
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 10))

        self.location_var = tk.StringVar(
            value=default_dir or os.path.expanduser("~")
        )
        self.name_var = tk.StringVar(value=default_name or i18n.t("dlg.create.default_name"))
        self.password_var = tk.StringVar()
        self.confirm_var = tk.StringVar()
        self.encrypt_header_var = tk.BooleanVar(value=False)
        self.level_var = tk.StringVar()
        self.method_var = tk.StringVar()
        self.split_var = tk.BooleanVar(value=False)
        self.part_size_var = tk.StringVar(value="100")
        self.part_unit_var = tk.StringVar(value=i18n.t("unit.mb"))

        self.add_entry_row(
            self.body, 2, "dlg.create.location", self.location_var, browse=True
        )
        self.add_entry_row(
            self.body, 3, "dlg.create.archive_name", self.name_var
        )

        ttk.Label(
            self.body, text=i18n.t("dlg.create.format"), style="Card.TLabel"
        ).grid(row=4, column=0, sticky="w", padx=(0, 12), pady=(8, 2))
        self.format_combo = ttk.Combobox(
            self.body,
            state="readonly",
            values=[ARCHIVE_FORMATS[k].label for k in self._format_keys],
        )
        self.format_combo.grid(row=4, column=1, sticky="ew", pady=(8, 2))

        ttk.Label(
            self.body, text=i18n.t("dlg.create.level"), style="Card.TLabel"
        ).grid(row=5, column=0, sticky="w", padx=(0, 12), pady=(8, 2))
        self.level_combo = ttk.Combobox(
            self.body,
            state="readonly",
            values=[i18n.t(LEVEL_KEYS[level]) for level in LEVEL_VALUES],
        )
        self.level_combo.grid(row=5, column=1, sticky="ew", pady=(8, 2))

        ttk.Label(
            self.body, text=i18n.t("dlg.create.method"), style="Card.TLabel"
        ).grid(row=6, column=0, sticky="w", padx=(0, 12), pady=(8, 2))
        self.method_combo = ttk.Combobox(self.body, state="readonly")
        self.method_combo.grid(row=6, column=1, sticky="ew", pady=(8, 2))

        self.split_check = ttk.Checkbutton(
            self.body,
            text=i18n.t("dlg.create.split"),
            variable=self.split_var,
            style="Card.TCheckbutton",
            command=self._update_split_state,
        )
        self.split_check.grid(row=7, column=1, sticky="w", pady=(8, 2))

        self.part_size_label = ttk.Label(
            self.body, text=i18n.t("dlg.create.part_size"),
            style="Card.TLabel",
        )
        self.part_size_label.grid(
            row=8, column=0, sticky="w", padx=(0, 12), pady=(2, 2)
        )
        split_frame = ttk.Frame(self.body, style="Card.TFrame")
        split_frame.grid(row=8, column=1, sticky="w", pady=(2, 2))
        self.part_size_spin = ttk.Spinbox(
            split_frame,
            from_=1,
            to=1048576,
            textvariable=self.part_size_var,
            width=8,
        )
        self.part_size_spin.grid(row=0, column=0, sticky="w")
        self.part_unit_combo = ttk.Combobox(
            split_frame,
            values=[i18n.t("unit.mb"), i18n.t("unit.gb")],
            textvariable=self.part_unit_var,
            state="readonly",
            width=4,
        )
        self.part_unit_combo.grid(row=0, column=1, padx=(6, 0))
        ttk.Label(
            split_frame,
            text=i18n.t("dlg.create.part_example"),
            style="MutedCard.TLabel",
        ).grid(row=0, column=2, padx=(10, 0))

        self.password_entry = self.add_entry_row(
            self.body, 9, "dlg.create.password", self.password_var, show="•"
        )
        self.confirm_entry = self.add_entry_row(
            self.body, 10, "dlg.create.password_confirm", self.confirm_var, show="•"
        )
        self.encrypt_check = ttk.Checkbutton(
            self.body,
            text=i18n.t("dlg.create.encrypt_header"),
            variable=self.encrypt_header_var,
            style="Card.TCheckbutton",
        )
        self.encrypt_check.grid(
            row=11, column=1, sticky="w", pady=(8, 2)
        )

        self.note = ttk.Label(
            self.body, text="", style="MutedCard.TLabel", wraplength=430,
            justify="left",
        )
        self.note.grid(row=12, column=0, columnspan=3, sticky="w", pady=(8, 0))

        self.output_label = ttk.Label(
            self.body, text="", style="MutedCard.TLabel", wraplength=430
        )
        self.output_label.grid(
            row=13, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

        # Initial selections.
        index = self._format_index.get(default_format, 0)
        self.format_combo.current(index)
        try:
            level_index = LEVEL_VALUES.index(default_level)
        except ValueError:
            level_index = LEVEL_VALUES.index(5)
        self.level_combo.current(level_index)
        self.format_combo.bind("<<ComboboxSelected>>", self._on_format_change)
        self.name_var.trace_add("write", lambda *_: self._update_output())
        self.location_var.trace_add("write", lambda *_: self._update_output())
        self._on_format_change()
        if default_method:
            values = list(self.method_combo.cget("values"))
            if default_method in values:
                self.method_combo.set(default_method)
        self._update_split_state()

        self.add_buttons(
            i18n.t("btn.create"), self._on_create, i18n.t("btn.cancel")
        )

    # ------------------------------------------------------------------
    def _current_format(self) -> str:
        return self._format_keys[self.format_combo.current()]

    def _on_format_change(self, _event=None) -> None:
        fmt_key = self._current_format()
        fmt = ARCHIVE_FORMATS[fmt_key]
        methods = METHODS_BY_KIND.get(fmt.kind, ["—"])
        self.method_combo.configure(values=methods)
        if len(methods) == 1:
            self.method_combo.set(methods[0])
            self.method_combo.configure(state="disabled")
        else:
            self.method_combo.configure(state="readonly")
            if self.method_combo.get() not in methods:
                preferred = "LZMA2" if "LZMA2" in methods else methods[0]
                self.method_combo.set(preferred)

        supports_password = fmt.kind == "7z"
        state = "normal" if supports_password else "disabled"
        self.password_entry.configure(state=state)
        self.confirm_entry.configure(state=state)
        self.encrypt_check.configure(state=state)
        if not supports_password:
            self.password_var.set("")
            self.confirm_var.set("")
            self.encrypt_header_var.set(False)

        note = ""
        if fmt.kind == "zip":
            note = self.i18n.t("dlg.create.zip_note")
        if fmt.single_file:
            note = self.i18n.t("dlg.create.single_note")
        if fmt.kind == "tar" or fmt.single_file:
            note = (note + " " if note else "") + self.i18n.t("dlg.create.zip_note")
        self.note.configure(text=note)
        self._update_output()

    def _archive_path(self) -> str:
        location = self.location_var.get().strip()
        name = self.name_var.get().strip()
        if name and detect_format(name):
            name = strip_archive_suffix(name)
        extension = format_extension(self._current_format())
        return os.path.join(location, (name or "") + extension)

    def _update_split_state(self) -> None:
        enabled = bool(self.split_var.get())
        self.part_size_spin.configure(
            state="normal" if enabled else "disabled"
        )
        self.part_unit_combo.configure(
            state="readonly" if enabled else "disabled"
        )
        self.part_size_label.configure(
            state="normal" if enabled else "disabled"
        )
        self._update_output()

    def _update_output(self) -> None:
        text = f"{self.i18n.t('dlg.create.output')} {self._archive_path()}"
        if self.split_var.get():
            text += "   →   .001, .002, …"
        self.output_label.configure(text=text)

    def _on_create(self) -> None:
        location = self.location_var.get().strip()
        name = self.name_var.get().strip()
        if not name:
            self.error(self.i18n.t("dlg.create.name_required"))
            return
        if not location or not os.path.isdir(location):
            self.error(self.i18n.t("dlg.create.location"))
            return
        if not self.sources:
            self.error(self.i18n.t("dlg.create.no_source"))
            return
        fmt_key = self._current_format()
        fmt = ARCHIVE_FORMATS[fmt_key]
        if fmt.single_file and (
            len(self.sources) != 1 or not os.path.isfile(self.sources[0])
        ):
            self.error(self.i18n.t("dlg.create.single_note"))
            return

        password = self.password_var.get()
        if fmt.kind == "7z" and password:
            if password != self.confirm_var.get():
                self.error(self.i18n.t("dlg.create.password_mismatch"))
                return
        elif fmt.kind != "7z":
            password = ""

        part_size = 0
        if self.split_var.get():
            try:
                amount = int(self.part_size_var.get())
            except (TypeError, ValueError):
                amount = 0
            unit = self.part_unit_var.get()
            multiplier = (
                1024 ** 3
                if unit == self.i18n.t("unit.gb")
                else 1024 ** 2
            )
            part_size = amount * multiplier
            if part_size < 1024 * 1024:
                self.error(self.i18n.t("dlg.create.part_invalid"))
                return

        archive_path = self._archive_path()
        if os.path.exists(archive_path):
            if not messagebox.askyesno(
                self.i18n.t("msg.confirm"),
                self.i18n.t("dlg.create.exists"),
                parent=self,
            ):
                return

        level = LEVEL_VALUES[
            max(0, min(len(LEVEL_VALUES) - 1, self.level_combo.current()))
        ]
        method = self.method_combo.get()
        if method in ("", "—"):
            method = "LZMA2" if fmt.kind == "7z" else "Deflate"

        self._close(
            {
                "path": archive_path,
                "format": fmt_key,
                "level": level,
                "method": method,
                "password": password or None,
                "encrypt_header": bool(self.encrypt_header_var.get()),
                "part_size": part_size,
                "sources": self.sources,
                "arc_root": common_parent(self.sources),
            }
        )


# ---------------------------------------------------------------------------
# Extract archive
# ---------------------------------------------------------------------------
class ExtractDialog(BaseDialog):
    def __init__(
        self,
        parent,
        i18n,
        theme,
        archive_path: str,
        default_destination: str,
        selected_members: list[str],
        total_members: int,
    ) -> None:
        super().__init__(parent, i18n, theme, i18n.t("dlg.extract.title"))
        self.archive_path = archive_path
        self.selected_members = list(selected_members)

        ttk.Label(
            self.body,
            text=i18n.t("dlg.extract.header"),
            style="Card.TLabel",
            font=theme.font_title,
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        archive_name = os.path.basename(archive_path)
        ttk.Label(
            self.body,
            text=f"{i18n.t('dlg.extract.archive')} {archive_name}",
            style="MutedCard.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 10))

        self.destination_var = tk.StringVar(
            value=default_destination or os.path.expanduser("~")
        )
        self.password_var = tk.StringVar()
        self.all_var = tk.BooleanVar(value=not selected_members)
        self.overwrite_var = tk.BooleanVar(value=True)
        self.subfolder_var = tk.BooleanVar(value=False)

        self.destination_entry = self.add_entry_row(
            self.body, 2, "dlg.extract.destination", self.destination_var,
            browse=True,
        )

        count_text = i18n.t(
            "dlg.extract.selected_count",
            count=len(selected_members),
            total=total_members,
        )
        options = ttk.Frame(self.body, style="Card.TFrame")
        options.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 2))
        ttk.Radiobutton(
            options, text=i18n.t("dlg.extract.all"), variable=self.all_var,
            value=True, style="Card.TRadiobutton",
        ).grid(row=0, column=0, sticky="w")
        selected_radio = ttk.Radiobutton(
            options,
            text=f"{i18n.t('dlg.extract.selected')} ({count_text})",
            variable=self.all_var,
            value=False,
            style="Card.TRadiobutton",
        )
        selected_radio.grid(row=1, column=0, sticky="w", pady=(2, 0))
        if not selected_members:
            selected_radio.configure(state="disabled")

        ttk.Checkbutton(
            self.body, text=i18n.t("dlg.extract.overwrite"),
            variable=self.overwrite_var, style="Card.TCheckbutton",
        ).grid(row=4, column=1, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            self.body, text=i18n.t("dlg.extract.use_subfolder"),
            variable=self.subfolder_var, style="Card.TCheckbutton",
        ).grid(row=5, column=1, sticky="w", pady=(6, 0))

        self.add_entry_row(
            self.body, 6, "dlg.extract.password", self.password_var, show="•"
        )

        self.add_buttons(
            i18n.t("btn.extract"), self._on_extract, i18n.t("btn.cancel")
        )
        self.destination_entry.focus_set()

    def _on_extract(self) -> None:
        destination = self.destination_var.get().strip()
        if not destination:
            self.error(self.i18n.t("dlg.extract.no_dest"))
            return
        destination = os.path.expanduser(destination)
        if self.subfolder_var.get():
            destination = os.path.join(
                destination, base_name_for_extract(self.archive_path)
            )
        members = None if self.all_var.get() else list(self.selected_members)
        self._close(
            {
                "destination": destination,
                "members": members,
                "overwrite": bool(self.overwrite_var.get()),
                "password": self.password_var.get() or None,
            }
        )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class SettingsDialog(BaseDialog):
    def __init__(self, parent, i18n, theme, settings) -> None:
        super().__init__(parent, i18n, theme, i18n.t("dlg.settings.title"))
        self.settings = settings

        ttk.Label(
            self.body,
            text=i18n.t("dlg.settings.header"),
            style="Card.TLabel",
            font=theme.font_title,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.language_var = tk.StringVar()
        self.theme_var = tk.StringVar()
        self.hidden_var = tk.BooleanVar(value=settings.get("show_hidden"))
        self.confirm_var = tk.BooleanVar(value=settings.get("confirm_delete"))
        self.preview_var = tk.BooleanVar(value=settings.get("preview_enabled"))
        self.extract_dir_var = tk.StringVar(value=settings.get("extract_dir"))
        self.level_var = tk.StringVar()

        appearance = ttk.LabelFrame(
            self.body, text=i18n.t("dlg.settings.appearance"),
            style="TLabelframe", padding=(12, 8),
        )
        appearance.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        appearance.columnconfigure(1, weight=1)
        ttk.Label(
            appearance, text=i18n.t("dlg.settings.language"), style="Card.TLabel"
        ).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=4)
        language_codes = list(LANGUAGES.keys())
        self._language_codes = language_codes
        self.language_combo = ttk.Combobox(
            appearance,
            state="readonly",
            values=list(LANGUAGES.values()),
        )
        self.language_combo.grid(row=0, column=1, sticky="ew", pady=4)
        try:
            self.language_combo.current(
                language_codes.index(settings.get("language", "tr"))
            )
        except ValueError:
            self.language_combo.current(0)
        ttk.Label(
            appearance, text=i18n.t("dlg.settings.theme"), style="Card.TLabel"
        ).grid(row=1, column=0, sticky="w", padx=(0, 12), pady=4)
        self.theme_combo = ttk.Combobox(
            appearance,
            state="readonly",
            values=[i18n.t("menu.view.dark"), i18n.t("menu.view.light")],
        )
        self.theme_combo.grid(row=1, column=1, sticky="ew", pady=4)
        self.theme_combo.current(0 if settings.get("theme") == "dark" else 1)

        general = ttk.LabelFrame(
            self.body, text=i18n.t("dlg.settings.general"),
            style="TLabelframe", padding=(12, 8),
        )
        general.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        general.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            general, text=i18n.t("dlg.settings.show_hidden"),
            variable=self.hidden_var, style="Card.TCheckbutton",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=3)
        ttk.Checkbutton(
            general, text=i18n.t("dlg.settings.confirm_delete"),
            variable=self.confirm_var, style="Card.TCheckbutton",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=3)
        ttk.Checkbutton(
            general, text=i18n.t("dlg.settings.preview"),
            variable=self.preview_var, style="Card.TCheckbutton",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=3)

        archives = ttk.LabelFrame(
            self.body, text=i18n.t("dlg.settings.archives"),
            style="TLabelframe", padding=(12, 8),
        )
        archives.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        archives.columnconfigure(1, weight=1)
        ttk.Label(
            archives, text=i18n.t("dlg.settings.default_extract"),
            style="Card.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=4)
        ttk.Entry(
            archives, textvariable=self.extract_dir_var
        ).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(
            archives,
            text=i18n.t("btn.browse"),
            command=self._browse_extract,
        ).grid(row=0, column=2, padx=(8, 0), pady=4)
        ttk.Label(
            archives, text=i18n.t("dlg.settings.compression"),
            style="Card.TLabel",
        ).grid(row=1, column=0, sticky="w", padx=(0, 12), pady=4)
        self.level_combo = ttk.Combobox(
            archives,
            state="readonly",
            values=[i18n.t(LEVEL_KEYS[level]) for level in LEVEL_VALUES],
        )
        self.level_combo.grid(row=1, column=1, sticky="ew", pady=4)
        try:
            self.level_combo.current(
                LEVEL_VALUES.index(int(settings.get("compression_level", 5)))
            )
        except ValueError:
            self.level_combo.current(LEVEL_VALUES.index(5))

        self.add_buttons(
            i18n.t("btn.apply"), self._on_apply, i18n.t("btn.cancel")
        )

    def _browse_extract(self) -> None:
        initial = self.extract_dir_var.get().strip() or os.path.expanduser("~")
        folder = filedialog.askdirectory(parent=self, initialdir=initial)
        if folder:
            self.extract_dir_var.set(folder)

    def _on_apply(self) -> None:
        language = self._language_codes[
            max(0, min(len(self._language_codes) - 1, self.language_combo.current()))
        ]
        theme = "dark" if self.theme_combo.current() == 0 else "light"
        level = LEVEL_VALUES[
            max(0, min(len(LEVEL_VALUES) - 1, self.level_combo.current()))
        ]
        self._close(
            {
                "language": language,
                "theme": theme,
                "show_hidden": bool(self.hidden_var.get()),
                "confirm_delete": bool(self.confirm_var.get()),
                "preview_enabled": bool(self.preview_var.get()),
                "extract_dir": self.extract_dir_var.get().strip(),
                "compression_level": level,
            }
        )


# ---------------------------------------------------------------------------
# Password
# ---------------------------------------------------------------------------
class PasswordDialog(BaseDialog):
    def __init__(self, parent, i18n, theme, hint: str | None = None) -> None:
        super().__init__(parent, i18n, theme, i18n.t("dlg.password.title"))
        ttk.Label(
            self.body,
            text=i18n.t("dlg.password.header"),
            style="Card.TLabel",
            font=theme.font_title,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            self.body,
            text=hint or i18n.t("dlg.password.hint"),
            style="MutedCard.TLabel",
            wraplength=380,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 10))

        self.password_var = tk.StringVar()
        self.show_var = tk.BooleanVar(value=False)
        ttk.Label(
            self.body, text=i18n.t("dlg.password.label"), style="Card.TLabel"
        ).grid(row=2, column=0, sticky="w", padx=(0, 12))
        self.entry = ttk.Entry(
            self.body, textvariable=self.password_var, show="•", width=32
        )
        self.entry.grid(row=2, column=1, sticky="ew")
        self.body.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            self.body,
            text="👁",
            variable=self.show_var,
            style="Card.TCheckbutton",
            command=self._toggle_show,
        ).grid(row=3, column=1, sticky="w", pady=(6, 0))

        self.add_buttons(
            i18n.t("btn.ok"), self._on_ok, i18n.t("btn.cancel")
        )
        self.entry.focus_set()

    def _toggle_show(self) -> None:
        self.entry.configure(show="" if self.show_var.get() else "•")

    def _on_ok(self) -> None:
        password = self.password_var.get()
        if not password:
            self.error(self.i18n.t("dlg.password.empty"))
            return
        self._close(password)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------
class PropertiesDialog(BaseDialog):
    def __init__(
        self, parent, i18n, theme, title: str, pairs: list[tuple[str, str]]
    ) -> None:
        super().__init__(parent, i18n, theme, title)
        ttk.Label(
            self.body,
            text=i18n.t("dlg.properties.header"),
            style="Card.TLabel",
            font=theme.font_title,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        for index, (label, value) in enumerate(pairs, start=1):
            ttk.Label(
                self.body, text=label, style="MutedCard.TLabel"
            ).grid(row=index, column=0, sticky="nw", padx=(0, 16), pady=2)
            ttk.Label(
                self.body,
                text=value or "—",
                style="Card.TLabel",
                wraplength=420,
                justify="left",
            ).grid(row=index, column=1, sticky="nw", pady=2)
        self.body.columnconfigure(1, weight=1)
        self.add_buttons(i18n.t("btn.close"), self.cancel, show_cancel=False)


# ---------------------------------------------------------------------------
# About / shortcuts
# ---------------------------------------------------------------------------
class TextDialog(BaseDialog):
    def __init__(
        self,
        parent,
        i18n,
        theme,
        title: str,
        body_text: str,
        subtitle: str | None = None,
    ) -> None:
        super().__init__(parent, i18n, theme, title)
        ttk.Label(
            self.body,
            text=title,
            style="Card.TLabel",
            font=theme.font_title,
        ).grid(row=0, column=0, sticky="w")
        if subtitle:
            ttk.Label(
                self.body, text=subtitle, style="MutedCard.TLabel"
            ).grid(row=1, column=0, sticky="w", pady=(2, 10))
        ttk.Label(
            self.body,
            text=body_text,
            style="Card.TLabel",
            wraplength=520,
            justify="left",
        ).grid(row=2, column=0, sticky="w")
        self.add_buttons(i18n.t("btn.close"), self.cancel, show_cancel=False)
