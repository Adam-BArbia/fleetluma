"""FleetLuma Windows Agent Setup.

Native local configuration interface, distinct from the cloud dashboard.
The user enters the displayed code in the *dashboard*, never the reverse.
This UI talks only to the administrator-protected local Windows service pipe.
No telemetry, device secrets, or JWT credentials are stored by this process.
"""
from __future__ import annotations

import sys
import threading
import tkinter as tk
from tkinter import ttk
from urllib.parse import urlsplit

from .windows_control import windows_command

BACKGROUND = "#0b1222"
PANEL = "#151f34"
TEXT = "#f4f7ff"
MUTED = "#a1afca"
ACCENT = "#55e5d3"
ERROR = "#ffb06a"


def setup_instructions(state: dict) -> tuple[str, str, str]:
    """Pure presentation adapter. Never display a device token."""
    kind = state.get("status")
    if kind == "waiting":
        code = state.get("user_code") or ""
        if not (isinstance(code, str) and len(code) == 9):
            return ("Unexpected pairing status", "Try again.", "")
        verification = state.get("verification_uri") or ""
        parsed = urlsplit(verification) if isinstance(verification, str) else None
        if (parsed is None or parsed.scheme != "https" or parsed.username
                or parsed.password or parsed.fragment or parsed.query):
            verification = ""
        return (
            "Waiting for approval",
            "Enter the code below in the FleetLuma dashboard's Manage devices screen.",
            code,
        )
    if kind == "paired":
        return ("Computer connected", "FleetLuma is ready to send monitoring reports.", "")
    if kind == "expired":
        return ("Pairing expired", "Request a new pairing code.", "")
    if kind == "denied":
        return ("Pairing denied", "Request a new pairing code from this computer.", "")
    if kind == "not_paired":
        return ("Pair your computer", "Start pairing, then approve it in your dashboard.", "")
    return ("Agent unavailable", "Check that FleetLuma Agent is installed and running.", "")


class AgentSetupWindow:
    def __init__(self, master: tk.Tk, command=windows_command):
        self.master = master
        self.command = command
        self._busy = False
        self._closed = False
        self._after_id = None

        master.title("FleetLuma · Agent Setup")
        master.minsize(430, 450)
        master.geometry("550x480")
        master.configure(bg=BACKGROUND)
        master.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style(master)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Fleet.TFrame", background=BACKGROUND)
        style.configure("Fleet.TLabel", background=BACKGROUND, foreground=TEXT,
                        font=("Segoe UI", 11))
        style.configure("Fleet.TButton", font=("Segoe UI", 11), padding=(16, 12))

        outer = ttk.Frame(master, padding=28, style="Fleet.TFrame")
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="◉  FleetLuma", style="Fleet.TLabel",
                  font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(outer, text="DEVICE SETUP", style="Fleet.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(8, 27))

        self.heading = tk.Label(outer, text="Connecting to local agent…",
                                bg=BACKGROUND, fg=TEXT,
                                font=("Segoe UI", 21, "bold"), anchor="w")
        self.heading.pack(fill="x")
        self.explanation = tk.Label(outer, text="",
                                    bg=BACKGROUND, fg=MUTED,
                                    font=("Segoe UI", 11), justify="left",
                                    anchor="w", wraplength=450)
        self.explanation.pack(fill="x", pady=(10, 18))
        self.code = tk.Label(outer, text="",
                             bg=PANEL, fg=ACCENT,
                             font=("Consolas", 27, "bold"),
                             padx=18, pady=15)
        self.code.pack(fill="x", pady=(3, 14))

        self.feedback = tk.Label(outer, text="",
                                 bg=BACKGROUND, fg=ERROR,
                                 font=("Segoe UI", 10), wraplength=450,
                                 anchor="w", justify="left")
        self.feedback.pack(fill="x", pady=(0, 10))

        actions = ttk.Frame(outer, style="Fleet.TFrame")
        actions.pack(fill="x", pady=(10, 0))
        self.start_button = ttk.Button(actions, text="Start pairing",
                                       command=lambda: self._invoke("begin"),
                                       style="Fleet.TButton")
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(actions, text="Cancel pairing",
                                        command=lambda: self._invoke("cancel"),
                                        style="Fleet.TButton")
        self.cancel_button.pack(side="left", padx=(10, 0))
        self.refresh_button = ttk.Button(actions, text="Refresh",
                                         command=lambda: self._invoke("status"),
                                         style="Fleet.TButton")
        self.refresh_button.pack(side="right")
        self._invoke("status")

    def _invoke(self, action: str):
        if self._closed or self._busy:
            return
        self._busy = True
        self._set_buttons(False)

        def operation():
            try:
                result = self.command(action)
                if not isinstance(result, dict):
                    raise ValueError("Invalid status")
                error = None
            except Exception:
                result = {"status": "error"}
                error = ("Cannot reach the local FleetLuma service. "
                         "Start the agent and run Setup with administrator permission.")
            if not self._closed:
                try:
                    self.master.after(0, lambda: self._complete(result, error))
                except RuntimeError:
                    pass
        threading.Thread(target=operation, name="fleetluma-setup-ipc",
                         daemon=True).start()

    def _complete(self, result: dict, error: str | None):
        if self._closed:
            return
        self._busy = False
        self._set_buttons(True)
        title, description, code = setup_instructions(result)
        self.heading.configure(text=title)
        self.explanation.configure(text=description)
        self.code.configure(text=code or "—")
        self.feedback.configure(text=error or "")
        self._schedule_refresh()

    def _set_buttons(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for button in (self.start_button, self.cancel_button, self.refresh_button):
            button.configure(state=state)

    def _schedule_refresh(self):
        if self._after_id is not None:
            self.master.after_cancel(self._after_id)
            self._after_id = None
        if not self._closed:
            self._after_id = self.master.after(5000, lambda: self._invoke("status"))

    def close(self):
        self._closed = True
        if self._after_id is not None:
            self.master.after_cancel(self._after_id)
        self.master.destroy()


def main():
    if sys.platform != "win32":
        raise RuntimeError("Windows Agent Setup is available on Windows only")
    root = tk.Tk()
    AgentSetupWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
