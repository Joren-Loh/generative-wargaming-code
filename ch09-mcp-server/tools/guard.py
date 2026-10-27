# -*- coding: utf-8 -*-
"""The safety boundary: refuse at the tool's front door whatever can be refused; do not rely on the model being careful."""

from __future__ import annotations

from pathlib import Path

# the only places read and write are allowed: the AFSIM install and this repository
ALLOWED_SUFFIX = {".txt", ".json", ".evt", ".log", ".aer", ".csv", ".md"}
DENY_KEYWORDS = ("rm ", "del ", "rmdir", "format ", "shutdown", "powershell -enc", "&&", "|")
MAX_TIMEOUT_SEC = 600
MAX_EVT_BYTES = 64 * 1024 * 1024


class GuardError(Exception):
    pass


def safe_path(raw: str, roots: list[Path], *, must_exist: bool = True) -> Path:
    """Allow only paths inside roots, and only with a whitelisted suffix."""
    path = Path(raw).expanduser()
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError as exc:
        raise GuardError(f"cannot resolve path: {raw} ({exc.__class__.__name__})")
    if not any(_is_within(resolved, root) for root in roots if root):
        raise GuardError(f"refused: path outside the working roots: {resolved}")
    if not resolved.is_dir() and resolved.suffix.lower() not in ALLOWED_SUFFIX:
        raise GuardError(f"refused: suffix not allowed: {resolved.suffix}")
    return resolved


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(Path(root).resolve())
        return True
    except (ValueError, OSError):
        return False


def clamp_timeout(value) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return 120.0
    return max(1.0, min(seconds, MAX_TIMEOUT_SEC))


def reject_command_text(text: str) -> None:
    lowered = (text or "").lower()
    for word in DENY_KEYWORDS:
        if word in lowered:
            raise GuardError(f"refused: input contains a forbidden fragment: {word!r}")
