"""Modal progress window with a percentage indicator."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class ProgressDialog(tk.Toplevel):
    """A compact, non-blocking progress window used by long operations.

    ``show`` is called by the main window after a short delay so very fast
    operations do not flash a window on the screen.
    """

    def __init__(
        self,
        parent: tk.Misc,
        i18n,
        theme,
        title: str,
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.withdraw()
        self.i18n = i18n
        self.theme = theme
        self.parent = parent
        self.on_cancel = on_cancel
        self._shown = False
        self._finished = False
        self._close_id: str | None = None

        self.title(i18n.t("progress.title"))
        self.configure(background=theme.palette["bg"])
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancel_clicked)
        self.bind("<Escape>", lambda _event: self._cancel_clicked())

        body = ttk.Frame(self, style="Card.TFrame", padding=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)

        self.operation_label = ttk.Label(
            body, text=title, style="Card.TLabel", font=theme.font_medium
        )
        self.operation_label.grid(row=0, column=0, sticky="w")
        self.percent_label = ttk.Label(body, text="…", style="Percent.TLabel")
        self.percent_label.grid(row=0, column=1, sticky="e", padx=(16, 0))

        self.progress = ttk.Progressbar(
            body, mode="indeterminate", maximum=100, length=420
        )
        self.progress.grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(12, 8)
        )
        self.progress.start(12)

        self.current_label = ttk.Label(
            body,
            text=i18n.t("progress.wait"),
            style="MutedCard.TLabel",
            wraplength=420,
            justify="left",
            anchor="w",
        )
        self.current_label.grid(row=2, column=0, columnspan=2, sticky="ew")

        footer = ttk.Frame(self, style="Toolbar.TFrame", padding=(12, 8))
        footer.pack(fill="x")
        self.cancel_button = ttk.Button(
            footer,
            text=i18n.t("msg.cancel"),
            style="TButton",
            command=self._cancel_clicked,
        )
        self.cancel_button.pack(side="right")

        self.update_idletasks()
        self._center()

    # ------------------------------------------------------------------
    def _center(self) -> None:
        try:
            self.update_idletasks()
            parent = self.parent
            width = self.winfo_reqwidth()
            height = self.winfo_reqheight()
            x = parent.winfo_rootx() + max(
                0, (parent.winfo_width() - width) // 2
            )
            y = parent.winfo_rooty() + max(
                0, (parent.winfo_height() - height) // 2
            )
            self.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

    def show(self) -> None:
        if self._finished:
            return
        try:
            self.deiconify()
            self.lift()
            self.grab_set()
        except tk.TclError:
            pass
        self._shown = True

    def is_shown(self) -> bool:
        return self._shown and not self._finished

    # ------------------------------------------------------------------
    def update_progress(
        self, current: int, total: int, message: str = ""
    ) -> None:
        if self._finished:
            return
        try:
            if total > 0:
                if str(self.progress.cget("mode")) != "determinate":
                    self.progress.stop()
                    self.progress.configure(mode="determinate")
                percent = max(0, min(100, int(round(current * 100 / total))))
                self.progress.configure(value=percent)
                self.percent_label.configure(text=f"{percent}%")
            else:
                if str(self.progress.cget("mode")) != "indeterminate":
                    self.progress.configure(mode="indeterminate")
                    self.progress.start(12)
                self.percent_label.configure(text="…")

            if message:
                self.current_label.configure(
                    text=self._translate_message(message)
                )
            elif total <= 0:
                self.current_label.configure(text=self.i18n.t("progress.wait"))
        except tk.TclError:
            pass

    def _translate_message(self, message: str) -> str:
        key = {
            "extract": "progress.phase.extract",
            "delete": "progress.phase.delete",
            "add": "progress.phase.add",
            "rebuild": "progress.phase.rebuild",
            "split": "progress.phase.split",
            "done": "progress.completed",
        }.get(message)
        return self.i18n.t(key) if key else message

    def mark_cancelling(self) -> None:
        if self._finished:
            return
        try:
            self.current_label.configure(text=self.i18n.t("progress.cancelling"))
            self.cancel_button.configure(state="disabled")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    def finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        try:
            self.progress.stop()
            self.progress.configure(mode="determinate", maximum=100, value=100)
            self.percent_label.configure(text="100%")
            self.current_label.configure(text=self.i18n.t("progress.completed"))
            self.cancel_button.configure(
                state="disabled", text=self.i18n.t("btn.close")
            )
        except tk.TclError:
            pass
        try:
            self._close_id = self.after(800, self.close)
        except tk.TclError:
            self.close()

    def close(self) -> None:
        if self._close_id is not None:
            try:
                self.after_cancel(self._close_id)
            except tk.TclError:
                pass
            self._close_id = None
        try:
            self.grab_release()
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass

    def _cancel_clicked(self) -> None:
        self.mark_cancelling()
        try:
            self.on_cancel()
        except Exception:
            pass
