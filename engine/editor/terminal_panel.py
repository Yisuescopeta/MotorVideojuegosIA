"""
engine/editor/terminal_panel.py - Terminal embebida para el editor
"""

from __future__ import annotations

import ctypes
import math
import os
import queue
import threading
from ctypes import byref, c_size_t, c_void_p, create_string_buffer, sizeof
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import pyray as rl
try:
    from PIL import ImageFont
except ImportError:  # pragma: no cover - optional dependency at runtime
    ImageFont = None

from engine.project.project_service import ProjectService

ColorTuple = tuple[int, int, int, int]


def _rgba(r: int, g: int, b: int, a: int = 255) -> ColorTuple:
    return (max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))), max(0, min(255, int(a))))


def _to_ray_color(color: ColorTuple) -> rl.Color:
    return rl.Color(color[0], color[1], color[2], color[3])


def _blend(fg: ColorTuple, bg: ColorTuple, ratio: float) -> ColorTuple:
    inv = 1.0 - ratio
    return _rgba(
        fg[0] * ratio + bg[0] * inv,
        fg[1] * ratio + bg[1] * inv,
        fg[2] * ratio + bg[2] * inv,
        fg[3],
    )


def _brighten(color: ColorTuple, amount: float = 0.18) -> ColorTuple:
    return _rgba(
        color[0] + (255 - color[0]) * amount,
        color[1] + (255 - color[1]) * amount,
        color[2] + (255 - color[2]) * amount,
        color[3],
    )


def _xterm_palette(index: int) -> ColorTuple:
    base = [
        _rgba(12, 12, 12),
        _rgba(197, 15, 31),
        _rgba(19, 161, 14),
        _rgba(193, 156, 0),
        _rgba(0, 55, 218),
        _rgba(136, 23, 152),
        _rgba(58, 150, 221),
        _rgba(204, 204, 204),
        _rgba(118, 118, 118),
        _rgba(231, 72, 86),
        _rgba(22, 198, 12),
        _rgba(249, 241, 165),
        _rgba(59, 120, 255),
        _rgba(180, 0, 158),
        _rgba(97, 214, 214),
        _rgba(242, 242, 242),
    ]
    if index < 16:
        return base[index]
    if index < 232:
        value = index - 16
        r = value // 36
        g = (value % 36) // 6
        b = value % 6
        scale = [0, 95, 135, 175, 215, 255]
        return _rgba(scale[r], scale[g], scale[b])
    gray = 8 + (index - 232) * 10
    return _rgba(gray, gray, gray)


class _TerminalBackend:
    def write_text(self, text: str) -> None:
        raise NotImplementedError

    def resize(self, cols: int, rows: int) -> None:
        raise NotImplementedError

    def poll(self) -> Optional[int]:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class _COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", _STARTUPINFOW), ("lpAttributeList", c_void_p)]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", c_void_p),
        ("bInheritHandle", wintypes.BOOL),
    ]


class _WinConPtyBackend(_TerminalBackend):
    PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
    EXTENDED_STARTUPINFO_PRESENT = 0x00080000
    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    HANDLE_FLAG_INHERIT = 0x00000001
    STARTF_USESTDHANDLES = 0x00000100
    STILL_ACTIVE = 259

    def __init__(self, cwd: str, cols: int, rows: int, on_output: Callable[[str], None], command_line: str | None = None) -> None:
        self.cwd = cwd
        self.cols = max(40, cols)
        self.rows = max(12, rows)
        self.on_output = on_output
        self.command_line = command_line or "powershell.exe -NoLogo -NoProfile"
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._hpc = c_void_p()
        self._input_write = wintypes.HANDLE()
        self._output_read = wintypes.HANDLE()
        self._process_info = _PROCESS_INFORMATION()
        self._attribute_buffer = None
        self._reader_thread: Optional[threading.Thread] = None
        self._close_thread: Optional[threading.Thread] = None
        self._closed = False
        self._configure_functions()
        self._start()

    def _configure_functions(self) -> None:
        self._kernel32.CreatePipe.argtypes = [
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(_SECURITY_ATTRIBUTES),
            wintypes.DWORD,
        ]
        self._kernel32.CreatePipe.restype = wintypes.BOOL
        self._kernel32.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
        self._kernel32.SetHandleInformation.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32.InitializeProcThreadAttributeList.argtypes = [c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(c_size_t)]
        self._kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
        self._kernel32.UpdateProcThreadAttribute.argtypes = [c_void_p, wintypes.DWORD, c_size_t, c_void_p, c_size_t, c_void_p, c_void_p]
        self._kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL
        self._kernel32.DeleteProcThreadAttributeList.argtypes = [c_void_p]
        self._kernel32.DeleteProcThreadAttributeList.restype = None
        self._kernel32.CreatePseudoConsole.argtypes = [_COORD, wintypes.HANDLE, wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(c_void_p)]
        self._kernel32.CreatePseudoConsole.restype = ctypes.c_long
        self._kernel32.ResizePseudoConsole.argtypes = [c_void_p, _COORD]
        self._kernel32.ResizePseudoConsole.restype = ctypes.c_long
        self._kernel32.ClosePseudoConsole.argtypes = [c_void_p]
        self._kernel32.ClosePseudoConsole.restype = None
        self._kernel32.CreateProcessW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            c_void_p,
            c_void_p,
            wintypes.BOOL,
            wintypes.DWORD,
            c_void_p,
            wintypes.LPCWSTR,
            ctypes.POINTER(_STARTUPINFOEXW),
            ctypes.POINTER(_PROCESS_INFORMATION),
        ]
        self._kernel32.CreateProcessW.restype = wintypes.BOOL
        self._kernel32.ReadFile.argtypes = [wintypes.HANDLE, c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), c_void_p]
        self._kernel32.ReadFile.restype = wintypes.BOOL
        self._kernel32.WriteFile.argtypes = [wintypes.HANDLE, c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), c_void_p]
        self._kernel32.WriteFile.restype = wintypes.BOOL
        self._kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self._kernel32.GetExitCodeProcess.restype = wintypes.BOOL

    def _start(self) -> None:
        sa = _SECURITY_ATTRIBUTES()
        sa.nLength = sizeof(_SECURITY_ATTRIBUTES)
        sa.bInheritHandle = True

        pty_input_read = wintypes.HANDLE()
        pty_input_write = wintypes.HANDLE()
        pty_output_read = wintypes.HANDLE()
        pty_output_write = wintypes.HANDLE()

        if not self._kernel32.CreatePipe(byref(pty_input_read), byref(pty_input_write), byref(sa), 0):
            raise ctypes.WinError(ctypes.get_last_error())
        if not self._kernel32.CreatePipe(byref(pty_output_read), byref(pty_output_write), byref(sa), 0):
            self._kernel32.CloseHandle(pty_input_read)
            self._kernel32.CloseHandle(pty_input_write)
            raise ctypes.WinError(ctypes.get_last_error())
        if not self._kernel32.SetHandleInformation(pty_input_write, self.HANDLE_FLAG_INHERIT, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        if not self._kernel32.SetHandleInformation(pty_output_read, self.HANDLE_FLAG_INHERIT, 0):
            raise ctypes.WinError(ctypes.get_last_error())

        hr = self._kernel32.CreatePseudoConsole(_COORD(self.cols, self.rows), pty_input_read, pty_output_write, 0, byref(self._hpc))
        if hr != 0:
            self._kernel32.CloseHandle(pty_input_read)
            self._kernel32.CloseHandle(pty_output_write)
            self._kernel32.CloseHandle(pty_input_write)
            self._kernel32.CloseHandle(pty_output_read)
            raise OSError(f"CreatePseudoConsole failed with HRESULT {hr}")

        self._input_write = pty_input_write
        self._output_read = pty_output_read

        attribute_size = c_size_t(0)
        self._kernel32.InitializeProcThreadAttributeList(None, 1, 0, byref(attribute_size))
        self._attribute_buffer = create_string_buffer(attribute_size.value)
        startup_info_ex = _STARTUPINFOEXW()
        startup_info_ex.StartupInfo.cb = sizeof(_STARTUPINFOEXW)
        startup_info_ex.StartupInfo.dwFlags |= self.STARTF_USESTDHANDLES
        startup_info_ex.StartupInfo.hStdInput = wintypes.HANDLE()
        startup_info_ex.StartupInfo.hStdOutput = wintypes.HANDLE()
        startup_info_ex.StartupInfo.hStdError = wintypes.HANDLE()
        startup_info_ex.lpAttributeList = ctypes.cast(self._attribute_buffer, c_void_p)
        if not self._kernel32.InitializeProcThreadAttributeList(startup_info_ex.lpAttributeList, 1, 0, byref(attribute_size)):
            raise ctypes.WinError(ctypes.get_last_error())

        if not self._kernel32.UpdateProcThreadAttribute(
            startup_info_ex.lpAttributeList,
            0,
            self.PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
            self._hpc,
            sizeof(self._hpc),
            None,
            None,
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        command = ctypes.create_unicode_buffer(self.command_line)
        if not self._kernel32.CreateProcessW(
            None,
            command,
            None,
            None,
            False,
            self.EXTENDED_STARTUPINFO_PRESENT | self.CREATE_UNICODE_ENVIRONMENT,
            None,
            self.cwd,
            byref(startup_info_ex),
            byref(self._process_info),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        self._kernel32.CloseHandle(pty_input_read)
        self._kernel32.CloseHandle(pty_output_write)
        self._kernel32.CloseHandle(self._process_info.hThread)
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        try:
            while not self._closed:
                buffer = create_string_buffer(4096)
                read = wintypes.DWORD(0)
                success = self._kernel32.ReadFile(self._output_read, buffer, len(buffer), byref(read), None)
                if not success or read.value == 0:
                    break
                self.on_output(buffer.raw[: read.value].decode("utf-8", errors="replace"))
        finally:
            code = self.poll()
            self.on_output(f"\r\n[process exited with code {code if code is not None else 'unknown'}]\r\n")

    def write_text(self, text: str) -> None:
        if self._closed:
            return
        data = text.encode("utf-8", errors="replace")
        written = wintypes.DWORD(0)
        if not self._kernel32.WriteFile(self._input_write, data, len(data), byref(written), None):
            raise ctypes.WinError(ctypes.get_last_error())

    def resize(self, cols: int, rows: int) -> None:
        cols = max(40, cols)
        rows = max(12, rows)
        if cols == self.cols and rows == self.rows:
            return
        self.cols = cols
        self.rows = rows
        if self._hpc:
            self._kernel32.ResizePseudoConsole(self._hpc, _COORD(cols, rows))

    def poll(self) -> Optional[int]:
        if not self._process_info.hProcess:
            return None
        code = wintypes.DWORD(0)
        if not self._kernel32.GetExitCodeProcess(self._process_info.hProcess, byref(code)):
            return None
        if code.value == self.STILL_ACTIVE:
            return None
        return int(code.value)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._input_write:
            self._kernel32.CloseHandle(self._input_write)
            self._input_write = wintypes.HANDLE()
        self._close_thread = threading.Thread(target=self._close_handles_worker, daemon=True)
        self._close_thread.start()

    def _close_handles_worker(self) -> None:
        if self._input_write:
            self._kernel32.CloseHandle(self._input_write)
            self._input_write = wintypes.HANDLE()
        if self._output_read:
            self._kernel32.CloseHandle(self._output_read)
            self._output_read = wintypes.HANDLE()
        if self._hpc:
            self._kernel32.ClosePseudoConsole(self._hpc)
            self._hpc = c_void_p()
        if self._process_info.hProcess:
            self._kernel32.CloseHandle(self._process_info.hProcess)
            self._process_info.hProcess = wintypes.HANDLE()
        if self._attribute_buffer is not None:
            try:
                self._kernel32.DeleteProcThreadAttributeList(ctypes.cast(self._attribute_buffer, c_void_p))
            except Exception:
                pass
            self._attribute_buffer = None


@dataclass
class _CursorState:
    row: int = 0
    col: int = 0


@dataclass(frozen=True)
class _TerminalStyle:
    fg: Optional[ColorTuple]
    bg: Optional[ColorTuple]
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    inverse: bool = False


@dataclass(frozen=True)
class _TerminalCell:
    char: str
    style: _TerminalStyle


@dataclass
class _TerminalSnapshot:
    cursor: _CursorState
    saved_cursor: _CursorState
    show_cursor: bool
    wrap_pending: bool
    default_style: _TerminalStyle
    current_style: _TerminalStyle
    scrollback: list[list[_TerminalCell]]
    main_buffer: list[list[_TerminalCell]]
    alt_buffer: list[list[_TerminalCell]]
    use_alt_buffer: bool


class _TerminalScreen:
    DEFAULT_FG = _rgba(242, 242, 242)
    DEFAULT_BG = _rgba(24, 24, 24)

    def __init__(
        self,
        cols: int,
        rows: int,
        sequence_handler: Optional[Callable[[str, str, str, list[int], str], None]] = None,
    ) -> None:
        self.cols = max(40, cols)
        self.rows = max(12, rows)
        self.sequence_handler = sequence_handler
        self.cursor = _CursorState()
        self.saved_cursor = _CursorState()
        self.show_cursor = True
        self._wrap_pending = False
        self.default_style = _TerminalStyle(self.DEFAULT_FG, self.DEFAULT_BG)
        self.current_style = self.default_style
        self.scrollback: list[list[_TerminalCell]] = []
        self.main_buffer = self._new_buffer()
        self.alt_buffer = self._new_buffer()
        self.use_alt_buffer = False
        self._state = "normal"
        self._csi_buffer = ""
        self._osc_buffer = ""
        self._osc_pending_escape = False
        self._sync_update_active = False
        self._sync_visible_state: Optional[_TerminalSnapshot] = None

    def _blank_cell(self, style: Optional[_TerminalStyle] = None) -> _TerminalCell:
        return _TerminalCell(" ", style or self.default_style)

    def _new_row(self, style: Optional[_TerminalStyle] = None) -> list[_TerminalCell]:
        return [self._blank_cell(style) for _ in range(self.cols)]

    def _new_buffer(self) -> list[list[_TerminalCell]]:
        return [self._new_row() for _ in range(self.rows)]

    @property
    def buffer(self) -> list[list[_TerminalCell]]:
        return self.alt_buffer if self.use_alt_buffer else self.main_buffer

    def _clone_rows(self, rows: list[list[_TerminalCell]]) -> list[list[_TerminalCell]]:
        return [[cell for cell in row] for row in rows]

    def _capture_snapshot(self) -> _TerminalSnapshot:
        return _TerminalSnapshot(
            cursor=_CursorState(self.cursor.row, self.cursor.col),
            saved_cursor=_CursorState(self.saved_cursor.row, self.saved_cursor.col),
            show_cursor=self.show_cursor,
            wrap_pending=self._wrap_pending,
            default_style=self.default_style,
            current_style=self.current_style,
            scrollback=self._clone_rows(self.scrollback),
            main_buffer=self._clone_rows(self.main_buffer),
            alt_buffer=self._clone_rows(self.alt_buffer),
            use_alt_buffer=self.use_alt_buffer,
        )

    def _resize_snapshot(self, snapshot: _TerminalSnapshot, cols: int, rows: int) -> _TerminalSnapshot:
        resized_main = self._resize_buffer(snapshot.main_buffer, cols, rows)
        resized_alt = self._resize_buffer(snapshot.alt_buffer, cols, rows)
        row_offset = max(0, len(snapshot.scrollback) - 2000)
        trimmed_scrollback = snapshot.scrollback[row_offset:]
        return _TerminalSnapshot(
            cursor=_CursorState(min(snapshot.cursor.row, rows - 1), min(snapshot.cursor.col, cols - 1)),
            saved_cursor=_CursorState(min(snapshot.saved_cursor.row, rows - 1), min(snapshot.saved_cursor.col, cols - 1)),
            show_cursor=snapshot.show_cursor,
            wrap_pending=snapshot.wrap_pending,
            default_style=snapshot.default_style,
            current_style=snapshot.current_style,
            scrollback=self._clone_rows(trimmed_scrollback),
            main_buffer=resized_main,
            alt_buffer=resized_alt,
            use_alt_buffer=snapshot.use_alt_buffer,
        )

    def _visible_snapshot(self) -> _TerminalSnapshot:
        if self._sync_update_active and self._sync_visible_state is not None:
            return self._sync_visible_state
        return self._capture_snapshot()

    def resize(self, cols: int, rows: int) -> None:
        cols = max(40, cols)
        rows = max(12, rows)
        if cols == self.cols and rows == self.rows:
            return
        self.main_buffer = self._resize_buffer(self.main_buffer, cols, rows)
        self.alt_buffer = self._resize_buffer(self.alt_buffer, cols, rows)
        self.cols = cols
        self.rows = rows
        self.cursor.col = min(self.cursor.col, self.cols - 1)
        self.cursor.row = min(self.cursor.row, self.rows - 1)
        self.saved_cursor.col = min(self.saved_cursor.col, self.cols - 1)
        self.saved_cursor.row = min(self.saved_cursor.row, self.rows - 1)
        if self._sync_update_active and self._sync_visible_state is not None:
            self._sync_visible_state = self._resize_snapshot(self._sync_visible_state, cols, rows)

    def _resize_buffer(self, source: list[list[_TerminalCell]], cols: int, rows: int) -> list[list[_TerminalCell]]:
        resized = [[self._blank_cell() for _ in range(cols)] for _ in range(rows)]
        row_offset = max(0, len(source) - rows)
        for target_row in range(min(rows, len(source))):
            src = source[target_row + row_offset]
            for target_col in range(min(cols, len(src))):
                resized[target_row][target_col] = src[target_col]
        return resized

    def feed(self, text: str) -> None:
        for ch in text:
            if self._state == "normal":
                if ch == "\x1b":
                    self._clear_wrap_pending()
                    self._state = "esc"
                elif ch == "\r":
                    self._clear_wrap_pending()
                    self.cursor.col = 0
                elif ch == "\n":
                    self._clear_wrap_pending()
                    self._linefeed()
                elif ch == "\b":
                    self._clear_wrap_pending()
                    self.cursor.col = max(0, self.cursor.col - 1)
                elif ch == "\t":
                    self._clear_wrap_pending()
                    spaces = 4 - (self.cursor.col % 4)
                    for _ in range(spaces):
                        self._put_char(" ")
                elif ord(ch) >= 32:
                    self._put_char(ch)
            elif self._state == "esc":
                if ch == "[":
                    self._state = "csi"
                    self._csi_buffer = ""
                elif ch == "]":
                    self._state = "osc"
                    self._osc_buffer = ""
                    self._osc_pending_escape = False
                elif ch == "7":
                    self._clear_wrap_pending()
                    self.saved_cursor = _CursorState(self.cursor.row, self.cursor.col)
                    self._state = "normal"
                elif ch == "8":
                    self._clear_wrap_pending()
                    self.cursor = _CursorState(self.saved_cursor.row, self.saved_cursor.col)
                    self._state = "normal"
                else:
                    self._state = "normal"
            elif self._state == "csi":
                self._csi_buffer += ch
                if ch.isalpha() or ch in "@`~":
                    self._handle_csi(self._csi_buffer)
                    self._state = "normal"
            elif self._state == "osc":
                if ch == "\x07":
                    self._handle_osc(self._osc_buffer)
                    self._state = "normal"
                    self._osc_pending_escape = False
                elif self._osc_pending_escape and ch == "\\":
                    self._handle_osc(self._osc_buffer[:-1] if self._osc_buffer.endswith("\x1b") else self._osc_buffer)
                    self._state = "normal"
                    self._osc_pending_escape = False
                else:
                    self._osc_buffer += ch
                    self._osc_pending_escape = ch == "\x1b"

    def _clear_wrap_pending(self) -> None:
        self._wrap_pending = False

    def _put_char(self, ch: str) -> None:
        if self._wrap_pending:
            self.cursor.col = 0
            self._linefeed()
            self._wrap_pending = False
        if self.cursor.col >= self.cols:
            self.cursor.col = 0
            self._linefeed()
        self.buffer[self.cursor.row][self.cursor.col] = _TerminalCell(ch, self.current_style)
        if self.cursor.col >= self.cols - 1:
            self._wrap_pending = True
        else:
            self.cursor.col += 1
            self._wrap_pending = False

    def _linefeed(self) -> None:
        if self.cursor.row >= self.rows - 1:
            self._scroll_up()
        else:
            self.cursor.row += 1

    def _scroll_up(self) -> None:
        top_row = [cell for cell in self.buffer[0]]
        if not self.use_alt_buffer:
            self.scrollback.append(top_row)
            if len(self.scrollback) > 2000:
                self.scrollback = self.scrollback[-2000:]
        self.buffer.pop(0)
        self.buffer.append(self._new_row(self.current_style))
        self.cursor.row = self.rows - 1

    def _parse_csi(self, seq: str) -> tuple[str, str, list[int], str]:
        final = seq[-1]
        params = seq[:-1]
        prefix = ""
        while params and params[0] in "?><=!":
            prefix += params[0]
            params = params[1:]
        values: list[int] = []
        if params:
            for value in params.split(";"):
                if not value:
                    values.append(0)
                elif value.lstrip("-").isdigit():
                    values.append(int(value))
                else:
                    return prefix, params, [], final
        return prefix, params, values, final

    def _handle_csi(self, seq: str) -> None:
        self._clear_wrap_pending()
        prefix, raw_params, values, final = self._parse_csi(seq)
        if raw_params and not values and all(part and not part.lstrip("-").isdigit() for part in raw_params.split(";")):
            if self.sequence_handler is not None:
                self.sequence_handler("csi", prefix, raw_params, [], final)
            return

        if self.sequence_handler is not None:
            self.sequence_handler("csi", prefix, raw_params, values, final)

        private = "?" in prefix
        if private and final in ("h", "l"):
            self._handle_private_mode(values, final == "h")
            return

        if final == "A":
            self.cursor.row = max(0, self.cursor.row - (values[0] if values else 1))
        elif final == "B":
            self.cursor.row = min(self.rows - 1, self.cursor.row + (values[0] if values else 1))
        elif final == "C":
            self.cursor.col = min(self.cols - 1, self.cursor.col + (values[0] if values else 1))
        elif final == "D":
            self.cursor.col = max(0, self.cursor.col - (values[0] if values else 1))
        elif final == "E":
            self.cursor.row = min(self.rows - 1, self.cursor.row + (values[0] if values else 1))
            self.cursor.col = 0
        elif final == "F":
            self.cursor.row = max(0, self.cursor.row - (values[0] if values else 1))
            self.cursor.col = 0
        elif final == "G":
            col = (values[0] if values and values[0] else 1) - 1
            self.cursor.col = min(max(0, col), self.cols - 1)
        elif final in ("H", "f"):
            row = (values[0] if len(values) >= 1 and values[0] else 1) - 1
            col = (values[1] if len(values) >= 2 and values[1] else 1) - 1
            self.cursor.row = min(max(0, row), self.rows - 1)
            self.cursor.col = min(max(0, col), self.cols - 1)
        elif final == "J":
            mode = values[0] if values else 0
            if mode == 2:
                self._clear_screen()
            elif mode == 0:
                self._clear_to_end()
            elif mode == 1:
                self._clear_to_start()
        elif final == "K":
            self._clear_line(values[0] if values else 0)
        elif final == "@":
            self._insert_chars(values[0] if values else 1)
        elif final == "X":
            self._erase_chars(values[0] if values else 1)
        elif final == "P":
            self._delete_chars(values[0] if values else 1)
        elif final == "L":
            self._insert_lines(values[0] if values else 1)
        elif final == "M":
            self._delete_lines(values[0] if values else 1)
        elif final == "S":
            self._scroll_region_up(values[0] if values else 1)
        elif final == "T":
            self._scroll_region_down(values[0] if values else 1)
        elif final == "m":
            self._handle_sgr(values or [0])
        elif final == "s":
            self.saved_cursor = _CursorState(self.cursor.row, self.cursor.col)
        elif final == "u":
            self.cursor = _CursorState(self.saved_cursor.row, self.saved_cursor.col)

    def _handle_osc(self, payload: str) -> None:
        if self.sequence_handler is not None:
            self.sequence_handler("osc", "", payload, [], "")

    def _handle_private_mode(self, values: list[int], enabled: bool) -> None:
        if 2026 in values:
            if enabled:
                if not self._sync_update_active:
                    self._sync_visible_state = self._capture_snapshot()
                    self._sync_update_active = True
            elif self._sync_update_active:
                self._sync_update_active = False
                self._sync_visible_state = None
        if 1049 in values:
            self.use_alt_buffer = enabled
            if enabled:
                self.alt_buffer = self._new_buffer()
            self.cursor = _CursorState()
        if 25 in values:
            self.show_cursor = enabled

    def _handle_sgr(self, values: list[int]) -> None:
        style = self.current_style
        fg = style.fg
        bg = style.bg
        bold = style.bold
        dim = style.dim
        italic = style.italic
        underline = style.underline
        inverse = style.inverse

        index = 0
        while index < len(values):
            value = values[index]
            if value == 0:
                fg = self.default_style.fg
                bg = self.default_style.bg
                bold = dim = italic = underline = inverse = False
            elif value == 1:
                bold = True
                dim = False
            elif value == 2:
                dim = True
                bold = False
            elif value == 3:
                italic = True
            elif value == 4:
                underline = True
            elif value == 7:
                inverse = True
            elif value == 22:
                bold = False
                dim = False
            elif value == 23:
                italic = False
            elif value == 24:
                underline = False
            elif value == 27:
                inverse = False
            elif 30 <= value <= 37:
                fg = _xterm_palette(value - 30)
            elif value == 39:
                fg = self.default_style.fg
            elif 40 <= value <= 47:
                bg = _xterm_palette(value - 40)
            elif value == 49:
                bg = self.default_style.bg
            elif 90 <= value <= 97:
                fg = _xterm_palette(value - 90 + 8)
            elif 100 <= value <= 107:
                bg = _xterm_palette(value - 100 + 8)
            elif value in (38, 48):
                target = "fg" if value == 38 else "bg"
                if index + 1 < len(values):
                    mode = values[index + 1]
                    if mode == 5 and index + 2 < len(values):
                        color = _xterm_palette(values[index + 2])
                        if target == "fg":
                            fg = color
                        else:
                            bg = color
                        index += 2
                    elif mode == 2 and index + 4 < len(values):
                        color = _rgba(values[index + 2], values[index + 3], values[index + 4])
                        if target == "fg":
                            fg = color
                        else:
                            bg = color
                        index += 4
            index += 1

        self.current_style = _TerminalStyle(fg, bg, bold, dim, italic, underline, inverse)

    def _clear_screen(self) -> None:
        for row in range(self.rows):
            self.buffer[row] = self._new_row(self.current_style)
        self.cursor = _CursorState()

    def _clear_to_end(self) -> None:
        for col in range(self.cursor.col, self.cols):
            self.buffer[self.cursor.row][col] = self._blank_cell(self.current_style)
        for row in range(self.cursor.row + 1, self.rows):
            self.buffer[row] = self._new_row(self.current_style)

    def _clear_to_start(self) -> None:
        for row in range(self.cursor.row):
            self.buffer[row] = self._new_row(self.current_style)
        for col in range(0, self.cursor.col + 1):
            self.buffer[self.cursor.row][col] = self._blank_cell(self.current_style)

    def _clear_line(self, mode: int) -> None:
        if mode == 2:
            start = 0
            end = self.cols
        elif mode == 1:
            start = 0
            end = self.cursor.col + 1
        else:
            start = self.cursor.col
            end = self.cols
        for col in range(start, end):
            self.buffer[self.cursor.row][col] = self._blank_cell(self.current_style)

    def _insert_chars(self, count: int) -> None:
        count = max(1, min(count, self.cols - self.cursor.col))
        row = self.buffer[self.cursor.row]
        insert_at = self.cursor.col
        for col in range(self.cols - 1, insert_at + count - 1, -1):
            row[col] = row[col - count]
        for col in range(insert_at, min(self.cols, insert_at + count)):
            row[col] = self._blank_cell(self.current_style)

    def _delete_chars(self, count: int) -> None:
        count = max(1, min(count, self.cols - self.cursor.col))
        row = self.buffer[self.cursor.row]
        delete_at = self.cursor.col
        for col in range(delete_at, self.cols - count):
            row[col] = row[col + count]
        for col in range(self.cols - count, self.cols):
            row[col] = self._blank_cell(self.current_style)

    def _erase_chars(self, count: int) -> None:
        count = max(1, min(count, self.cols - self.cursor.col))
        row = self.buffer[self.cursor.row]
        for col in range(self.cursor.col, self.cursor.col + count):
            row[col] = self._blank_cell(self.current_style)

    def _insert_lines(self, count: int) -> None:
        count = max(1, min(count, self.rows - self.cursor.row))
        for _ in range(count):
            self.buffer.insert(self.cursor.row, self._new_row(self.current_style))
            self.buffer.pop()

    def _delete_lines(self, count: int) -> None:
        count = max(1, min(count, self.rows - self.cursor.row))
        for _ in range(count):
            self.buffer.pop(self.cursor.row)
            self.buffer.append(self._new_row(self.current_style))

    def _scroll_region_up(self, count: int) -> None:
        for _ in range(max(1, count)):
            self._scroll_up()

    def _scroll_region_down(self, count: int) -> None:
        for _ in range(max(1, count)):
            self.buffer.insert(0, self._new_row(self.current_style))
            self.buffer.pop()
            self.cursor.row = min(self.cursor.row + 1, self.rows - 1)

    def visible_rows(self) -> list[list[_TerminalCell]]:
        snapshot = self._visible_snapshot()
        buffer = snapshot.alt_buffer if snapshot.use_alt_buffer else snapshot.main_buffer
        if snapshot.use_alt_buffer:
            return self._clone_rows(buffer)
        return self._clone_rows(snapshot.scrollback) + self._clone_rows(buffer)

    def visible_lines(self) -> list[str]:
        return ["".join(cell.char for cell in row) for row in self.visible_rows()]

    def visible_cursor(self) -> _CursorState:
        snapshot = self._visible_snapshot()
        return _CursorState(snapshot.cursor.row, snapshot.cursor.col)

    def visible_show_cursor(self) -> bool:
        return self._visible_snapshot().show_cursor

    def visible_use_alt_buffer(self) -> bool:
        return self._visible_snapshot().use_alt_buffer


class TerminalPanel:
    UNITY_BG = _rgba(20, 20, 20)
    UNITY_HEADER = _rgba(56, 56, 56)
    UNITY_BORDER = _rgba(25, 25, 25)
    UNITY_TEXT = _rgba(210, 210, 210)
    UNITY_TEXT_DIM = _rgba(128, 128, 128)
    UNITY_ACCENT = _rgba(58, 121, 187)
    UNITY_STATUS_OK = _rgba(86, 156, 86)
    UNITY_STATUS_ERR = _rgba(176, 64, 64)

    TOOLBAR_HEIGHT = 24
    FONT_SIZE = 16
    FONT_SPACING = 0.0
    TEXT_PADDING_X = 6
    TEXT_PADDING_Y = 2
    ALT_BUFFER_TOP_PADDING = 4
    FALLBACK_LINE_HEIGHT = 16.0
    FALLBACK_CHAR_WIDTH = 8.0
    FALLBACK_ROW_STEP = 16.0
    FONT_PRIMARY_PATH = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "CascadiaMono.ttf"
    FONT_FALLBACK_PATH = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "DejaVuSansMono.ttf"
    REPLACEMENT_CODEPOINT = 0xFFFD
    TERMINAL_POLICY_INHERIT = "inherit"
    TERMINAL_POLICY_REMOTE_SIGNED = "RemoteSigned"
    TERMINAL_POLICY_BYPASS = "Bypass"

    def __init__(self) -> None:
        self.project_service: Optional[ProjectService] = None
        self.backend: Optional[_TerminalBackend] = None
        self.output_queue: "queue.Queue[str]" = queue.Queue()
        self.screen = _TerminalScreen(100, 24, sequence_handler=self._handle_terminal_sequence)
        self.scroll_offset: float = 0.0
        self.has_focus: bool = False
        self.last_project_root: str = ""
        self.current_cwd: str = ""
        self.current_execution_policy: str = self.TERMINAL_POLICY_INHERIT
        self.status_text: str = "Terminal idle"
        self._session_started: bool = False
        self.toolbar_rect = rl.Rectangle(0, 0, 0, 0)
        self.content_rect = rl.Rectangle(0, 0, 0, 0)
        self.restart_button_rect = rl.Rectangle(0, 0, 0, 0)
        self._follow_output: bool = True
        self.render_font = None
        self._font_load_attempted = False
        self._font_ready = False
        self._font_status_suffix = ""
        self.cell_width = self.FALLBACK_CHAR_WIDTH
        self.line_height = self.FALLBACK_LINE_HEIGHT
        self.row_step = self.FALLBACK_ROW_STEP
        self.text_baseline_offset = 12.0
        self.glyph_draw_offset_y = 0.0
        self._glyph_support_cache: dict[int, bool] = {}
        self._question_glyph_index: Optional[int] = None
        self._replacement_glyph_index: Optional[int] = None

    @classmethod
    def build_text_font_codepoints(cls) -> list[int]:
        codepoints = set(range(32, 127))
        codepoints.update(range(160, 256))
        codepoints.update({
            0x00A1,
            0x00BF,
            0x2022,
            0x2026,
            0x2018,
            0x2019,
            0x201C,
            0x201D,
            cls.REPLACEMENT_CODEPOINT,
        })
        return sorted(codepoints)

    @classmethod
    def build_minimal_text_font_codepoints(cls) -> list[int]:
        return sorted(set(range(32, 127)) | {cls.REPLACEMENT_CODEPOINT})

    @classmethod
    def build_font_codepoints(cls) -> list[int]:
        return cls.build_text_font_codepoints()

    def _resolve_font_path(self) -> Optional[Path]:
        for candidate in (self.FONT_PRIMARY_PATH, self.FONT_FALLBACK_PATH):
            if candidate.exists():
                return candidate
        return None

    def _load_font_from_codepoints(self, font_path: Path, codepoints: list[int]):
        codepoints_ptr = rl.ffi.cast("int *", rl.ffi.new("int[]", codepoints))
        return rl.load_font_ex(str(font_path), self.FONT_SIZE, codepoints_ptr, len(codepoints))

    def _reset_font_support_cache(self) -> None:
        self._glyph_support_cache.clear()
        self._question_glyph_index = None
        self._replacement_glyph_index = None
        if not self._font_ready or self.render_font is None:
            return
        try:
            self._question_glyph_index = int(rl.get_glyph_index(self.render_font, ord("?")))
        except Exception:
            self._question_glyph_index = None
        try:
            self._replacement_glyph_index = int(rl.get_glyph_index(self.render_font, self.REPLACEMENT_CODEPOINT))
        except Exception:
            self._replacement_glyph_index = None

    def _font_has_critical_glyphs(self) -> bool:
        if not self._font_ready or self.render_font is None:
            return False
        required = ("A", "a", "0", "?")
        for ch in required:
            try:
                glyph_index = int(rl.get_glyph_index(self.render_font, ord(ch)))
            except Exception:
                return False
            if glyph_index < 0:
                return False
            if ch != "?" and self._question_glyph_index is not None and glyph_index == self._question_glyph_index:
                return False
        return True

    def _ensure_render_font(self) -> None:
        if self._font_load_attempted:
            return
        self._font_load_attempted = True
        font_path = self._resolve_font_path()
        if font_path is None:
            self._font_status_suffix = " | fallback font"
            return
        try:
            self.render_font = self._load_font_from_codepoints(font_path, self.build_text_font_codepoints())
            self._font_ready = True
            self._font_status_suffix = "" if font_path == self.FONT_PRIMARY_PATH else " | fallback font"
            self._reset_font_support_cache()
            if not self._font_has_critical_glyphs():
                self.render_font = self._load_font_from_codepoints(font_path, self.build_minimal_text_font_codepoints())
                self._font_status_suffix = " | minimal font atlas"
                self._reset_font_support_cache()
            self._update_font_metrics()
        except Exception:
            self.render_font = None
            self._font_ready = False
            self._font_status_suffix = " | fallback font"
            self.cell_width = self.FALLBACK_CHAR_WIDTH
            self.line_height = self.FALLBACK_LINE_HEIGHT
            self.row_step = self.FALLBACK_ROW_STEP

    def _measure_font_metrics_with_pillow(self, font_path: Path) -> Optional[tuple[float, float, float, float]]:
        if ImageFont is None:
            return None
        try:
            pil_font = ImageFont.truetype(str(font_path), self.FONT_SIZE)
        except Exception:
            return None

        width_samples = ("M", "W", " ", "A")
        text_samples = ("M", "A", "g", "y")
        measured_width = 0.0
        bbox_top: Optional[int] = None
        bbox_bottom: Optional[int] = None
        for sample in width_samples:
            try:
                measured_width = max(measured_width, float(pil_font.getlength(sample)))
            except Exception:
                continue
        for sample in text_samples:
            try:
                bbox = pil_font.getbbox(sample)
            except Exception:
                continue
            bbox_top = int(bbox[1]) if bbox_top is None else min(bbox_top, int(bbox[1]))
            bbox_bottom = int(bbox[3]) if bbox_bottom is None else max(bbox_bottom, int(bbox[3]))

        try:
            ascent, descent = pil_font.getmetrics()
        except Exception:
            ascent, descent = self.FONT_SIZE, max(2, self.FONT_SIZE // 4)

        if bbox_top is None or bbox_bottom is None:
            bbox_top = 0
            bbox_bottom = self.FONT_SIZE
        visible_height = max(1, bbox_bottom - bbox_top)
        row_height = max(int(math.ceil(ascent + descent)), visible_height, self.FONT_SIZE)
        cell_width = max(self.FALLBACK_CHAR_WIDTH, int(math.ceil(measured_width or self.FALLBACK_CHAR_WIDTH)))
        glyph_draw_offset_y = int(round((row_height - visible_height) / 2 - bbox_top))
        baseline_offset = glyph_draw_offset_y + ascent
        return float(cell_width), float(row_height), float(baseline_offset), float(glyph_draw_offset_y)

    def _measure_font_metrics_with_raylib(self) -> tuple[float, float]:
        samples = ("M", "\u2588", "\u2502", "\u2580", "\u2584", "\u28ff")
        measured_width = 0.0
        measured_height = 0.0
        for sample in samples:
            measured = rl.measure_text_ex(self.render_font, sample, float(self.FONT_SIZE), self.FONT_SPACING)
            measured_width = max(measured_width, float(getattr(measured, "x", 0.0) or 0.0))
            measured_height = max(measured_height, float(getattr(measured, "y", 0.0) or 0.0))
        return measured_width, measured_height

    def _update_font_metrics(self) -> None:
        if not self._font_ready or self.render_font is None:
            self.cell_width = self.FALLBACK_CHAR_WIDTH
            self.line_height = self.FALLBACK_LINE_HEIGHT
            self.row_step = self.FALLBACK_ROW_STEP
            self.text_baseline_offset = 12.0
            self.glyph_draw_offset_y = 0.0
            return
        font_path = self._resolve_font_path()
        pillow_metrics = self._measure_font_metrics_with_pillow(font_path) if font_path is not None else None
        if pillow_metrics is not None:
            self.cell_width, self.line_height, self.text_baseline_offset, self.glyph_draw_offset_y = pillow_metrics
            self.row_step = self.line_height
            return

        measured_width, measured_height = self._measure_font_metrics_with_raylib()
        self.cell_width = float(max(self.FALLBACK_CHAR_WIDTH, math.ceil(measured_width)))
        self.line_height = float(max(self.render_font.baseSize, math.ceil(measured_height)))
        self.row_step = self.line_height
        self.text_baseline_offset = max(12.0, self.line_height - 3.0)
        self.glyph_draw_offset_y = 0.0

    def _calculate_terminal_size(self) -> tuple[int, int]:
        drawable_rect = self.get_terminal_drawable_rect()
        cell_width = max(1.0, self.cell_width)
        line_height = max(1.0, self.row_step)
        cols = max(80, int(max(1.0, drawable_rect.width) // cell_width))
        rows = max(12, int(max(1.0, drawable_rect.height) // line_height))
        return cols, rows

    def _current_terminal_insets(self, use_visible_state: bool = False) -> tuple[float, float, float, float]:
        use_alt_buffer = self.screen.visible_use_alt_buffer() if use_visible_state else self.screen.use_alt_buffer
        if use_alt_buffer:
            return 0.0, float(self.ALT_BUFFER_TOP_PADDING), 0.0, 0.0
        return (
            float(self.TEXT_PADDING_X),
            float(self.TEXT_PADDING_Y),
            float(self.TEXT_PADDING_X),
            float(self.TEXT_PADDING_Y),
        )

    def get_terminal_drawable_rect(self, use_visible_state: bool = False) -> rl.Rectangle:
        inset_left, inset_top, inset_right, inset_bottom = self._current_terminal_insets(use_visible_state)
        width = max(0.0, float(self.content_rect.width) - inset_left - inset_right)
        height = max(0.0, float(self.content_rect.height) - inset_top - inset_bottom)
        return rl.Rectangle(float(self.content_rect.x) + inset_left, float(self.content_rect.y) + inset_top, width, height)

    def _display_status_text(self) -> str:
        return f"{self.status_text}{self._font_status_suffix}"

    def _get_terminal_execution_policy(self) -> str:
        if self.project_service is None or not self.project_service.has_project:
            return self.TERMINAL_POLICY_INHERIT
        settings = self.project_service.load_project_settings()
        terminal = settings.get("terminal", {})
        if not isinstance(terminal, dict):
            return self.TERMINAL_POLICY_INHERIT
        policy = str(terminal.get("execution_policy", self.TERMINAL_POLICY_INHERIT)).strip() or self.TERMINAL_POLICY_INHERIT
        if policy not in {self.TERMINAL_POLICY_INHERIT, self.TERMINAL_POLICY_REMOTE_SIGNED, self.TERMINAL_POLICY_BYPASS}:
            return self.TERMINAL_POLICY_INHERIT
        return policy

    def _format_terminal_status(self, state: str) -> str:
        if not self.current_cwd:
            return state
        return f"{state} in {self.current_cwd} [policy: {self.current_execution_policy}]"

    def _build_terminal_command(self, execution_policy: Optional[str] = None) -> str:
        policy = execution_policy or self._get_terminal_execution_policy()
        command_parts = ["powershell.exe", "-NoLogo", "-NoProfile"]
        if policy == self.TERMINAL_POLICY_REMOTE_SIGNED:
            command_parts.extend(["-ExecutionPolicy", self.TERMINAL_POLICY_REMOTE_SIGNED])
        elif policy == self.TERMINAL_POLICY_BYPASS:
            command_parts.extend(["-ExecutionPolicy", self.TERMINAL_POLICY_BYPASS])
        return " ".join(command_parts)

    def set_project_service(self, project_service: Optional[ProjectService]) -> None:
        next_root = ""
        if project_service is not None and project_service.has_project:
            next_root = project_service.project_root.as_posix()
        project_changed = next_root != self.last_project_root
        self.project_service = project_service
        self.last_project_root = next_root
        self.current_cwd = next_root
        self.current_execution_policy = self._get_terminal_execution_policy()
        if project_changed and self._session_started:
            self.restart_session()
        elif not next_root:
            self.status_text = "No active project"
        else:
            self.status_text = self._format_terminal_status("PowerShell ready" if self._session_started else "Terminal idle")

    def ensure_session(self) -> None:
        if self.backend is not None and self.backend.poll() is None:
            return
        if self.project_service is None or not self.project_service.has_project:
            self.status_text = "No active project"
            return
        if os.name != "nt":
            self.status_text = "Embedded terminal is only available on Windows"
            return

        project_root = self.project_service.project_root.as_posix()
        self.shutdown()
        cols, rows = self._calculate_terminal_size()
        self.screen = _TerminalScreen(cols, rows, sequence_handler=self._handle_terminal_sequence)
        self.scroll_offset = 0.0
        self._follow_output = True
        self.current_cwd = project_root
        self.current_execution_policy = self._get_terminal_execution_policy()
        self.status_text = self._format_terminal_status("PowerShell ready")

        try:
            self.backend = self._create_backend(project_root, cols, rows)
        except Exception as exc:
            self.backend = None
            self._session_started = False
            self.status_text = f"Terminal init failed: {exc}"
            self.screen.feed(f"[terminal init failed] {exc}\r\n")
            return
        self._session_started = True

    def restart_session(self) -> None:
        self.shutdown()
        if self.project_service is not None and self.project_service.has_project:
            self.ensure_session()
        else:
            self.status_text = "No active project"

    def shutdown(self) -> None:
        backend = self.backend
        self.backend = None
        if backend is not None:
            backend.close()
        self.status_text = "Terminal stopped"

    def update_input(self, active: bool) -> None:
        self._drain_output_queue()
        if not active:
            return

        self.ensure_session()
        mouse = rl.get_mouse_position()
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self.has_focus = rl.check_collision_point_rec(mouse, self.content_rect)
            if rl.check_collision_point_rec(mouse, self.restart_button_rect):
                self.restart_session()
                self.has_focus = False
                return

        if rl.check_collision_point_rec(mouse, self.content_rect):
            wheel_move = rl.get_mouse_wheel_move()
            if wheel_move != 0:
                self.scroll_offset -= wheel_move * self.row_step * 2
                self._clamp_scroll()
                self._follow_output = self.scroll_offset >= self._max_scroll() - self.row_step

        if not self.has_focus or self.backend is None:
            return

        if rl.is_key_pressed(rl.KEY_ESCAPE):
            self.has_focus = False
            return
        if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER):
            self.backend.write_text("\r")
        if rl.is_key_pressed(rl.KEY_BACKSPACE):
            self.backend.write_text("\x08")
        if rl.is_key_pressed(rl.KEY_TAB):
            self.backend.write_text("\t")
        if rl.is_key_pressed(rl.KEY_LEFT):
            self.backend.write_text("\x1b[D")
        if rl.is_key_pressed(rl.KEY_RIGHT):
            self.backend.write_text("\x1b[C")
        if rl.is_key_pressed(rl.KEY_UP):
            self.backend.write_text("\x1b[A")
        if rl.is_key_pressed(rl.KEY_DOWN):
            self.backend.write_text("\x1b[B")
        if rl.is_key_pressed(rl.KEY_HOME):
            self.backend.write_text("\x1b[H")
        if rl.is_key_pressed(rl.KEY_END):
            self.backend.write_text("\x1b[F")
        if rl.is_key_pressed(rl.KEY_DELETE):
            self.backend.write_text("\x1b[3~")
        if rl.is_key_pressed(rl.KEY_PAGE_UP):
            self.backend.write_text("\x1b[5~")
        if rl.is_key_pressed(rl.KEY_PAGE_DOWN):
            self.backend.write_text("\x1b[6~")

        while True:
            codepoint = rl.get_char_pressed()
            if codepoint == 0:
                break
            if codepoint in (8, 9, 10, 13, 27):
                continue
            try:
                char = chr(codepoint)
            except ValueError:
                continue
            if char.isprintable():
                self.backend.write_text(char)

    def render(self, x: int, y: int, width: int, height: int) -> None:
        self._drain_output_queue()
        self._ensure_render_font()
        self.toolbar_rect = rl.Rectangle(float(x), float(y), float(width), float(self.TOOLBAR_HEIGHT))
        self.content_rect = rl.Rectangle(float(x), float(y + self.TOOLBAR_HEIGHT), float(width), float(max(0, height - self.TOOLBAR_HEIGHT)))
        self.restart_button_rect = rl.Rectangle(float(x + 6), float(y + 2), 70.0, 20.0)

        cols, rows = self._calculate_terminal_size()
        self.screen.resize(cols, rows)
        if self.backend is not None:
            self.backend.resize(cols, rows)

        rl.draw_rectangle_rec(self.toolbar_rect, _to_ray_color(self.UNITY_HEADER))
        rl.draw_line(x, y + self.TOOLBAR_HEIGHT - 1, x + width, y + self.TOOLBAR_HEIGHT - 1, _to_ray_color(self.UNITY_BORDER))
        if rl.gui_button(self.restart_button_rect, "Restart"):
            self.restart_session()
            self.has_focus = False

        rl.draw_text("PowerShell", x + 86, y + 7, 10, _to_ray_color(self.UNITY_TEXT))
        status_color = self.UNITY_STATUS_OK if self.backend is not None and self.backend.poll() is None else self.UNITY_STATUS_ERR
        rl.draw_text(self._display_status_text(), x + 170, y + 7, 10, _to_ray_color(status_color))

        default_bg = self.screen.default_style.bg or self.UNITY_BG
        rl.draw_rectangle_rec(self.content_rect, _to_ray_color(default_bg))
        rl.draw_rectangle_lines_ex(self.content_rect, 1, _to_ray_color(self.UNITY_ACCENT if self.has_focus else self.UNITY_BORDER))

        if self.project_service is None or not self.project_service.has_project:
            rl.draw_text("Open a project to start the embedded terminal.", x + 10, int(self.content_rect.y) + 12, 10, _to_ray_color(self.UNITY_TEXT_DIM))
            return

        visible_rows = self.screen.visible_rows()
        drawable_rect = self.get_terminal_drawable_rect(use_visible_state=True)
        rl.begin_scissor_mode(int(drawable_rect.x), int(drawable_rect.y), int(drawable_rect.width), int(drawable_rect.height))
        start_y = float(drawable_rect.y) - self.scroll_offset
        text_x = float(drawable_rect.x)
        for row_index, row in enumerate(visible_rows):
            line_y = start_y + row_index * self.row_step
            if line_y + self.row_step < drawable_rect.y:
                continue
            if line_y > drawable_rect.y + drawable_rect.height:
                break
            self._draw_row_backgrounds(row, text_x, line_y)
            self._draw_row_text(row, text_x, line_y)

        visible_cursor = self.screen.visible_cursor()
        if self.has_focus and self.screen.visible_show_cursor():
            visible_index = visible_cursor.row if self.screen.visible_use_alt_buffer() else len(visible_rows) - self.screen.rows + visible_cursor.row
            cursor_x = int(text_x + visible_cursor.col * self.cell_width)
            cursor_y = int(start_y + visible_index * self.row_step)
            if drawable_rect.y <= cursor_y <= drawable_rect.y + drawable_rect.height:
                rl.draw_rectangle(cursor_x, cursor_y + int(self.row_step) - 2, max(2, int(self.cell_width)), 2, _to_ray_color(self.UNITY_ACCENT))
        rl.end_scissor_mode()

    def captures_keyboard(self) -> bool:
        return self.has_focus

    def _create_backend(self, cwd: str, cols: int, rows: int) -> _TerminalBackend:
        return _WinConPtyBackend(cwd, cols, rows, self._on_backend_output, command_line=self._build_terminal_command(self.current_execution_policy))

    def _on_backend_output(self, chunk: str) -> None:
        self.output_queue.put(chunk)

    def _handle_terminal_sequence(self, kind: str, prefix: str, payload: str, values: list[int], final: str) -> None:
        if self.backend is None:
            return
        response: Optional[str] = None
        if kind == "csi":
            drawable_rect = self.get_terminal_drawable_rect()
            if final == "t" and values == [14]:
                response = f"\x1b[4;{int(drawable_rect.height)};{int(drawable_rect.width)}t"
            elif prefix == "?" and final == "u":
                response = "\x1b[?0u"
            elif prefix == "?" and final == "n" and values == [996]:
                response = f"\x1b[?996;{int(self.cell_width)};{int(self.row_step)}n"
        elif kind == "osc" and payload.startswith("66;"):
            response = None
        if response:
            try:
                self.backend.write_text(response)
            except Exception:
                pass

    def _resolve_style_colors(self, style: _TerminalStyle) -> tuple[ColorTuple, ColorTuple]:
        fg = style.fg or self.screen.default_style.fg or self.UNITY_TEXT
        bg = style.bg or self.screen.default_style.bg or self.UNITY_BG
        if style.inverse:
            fg, bg = bg, fg
        if style.bold:
            fg = _brighten(fg, 0.2)
        if style.dim:
            fg = _blend(fg, bg, 0.55)
        return fg, bg

    def _is_block_element(self, ch: str) -> bool:
        codepoint = ord(ch)
        return 0x2580 <= codepoint <= 0x259F

    def _is_box_drawing(self, ch: str) -> bool:
        return ch in {"\u2500", "\u2502", "\u2503", "\u250c", "\u2510", "\u2514", "\u2518", "\u251c", "\u2524", "\u252c", "\u2534", "\u253c", "\u2579"}

    def _is_braille(self, ch: str) -> bool:
        codepoint = ord(ch)
        return 0x2800 <= codepoint <= 0x28FF

    def _cell_requires_shape_renderer(self, ch: str) -> bool:
        return self._is_block_element(ch) or self._is_box_drawing(ch) or self._is_braille(ch)

    def _font_supports_char(self, ch: str) -> bool:
        if not self._font_ready or self.render_font is None:
            return False
        codepoint = ord(ch)
        cached = self._glyph_support_cache.get(codepoint)
        if cached is not None:
            return cached
        try:
            glyph_index = int(rl.get_glyph_index(self.render_font, codepoint))
        except Exception:
            glyph_index = -1
        supported = glyph_index >= 0
        if supported and ch != "?" and self._question_glyph_index is not None and glyph_index == self._question_glyph_index:
            supported = False
        self._glyph_support_cache[codepoint] = supported
        return supported

    def _renderable_text_char(self, ch: str) -> str:
        if self._font_supports_char(ch):
            return ch
        replacement = "\uFFFD"
        if self._font_supports_char(replacement):
            return replacement
        return "?"

    def _line_thickness(self) -> int:
        return max(1, int(round(min(self.cell_width, self.row_step) / 7.0)))

    def _draw_special_cell(self, ch: str, style: _TerminalStyle, x: float, y: float) -> bool:
        fg, bg = self._resolve_style_colors(style)
        if self._is_block_element(ch):
            return self._draw_block_element(ch, fg, bg, x, y)
        if self._is_box_drawing(ch):
            return self._draw_box_drawing_char(ch, fg, x, y)
        if self._is_braille(ch):
            return self._draw_braille_char(ch, fg, x, y)
        return False

    def _draw_block_rect(self, x: int, y: int, width: int, height: int, color: ColorTuple) -> None:
        if width <= 0 or height <= 0:
            return
        rl.draw_rectangle(x, y, width, height, _to_ray_color(color))

    def _draw_block_element(self, ch: str, fg: ColorTuple, bg: ColorTuple, x: float, y: float) -> bool:
        left = int(round(x))
        top = int(round(y))
        width = max(1, int(round(self.cell_width)))
        height = max(1, int(round(self.row_step)))
        codepoint = ord(ch)

        if codepoint == 0x2588:
            self._draw_block_rect(left, top, width, height, fg)
            return True
        if codepoint == 0x2580:
            self._draw_block_rect(left, top, width, max(1, height // 2), fg)
            return True
        if codepoint == 0x2584:
            half = max(1, height // 2)
            self._draw_block_rect(left, top + height - half, width, half, fg)
            return True
        if codepoint == 0x258C:
            self._draw_block_rect(left, top, max(1, width // 2), height, fg)
            return True
        if codepoint == 0x2590:
            half = max(1, width // 2)
            self._draw_block_rect(left + width - half, top, half, height, fg)
            return True
        if 0x2581 <= codepoint <= 0x2587:
            units = codepoint - 0x2580
            block_height = max(1, int(round(height * units / 8.0)))
            self._draw_block_rect(left, top + height - block_height, width, block_height, fg)
            return True
        if 0x2589 <= codepoint <= 0x258F:
            units = 0x2590 - codepoint
            block_width = max(1, int(round(width * units / 8.0)))
            self._draw_block_rect(left, top, block_width, height, fg)
            return True
        if codepoint == 0x2591:
            self._draw_block_rect(left, top, width, height, _blend(fg, bg, 0.28))
            return True
        if codepoint == 0x2592:
            self._draw_block_rect(left, top, width, height, _blend(fg, bg, 0.5))
            return True
        if codepoint == 0x2593:
            self._draw_block_rect(left, top, width, height, _blend(fg, bg, 0.72))
            return True
        if codepoint == 0x2594:
            block_height = max(1, int(round(height / 8.0)))
            self._draw_block_rect(left, top, width, block_height, fg)
            return True
        if codepoint == 0x2595:
            block_width = max(1, int(round(width / 8.0)))
            self._draw_block_rect(left + width - block_width, top, block_width, height, fg)
            return True
        return False

    def _draw_box_drawing_char(self, ch: str, fg: ColorTuple, x: float, y: float) -> bool:
        left = int(round(x))
        top = int(round(y))
        right = left + max(1, int(round(self.cell_width)))
        bottom = top + max(1, int(round(self.row_step)))
        mid_x = left + max(0, (right - left - self._line_thickness()) // 2)
        mid_y = top + max(0, (bottom - top - self._line_thickness()) // 2)
        thickness = self._line_thickness()
        heavy_thickness = max(thickness, int(round(thickness * 1.8)))

        def horiz(x1: int, x2: int) -> None:
            self._draw_block_rect(x1, mid_y, max(1, x2 - x1), thickness, fg)

        def vert(y1: int, y2: int, line_thickness: int = thickness) -> None:
            offset_x = left + max(0, (right - left - line_thickness) // 2)
            self._draw_block_rect(offset_x, y1, line_thickness, max(1, y2 - y1), fg)

        if ch == "\u2500":
            horiz(left, right)
        elif ch == "\u2502":
            vert(top, bottom)
        elif ch == "\u2503":
            vert(top, bottom, heavy_thickness)
        elif ch == "\u250c":
            horiz(mid_x, right)
            vert(mid_y, bottom)
        elif ch == "\u2510":
            horiz(left, mid_x + thickness)
            vert(mid_y, bottom)
        elif ch == "\u2514":
            horiz(mid_x, right)
            vert(top, mid_y + thickness)
        elif ch == "\u2518":
            horiz(left, mid_x + thickness)
            vert(top, mid_y + thickness)
        elif ch == "\u251c":
            horiz(mid_x, right)
            vert(top, bottom)
        elif ch == "\u2524":
            horiz(left, mid_x + thickness)
            vert(top, bottom)
        elif ch == "\u252c":
            horiz(left, right)
            vert(mid_y, bottom)
        elif ch == "\u2534":
            horiz(left, right)
            vert(top, mid_y + thickness)
        elif ch == "\u253c":
            horiz(left, right)
            vert(top, bottom)
        elif ch == "\u2579":
            vert(top, mid_y + heavy_thickness, heavy_thickness)
        else:
            return False
        return True

    def _draw_braille_char(self, ch: str, fg: ColorTuple, x: float, y: float) -> bool:
        pattern = ord(ch) - 0x2800
        if pattern <= 0:
            return True

        left = int(round(x))
        top = int(round(y))
        width = max(2, int(round(self.cell_width)))
        height = max(4, int(round(self.row_step)))
        dot_width = max(1, width // 5)
        dot_height = max(1, height // 9)
        x_positions = (left + dot_width, left + width - 2 * dot_width)
        y_positions = (
            top + dot_height,
            top + height // 3,
            top + (2 * height) // 3 - dot_height,
            top + height - 2 * dot_height,
        )
        dot_map = {
            0: (0, 0),
            1: (0, 1),
            2: (0, 2),
            3: (1, 0),
            4: (1, 1),
            5: (1, 2),
            6: (0, 3),
            7: (1, 3),
        }
        for bit, (col_idx, row_idx) in dot_map.items():
            if pattern & (1 << bit):
                self._draw_block_rect(x_positions[col_idx], y_positions[row_idx], dot_width, dot_height, fg)
        return True

    def _draw_row_backgrounds(self, row: list[_TerminalCell], x: float, y: float) -> None:
        default_bg = self.screen.default_style.bg or self.UNITY_BG
        start = 0
        while start < len(row):
            _, bg = self._resolve_style_colors(row[start].style)
            end = start + 1
            while end < len(row) and self._resolve_style_colors(row[end].style)[1] == bg:
                end += 1
            if bg != default_bg:
                rl.draw_rectangle(
                    int(round(x + start * self.cell_width)),
                    int(round(y)),
                    max(1, int((end - start) * self.cell_width + 0.5)),
                    max(1, int(self.row_step + 0.5)),
                    _to_ray_color(bg),
                )
            start = end

    def _draw_row_text(self, row: list[_TerminalCell], x: float, y: float) -> None:
        run_text: list[str] = []
        run_start = 0
        run_fg: Optional[ColorTuple] = None
        run_underline = False

        def flush_run(end_index: int) -> None:
            nonlocal run_text, run_start, run_fg, run_underline
            if not run_text or run_fg is None:
                run_text = []
                return
            text = "".join(run_text)
            if text.strip():
                run_x = float(round(x + run_start * self.cell_width))
                draw_y = float(round(y + self.glyph_draw_offset_y))
                if self._font_ready and self.render_font is not None:
                    rl.draw_text_ex(
                        self.render_font,
                        text,
                        rl.Vector2(run_x, draw_y),
                        float(self.FONT_SIZE),
                        self.FONT_SPACING,
                        _to_ray_color(run_fg),
                    )
                else:
                    rl.draw_text(text, int(run_x), int(draw_y), self.FONT_SIZE, _to_ray_color(run_fg))
                if run_underline:
                    underline_y = int(round(y + min(self.row_step - 2.0, self.text_baseline_offset + 1.0)))
                    rl.draw_rectangle(int(run_x), underline_y, max(1, int((end_index - run_start) * self.cell_width)), 1, _to_ray_color(run_fg))
            run_text = []
            run_fg = None
            run_underline = False

        for index, cell in enumerate(row):
            fg, _ = self._resolve_style_colors(cell.style)
            if self._cell_requires_shape_renderer(cell.char):
                flush_run(index)
                self._draw_special_cell(cell.char, cell.style, x + index * self.cell_width, y)
                continue

            render_char = self._renderable_text_char(cell.char)

            if run_fg is None:
                run_start = index
                run_fg = fg
                run_underline = cell.style.underline
            elif fg != run_fg or cell.style.underline != run_underline:
                flush_run(index)
                run_start = index
                run_fg = fg
                run_underline = cell.style.underline

            run_text.append(render_char)

        flush_run(len(row))

    def _drain_output_queue(self) -> None:
        drained = False
        while True:
            try:
                chunk = self.output_queue.get_nowait()
            except queue.Empty:
                break
            drained = True
            self.screen.feed(chunk)
        if drained:
            if self._follow_output and not self.screen.use_alt_buffer:
                self.scroll_offset = 10**9
            else:
                self.scroll_offset = max(0.0, self.scroll_offset)
            self._clamp_scroll()
            if self.backend is not None and self.backend.poll() is not None:
                self.status_text = f"process exited with code {self.backend.poll()}"

    def _clamp_scroll(self) -> None:
        self.scroll_offset = max(0.0, min(self.scroll_offset, self._max_scroll()))

    def _max_scroll(self) -> float:
        visible_rows = self.screen.visible_rows()
        drawable_rect = self.get_terminal_drawable_rect(use_visible_state=True)
        return max(0.0, len(visible_rows) * self.row_step - drawable_rect.height)
