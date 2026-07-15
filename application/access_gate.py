"""Whole-app password gate for the public Cloud deploy.

Bounds quota/rate-limit exposure to invited friends rather than arbitrary
internet visitors. Mirrors runtime_guard.py's fail-safe shape: the unset case
must never grant access, with no special-case branch needed to get the safe
default right — it falls out of the comparison itself.
"""

from __future__ import annotations

from application.runtime_guard import is_local_runtime


def is_access_gate_required() -> bool:
    return not is_local_runtime()


def check_password(entered: str, expected: str | None) -> bool:
    return bool(expected) and entered == expected
