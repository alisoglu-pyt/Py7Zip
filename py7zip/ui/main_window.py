"""The Py7-Zip main window."""

from __future__ import annotations

import os
import queue
import shutil
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from .. import APP_NAME, __version__
from ..engine import (
    ARCHIVE_FORMATS,
    ArchiveEngine,
    ArchiveError,
    OperationCancelled,
    PasswordRequiredError,
    detect_format,
    is_archive_path,
    split_base_path,
)
from ..engine.entries import (
    Entry,
    child_entries,
    normalize_name,
    parent_of,
    search_entries,
    selected_member_names,
)
from ..engine.formats import base_name_for_extract
from ..settings_store import Settings
from ..utils import (
    common_parent,
    file_icon_name,
    format_timestamp,
    human_size,
    make_temp_dir,
    open_with_default,
    ratio_text,
    remove_tree,
    shorten_path,
)
from .dialogs import (
    CreateArchiveDialog,
    ExtractDialog,
    PasswordDialog,
    PropertiesDialog,
    SettingsDialog,
    TextDialog,
)
from .icons import IconSet
from .preview import PreviewPanel
from .progress import ProgressDialog
from .theme import ThemeManager
from .widgets import (
    PlaceholderEntry,
    SidebarTree,
    StatusBar,
    Tooltip,
    filesystem_roots,
)


@dataclass
class FsItem:
    name: str
    path: str
    is_dir: bool
    size: int
    mtime: float | None = None
    is_link: bool = False
    is_archive: bool = False


class MainWindow:
    """Owns the Tk root, the engine and all user interactions."""

    def __init__(
        self,
        root: tk.Tk,
        initial_path: str | None = None,
        lang_override: str | None = None,
        theme_override: str | None = None,
    ) -> None:
        self.root = root
        self.settings = Settings()
        if lang_override:
            self.settings.set("language", lang_override)
        if theme_override:
            self.settings.set("theme", theme_override)
        if self.settings.get("compression_method") not in (
            "LZMA2", "LZMA", "Deflate", "BZip2", "PPMD", "Copy"
        ):
            # Older releases offered py7zr-only methods that mainline
            # 7-Zip cannot open.
            self.settings.set("compression_method", "LZMA2")

        from ..i18n import I18N

        self.i18n = I18N(self.settings.get("language", "tr"))
        self.theme = ThemeManager(root)
        self.theme.apply(self.settings.get("theme", "light"))
        self.engine = ArchiveEngine()

        self.mode = "fs"
        self.cwd = os.getcwd()
        self.archive_path: str | None = None
        self.archive_entries: list[Entry] = []
        self.archive_prefix = ""
        self.archive_password: str | None = None

        self._fs_items: list[FsItem] = []
        self._row_map: dict[str, Any] = {}
        self._displayed_count = 0
        self._total_count = 0
        self._filter_query = ""
        self._back: list[tuple] = []
        self._forward: list[tuple] = []
        self._busy = False
        self._cancel_event = threading.Event()
        self._temp_dirs: list[str] = []
        self._passwords: dict[str, str] = {}
        self._progress_dialog: ProgressDialog | None = None
        self._progress_show_id: str | None = None
        self._sort_column = self.settings.get("sort_column", "name")
        self._sort_reverse = bool(self.settings.get("sort_reverse", False))
        self._preview_visible = bool(self.settings.get("preview_enabled", True))
        self._sidebar_visible = bool(self.settings.get("sidebar_visible", True))

        self._buttons: dict[str, ttk.Button] = {}
        self._button_defs: dict[str, tuple[str, str | None, str, int, bool]] = {}
        self._tooltips: dict[tk.Widget, tuple[Tooltip, str]] = {}
        self._icons: IconSet | None = None

        self._build_vars()
        self._build_ui()
        self._build_menu()
        self._bind_shortcuts()
        self._apply_window_geometry()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(60, lambda: self._setup_initial(initial_path))

    # ==================================================================
    # Construction
    # ==================================================================
    def _build_vars(self) -> None:
        self.path_var = tk.StringVar(value=self.cwd)
        self._preview_var = tk.BooleanVar(value=self._preview_visible)
        self._sidebar_var = tk.BooleanVar(value=self._sidebar_visible)
        self._theme_var = tk.IntVar(value=0 if self.theme.mode == "dark" else 1)
        self._lang_var = tk.StringVar(value=self.i18n.language)

    def _build_ui(self) -> None:
        self.root.title(
            f"{APP_NAME} — {self.i18n.t('app.archive_manager')}"
        )
        self.root.minsize(780, 500)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        palette = self.theme.palette
        self._icons = IconSet(
            self.root,
            {
                "normal": palette["text"],
                "muted": palette["muted"],
                "accent": palette["accent_text"],
                "danger": palette["danger"],
            },
        )

        # -- toolbar (classic Explorer / 7-Zip style) ------------------
        self.header = ttk.Frame(
            self.root, style="Toolbar.TFrame", padding=(8, 5, 8, 2)
        )
        self.header.grid(row=0, column=0, sticky="ew")
        ttk.Separator(self.header, orient="horizontal").pack(
            side="bottom", fill="x", pady=(5, 0)
        )
        left = ttk.Frame(self.header, style="Toolbar.TFrame")
        left.pack(side="left")
        right = ttk.Frame(self.header, style="Toolbar.TFrame")
        right.pack(side="right")

        self._icon_button(left, "toolbar.back", "back", self._go_back)
        self._icon_button(left, "toolbar.forward", "forward", self._go_forward)
        self._icon_button(left, "toolbar.up", "up", self._go_up)
        self._icon_button(left, "toolbar.refresh", "refresh", self._refresh)
        ttk.Separator(left, orient="vertical").pack(
            side="left", fill="y", padx=5, pady=2
        )

        self._tool_button(left, "toolbar.open", "open", self._open_dialog)
        self._tool_button(left, "toolbar.create", "new", self._action_new)
        self._tool_button(left, "toolbar.extract", "extract", self._action_extract)
        self._tool_button(left, "toolbar.add", "add", self._action_add)
        self._tool_button(left, "toolbar.delete", "delete", self._action_delete)
        self._tool_button(left, "toolbar.test", "test", self._action_test)
        self._tool_button(left, "toolbar.info", "info", self._action_properties)

        # Search (right side, packed in reverse visual order).
        self._icon_button(right, "toolbar.settings", "settings", self._action_settings)
        self._icon_button(right, "toolbar.preview", "preview", self._toggle_preview)
        self.search_entry = PlaceholderEntry(
            right,
            placeholder=self.i18n.t("search.placeholder"),
            text_color=self.theme.palette["text"],
            muted_color=self.theme.palette["muted"],
            width=18,
        )
        self.search_entry.pack(side="right", padx=(0, 8))
        self.search_entry.bind("<Return>", lambda _e: self._apply_filter())
        self.search_entry.bind("<Escape>", lambda _e: self._clear_filter())

        # -- path bar (compact Explorer address bar) -------------------
        self.pathbar = ttk.Frame(
            self.root, style="Toolbar.TFrame", padding=(8, 0, 8, 5)
        )
        self.pathbar.grid(row=1, column=0, sticky="ew")
        self.pathbar.columnconfigure(1, weight=1)

        self.path_icon = ttk.Label(
            self.pathbar,
            image=self._icons.get("open", "colored", 16),
            style="Toolbar.TLabel",
        )
        self.path_icon.grid(row=0, column=0, padx=(2, 6))
        self.path_entry = ttk.Entry(
            self.pathbar, textvariable=self.path_var, style="Path.TEntry"
        )
        self.path_entry.grid(row=0, column=1, sticky="ew")
        self.path_entry.bind("<Return>", lambda _e: self._navigate_from_entry())
        self._path_menu_button = ttk.Button(
            self.pathbar,
            image=self._icons.get("down", "normal", 12),
            style="Icon.TButton",
            command=self._show_path_menu,
            takefocus=False,
        )
        self._path_menu_button.grid(row=0, column=2, padx=(4, 0))

        # -- main area -------------------------------------------------
        self.paned = ttk.Panedwindow(self.root, orient="horizontal")
        self.paned.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 4))

        self.sidebar = SidebarTree(
            self.paned,
            on_select=self._on_sidebar_select,
            show_hidden=lambda: bool(self.settings.get("show_hidden")),
        )
        self.paned.add(self.sidebar, weight=1)

        self.content = ttk.Frame(self.paned, style="Card.TFrame")
        self.paned.add(self.content, weight=5)
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(1, weight=1)

        header = ttk.Frame(
            self.content, style="Header.TFrame", padding=(8, 5)
        )
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)
        self.title_label = ttk.Label(header, text="", style="Title.TLabel")
        self.title_label.grid(row=0, column=0, sticky="w")
        self.badge_label = ttk.Label(header, text="", style="Badge.TLabel")
        self.badge_label.grid(row=0, column=1, sticky="e", padx=(8, 8))
        self.header_close = ttk.Button(
            header,
            text=self.i18n.t("menu.file.close_archive"),
            style="Link.TButton",
            command=self._close_archive,
        )
        self.header_close.grid(row=0, column=2, sticky="e")
        self.header_close.grid_remove()

        tree_frame = ttk.Frame(self.content, style="Card.TFrame")
        tree_frame.grid(
            row=1, column=0, sticky="nsew", padx=(6, 0), pady=(0, 6)
        )
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        columns = ("name", "size", "packed", "ratio", "modified", "crc")
        self._all_columns = columns
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.tree.yview
        )
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll = ttk.Scrollbar(
            tree_frame, orient="horizontal", command=self.tree.xview
        )
        xscroll.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self._column_keys = {
            "name": "col.name",
            "size": "col.size",
            "packed": "col.packed",
            "ratio": "col.ratio",
            "modified": "col.modified",
            "crc": "col.crc",
        }
        widths = {
            "name": 300, "size": 78, "packed": 90, "ratio": 56,
            "modified": 118, "crc": 88,
        }
        anchors = {
            "name": "w", "size": "e", "packed": "e", "ratio": "e",
            "modified": "w", "crc": "w",
        }
        for column in columns:
            self.tree.heading(
                column,
                text=self.i18n.t(self._column_keys[column]),
                anchor=anchors[column],
                command=lambda col=column: self._sort_by(col),
            )
            self.tree.column(
                column,
                width=widths[column],
                minwidth=45,
                anchor=anchors[column],
                stretch=(column == "name"),
            )

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", lambda _e: self._on_activate())
        self.tree.bind("<Button-3>", self._on_context_menu)

        self.preview = PreviewPanel(
            self.content,
            self.i18n,
            self.theme,
            on_open=self._preview_open,
            on_extract=self._preview_extract,
        )
        self.preview.grid(
            row=1, column=1, sticky="nsew", padx=(6, 6), pady=(0, 6)
        )

        # -- status bar ------------------------------------------------
        self.status = StatusBar(self.root, self.i18n, on_cancel=self._cancel_task)
        self.status.grid(row=3, column=0, sticky="ew")

        self._apply_tree_tags()
        self._set_window_icon()
        if not self._sidebar_visible:
            self.paned.forget(self.sidebar)
        if not self._preview_visible:
            self.preview.grid_remove()

    def _set_window_icon(self) -> None:
        try:
            if getattr(sys, "_MEIPASS", None):
                base = Path(sys._MEIPASS) / "py7zip" / "resources"
            else:
                base = Path(__file__).resolve().parent.parent / "resources"
            self._icon_image = tk.PhotoImage(file=str(base / "icon.png"))
            self.root.iconphoto(True, self._icon_image)
        except Exception:
            self._icon_image = None

    def _register_button(
        self,
        key: str,
        button: ttk.Button,
        icon: str,
        variant: str,
        size: int,
        show_text: bool,
    ) -> None:
        name = key.split(".")[-1]
        self._buttons[name] = button
        self._button_defs[name] = (icon, key, variant, size, show_text)
        tooltip = Tooltip(button, self.i18n.t(key), self.theme)
        self._tooltips[button] = (tooltip, key)

    def _icon_button(
        self,
        parent,
        key: str,
        icon: str,
        command: Callable[[], None],
    ) -> ttk.Button:
        button = ttk.Button(
            parent,
            image=self._icons.get(icon, "normal", 16),
            style="Icon.TButton",
            command=command,
            takefocus=False,
        )
        button.pack(side="left", padx=(0, 1))
        self._register_button(key, button, icon, "normal", 16, False)
        return button

    def _tool_button(
        self,
        parent,
        key: str,
        icon: str,
        command: Callable[[], None],
    ) -> ttk.Button:
        button = ttk.Button(
            parent,
            image=self._icons.get(icon, "colored", 22),
            text="  " + self.i18n.t(key),
            compound="top",
            style="Tool.TButton",
            command=command,
            takefocus=False,
        )
        button.pack(side="left", padx=(0, 2))
        self._register_button(key, button, icon, "colored", 22, True)
        return button

    def _apply_button_icons(self) -> None:
        if self._icons is None:
            return
        for name, (icon, key, variant, size, show_text) in self._button_defs.items():
            button = self._buttons.get(name)
            if button is None:
                continue
            button.configure(image=self._icons.get(icon, variant, size))
            if show_text and key:
                button.configure(text="  " + self.i18n.t(key))
        try:
            self.path_icon.configure(
                image=self._icons.get("open", "colored", 16)
            )
            self._path_menu_button.configure(
                image=self._icons.get("down", "normal", 12)
            )
        except (AttributeError, tk.TclError):
            pass

    def _rebuild_icons(self) -> None:
        palette = self.theme.palette
        self._icons = IconSet(
            self.root,
            {
                "normal": palette["text"],
                "muted": palette["muted"],
                "accent": palette["accent_text"],
                "danger": palette["danger"],
            },
        )
        self._apply_button_icons()

    def _show_path_menu(self) -> None:
        menu = tk.Menu(self.root, tearoff=0, **self.theme.menu_options())
        for label, path in filesystem_roots():
            menu.add_command(
                label=label, command=lambda p=path: self._navigate(p, record=True)
            )
        recent = [
            path for path in self.settings.get("recent_files", [])
            if os.path.exists(path)
        ]
        if recent:
            menu.add_separator()
            for path in recent[:6]:
                menu.add_command(
                    label=f"{os.path.basename(path)}    —    {os.path.dirname(path)}",
                    command=lambda p=path: self._open_recent(p),
                )
        button = self._path_menu_button
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _apply_tree_tags(self) -> None:
        p = self.theme.palette
        self.tree.tag_configure("dir", foreground=p["accent"])
        self.tree.tag_configure("archive", font=self.theme.font_bold)
        self.tree.tag_configure("odd", background=p["surface"])
        self.tree.tag_configure("even", background=p["tree_alt"])
        self.tree.tag_configure("error", foreground=p["danger"])

    def _apply_window_geometry(self) -> None:
        geometry = self.settings.get("window_geometry") or "1000x640"
        try:
            self.root.geometry(geometry)
        except tk.TclError:
            self.root.geometry("1000x640")

    # ==================================================================
    # Menu
    # ==================================================================
    def _build_menu(self) -> None:
        options = self.theme.menu_options()
        menubar = tk.Menu(self.root, **options)
        self.menubar = menubar

        def menu(parent, label_key: str) -> tk.Menu:
            sub = tk.Menu(parent, tearoff=0, **options)
            parent.add_cascade(label=self.i18n.t(label_key), menu=sub)
            return sub

        def item(
            parent: tk.Menu,
            label_key: str,
            command: Callable[[], None],
            accelerator: str | None = None,
        ) -> None:
            parent.add_command(
                label=self.i18n.t(label_key),
                command=command,
                accelerator=accelerator,
            )

        file_menu = menu(menubar, "menu.file")
        item(file_menu, "menu.file.open", self._open_dialog, "Ctrl+O")
        item(file_menu, "menu.file.create", self._action_new, "Ctrl+N")
        item(file_menu, "menu.file.extract", self._action_extract, "Ctrl+E")
        add_menu = tk.Menu(file_menu, tearoff=0, **options)
        file_menu.add_cascade(
            label=self.i18n.t("menu.file.add"), menu=add_menu
        )
        item(add_menu, "menu.file.add_files", lambda: self._add_files("files"))
        item(add_menu, "menu.file.add_folder", lambda: self._add_files("folder"))
        item(file_menu, "menu.file.delete", self._action_delete, "Del")
        item(file_menu, "menu.file.test", self._action_test)
        item(
            file_menu, "menu.file.properties", self._action_properties,
            "Alt+Enter",
        )
        file_menu.add_separator()

        recent_menu = tk.Menu(file_menu, tearoff=0, **options)
        file_menu.add_cascade(
            label=self.i18n.t("menu.file.recent"), menu=recent_menu
        )
        recent = [
            path for path in self.settings.get("recent_files", [])
            if os.path.exists(path)
        ]
        if recent:
            for path in recent:
                label = f"{os.path.basename(path)}    —    {os.path.dirname(path)}"
                recent_menu.add_command(
                    label=label, command=lambda p=path: self._open_recent(p)
                )
            recent_menu.add_separator()
            recent_menu.add_command(
                label=self.i18n.t("menu.file.clear_recent"),
                command=self._clear_recent,
            )
        else:
            recent_menu.add_command(
                label=self.i18n.t("misc.unknown"), state="disabled"
            )

        file_menu.add_separator()
        item(file_menu, "menu.file.close_archive", self._close_archive)
        item(file_menu, "menu.file.exit", self.on_close, "Ctrl+Q")

        edit_menu = menu(menubar, "menu.edit")
        item(edit_menu, "menu.edit.select_all", self._select_all, "Ctrl+A")
        item(edit_menu, "menu.edit.deselect", self._deselect_all)
        item(edit_menu, "menu.edit.invert", self._invert_selection)
        edit_menu.add_separator()
        item(edit_menu, "menu.edit.find", self._focus_search, "Ctrl+F")

        view_menu = menu(menubar, "menu.view")
        item(view_menu, "menu.view.refresh", self._refresh, "F5")
        item(view_menu, "menu.view.up", self._go_up, "Backspace")
        item(view_menu, "menu.view.back", self._go_back)
        item(view_menu, "menu.view.forward", self._go_forward)
        view_menu.add_separator()
        view_menu.add_checkbutton(
            label=self.i18n.t("menu.view.preview"),
            variable=self._preview_var,
            command=self._toggle_preview,
        )
        view_menu.add_checkbutton(
            label=self.i18n.t("menu.view.sidebar"),
            variable=self._sidebar_var,
            command=self._toggle_sidebar,
        )
        view_menu.add_separator()
        view_menu.add_radiobutton(
            label=self.i18n.t("menu.view.dark"),
            variable=self._theme_var,
            value=0,
            command=lambda: self._set_theme("dark"),
        )
        view_menu.add_radiobutton(
            label=self.i18n.t("menu.view.light"),
            variable=self._theme_var,
            value=1,
            command=lambda: self._set_theme("light"),
        )
        language_menu = tk.Menu(view_menu, tearoff=0, **options)
        view_menu.add_cascade(
            label=self.i18n.t("menu.view.language"), menu=language_menu
        )
        from ..i18n import LANGUAGES

        for code, name in LANGUAGES.items():
            language_menu.add_radiobutton(
                label=name,
                variable=self._lang_var,
                value=code,
                command=lambda lang=code: self._set_language(lang),
            )

        tools_menu = menu(menubar, "menu.tools")
        item(tools_menu, "menu.tools.settings", self._action_settings)

        help_menu = menu(menubar, "menu.help")
        item(help_menu, "menu.help.shortcuts", self._show_shortcuts)
        item(help_menu, "menu.help.about", self._show_about)

        self.root.config(menu=menubar)

    # ==================================================================
    # Shortcuts
    # ==================================================================
    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda _e: self._open_dialog())
        self.root.bind("<Control-n>", lambda _e: self._action_new())
        self.root.bind("<Control-e>", lambda _e: self._action_extract())
        self.root.bind("<Control-f>", lambda _e: self._focus_search())
        self.root.bind("<F5>", lambda _e: self._refresh())
        self.root.bind("<Control-q>", lambda _e: self.on_close())
        self.root.bind("<Alt-Return>", lambda _e: self._action_properties())
        self.root.bind("<Control-a>", self._on_ctrl_a)
        self.root.bind("<BackSpace>", self._on_backspace)
        self.root.bind("<Delete>", self._on_delete_key)

    def _focus_in_text_input(self) -> bool:
        widget = self.root.focus_get()
        return isinstance(widget, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox))

    def _on_ctrl_a(self, _event=None):
        if self._focus_in_text_input():
            return None
        self._select_all()
        return "break"

    def _on_backspace(self, _event=None):
        if self._focus_in_text_input():
            return None
        self._go_up()
        return "break"

    def _on_delete_key(self, _event=None):
        if self._focus_in_text_input():
            return None
        if self.mode == "archive":
            self._action_delete()
            return "break"
        return None

    # ==================================================================
    # Navigation / history
    # ==================================================================
    def _location(self) -> tuple:
        if self.mode == "archive":
            return ("archive", self.archive_path, self.archive_prefix)
        return ("fs", self.cwd)

    def _push_history(self) -> None:
        location = self._location()
        if not self._back or self._back[-1] != location:
            self._back.append(location)
            if len(self._back) > 60:
                self._back.pop(0)
        self._forward.clear()

    def _navigate_location(self, location: tuple) -> None:
        if location[0] == "archive" and len(location) >= 2:
            prefix = location[2] if len(location) > 2 else ""
            self._open_archive(location[1], prefix=prefix, record=False)
        elif len(location) >= 2:
            self._navigate(location[1], record=False)

    def _go_back(self) -> None:
        if self._busy or not self._back:
            return
        self._forward.append(self._location())
        self._navigate_location(self._back.pop())

    def _go_forward(self) -> None:
        if self._busy or not self._forward:
            return
        self._back.append(self._location())
        self._navigate_location(self._forward.pop())

    def _can_go_up(self) -> bool:
        if self.mode == "archive":
            return True
        parent = os.path.dirname(self.cwd)
        return bool(parent and parent != self.cwd)

    def _go_up(self) -> None:
        if self._busy:
            return
        if self.mode == "archive":
            if self.archive_prefix:
                self._go_archive_prefix(parent_of(self.archive_prefix))
            else:
                target = os.path.dirname(self.archive_path or "") or self.cwd
                self._navigate(target, record=True)
        elif self._can_go_up():
            self._navigate(os.path.dirname(self.cwd), record=True)

    def _navigate_from_entry(self) -> None:
        text = self.path_var.get().strip().strip('"')
        if not text:
            return
        text = os.path.expanduser(text)
        if os.path.isfile(text) and is_archive_path(text):
            self._open_archive(text, record=True)
        elif os.path.isdir(text):
            self._navigate(text, record=True)
        else:
            messagebox.showwarning(
                self.i18n.t("msg.warning"),
                self.i18n.t("msg.file_missing", path=text),
                parent=self.root,
            )

    def _navigate(self, path: str, record: bool = True) -> None:
        if self._busy:
            return
        path = os.path.abspath(os.path.expanduser(path))
        try:
            items = self._list_fs(path)
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)
            return
        if record:
            self._push_history()
        self.mode = "fs"
        self.archive_path = None
        self.archive_entries = []
        self.archive_prefix = ""
        self.archive_password = None
        self.cwd = path
        self.settings.set("last_dir", path)
        self._fs_items = items
        self._filter_query = ""
        self.search_entry.clear()
        self.path_var.set(path)
        self.preview.clear()
        self._populate()
        self._update_header()
        self._update_actions()
        self._sync_sidebar()

    def _setup_initial(self, initial_path: str | None) -> None:
        candidate = initial_path or self.settings.get("last_dir") or os.path.expanduser("~")
        if candidate and os.path.isfile(candidate) and is_archive_path(candidate):
            self.cwd = os.path.dirname(candidate) or os.getcwd()
            self._open_archive(candidate, record=False)
        elif candidate and os.path.isdir(candidate):
            self._navigate(candidate, record=False)
        else:
            self._navigate(os.getcwd(), record=False)

    def _sync_sidebar(self) -> None:
        if self._sidebar_visible and self.mode == "fs":
            try:
                self.sidebar.select_path(self.cwd)
            except Exception:
                pass

    def _on_sidebar_select(self, path: str) -> None:
        if self._busy:
            return
        if self.mode == "archive" or os.path.abspath(path) != os.path.abspath(self.cwd):
            self._navigate(path, record=True)

    # ==================================================================
    # Filesystem
    # ==================================================================
    def _list_fs(self, path: str) -> list[FsItem]:
        items: list[FsItem] = []
        show_hidden = bool(self.settings.get("show_hidden"))
        try:
            with os.scandir(path) as iterator:
                for entry in iterator:
                    try:
                        is_dir = entry.is_dir(follow_symlinks=False)
                        stat = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if not show_hidden and self._is_hidden(entry.name, stat):
                        continue
                    items.append(
                        FsItem(
                            name=entry.name,
                            path=entry.path,
                            is_dir=is_dir,
                            size=0 if is_dir else int(stat.st_size),
                            mtime=stat.st_mtime,
                            is_link=entry.is_symlink(),
                            is_archive=is_archive_path(entry.name),
                        )
                    )
        except PermissionError as exc:
            raise ArchiveError(str(exc)) from exc
        except OSError as exc:
            raise ArchiveError(str(exc)) from exc
        return items

    @staticmethod
    def _is_hidden(name: str, stat: os.stat_result) -> bool:
        if name.startswith("."):
            return True
        attributes = getattr(stat, "st_file_attributes", 0)
        return bool(attributes & 0x2)

    # ==================================================================
    # Populating the list
    # ==================================================================
    def _current_items(self) -> list[Any]:
        query = self._filter_query.strip()
        if self.mode == "fs":
            items: list[Any] = list(self._fs_items)
            self._total_count = len(items)
            if query:
                items = [i for i in items if query.casefold() in i.name.casefold()]
        else:
            self._total_count = len(self.archive_entries)
            if query:
                items = search_entries(
                    self.archive_entries, self.archive_prefix, query
                )
            else:
                items = child_entries(self.archive_entries, self.archive_prefix)
        return self._sort_items(items)

    def _sort_items(self, items: list[Any]) -> list[Any]:
        column = self._sort_column
        reverse = self._sort_reverse
        mode = self.mode

        def name_key(item):
            return (item.basename if mode == "archive" else item.name).casefold()

        def type_key(item):
            if item.is_dir:
                return 0
            if mode == "fs":
                return 1 if item.is_archive else 2
            return 1 if is_archive_path(item.name) else 2

        keys = {
            "name": name_key,
            "size": lambda item: item.size,
            "packed": lambda item: item.packed if mode == "archive" else 0,
            "ratio": lambda item: (
                (item.packed / item.size) if item.size else 0.0
            ) if mode == "archive" else 0.0,
            "modified": lambda item: item.mtime or 0,
            "crc": lambda item: getattr(item, "crc", "") or "",
            "method": lambda item: getattr(item, "method", "") or "",
            "type": type_key,
        }
        key = keys.get(column, name_key)
        directories = [item for item in items if item.is_dir]
        files = [item for item in items if not item.is_dir]
        directories.sort(key=key, reverse=reverse)
        files.sort(key=key, reverse=reverse)
        return directories + files

    def _populate(self) -> None:
        self.tree.delete(*self.tree.get_children(""))
        self._row_map.clear()
        if self.mode == "fs":
            # Keep the file view simple and compact, like Explorer.
            self.tree.configure(
                displaycolumns=("name", "size", "modified")
            )
            if self._sort_column not in ("name", "size", "modified"):
                self._sort_column = "name"
                self._sort_reverse = False
        else:
            self.tree.configure(displaycolumns=self._all_columns)

        items = self._current_items()
        self._displayed_count = len(items)

        index = 0
        if self._show_parent_row():
            self.tree.insert(
                "",
                "end",
                iid="__parent__",
                values=(
                    "📁  ..",
                    "",
                    "",
                    "",
                    "",
                    "",
                ),
                tags=("dir", "odd"),
            )
            index = 1

        for item in items:
            iid = f"row{index}"
            index += 1
            self._row_map[iid] = item
            values = self._row_values(item)
            tags = []
            if item.is_dir:
                tags.append("dir")
            else:
                if self.mode == "fs" and item.is_archive:
                    tags.append("archive")
                elif self.mode == "archive" and is_archive_path(item.name):
                    tags.append("archive")
            tags.append("odd" if index % 2 else "even")
            self.tree.insert("", "end", iid=iid, values=values, tags=tuple(tags))

        self._update_headings()
        self._update_status()
        self._update_actions()

    def _show_parent_row(self) -> bool:
        if self._filter_query.strip():
            return False
        if self.mode == "archive":
            return bool(self.archive_prefix)
        return self._can_go_up()

    def _row_values(self, item: Any) -> tuple:
        if self.mode == "archive":
            name = item.basename
            if self._filter_query.strip() and self.archive_prefix:
                marker = self.archive_prefix + "/"
                if item.name.startswith(marker):
                    name = item.name[len(marker):]
            size = "" if item.is_dir else human_size(item.size)
            packed = "" if item.is_dir else human_size(item.packed)
            ratio = "" if item.is_dir else ratio_text(item.size, item.packed)
            modified = format_timestamp(item.mtime)
            crc = "" if item.is_dir else (item.crc or "")
        else:
            name = item.name
            size = "" if item.is_dir else human_size(item.size)
            packed = ratio = crc = ""
            modified = format_timestamp(item.mtime)

        icon = file_icon_name(item.name, item.is_dir)
        return (
            f"{icon}  {name}",
            size,
            packed,
            ratio,
            modified,
            crc,
        )

    def _type_label(self, item: Any) -> str:
        if item.is_dir:
            return self.i18n.t("type.folder")
        if getattr(item, "is_link", False) or getattr(item, "is_symlink", False):
            return self.i18n.t("type.symlink")
        if is_archive_path(item.name):
            return self.i18n.t("type.archive")
        return self.i18n.t("type.file")

    def _update_headings(self) -> None:
        for column, key in self._column_keys.items():
            text = self.i18n.t(key)
            if column == self._sort_column:
                text += " ▲" if not self._sort_reverse else " ▼"
            self.tree.heading(column, text=text)

    def _sort_by(self, column: str) -> None:
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = column in ("size", "packed", "ratio", "modified")
        self.settings.set("sort_column", self._sort_column)
        self.settings.set("sort_reverse", self._sort_reverse)
        self._populate()

    # ==================================================================
    # Status / header / actions
    # ==================================================================
    def _update_header(self) -> None:
        if self.mode == "archive" and self.archive_path:
            split_base = split_base_path(self.archive_path)
            name = os.path.basename(split_base or self.archive_path)
            self.title_label.configure(text=name)
            fmt_key = detect_format(self.archive_path)
            fmt = ARCHIVE_FORMATS.get(fmt_key or "")
            badge = fmt.label if fmt else ""
            if split_base:
                badge += " · " + self.i18n.t("type.split")
            self.badge_label.configure(text=badge)
            self.badge_label.grid()
            self.header_close.grid()
            self.path_var.set(self.archive_path)
        else:
            name = os.path.basename(self.cwd.rstrip("\\/")) or self.cwd
            self.title_label.configure(text=name)
            self.badge_label.grid_remove()
            self.header_close.grid_remove()
            self.path_var.set(self.cwd)

    def _update_status(self) -> None:
        if self._busy:
            return
        if self.mode == "archive" and self.archive_path:
            left = self.i18n.t(
                "status.archive", name=os.path.basename(self.archive_path)
            )
            if self.archive_prefix:
                left += f"  ›  {self.archive_prefix}"
        else:
            left = shorten_path(self.cwd, 95)
        self.status.set_left(left)

        if self._filter_query.strip():
            text = self.i18n.t(
                "status.filtered",
                count=self._displayed_count,
                total=self._total_count,
            )
        else:
            text = self.i18n.t("status.items", count=self._displayed_count)
        selected = self._selected_items()
        if selected:
            size = sum(
                item.size for item in selected
                if not getattr(item, "is_dir", False)
            )
            text += "  ·  " + self.i18n.t(
                "status.selected", count=len(selected)
            )
            if size:
                text += "  ·  " + self.i18n.t(
                    "status.selected_size", size=human_size(size)
                )
        self.status.set_center(text)

    def _selected_items(self) -> list[Any]:
        result = []
        for iid in self.tree.selection():
            item = self._row_map.get(iid)
            if item is not None:
                result.append(item)
        return result

    def _selected_fs_paths(self) -> list[str]:
        return [
            item.path for item in self._selected_items()
            if isinstance(item, FsItem)
        ]

    def _update_actions(self) -> None:
        in_archive = self.mode == "archive"
        selected = self._selected_items()
        has_selection = bool(selected)
        fs_archive_selected = any(
            isinstance(item, FsItem) and item.is_archive for item in selected
        )
        busy = self._busy

        state = lambda enabled: "normal" if enabled and not busy else "disabled"
        self._buttons["open"].configure(state=state(True))
        self._buttons["create"].configure(state=state(True))
        self._buttons["extract"].configure(
            state=state(
                (in_archive and bool(self.archive_entries))
                or (not in_archive and fs_archive_selected)
            )
        )
        self._buttons["add"].configure(state=state(in_archive))
        self._buttons["delete"].configure(state=state(in_archive and has_selection))
        self._buttons["test"].configure(state=state(in_archive))
        self._buttons["back"].configure(state=state(bool(self._back)))
        self._buttons["forward"].configure(state=state(bool(self._forward)))
        self._buttons["up"].configure(state=state(self._can_go_up()))
        self._buttons["refresh"].configure(state=state(True))
        self._buttons["preview"].configure(state=state(True))
        self._buttons["settings"].configure(state=state(True))
        self._buttons["info"].configure(state=state(True))
        self.header_close.configure(state=state(in_archive))

    # ==================================================================
    # Task runner
    # ==================================================================
    def _run_task(
        self,
        label: str,
        job: Callable[[Callable[[int, int, str], None], threading.Event], Any],
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        if self._busy:
            return
        self._busy = True
        self._cancel_event = threading.Event()
        self.status.begin(label)
        self._update_actions()

        self._cancel_progress_show()
        if self._progress_dialog is not None:
            self._progress_dialog.close()
        self._progress_dialog = ProgressDialog(
            self.root, self.i18n, self.theme, label, self._cancel_task
        )
        self._progress_show_id = self.root.after(
            200, self._show_progress_dialog
        )

        events: queue.Queue = queue.Queue()

        def progress(current: int, total: int, message: str) -> None:
            events.put(("progress", current, total, message))

        def worker() -> None:
            try:
                result = job(progress, self._cancel_event)
                events.put(("done", result))
            except OperationCancelled:
                events.put(("cancel", None))
            except Exception as exc:  # noqa: BLE001 - surfaced in the UI
                events.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()
        self._poll_task(events, on_success, on_error)

    def _poll_task(
        self,
        events: queue.Queue,
        on_success: Callable[[Any], None] | None,
        on_error: Callable[[Exception], None] | None,
    ) -> None:
        try:
            while True:
                event = events.get_nowait()
                kind = event[0]
                if kind == "progress":
                    _, current, total, message = event
                    self.status.set_progress(current, total, message)
                    if self._progress_dialog is not None:
                        self._progress_dialog.update_progress(
                            current, total, message
                        )
                elif kind == "done":
                    self._close_progress(finished=True)
                    self._finish_task()
                    if on_success:
                        on_success(event[1])
                    return
                elif kind == "cancel":
                    self._close_progress()
                    self._finish_task()
                    self.status.end(self.i18n.t("status.cancelled"))
                    return
                elif kind == "error":
                    self._close_progress()
                    self._finish_task()
                    if on_error:
                        on_error(event[1])
                    else:
                        self._show_error(event[1])
                    return
        except queue.Empty:
            pass
        try:
            self.root.after(80, lambda: self._poll_task(events, on_success, on_error))
        except tk.TclError:
            pass

    def _finish_task(self) -> None:
        self._busy = False
        self.status.end(None)
        self._update_actions()
        self._update_status()

    def _show_progress_dialog(self) -> None:
        self._progress_show_id = None
        if self._busy and self._progress_dialog is not None:
            self._progress_dialog.show()

    def _cancel_progress_show(self) -> None:
        if self._progress_show_id is not None:
            try:
                self.root.after_cancel(self._progress_show_id)
            except tk.TclError:
                pass
            self._progress_show_id = None

    def _close_progress(self, finished: bool = False) -> None:
        self._cancel_progress_show()
        dialog = self._progress_dialog
        self._progress_dialog = None
        if dialog is None:
            return
        if finished and dialog.is_shown():
            dialog.finish()
        else:
            dialog.close()

    def _cancel_task(self) -> None:
        self._cancel_event.set()
        if self._progress_dialog is not None:
            self._progress_dialog.mark_cancelling()

    def _show_error(self, exc: Exception) -> None:
        if isinstance(exc, OperationCancelled):
            self.status.end(self.i18n.t("status.cancelled"))
            return
        if isinstance(exc, PasswordRequiredError):
            message = self.i18n.t("dlg.password.wrong")
        else:
            message = str(exc) or exc.__class__.__name__
        messagebox.showerror(
            self.i18n.t("msg.error"), message, parent=self.root
        )

    # ==================================================================
    # Opening archives
    # ==================================================================
    def _archive_filetypes(self) -> list[tuple[str, str]]:
        patterns: set[str] = set()
        for fmt in ARCHIVE_FORMATS.values():
            for ext in fmt.all_extensions:
                patterns.add("*" + ext)
        patterns.add("*.001")
        joined = " ".join(sorted(patterns))
        return [
            (self.i18n.t("app.archive_manager"), joined),
            (self.i18n.t("misc.file"), "*.*"),
        ]

    def _open_dialog(self) -> None:
        if self._busy:
            return
        path = filedialog.askopenfilename(
            parent=self.root,
            title=self.i18n.t("menu.file.open"),
            initialdir=self.settings.get("last_archive_dir") or self.cwd,
            filetypes=self._archive_filetypes(),
        )
        if not path:
            return
        self.settings.set("last_archive_dir", os.path.dirname(path))
        if is_archive_path(path):
            self._open_archive(path, record=True)
        else:
            messagebox.showwarning(
                self.i18n.t("msg.warning"),
                self.i18n.t("msg.not_archive"),
                parent=self.root,
            )

    def _open_recent(self, path: str) -> None:
        if os.path.exists(path):
            self._open_archive(path, record=True)
        else:
            messagebox.showwarning(
                self.i18n.t("msg.warning"),
                self.i18n.t("msg.file_missing", path=path),
                parent=self.root,
            )

    def _clear_recent(self) -> None:
        self.settings.clear_recent()
        self.settings.save()
        self._build_menu()

    def _open_archive(
        self,
        path: str,
        prefix: str = "",
        record: bool = True,
        password: str | None = None,
        retries: int = 3,
    ) -> None:
        if self._busy:
            return
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            messagebox.showwarning(
                self.i18n.t("msg.warning"),
                self.i18n.t("msg.file_missing", path=path),
                parent=self.root,
            )
            return
        if record:
            self._push_history()
        if password is None:
            password = self._passwords.get(path)
        self.archive_password = password
        self.settings.set("last_archive_dir", os.path.dirname(path))

        def job(progress, cancel):
            return self.engine.list_archive(
                path, password=self.archive_password
            )

        def done(entries: list[Entry]) -> None:
            if self.archive_password:
                self._passwords[path] = self.archive_password
            self.mode = "archive"
            self.archive_path = path
            self.archive_entries = entries
            self.archive_prefix = self._validate_prefix(prefix, entries)
            self._filter_query = ""
            self.search_entry.clear()
            self.preview.clear()
            self._populate()
            self._update_header()
            self._update_actions()
            self._update_status()
            self.settings.add_recent(path)
            self.settings.save()
            self._build_menu()
            self.status.end(self.i18n.t("status.done"))

        def failed(exc: Exception) -> None:
            if isinstance(exc, PasswordRequiredError) and retries > 0:
                dialog = PasswordDialog(
                    self.root, self.i18n, self.theme,
                    hint=self.i18n.t("msg.password_required"),
                )
                entered = dialog.show()
                if entered:
                    self._open_archive(
                        path, prefix=prefix, record=False,
                        password=entered, retries=retries - 1,
                    )
                    return
                self.status.end(self.i18n.t("status.ready"))
                return
            self._show_error(exc)
            self.status.end(self.i18n.t("status.ready"))

        self._run_task(self.i18n.t("status.opening"), job, done, failed)

    @staticmethod
    def _validate_prefix(prefix: str, entries: list[Entry]) -> str:
        prefix = normalize_name(prefix)
        if not prefix:
            return ""
        for entry in entries:
            if entry.name == prefix or entry.name.startswith(prefix + "/"):
                return prefix
        return ""

    def _reload_archive(self, on_done: Callable[[], None] | None = None) -> None:
        if not self.archive_path:
            return
        self._open_archive(
            self.archive_path,
            prefix=self.archive_prefix,
            record=False,
            password=self.archive_password,
        )

    def _go_archive_prefix(self, prefix: str) -> None:
        prefix = normalize_name(prefix)
        self._push_history()
        self.archive_prefix = prefix
        self._filter_query = ""
        self.search_entry.clear()
        self.preview.clear()
        self._populate()
        self._update_header()
        self._update_actions()
        self._update_status()

    def _close_archive(self, navigate_to: str | None = None) -> None:
        if self.mode != "archive":
            return
        target = navigate_to or (
            os.path.dirname(self.archive_path or "") or self.cwd
        )
        self._navigate(target, record=True)

    # ==================================================================
    # Selection / activation
    # ==================================================================
    def _on_tree_select(self, _event=None) -> None:
        self._update_status()
        self._update_actions()
        if not self._preview_visible:
            return
        selection = self.tree.selection()
        if len(selection) != 1 or selection[0] == "__parent__":
            self.preview.clear()
            return
        item = self._row_map.get(selection[0])
        if item is None:
            self.preview.clear()
            return
        if item.is_dir:
            self.preview.clear()
            return
        if self.mode == "fs":
            self.preview.show_path(item.path)
        else:
            self.preview.show_archive_entry(
                self.engine, self.archive_path, item,
                self.archive_password,
            )

    def _on_double_click(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self._on_activate()

    def _on_activate(self) -> None:
        selection = self.tree.selection()
        if len(selection) != 1:
            return
        iid = selection[0]
        if iid == "__parent__":
            self._go_up()
            return
        item = self._row_map.get(iid)
        if item is None:
            return
        if self.mode == "fs":
            if item.is_dir:
                self._navigate(item.path, record=True)
            elif item.is_archive:
                self._open_archive(item.path, record=True)
            else:
                self._open_path_external(item.path)
        else:
            if item.is_dir:
                self._go_archive_prefix(item.name)
            else:
                self._open_entry_external(item)

    def _open_path_external(self, path: str) -> None:
        try:
            open_with_default(path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                self.i18n.t("msg.error"),
                self.i18n.t("msg.open_error", detail=str(exc)),
                parent=self.root,
            )

    def _open_entry_external(self, entry: Entry) -> None:
        if not self.archive_path or self._busy:
            return
        temp_dir = make_temp_dir("py7zip-open-")
        self._temp_dirs.append(temp_dir)
        archive_path = self.archive_path
        password = self.archive_password

        def job(progress, cancel):
            return self.engine.extract_member(
                archive_path, entry.name, temp_dir, password=password
            )

        def done(target: str) -> None:
            self.status.end(self.i18n.t("status.done"))
            self._open_path_external(target)

        self._run_task(self.i18n.t("status.extracting"), job, done)

    # ==================================================================
    # Preview callbacks
    # ==================================================================
    def _preview_open(self, context) -> None:
        if context[0] == "fs":
            self._open_path_external(context[1])
        elif context[0] == "archive":
            self._open_entry_external(context[2])

    def _preview_extract(self, context) -> None:
        if context[0] != "archive":
            return
        entry = context[2]
        destination = filedialog.askdirectory(
            parent=self.root,
            title=self.i18n.t("preview.extract"),
            initialdir=self.settings.get("extract_dir") or self.cwd,
        )
        if not destination:
            return
        archive_path = context[1]
        password = context[3]

        def job(progress, cancel):
            return self.engine.extract_member(
                archive_path, entry.name, destination, password=password
            )

        def done(_target) -> None:
            self.status.end(
                self.i18n.t("msg.extract_success", path=destination)
            )

        self._run_task(self.i18n.t("status.extracting"), job, done)

    # ==================================================================
    # Create / extract / add / delete / test
    # ==================================================================
    def _action_new(self) -> None:
        if self._busy:
            return
        if self.mode == "archive":
            sources = [self.cwd]
            default_dir = self.cwd
        else:
            sources = self._selected_fs_paths() or [self.cwd]
            default_dir = self.cwd
        first = sources[0].rstrip("\\/")
        default_name = os.path.basename(first) or self.i18n.t(
            "dlg.create.default_name"
        )
        dialog = CreateArchiveDialog(
            self.root,
            self.i18n,
            self.theme,
            sources=sources,
            default_dir=default_dir,
            default_name=default_name,
            default_format="7z",
            default_level=int(self.settings.get("compression_level", 5)),
            default_method=self.settings.get("compression_method", "LZMA2"),
        )
        result = dialog.show()
        if not result:
            return
        self.settings.set("compression_level", result["level"])
        self.settings.set("compression_method", result["method"])
        self.settings.save()

        def job(progress, cancel):
            self.engine.create_archive(
                result["path"],
                result["sources"],
                fmt_key=result["format"],
                arc_root=result["arc_root"],
                password=result["password"],
                level=result["level"],
                method=result["method"],
                encrypt_header=result["encrypt_header"],
                progress=progress,
                cancel=cancel,
                part_size=result.get("part_size", 0),
            )

        def done(_result) -> None:
            created = result["path"]
            if result.get("part_size") and os.path.exists(created + ".001"):
                created = created + ".001"
            self.settings.add_recent(created)
            self.settings.save()
            self._build_menu()
            self.status.end(self.i18n.t("status.done"))
            if self.mode == "fs":
                self._navigate(self.cwd, record=False)
                self._select_path(os.path.abspath(created))

        self._run_task(self.i18n.t("status.creating"), job, done)

    def _select_path(self, path: str) -> None:
        for iid, item in self._row_map.items():
            if isinstance(item, FsItem) and os.path.abspath(item.path) == path:
                self.tree.selection_set(iid)
                self.tree.see(iid)
                return

    def _action_extract(self) -> None:
        if self._busy:
            return
        if self.mode == "archive":
            if not self.archive_path:
                return
            archives = [self.archive_path]
            selected = self._selected_items()
            chosen = {
                item.name for item in selected if isinstance(item, Entry)
            }
            if chosen:
                members = selected_member_names(
                    self.archive_entries, chosen, recursive=True
                )
                if not members:
                    messagebox.showinfo(
                        self.i18n.t("msg.info"),
                        self.i18n.t("msg.nothing_to_extract"),
                        parent=self.root,
                    )
                    return
            else:
                members = []
            total = len([e for e in self.archive_entries if not e.is_dir])
            default_destination = (
                self.settings.get("extract_dir")
                or os.path.dirname(self.archive_path)
                or self.cwd
            )
        else:
            archives = [
                item.path for item in self._selected_items()
                if isinstance(item, FsItem) and item.is_archive
            ]
            if not archives:
                messagebox.showinfo(
                    self.i18n.t("msg.info"),
                    self.i18n.t("msg.select_archive_first"),
                    parent=self.root,
                )
                return
            members = []
            total = 0
            default_destination = (
                self.settings.get("extract_dir") or self.cwd
            )

        dialog = ExtractDialog(
            self.root,
            self.i18n,
            self.theme,
            archive_path=archives[0],
            default_destination=default_destination,
            selected_members=members,
            total_members=total,
        )
        result = dialog.show()
        if not result:
            return
        self._start_extract(archives, result)

    def _start_extract(self, archives: list[str], result: dict) -> None:
        destination = result["destination"]
        members = result["members"]
        password = result["password"] or self.archive_password
        overwrite = result["overwrite"]
        if password:
            for archive in archives:
                self._passwords[archive] = password

        def job(progress, cancel):
            total = len(archives)
            for index, archive in enumerate(archives):
                progress(index, total, os.path.basename(archive))
                self.engine.extract_archive(
                    archive,
                    destination,
                    members=members,
                    password=password,
                    overwrite=overwrite,
                    progress=progress,
                    cancel=cancel,
                )
            progress(total, total, "")

        def done(_result) -> None:
            self.status.end(
                self.i18n.t("msg.extract_success", path=destination)
            )

        def failed(exc: Exception) -> None:
            if isinstance(exc, PasswordRequiredError):
                dialog = PasswordDialog(
                    self.root, self.i18n, self.theme,
                    hint=self.i18n.t("msg.password_required"),
                )
                entered = dialog.show()
                if entered:
                    result["password"] = entered
                    self._start_extract(archives, result)
                    return
            self._show_error(exc)

        self._run_task(self.i18n.t("status.extracting"), job, done, failed)

    def _action_add(self) -> None:
        if self.mode != "archive" or not self.archive_path:
            messagebox.showinfo(
                self.i18n.t("msg.info"),
                self.i18n.t("msg.no_archive_open"),
                parent=self.root,
            )
            return
        if split_base_path(self.archive_path):
            messagebox.showinfo(
                self.i18n.t("msg.info"),
                self.i18n.t("msg.split_modify_unsupported"),
                parent=self.root,
            )
            return
        button = self._buttons.get("add")
        menu = tk.Menu(self.root, tearoff=0, **self.theme.menu_options())
        menu.add_command(
            label=self.i18n.t("menu.file.add_files"),
            command=lambda: self._add_files("files"),
        )
        menu.add_command(
            label=self.i18n.t("menu.file.add_folder"),
            command=lambda: self._add_files("folder"),
        )
        if button is not None:
            x = button.winfo_rootx()
            y = button.winfo_rooty() + button.winfo_height()
            menu.post(x, y)
        else:
            menu.post(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def _add_files(self, kind: str) -> None:
        if self.mode != "archive" or not self.archive_path or self._busy:
            return
        if kind == "folder":
            folder = filedialog.askdirectory(
                parent=self.root,
                title=self.i18n.t("menu.file.add_folder"),
                initialdir=self.cwd,
            )
            if not folder:
                return
            items = [folder]
            arc_root = os.path.dirname(folder)
        else:
            files = filedialog.askopenfilenames(
                parent=self.root,
                title=self.i18n.t("menu.file.add_files"),
                initialdir=self.cwd,
            )
            if not files:
                return
            items = list(files)
            arc_root = common_parent(items)

        archive_path = self.archive_path
        password = self.archive_password

        def job(progress, cancel):
            self.engine.add_to_archive(
                archive_path,
                items,
                arc_root=arc_root,
                password=password,
                level=int(self.settings.get("compression_level", 5)),
                method=self.settings.get("compression_method", "LZMA2"),
                progress=progress,
                cancel=cancel,
            )

        def done(_result) -> None:
            self.status.end(self.i18n.t("msg.add_success"))
            self._reload_archive()

        self._run_task(self.i18n.t("status.adding"), job, done)

    def _action_delete(self) -> None:
        if self.mode != "archive" or not self.archive_path:
            return
        if split_base_path(self.archive_path):
            messagebox.showinfo(
                self.i18n.t("msg.info"),
                self.i18n.t("msg.split_modify_unsupported"),
                parent=self.root,
            )
            return
        selected = [
            item for item in self._selected_items() if isinstance(item, Entry)
        ]
        if not selected:
            messagebox.showinfo(
                self.i18n.t("msg.info"),
                self.i18n.t("msg.nothing_to_delete"),
                parent=self.root,
            )
            return
        if self.settings.get("confirm_delete", True):
            text = self.i18n.t("msg.confirm_delete", count=len(selected))
            if not messagebox.askyesno(
                self.i18n.t("msg.confirm"), text, parent=self.root
            ):
                return

        names = [item.name for item in selected]
        archive_path = self.archive_path
        password = self.archive_password
        prefix = self.archive_prefix

        def job(progress, cancel):
            self.engine.delete_from_archive(
                archive_path,
                names,
                password=password,
                progress=progress,
                cancel=cancel,
            )

        def done(_result) -> None:
            self.status.end(self.i18n.t("msg.delete_success"))
            self._filter_query = ""
            self.search_entry.clear()
            for name in names:
                if prefix == name or prefix.startswith(name + "/"):
                    self.archive_prefix = parent_of(name)
                    break
            self._reload_archive()

        self._run_task(self.i18n.t("status.deleting"), job, done)

    def _action_test(self) -> None:
        if self.mode != "archive" or not self.archive_path:
            messagebox.showinfo(
                self.i18n.t("msg.info"),
                self.i18n.t("msg.no_archive_open"),
                parent=self.root,
            )
            return
        archive_path = self.archive_path
        password = self.archive_password

        def job(progress, cancel):
            self.engine.test_archive(
                archive_path, password=password, progress=progress, cancel=cancel
            )

        def done(_result) -> None:
            self.status.end(self.i18n.t("status.done"))
            messagebox.showinfo(
                self.i18n.t("msg.info"),
                self.i18n.t("msg.test_ok"),
                parent=self.root,
            )

        def failed(exc: Exception) -> None:
            messagebox.showerror(
                self.i18n.t("msg.error"),
                self.i18n.t("msg.test_failed", detail=str(exc)),
                parent=self.root,
            )

        self._run_task(self.i18n.t("status.testing"), job, done, failed)

    # ==================================================================
    # Properties / settings / help
    # ==================================================================
    def _action_properties(self) -> None:
        if self._busy:
            return
        if self.mode == "archive":
            selected = [
                item for item in self._selected_items()
                if isinstance(item, Entry)
            ]
            if len(selected) == 1:
                self._show_entry_properties(selected[0])
            else:
                self._show_archive_properties()
            return
        selected = self._selected_items()
        if not selected:
            selected = [
                FsItem(
                    name=os.path.basename(self.cwd.rstrip("\\/")) or self.cwd,
                    path=self.cwd,
                    is_dir=True,
                    size=0,
                    mtime=os.path.getmtime(self.cwd),
                    is_archive=is_archive_path(self.cwd),
                )
            ]
        if len(selected) > 1:
            pairs = [
                (self.i18n.t("dlg.properties.entries"), str(len(selected))),
                (
                    self.i18n.t("dlg.properties.size"),
                    human_size(sum(i.size for i in selected)),
                ),
            ]
            PropertiesDialog(
                self.root, self.i18n, self.theme,
                self.i18n.t("dlg.properties.title"), pairs,
            ).show()
            return
        item = selected[0]
        try:
            stat = os.stat(item.path)
            mtime = stat.st_mtime
            size = stat.st_size
        except OSError:
            mtime = item.mtime
            size = item.size
        pairs = [
            (self.i18n.t("dlg.properties.name"), item.name),
            (
                self.i18n.t("dlg.properties.type"),
                self.i18n.t("type.folder") if item.is_dir
                else (self.i18n.t("type.archive") if item.is_archive
                      else self.i18n.t("type.file")),
            ),
            (self.i18n.t("dlg.properties.size"), human_size(size)),
            (self.i18n.t("dlg.properties.modified"), format_timestamp(mtime)),
            (self.i18n.t("dlg.properties.path"), item.path),
        ]
        PropertiesDialog(
            self.root, self.i18n, self.theme,
            self.i18n.t("dlg.properties.title"), pairs,
        ).show()

    def _show_entry_properties(self, entry: Entry) -> None:
        pairs = [
            (self.i18n.t("dlg.properties.name"), entry.name),
            (
                self.i18n.t("dlg.properties.type"),
                self.i18n.t("type.folder") if entry.is_dir
                else self.i18n.t("type.file"),
            ),
            (self.i18n.t("dlg.properties.size"), human_size(entry.size)),
            (self.i18n.t("dlg.properties.packed"), human_size(entry.packed)),
            (
                self.i18n.t("dlg.properties.ratio"),
                ratio_text(entry.size, entry.packed),
            ),
            (self.i18n.t("dlg.properties.modified"),
             format_timestamp(entry.mtime)),
            (self.i18n.t("dlg.properties.methods"), entry.method or "—"),
            (self.i18n.t("col.crc"), entry.crc or "—"),
            (
                self.i18n.t("dlg.properties.encrypted"),
                self.i18n.t("dlg.properties.yes") if entry.encrypted
                else self.i18n.t("dlg.properties.no"),
            ),
        ]
        PropertiesDialog(
            self.root, self.i18n, self.theme,
            f"{self.i18n.t('dlg.properties.title')} — {entry.basename}", pairs,
        ).show()

    def _show_archive_properties(self) -> None:
        archive_path = self.archive_path
        password = self.archive_password

        def job(progress, cancel):
            return self.engine.archive_info(archive_path, password=password)

        def done(info: dict) -> None:
            pairs = [
                (self.i18n.t("dlg.properties.name"), info["name"]),
                (self.i18n.t("dlg.properties.format"), info["format"]),
                (self.i18n.t("dlg.properties.entries"), str(info["count"])),
                (
                    self.i18n.t("dlg.properties.size"),
                    human_size(info["unpacked"]),
                ),
                (
                    self.i18n.t("dlg.properties.packed"),
                    human_size(info["size_on_disk"]),
                ),
                (
                    self.i18n.t("dlg.properties.ratio"),
                    f"{info['ratio']:.1f}%",
                ),
                (
                    self.i18n.t("dlg.properties.methods"),
                    ", ".join(info["methods"]) or "—",
                ),
                (
                    self.i18n.t("dlg.properties.encrypted"),
                    self.i18n.t("dlg.properties.yes") if info["encrypted"]
                    else self.i18n.t("dlg.properties.no"),
                ),
                (
                    self.i18n.t("dlg.properties.modified"),
                    format_timestamp(info["mtime"]),
                ),
                (self.i18n.t("dlg.properties.path"), info["path"]),
            ]
            if info.get("split"):
                pairs.insert(
                    2,
                    (
                        self.i18n.t("type.split"),
                        self.i18n.t("dlg.properties.yes"),
                    ),
                )
            self.status.end(self.i18n.t("status.done"))
            PropertiesDialog(
                self.root, self.i18n, self.theme,
                self.i18n.t("dlg.properties.title"), pairs,
            ).show()

        self._run_task(self.i18n.t("status.working"), job, done)

    def _action_settings(self) -> None:
        if self._busy:
            return
        dialog = SettingsDialog(
            self.root, self.i18n, self.theme, self.settings
        )
        result = dialog.show()
        if result:
            self._apply_settings(result)

    def _apply_settings(self, values: dict) -> None:
        self.settings.update(**values)
        self.settings.save()

        if values.get("language"):
            self.i18n.set_language(values["language"])
            self._lang_var.set(self.i18n.language)
        if values.get("theme"):
            self.theme.apply(values["theme"])
            self._theme_var.set(0 if values["theme"] == "dark" else 1)

        self._preview_visible = bool(values.get("preview_enabled", True))
        self._preview_var.set(self._preview_visible)
        self._sidebar_visible = bool(values.get("sidebar_visible", self._sidebar_visible))
        self._sidebar_var.set(self._sidebar_visible)
        self._apply_visibility()

        self._apply_tree_tags()
        self.preview.apply_theme()
        self._rebuild_icons()
        self.search_entry.set_colors(
            self.theme.palette["text"], self.theme.palette["muted"]
        )
        self._retranslate()
        self._build_menu()
        self._populate()
        self._update_header()
        self._update_status()

    def _apply_visibility(self) -> None:
        if self._preview_visible:
            self.preview.grid()
        else:
            self.preview.grid_remove()
        if self._sidebar_visible:
            try:
                self.paned.add(self.sidebar, weight=1)
            except tk.TclError:
                pass
        else:
            try:
                self.paned.forget(self.sidebar)
            except tk.TclError:
                pass

    def _toggle_preview(self) -> None:
        self._preview_visible = not self._preview_visible
        self._preview_var.set(self._preview_visible)
        self.settings.set("preview_enabled", self._preview_visible)
        self.settings.save()
        self._apply_visibility()
        if self._preview_visible:
            self._on_tree_select()

    def _toggle_sidebar(self) -> None:
        self._sidebar_visible = not self._sidebar_visible
        self._sidebar_var.set(self._sidebar_visible)
        self.settings.set("sidebar_visible", self._sidebar_visible)
        self.settings.save()
        try:
            if self._sidebar_visible:
                self.paned.add(self.sidebar, weight=1)
            else:
                self.paned.forget(self.sidebar)
        except tk.TclError:
            pass

    def _set_theme(self, mode: str) -> None:
        self.settings.set("theme", mode)
        self.settings.save()
        self.theme.apply(mode)
        self._theme_var.set(0 if mode == "dark" else 1)
        self._apply_tree_tags()
        self.preview.apply_theme()
        self._rebuild_icons()
        self.search_entry.set_colors(
            self.theme.palette["text"], self.theme.palette["muted"]
        )
        self._build_menu()

    def _set_language(self, language: str) -> None:
        self.i18n.set_language(language)
        self.settings.set("language", language)
        self.settings.save()
        self._lang_var.set(language)
        self._retranslate()
        self._build_menu()

    def _retranslate(self) -> None:
        self.root.title(f"{APP_NAME} — {self.i18n.t('app.archive_manager')}")
        self._apply_button_icons()
        for widget, (tooltip, key) in self._tooltips.items():
            try:
                tooltip.set_text(self.i18n.t(key))
            except tk.TclError:
                pass
        self.search_entry.set_placeholder(self.i18n.t("search.placeholder"))
        self.header_close.configure(
            text=self.i18n.t("menu.file.close_archive")
        )
        self.preview.retranslate()
        self.status.retranslate()
        self._update_headings()
        self._update_header()
        self._update_status()

    def _show_shortcuts(self) -> None:
        TextDialog(
            self.root,
            self.i18n,
            self.theme,
            self.i18n.t("dlg.shortcuts.title"),
            self.i18n.t("dlg.shortcuts.text"),
        ).show()

    def _show_about(self) -> None:
        TextDialog(
            self.root,
            self.i18n,
            self.theme,
            self.i18n.t("dlg.about.title"),
            self.i18n.t("dlg.about.description")
            + "\n\n"
            + self.i18n.t("dlg.about.author"),
            subtitle=self.i18n.t("dlg.about.version", version=__version__),
        ).show()

    # ==================================================================
    # Search / selection helpers
    # ==================================================================
    def _apply_filter(self) -> None:
        self._filter_query = self.search_entry.get_text().strip()
        self._populate()
        self._update_status()

    def _clear_filter(self) -> None:
        self.search_entry.clear()
        self._filter_query = ""
        self._populate()
        self._update_status()

    def _focus_search(self) -> None:
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, "end")

    def _select_all(self) -> None:
        children = self.tree.get_children("")
        if children:
            self.tree.selection_set(children)

    def _deselect_all(self) -> None:
        self.tree.selection_remove(*self.tree.selection())

    def _invert_selection(self) -> None:
        selected = set(self.tree.selection())
        inverted = [
            iid for iid in self.tree.get_children("") if iid not in selected
        ]
        self.tree.selection_set(inverted)

    # ==================================================================
    # Context menu
    # ==================================================================
    def _on_context_menu(self, event) -> None:
        iid = self.tree.identify_row(event.y)
        if iid and iid not in self.tree.selection():
            self.tree.selection_set(iid)
        options = self.theme.menu_options()
        menu = tk.Menu(self.root, tearoff=0, **options)
        menu.add_command(
            label=self.i18n.t("btn.open"), command=self._on_activate
        )
        if self.mode == "archive":
            menu.add_command(
                label=self.i18n.t("menu.file.extract"),
                command=self._action_extract,
            )
            menu.add_separator()
            menu.add_command(
                label=self.i18n.t("menu.file.add_files"),
                command=lambda: self._add_files("files"),
            )
            menu.add_command(
                label=self.i18n.t("menu.file.add_folder"),
                command=lambda: self._add_files("folder"),
            )
            menu.add_command(
                label=self.i18n.t("menu.file.delete"),
                command=self._action_delete,
            )
            menu.add_command(
                label=self.i18n.t("menu.file.test"),
                command=self._action_test,
            )
        menu.add_separator()
        menu.add_command(
            label=self.i18n.t("menu.file.properties"),
            command=self._action_properties,
        )
        menu.add_command(
            label=self.i18n.t("menu.view.refresh"), command=self._refresh
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ==================================================================
    # Refresh / close
    # ==================================================================
    def _refresh(self) -> None:
        if self._busy:
            return
        if self.mode == "archive" and self.archive_path:
            self._reload_archive()
        else:
            try:
                self._fs_items = self._list_fs(self.cwd)
            except Exception as exc:  # noqa: BLE001
                self._show_error(exc)
                return
            self._populate()
            self._update_status()

    def on_close(self) -> None:
        self._close_progress()
        try:
            self.settings.set("window_geometry", self.root.winfo_geometry())
            self.settings.set("preview_enabled", self._preview_visible)
            self.settings.set("sidebar_visible", self._sidebar_visible)
            self.settings.set("sort_column", self._sort_column)
            self.settings.set("sort_reverse", self._sort_reverse)
            if self.mode == "fs":
                self.settings.set("last_dir", self.cwd)
            self.settings.save()
        except Exception:
            pass
        self._cancel_event.set()
        for temp_dir in self._temp_dirs:
            remove_tree(temp_dir)
        try:
            self.root.destroy()
        except tk.TclError:
            pass
