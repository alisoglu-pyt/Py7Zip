"""Modern flat theme built on top of the ``clam`` ttk engine.

Everything is styled from two palettes (light/dark) so switching themes at
runtime is a single call and requires no external theme packages.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

LIGHT = {
    "name": "light",
    "bg": "#f0f0f0",
    "surface": "#ffffff",
    "surface_alt": "#f7f7f7",
    "toolbar": "#f0f0f0",
    "text": "#1b1b1b",
    "muted": "#5f5f5f",
    "border": "#d7d7d7",
    "accent": "#0067c0",
    "accent_hover": "#005a9e",
    "accent_text": "#ffffff",
    "selection": "#cce8ff",
    "selection_text": "#003a66",
    "tree_alt": "#fafafa",
    "danger": "#c42b1c",
    "warning": "#9d5d00",
    "success": "#107c10",
    "shadow": "#d0d0d0",
}

DARK = {
    "name": "dark",
    "bg": "#1f1f1f",
    "surface": "#2b2b2b",
    "surface_alt": "#333333",
    "toolbar": "#1f1f1f",
    "text": "#f2f2f2",
    "muted": "#a6a6a6",
    "border": "#3f3f3f",
    "accent": "#4cc2ff",
    "accent_hover": "#6fd0ff",
    "accent_text": "#08283a",
    "selection": "#3a3a3a",
    "selection_text": "#ffffff",
    "tree_alt": "#303030",
    "danger": "#ff6b6b",
    "warning": "#ffd166",
    "success": "#6ccb5f",
    "shadow": "#111111",
}

PALETTES = {"light": LIGHT, "dark": DARK}


def _pick_family(root: tk.Misc) -> str:
    try:
        available = set(tkfont.families(root))
    except tk.TclError:
        return "TkDefaultFont"
    candidates = (
        "Segoe UI Variable Text",
        "Segoe UI",
        "Inter",
        "Noto Sans",
        "Ubuntu",
        "DejaVu Sans",
        "Helvetica",
        "Arial",
    )
    for candidate in candidates:
        if candidate in available:
            return candidate
    return "TkDefaultFont"


def _pick_mono(root: tk.Misc) -> str:
    try:
        available = set(tkfont.families(root))
    except tk.TclError:
        return "TkFixedFont"
    for candidate in (
        "Cascadia Mono",
        "Cascadia Code",
        "Consolas",
        "JetBrains Mono",
        "DejaVu Sans Mono",
        "Monospace",
    ):
        if candidate in available:
            return candidate
    return "TkFixedFont"


class ThemeManager:
    """Applies a palette to ttk styles and exposes the active colours."""

    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.style = ttk.Style(root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        family = _pick_family(root)
        mono = _pick_mono(root)
        self.family = family
        self.mono_family = mono

        self.font_small = tkfont.Font(root=root, family=family, size=8)
        self.font_normal = tkfont.Font(root=root, family=family, size=9)
        self.font_medium = tkfont.Font(root=root, family=family, size=10)
        self.font_bold = tkfont.Font(root=root, family=family, size=9, weight="bold")
        self.font_heading = tkfont.Font(root=root, family=family, size=9, weight="bold")
        self.font_title = tkfont.Font(root=root, family=family, size=11, weight="bold")
        self.font_percent = tkfont.Font(
            root=root, family=family, size=18, weight="bold"
        )
        self.font_icon = tkfont.Font(root=root, family=family, size=10)
        self.font_mono = tkfont.Font(root=root, family=mono, size=8)

        # Make plain Tk widgets (menus, message boxes, text) match the theme.
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(name, root=root).configure(family=family, size=9)
            except tk.TclError:
                pass

        self.palette: dict[str, str] = dict(DARK)
        self._mode = "dark"

    # ------------------------------------------------------------------
    @property
    def mode(self) -> str:
        return self._mode

    def apply(self, mode: str) -> dict[str, str]:
        mode = mode if mode in PALETTES else "dark"
        self._mode = mode
        p = PALETTES[mode]
        self.palette = dict(p)
        style = self.style
        root = self.root

        try:
            root.configure(background=p["bg"])
        except tk.TclError:
            pass

        # Base defaults -------------------------------------------------
        style.configure(
            ".",
            background=p["bg"],
            foreground=p["text"],
            font=self.font_normal,
            bordercolor=p["border"],
            focuscolor=p["accent"],
            troughcolor=p["surface_alt"],
            selectbackground=p["selection"],
            selectforeground=p["selection_text"],
        )

        # Frames / labels ----------------------------------------------
        style.configure("TFrame", background=p["bg"])
        style.configure("Card.TFrame", background=p["surface"])
        style.configure("Toolbar.TFrame", background=p["toolbar"])
        style.configure("Sidebar.TFrame", background=p["surface"])
        style.configure("Header.TFrame", background=p["surface"])
        style.configure("Status.TFrame", background=p["surface"])
        style.configure("Accent.TFrame", background=p["accent"])

        style.configure("TLabel", background=p["bg"], foreground=p["text"])
        style.configure(
            "Toolbar.TLabel", background=p["toolbar"], foreground=p["muted"]
        )
        style.configure(
            "ToolbarTitle.TLabel",
            background=p["toolbar"],
            foreground=p["text"],
            font=self.font_medium,
        )
        style.configure("Card.TLabel", background=p["surface"], foreground=p["text"])
        style.configure("Muted.TLabel", background=p["bg"], foreground=p["muted"])
        style.configure(
            "MutedCard.TLabel", background=p["surface"], foreground=p["muted"]
        )
        style.configure(
            "Title.TLabel",
            background=p["surface"],
            foreground=p["text"],
            font=self.font_title,
        )
        style.configure(
            "Heading.TLabel",
            background=p["bg"],
            foreground=p["text"],
            font=self.font_medium,
        )
        style.configure(
            "Section.TLabel",
            background=p["surface"],
            foreground=p["muted"],
            font=self.font_bold,
        )
        style.configure(
            "Badge.TLabel",
            background=p["selection"],
            foreground=p["selection_text"],
            padding=(8, 2),
        )
        style.configure(
            "Percent.TLabel",
            background=p["surface"],
            foreground=p["accent"],
            font=self.font_percent,
        )
        style.configure(
            "Status.TLabel", background=p["surface"], foreground=p["muted"]
        )
        style.configure(
            "StatusStrong.TLabel",
            background=p["surface"],
            foreground=p["text"],
            font=self.font_bold,
        )

        # Buttons ------------------------------------------------------
        button_common = dict(
            padding=(8, 4),
            background=p["surface"],
            foreground=p["text"],
            bordercolor=p["border"],
            lightcolor=p["surface"],
            darkcolor=p["surface"],
            relief="flat",
            focusthickness=0,
        )
        style.configure("TButton", **button_common)
        style.map(
            "TButton",
            background=[("disabled", p["surface_alt"]), ("pressed", p["selection"]),
                        ("active", p["surface_alt"])],
            foreground=[("disabled", p["muted"])],
            bordercolor=[("focus", p["accent"]), ("active", p["border"])],
        )
        style.configure(
            "Accent.TButton",
            padding=(10, 4),
            background=p["accent"],
            foreground=p["accent_text"],
            bordercolor=p["accent"],
            lightcolor=p["accent"],
            darkcolor=p["accent"],
            relief="flat",
        )
        style.map(
            "Accent.TButton",
            background=[("disabled", p["border"]), ("pressed", p["accent_hover"]),
                        ("active", p["accent_hover"])],
            foreground=[("disabled", p["muted"])],
        )
        style.configure(
            "Danger.TButton",
            padding=(8, 4),
            background=p["surface"],
            foreground=p["danger"],
            bordercolor=p["border"],
            lightcolor=p["surface"],
            darkcolor=p["surface"],
            relief="flat",
        )
        style.map(
            "Danger.TButton",
            background=[("active", p["surface_alt"]), ("pressed", p["selection"])],
            foreground=[("disabled", p["muted"])],
        )
        style.configure(
            "Tool.TButton",
            padding=(6, 2),
            font=self.font_small,
            background=p["toolbar"],
            foreground=p["text"],
            bordercolor=p["toolbar"],
            lightcolor=p["toolbar"],
            darkcolor=p["toolbar"],
            relief="flat",
        )
        style.map(
            "Tool.TButton",
            background=[("disabled", p["toolbar"]), ("pressed", p["selection"]),
                        ("active", p["surface_alt"])],
            foreground=[("disabled", p["muted"])],
        )
        style.configure(
            "Icon.TButton",
            padding=(4, 2),
            background=p["toolbar"],
            foreground=p["muted"],
            bordercolor=p["toolbar"],
            lightcolor=p["toolbar"],
            darkcolor=p["toolbar"],
            relief="flat",
            font=self.font_icon,
        )
        style.map(
            "Icon.TButton",
            background=[("pressed", p["selection"]), ("active", p["surface_alt"])],
            foreground=[("active", p["text"])],
        )
        style.configure(
            "Link.TButton",
            padding=(2, 2),
            background=p["surface"],
            foreground=p["accent"],
            bordercolor=p["surface"],
            lightcolor=p["surface"],
            darkcolor=p["surface"],
            relief="flat",
            font=self.font_small,
        )
        style.map(
            "Link.TButton",
            background=[("active", p["surface"])],
            foreground=[("active", p["accent_hover"]), ("disabled", p["muted"])],
        )

        # Inputs -------------------------------------------------------
        style.configure(
            "TEntry",
            fieldbackground=p["surface"],
            foreground=p["text"],
            insertcolor=p["text"],
            bordercolor=p["border"],
            lightcolor=p["surface"],
            darkcolor=p["surface"],
            padding=(6, 4),
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", p["accent"])],
            lightcolor=[("focus", p["accent"])],
            darkcolor=[("focus", p["accent"])],
        )
        style.configure(
            "Path.TEntry",
            fieldbackground=p["surface"],
            foreground=p["text"],
            insertcolor=p["text"],
            bordercolor=p["border"],
            lightcolor=p["surface"],
            darkcolor=p["surface"],
            padding=(7, 4),
        )
        style.map("Path.TEntry", bordercolor=[("focus", p["accent"])])

        style.configure(
            "TCombobox",
            fieldbackground=p["surface"],
            background=p["surface"],
            foreground=p["text"],
            arrowcolor=p["muted"],
            bordercolor=p["border"],
            lightcolor=p["surface"],
            darkcolor=p["surface"],
            padding=(5, 3),
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", p["surface"])],
            foreground=[("readonly", p["text"])],
            bordercolor=[("focus", p["accent"])],
            arrowcolor=[("active", p["accent"])],
        )
        style.configure(
            "TSpinbox",
            fieldbackground=p["surface"],
            background=p["surface"],
            foreground=p["text"],
            arrowcolor=p["muted"],
            bordercolor=p["border"],
            lightcolor=p["surface"],
            darkcolor=p["surface"],
            padding=(6, 4),
        )

        style.configure(
            "TCheckbutton",
            background=p["bg"],
            foreground=p["text"],
            focuscolor=p["accent"],
            indicatorcolor=p["surface"],
            padding=(2, 2),
        )
        style.map(
            "TCheckbutton",
            background=[("active", p["bg"])],
            foreground=[("disabled", p["muted"])],
            indicatorcolor=[("selected", p["accent"])],
        )
        style.configure(
            "Card.TCheckbutton",
            background=p["surface"],
            foreground=p["text"],
            focuscolor=p["accent"],
            indicatorcolor=p["surface"],
        )
        style.map(
            "Card.TCheckbutton",
            background=[("active", p["surface"])],
            indicatorcolor=[("selected", p["accent"])],
        )
        style.configure(
            "TRadiobutton",
            background=p["bg"],
            foreground=p["text"],
            focuscolor=p["accent"],
            indicatorcolor=p["surface"],
            padding=(2, 2),
        )
        style.map(
            "TRadiobutton",
            background=[("active", p["bg"])],
            indicatorcolor=[("selected", p["accent"])],
        )
        style.configure(
            "Card.TRadiobutton",
            background=p["surface"],
            foreground=p["text"],
            focuscolor=p["accent"],
            indicatorcolor=p["surface"],
        )
        style.map(
            "Card.TRadiobutton",
            background=[("active", p["surface"])],
            indicatorcolor=[("selected", p["accent"])],
        )

        # Treeview -----------------------------------------------------
        style.configure(
            "Treeview",
            background=p["surface"],
            fieldbackground=p["surface"],
            foreground=p["text"],
            bordercolor=p["border"],
            lightcolor=p["surface"],
            darkcolor=p["surface"],
            rowheight=24,
            font=self.font_normal,
        )
        style.map(
            "Treeview",
            background=[("selected", p["selection"])],
            foreground=[("selected", p["selection_text"])],
        )
        style.configure(
            "Treeview.Heading",
            background=p["surface_alt"],
            foreground=p["muted"],
            relief="flat",
            padding=(4, 5),
            bordercolor=p["border"],
            lightcolor=p["surface_alt"],
            darkcolor=p["surface_alt"],
            font=self.font_heading,
        )
        style.map(
            "Treeview.Heading",
            background=[("active", p["selection"]), ("pressed", p["selection"])],
            foreground=[("active", p["text"])],
        )
        style.configure(
            "Sidebar.Treeview",
            background=p["surface"],
            fieldbackground=p["surface"],
            foreground=p["text"],
            bordercolor=p["surface"],
            rowheight=22,
        )
        style.map(
            "Sidebar.Treeview",
            background=[("selected", p["selection"])],
            foreground=[("selected", p["selection_text"])],
        )

        # Progress / scrollbars / misc ---------------------------------
        style.configure(
            "TProgressbar",
            troughcolor=p["surface_alt"],
            background=p["accent"],
            bordercolor=p["surface_alt"],
            lightcolor=p["accent"],
            darkcolor=p["accent"],
            thickness=6,
        )
        style.configure(
            "TScrollbar",
            background=p["surface_alt"],
            troughcolor=p["bg"],
            bordercolor=p["bg"],
            arrowcolor=p["muted"],
            lightcolor=p["surface_alt"],
            darkcolor=p["surface_alt"],
        )
        style.map(
            "TScrollbar",
            background=[("active", p["border"])],
        )
        style.configure("Sash", sashthickness=7, background=p["border"])
        style.configure("TPanedwindow", background=p["border"])
        style.configure(
            "TSeparator", background=p["border"], bordercolor=p["border"]
        )
        style.configure(
            "TNotebook", background=p["bg"], bordercolor=p["border"], tabmargins=(2, 4, 2, 0)
        )
        style.configure(
            "TNotebook.Tab",
            background=p["surface_alt"],
            foreground=p["muted"],
            padding=(12, 5),
            bordercolor=p["border"],
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", p["surface"])],
            foreground=[("selected", p["text"])],
        )
        style.configure(
            "TLabelframe",
            background=p["surface"],
            bordercolor=p["border"],
            lightcolor=p["border"],
            darkcolor=p["border"],
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "TLabelframe.Label",
            background=p["surface"],
            foreground=p["muted"],
            font=self.font_bold,
        )
        style.configure(
            "TSeparator", background=p["border"]
        )
        style.configure(
            "TScale", background=p["bg"], troughcolor=p["surface_alt"],
            bordercolor=p["border"],
        )
        return self.palette

    # ------------------------------------------------------------------
    def menu_options(self) -> dict[str, str]:
        p = self.palette
        return {
            "bg": p["surface"],
            "fg": p["text"],
            "activebackground": p["accent"],
            "activeforeground": p["accent_text"],
            "selectcolor": p["accent"],
            "bd": "0",
            "relief": "flat",
        }

    def text_options(self) -> dict[str, str]:
        p = self.palette
        return {
            "bg": p["surface"],
            "fg": p["text"],
            "insertbackground": p["text"],
            "selectbackground": p["selection"],
            "selectforeground": p["selection_text"],
            "highlightthickness": "0",
            "borderwidth": "0",
        }

    def label_options(self) -> dict[str, str]:
        p = self.palette
        return {"bg": p["surface"], "fg": p["text"], "bd": "0"}
