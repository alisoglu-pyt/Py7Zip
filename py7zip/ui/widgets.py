"""Reusable Tkinter widgets for the Py7-Zip interface."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk
from typing import Callable


class PlaceholderEntry(ttk.Entry):
    """An entry that shows a muted placeholder while empty."""

    def __init__(
        self,
        master,
        placeholder: str = "",
        text_color: str = "#e6e9ef",
        muted_color: str = "#98a2b3",
        style: str = "TEntry",
        **kwargs,
    ) -> None:
        self._var = tk.StringVar()
        super().__init__(master, textvariable=self._var, style=style, **kwargs)
        self.placeholder = placeholder
        self._text_color = text_color
        self._muted_color = muted_color
        self._showing_placeholder = False
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        if not self._var.get() and self.placeholder:
            self._showing_placeholder = True
            self._var.set(self.placeholder)
            try:
                self.configure(foreground=self._muted_color)
            except tk.TclError:
                pass

    def _on_focus_in(self, _event=None) -> None:
        if self._showing_placeholder:
            self._showing_placeholder = False
            self._var.set("")
            try:
                self.configure(foreground=self._text_color)
            except tk.TclError:
                pass

    def _on_focus_out(self, _event=None) -> None:
        self._show_placeholder()

    def get_text(self) -> str:
        return "" if self._showing_placeholder else self._var.get()

    def set_text(self, value: str) -> None:
        self._showing_placeholder = False
        self._var.set(value)
        try:
            self.configure(foreground=self._text_color)
        except tk.TclError:
            pass
        if not value:
            self._show_placeholder()

    def clear(self) -> None:
        self.set_text("")

    def set_placeholder(self, text: str) -> None:
        self.placeholder = text
        if not self.get_text():
            self._show_placeholder()

    def set_colors(self, text_color: str, muted_color: str) -> None:
        self._text_color = text_color
        self._muted_color = muted_color
        try:
            self.configure(
                foreground=muted_color if self._showing_placeholder else text_color
            )
        except tk.TclError:
            pass


class StatusBar(ttk.Frame):
    """Bottom status bar with progress and a cancel button."""

    def __init__(
        self, master, i18n, on_cancel: Callable[[], None]
    ) -> None:
        super().__init__(master, style="Status.TFrame", padding=(8, 3))
        self.i18n = i18n
        self._on_cancel = on_cancel

        self.left = ttk.Label(self, text="", style="Status.TLabel")
        self.center = ttk.Label(self, text="", style="Status.TLabel")
        self.progress = ttk.Progressbar(
            self, mode="determinate", length=150, style="TProgressbar"
        )
        self.cancel_button = ttk.Button(
            self, text="", style="Link.TButton", command=self._cancel_clicked
        )

        self.left.grid(row=0, column=0, sticky="w")
        self.center.grid(row=0, column=1, sticky="e", padx=(12, 16))
        self.progress.grid(row=0, column=2, sticky="e", padx=(0, 8))
        self.cancel_button.grid(row=0, column=3, sticky="e")
        self.columnconfigure(0, weight=1)
        self.progress.grid_remove()
        self.cancel_button.grid_remove()

    def _cancel_clicked(self) -> None:
        self.cancel_button.configure(state="disabled")
        self._on_cancel()

    def set_left(self, text: str) -> None:
        self.left.configure(text=text)

    def set_center(self, text: str) -> None:
        self.center.configure(text=text)

    def begin(self, text: str) -> None:
        self.left.configure(text=text)
        self.progress.configure(value=0, maximum=100, mode="indeterminate")
        self.progress.grid()
        self.progress.start(12)
        self.cancel_button.configure(text=self.i18n.t("msg.cancel"), state="normal")
        self.cancel_button.grid()

    def set_progress(self, current: int, total: int, message: str = "") -> None:
        if total > 0:
            if str(self.progress.cget("mode")) != "determinate":
                self.progress.stop()
                self.progress.configure(mode="determinate")
            self.progress.configure(maximum=max(total, 1), value=min(current, total))
        if message:
            self.left.configure(text=message)

    def end(self, text: str | None = None) -> None:
        try:
            self.progress.stop()
        except tk.TclError:
            pass
        self.progress.grid_remove()
        self.cancel_button.grid_remove()
        if text is not None:
            self.left.configure(text=text)

    def retranslate(self) -> None:
        self.cancel_button.configure(text=self.i18n.t("msg.cancel"))


class SidebarTree(ttk.Frame):
    """Lazy filesystem tree shown on the left side of the window."""

    def __init__(
        self,
        master,
        on_select: Callable[[str], None],
        show_hidden: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(master, style="Sidebar.TFrame")
        self.on_select = on_select
        self.show_hidden = show_hidden or (lambda: False)
        self._paths: dict[str, str] = {}

        self.tree = ttk.Treeview(
            self, show="tree", selectmode="browse", style="Sidebar.Treeview"
        )
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.column("#0", width=150, minwidth=100, stretch=True)
        scroll.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewOpen>>", self._on_open)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh_roots()

    # ------------------------------------------------------------------
    def _insert(self, parent: str, path: str, label: str) -> str:
        node = self.tree.insert(parent, "end", text=label, open=False)
        self._paths[node] = path
        # Placeholder so the expand arrow appears.
        self.tree.insert(node, "end", text="…")
        return node

    def refresh_roots(self) -> None:
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children(""))
        self._paths.clear()
        roots = filesystem_roots()
        for label, path in roots:
            self._insert("", path, f"  {label}")
        if selected:
            self.tree.selection_set(selected[0]) if self.tree.exists(selected[0]) else None

    def _on_open(self, _event=None) -> None:
        node = self.tree.focus()
        if not node:
            return
        children = self.tree.get_children(node)
        if len(children) == 1 and not self._paths.get(children[0]):
            self.tree.delete(*children)
        elif children:
            return
        path = self._paths.get(node)
        if not path:
            return
        for child in _list_subdirectories(path, self.show_hidden()):
            self._insert(node, child, os.path.basename(child) or child)

    def _on_select(self, _event=None) -> None:
        node = self.tree.focus()
        path = self._paths.get(node)
        if path and os.path.isdir(path):
            self.on_select(path)

    def select_path(self, path: str) -> None:
        """Best-effort expansion/selection of *path* in the sidebar."""
        path = os.path.abspath(path)
        for node in self.tree.get_children(""):
            root_path = self._paths.get(node, "")
            if root_path and (path == root_path or path.startswith(root_path.rstrip("\\/") + os.sep)
                              or root_path == "/"):
                self._expand_to(node, path)
                return

    def _expand_to(self, node: str, target: str) -> None:
        self.tree.item(node, open=True)
        self.tree.event_generate("<<TreeviewOpen>>")
        self.update_idletasks()
        for child in self.tree.get_children(node):
            child_path = self._paths.get(child, "")
            if not child_path:
                continue
            if target == child_path:
                self.tree.selection_set(child)
                self.tree.see(child)
                return
            if target.startswith(child_path.rstrip("\\/") + os.sep):
                self._expand_to(child, target)
                return


def filesystem_roots() -> list[tuple[str, str]]:
    roots: list[tuple[str, str]] = []
    if sys.platform == "win32":
        drives = []
        try:
            drives = list(os.listdrives())  # Python 3.12+
        except (AttributeError, OSError):
            drives = [
                f"{letter}:\\"
                for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                if os.path.exists(f"{letter}:\\")
            ]
        for drive in drives:
            roots.append((drive, drive))
    else:
        roots.append(("/", "/"))
        home = os.path.expanduser("~")
        if home and home != "/":
            roots.append((os.path.basename(home) or home, home))
        if os.path.isdir("/mnt"):
            roots.append(("/mnt", "/mnt"))
    return roots


def _list_subdirectories(path: str, show_hidden: bool) -> list[str]:
    result: list[str] = []
    try:
        with os.scandir(path) as iterator:
            for entry in iterator:
                try:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                if not show_hidden and _is_hidden(entry.name):
                    continue
                result.append(entry.path)
    except (PermissionError, OSError):
        return []
    result.sort(key=lambda item: os.path.basename(item).casefold())
    return result


def _is_hidden(name: str) -> bool:
    if name.startswith("."):
        return True
    if sys.platform == "win32":
        try:
            import ctypes

            attrs = ctypes.windll.kernel32.GetFileAttributesW(name)
            return attrs != -1 and bool(attrs & 0x2)
        except Exception:
            return False
    return False


class Tooltip:
    """Lightweight tooltip used by the toolbar buttons."""

    def __init__(
        self, widget: tk.Widget, text: str, theme, delay: int = 550
    ) -> None:
        self.widget = widget
        self.text = text
        self.theme = theme
        self.delay = delay
        self._after_id: str | None = None
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def set_text(self, text: str) -> None:
        self.text = text

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self) -> None:
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self) -> None:
        if self._tip or not self.text:
            return
        pal = self.theme.palette
        x = self.widget.winfo_rootx() + 8
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tip,
            text=self.text,
            background=pal["surface_alt"],
            foreground=pal["text"],
            relief="solid",
            borderwidth=1,
            font=self.theme.font_small,
            padx=8,
            pady=4,
        )
        label.pack()
        self._tip = tip

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._tip:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None
