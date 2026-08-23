"""Run one Windows process on a private, inactive desktop."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from collections.abc import Sequence
import os
from pathlib import Path
import subprocess


CREATE_NO_WINDOW = 0x08000000
GENERIC_ALL = 0x10000000
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WNDENUMPROC = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(
    wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class STARTUPINFOW(ctypes.Structure):
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
        ("lpReserved2", ctypes.POINTER(wintypes.BYTE)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


def _configured_kernel32():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.CreateDesktopW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
    ]
    user32.CreateDesktopW.restype = wintypes.HANDLE
    user32.CloseDesktop.argtypes = [wintypes.HANDLE]
    user32.CloseDesktop.restype = wintypes.BOOL
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
        wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
        ctypes.POINTER(STARTUPINFOW), ctypes.POINTER(PROCESS_INFORMATION),
    ]
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.QueryPerformanceCounter.argtypes = [ctypes.POINTER(ctypes.c_longlong)]
    kernel32.QueryPerformanceCounter.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    user32.EnumDesktopWindows.argtypes = [
        wintypes.HANDLE, WNDENUMPROC, wintypes.LPARAM]
    user32.EnumDesktopWindows.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    return kernel32, user32


class PrivateDesktopProcess:
    """A controllable process on an inactive Windows desktop."""

    def __init__(self, executable: Path, cwd: Path,
                 arguments: Sequence[str] = ()) -> None:
        if os.name != "nt":
            raise OSError("private Windows desktops are available only on Windows")
        self.kernel32, self.user32 = _configured_kernel32()
        self.desktop_name = f"NoctisProfile-{os.getpid()}-{id(self):x}"
        self.desktop = self.user32.CreateDesktopW(
            self.desktop_name, None, None, 0, GENERIC_ALL, None)
        if not self.desktop:
            raise ctypes.WinError(ctypes.get_last_error())

        self.process = PROCESS_INFORMATION()
        self.command = [str(Path(executable).resolve()), *map(str, arguments)]
        command_line = ctypes.create_unicode_buffer(
            subprocess.list2cmdline(self.command))
        startup = STARTUPINFOW()
        startup.cb = ctypes.sizeof(startup)
        startup.lpDesktop = f"WinSta0\\{self.desktop_name}"
        try:
            created = self.kernel32.CreateProcessW(
                str(Path(executable).resolve()), command_line,
                None, None, False, CREATE_NO_WINDOW, None,
                str(Path(cwd).resolve()), ctypes.byref(startup),
                ctypes.byref(self.process),
            )
            if not created:
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self.user32.CloseDesktop(self.desktop)
            self.desktop = None
            raise
        self._closed = False

    @property
    def pid(self) -> int:
        return int(self.process.dwProcessId)

    def poll(self) -> int | None:
        result = self.kernel32.WaitForSingleObject(self.process.hProcess, 0)
        if result == WAIT_TIMEOUT:
            return None
        if result != WAIT_OBJECT_0:
            raise ctypes.WinError(ctypes.get_last_error())
        return_code = wintypes.DWORD()
        if not self.kernel32.GetExitCodeProcess(
                self.process.hProcess, ctypes.byref(return_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(return_code.value)

    def wait(self, timeout: float) -> int | None:
        milliseconds = max(1, min(round(timeout * 1000), 0xFFFFFFFE))
        result = self.kernel32.WaitForSingleObject(
            self.process.hProcess, milliseconds)
        if result == WAIT_TIMEOUT:
            return None
        if result != WAIT_OBJECT_0:
            raise ctypes.WinError(ctypes.get_last_error())
        return self.poll()

    def main_window_handle(self) -> int | None:
        candidates: list[tuple[int, int]] = []
        callback_error: list[BaseException] = []

        def visit(hwnd, _lparam):
            try:
                process_id = wintypes.DWORD()
                self.user32.GetWindowThreadProcessId(
                    hwnd, ctypes.byref(process_id))
                if process_id.value == self.process.dwProcessId:
                    rect = RECT()
                    if self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                        area = max(0, rect.right - rect.left) * max(
                            0, rect.bottom - rect.top)
                        candidates.append((area, hwnd))
                return True
            except BaseException as error:
                callback_error.append(error)
                return False

        callback = WNDENUMPROC(visit)
        enumerated = self.user32.EnumDesktopWindows(self.desktop, callback, 0)
        if callback_error:
            raise callback_error[0]
        if not enumerated:
            error = ctypes.get_last_error()
            if error:
                raise ctypes.WinError(error)
        if not candidates:
            return None
        return max(candidates)[1]

    def window_rectangle(self, handle: int) -> tuple[int, int, int, int]:
        rect = RECT()
        if not self.user32.GetWindowRect(handle, ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        return rect.left, rect.top, rect.right, rect.bottom

    def post_key(self, handle: int, virtual_key: int, down: bool) -> None:
        message = WM_KEYDOWN if down else WM_KEYUP
        lparam = 1 if down else 0xC0000001
        if not self.user32.PostMessageW(
                handle, message, virtual_key, lparam):
            raise ctypes.WinError(ctypes.get_last_error())

    def performance_counter(self) -> int:
        value = ctypes.c_longlong()
        if not self.kernel32.QueryPerformanceCounter(ctypes.byref(value)):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(value.value)

    def terminate(self, exit_code: int = 1) -> None:
        if self.poll() is None:
            if not self.kernel32.TerminateProcess(
                    self.process.hProcess, exit_code):
                error = ctypes.get_last_error()
                if (self.kernel32.WaitForSingleObject(
                        self.process.hProcess, 100) != WAIT_OBJECT_0):
                    raise ctypes.WinError(error)
                return
            self.kernel32.WaitForSingleObject(self.process.hProcess, 5000)

    def close(self) -> None:
        if self._closed:
            return
        try:
            self.terminate()
        finally:
            self.kernel32.CloseHandle(self.process.hThread)
            self.kernel32.CloseHandle(self.process.hProcess)
            self.user32.CloseDesktop(self.desktop)
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()


def run(executable: Path, cwd: Path, timeout: float,
        arguments: Sequence[str] = ()) -> subprocess.CompletedProcess:
    if os.name != "nt":
        raise OSError("private Windows desktops are available only on Windows")
    kernel32, user32 = _configured_kernel32()
    desktop_name = f"NoctisNivgen-{os.getpid()}"
    desktop = user32.CreateDesktopW(
        desktop_name, None, None, 0, GENERIC_ALL, None)
    if not desktop:
        raise ctypes.WinError(ctypes.get_last_error())

    startup = STARTUPINFOW()
    startup.cb = ctypes.sizeof(startup)
    startup.lpDesktop = f"WinSta0\\{desktop_name}"
    process = PROCESS_INFORMATION()
    command = [str(Path(executable).resolve()), *map(str, arguments)]
    command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
    try:
        created = kernel32.CreateProcessW(
            str(Path(executable).resolve()), command_line,
            None, None, False, CREATE_NO_WINDOW, None,
            str(Path(cwd).resolve()), ctypes.byref(startup), ctypes.byref(process),
        )
        if not created:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            milliseconds = max(1, min(round(timeout * 1000), 0xFFFFFFFE))
            result = kernel32.WaitForSingleObject(process.hProcess, milliseconds)
            if result == WAIT_TIMEOUT:
                kernel32.TerminateProcess(process.hProcess, 1)
                kernel32.WaitForSingleObject(process.hProcess, 5000)
                raise subprocess.TimeoutExpired(str(executable), timeout)
            if result != WAIT_OBJECT_0:
                raise ctypes.WinError(ctypes.get_last_error())
            return_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(
                    process.hProcess, ctypes.byref(return_code)):
                raise ctypes.WinError(ctypes.get_last_error())
            return subprocess.CompletedProcess(
                command, int(return_code.value), "", "")
        finally:
            kernel32.CloseHandle(process.hThread)
            kernel32.CloseHandle(process.hProcess)
    finally:
        user32.CloseDesktop(desktop)
