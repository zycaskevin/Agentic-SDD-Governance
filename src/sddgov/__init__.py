"""Agentic SDD Governance."""

import sys


def _require_supported_python(version_info=None) -> None:
    detected = sys.version_info if version_info is None else version_info
    if tuple(detected[:2]) < (3, 10):
        version = ".".join(str(part) for part in detected[:2])
        raise RuntimeError(
            "Agentic SDD Governance requires Python 3.10 or newer; "
            f"detected Python {version}. Install a supported Python and recreate the virtual environment."
        )


_require_supported_python()

__version__ = "0.2.0rc1"
