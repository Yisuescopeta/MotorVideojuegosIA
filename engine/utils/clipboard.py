import tkinter as tk


def get_clipboard_text() -> str:
    try:
        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        return text
    except Exception:
        return ""


def set_clipboard_text(text: str) -> None:
    try:
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
    except Exception:
        pass
