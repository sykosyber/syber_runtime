"""Restricted worker for deterministic Python artifact verification.

This module is launched as a script with Python isolated mode. It applies OS
resource ceilings before importing the artifact and installs an audit policy
that denies network access, child processes, native-library loading, and file
access outside the disposable work directory and explicitly approved read
roots.

The policy is defense in depth for Python artifacts, not a replacement for an
OS account/container boundary when hostile native code is in scope.
"""

from __future__ import annotations

import io
import json
import os
import sys
import unittest
from pathlib import Path
from typing import Any


_WINDOWS_JOB_HANDLE: object | None = None
_WRITE_OPEN_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND


def main() -> int:
    try:
        manifest = json.loads(sys.stdin.read())
        if not isinstance(manifest, dict):
            raise ValueError("worker manifest must be a JSON object")
        workdir = Path(str(manifest["workdir"])).resolve(strict=True)
        read_roots = tuple(Path(str(item)).resolve(strict=True) for item in manifest.get("read_roots", []))
        memory_bytes = int(manifest["memory_bytes"])
        cpu_seconds = int(manifest["cpu_seconds"])
        if memory_bytes <= 0 or cpu_seconds <= 0:
            raise ValueError("worker resource limits must be positive")

        _apply_resource_limits(memory_bytes=memory_bytes, cpu_seconds=cpu_seconds)
        os.chdir(workdir)
        _install_audit_policy(workdir=workdir, read_roots=read_roots)
        sys.dont_write_bytecode = True
        sys.path[:] = [str(workdir), *(str(path) for path in read_roots), *sys.path]

        stream = _BoundedTextBuffer(limit=64_000)
        suite = unittest.defaultTestLoader.loadTestsFromName("test_oracle_suite")
        result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
        sys.stdout.write(stream.getvalue())
        return 0 if result.wasSuccessful() else 1
    except BaseException as exc:  # noqa: BLE001 - the worker must fail closed.
        sys.stderr.write(f"isolated worker failed closed: {type(exc).__name__}: {exc}\n")
        return 2


class _BoundedTextBuffer(io.StringIO):
    def __init__(self, *, limit: int) -> None:
        super().__init__()
        self.limit = limit
        self.truncated = False

    def write(self, value: str) -> int:
        remaining = self.limit - self.tell()
        if remaining <= 0:
            self.truncated = True
            return len(value)
        if len(value) > remaining:
            super().write(value[:remaining])
            self.truncated = True
            return len(value)
        return super().write(value)

    def getvalue(self) -> str:
        value = super().getvalue()
        if self.truncated:
            value += "\n[worker output truncated]\n"
        return value


def _install_audit_policy(*, workdir: Path, read_roots: tuple[Path, ...]) -> None:
    stdlib_roots = {
        Path(sys.base_prefix).resolve(),
        Path(sys.prefix).resolve(),
        Path(sys.executable).resolve().parent,
    }
    allowed_read_roots = tuple(sorted({workdir, *read_roots, *stdlib_roots}, key=str))

    def audit(event: str, args: tuple[Any, ...]) -> None:
        if event.startswith("socket."):
            raise PermissionError("isolated worker denied network access")
        if event in {
            "subprocess.Popen",
            "os.system",
            "os.posix_spawn",
            "os.posix_spawnp",
            "os.startfile",
            "ctypes.dlopen",
            "ctypes.dlsym",
            "ctypes.call_function",
        }:
            raise PermissionError(f"isolated worker denied operation: {event}")
        if event.startswith("winreg."):
            raise PermissionError("isolated worker denied registry access")
        if event == "open" and args:
            path_value = args[0]
            if isinstance(path_value, int):
                return
            mode_or_flags = args[1] if len(args) > 1 else "r"
            writing = _is_write_mode(mode_or_flags)
            _require_allowed_path(
                path_value,
                allowed_roots=(workdir,) if writing else allowed_read_roots,
                action="write" if writing else "read",
            )
        elif event in {
            "os.remove",
            "os.rename",
            "os.replace",
            "os.rmdir",
            "os.mkdir",
            "os.chmod",
            "os.chown",
            "os.link",
            "os.symlink",
            "os.truncate",
            "shutil.copyfile",
            "shutil.copymode",
            "shutil.copystat",
        }:
            for value in args[:2]:
                if isinstance(value, (str, bytes, os.PathLike)):
                    _require_allowed_path(value, allowed_roots=(workdir,), action=event)

    sys.addaudithook(audit)


def _is_write_mode(mode_or_flags: Any) -> bool:
    if isinstance(mode_or_flags, int):
        return bool(mode_or_flags & _WRITE_OPEN_FLAGS)
    mode = str(mode_or_flags)
    return any(marker in mode for marker in ("w", "a", "x", "+"))


def _require_allowed_path(value: str | bytes | os.PathLike[str], *, allowed_roots: tuple[Path, ...], action: str) -> None:
    path = Path(os.fsdecode(value))
    if not path.is_absolute():
        path = Path.cwd() / path
    resolved = path.resolve(strict=False)
    if any(resolved == root or resolved.is_relative_to(root) for root in allowed_roots):
        return
    raise PermissionError(f"isolated worker denied {action} outside allowed roots: {resolved}")


def _apply_resource_limits(*, memory_bytes: int, cpu_seconds: int) -> None:
    if os.name == "nt":
        _apply_windows_job_limits(memory_bytes=memory_bytes, cpu_seconds=cpu_seconds)
    else:
        _apply_posix_limits(memory_bytes=memory_bytes, cpu_seconds=cpu_seconds)


def _apply_posix_limits(*, memory_bytes: int, cpu_seconds: int) -> None:
    import resource

    limits = (
        (resource.RLIMIT_CPU, cpu_seconds),
        (resource.RLIMIT_AS, memory_bytes),
        (resource.RLIMIT_FSIZE, 8 * 1024 * 1024),
        (resource.RLIMIT_NOFILE, 64),
    )
    for kind, value in limits:
        resource.setrlimit(kind, (value, value))
    if hasattr(resource, "RLIMIT_NPROC"):
        resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))


def _apply_windows_job_limits(*, memory_bytes: int, cpu_seconds: int) -> None:
    # ctypes stays local to setup; generated code is denied native-library audit
    # events after the policy is installed.
    import ctypes
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")

    JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002
    JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.PerProcessUserTimeLimit = cpu_seconds * 10_000_000
    info.BasicLimitInformation.ActiveProcessLimit = 1
    info.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_PROCESS_TIME
        | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        | JOB_OBJECT_LIMIT_PROCESS_MEMORY
        | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    info.ProcessMemoryLimit = memory_bytes
    if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
    if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
        raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")

    global _WINDOWS_JOB_HANDLE
    _WINDOWS_JOB_HANDLE = job


if __name__ == "__main__":
    raise SystemExit(main())
