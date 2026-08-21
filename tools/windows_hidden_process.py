"""Run one Windows process on a private, inactive desktop."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess


CREATE_NO_WINDOW = 0x08000000
GENERIC_ALL = 0x10000000
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258


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
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32, user32


def run(executable: Path, cwd: Path, timeout: float) -> subprocess.CompletedProcess:
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
    command_line = ctypes.create_unicode_buffer(f'"{Path(executable).resolve()}"')
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
                [str(executable)], int(return_code.value), "", "")
        finally:
            kernel32.CloseHandle(process.hThread)
            kernel32.CloseHandle(process.hProcess)
    finally:
        user32.CloseDesktop(desktop)
