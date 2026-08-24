"""Minimal child-side resource limiter for the trusted Runner."""

from __future__ import annotations

import os
import resource
import sys


def main() -> int:
    if len(sys.argv) < 5:
        return 64
    try:
        maximum_file_size = int(sys.argv[1])
        maximum_secret_size = int(sys.argv[2])
        secret_fd = int(sys.argv[3])
    except ValueError:
        return 64
    if maximum_file_size <= 0 or maximum_secret_size <= 0 or secret_fd < 0:
        return 64
    executable = sys.argv[4]
    if not os.path.isabs(executable):
        return 64
    secret = bytearray()
    try:
        while len(secret) <= maximum_secret_size:
            chunk = os.read(secret_fd, maximum_secret_size + 1 - len(secret))
            if not chunk:
                break
            secret.extend(chunk)
    finally:
        os.close(secret_fd)
    if not secret or len(secret) > maximum_secret_size:
        secret[:] = b"\x00" * len(secret)
        return 65
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(
        resource.RLIMIT_FSIZE,
        (maximum_file_size, maximum_file_size),
    )
    environment = dict(os.environb)
    environment[b"OPENAI_API_KEY"] = bytes(secret)
    secret[:] = b"\x00" * len(secret)
    os.execve(executable, [executable, *sys.argv[5:]], environment)
    return 70  # pragma: no cover - execve only returns by raising an exception.


if __name__ == "__main__":  # pragma: no cover - exercised through the Runner.
    raise SystemExit(main())
