"""Small process-local admin login for the local administration dashboard."""

from __future__ import annotations

import secrets
from typing import Dict

ADMIN_REGISTRY: Dict[str, str] = {"admin": "admin123"}
_active_tokens: set[str] = set()


def authenticate(username: str, password: str) -> str | None:
    if ADMIN_REGISTRY.get(username) != password:
        return None
    token = secrets.token_urlsafe(32)
    _active_tokens.add(token)
    return token


def is_authenticated(token: str | None) -> bool:
    return bool(token and token in _active_tokens)


def revoke(token: str) -> None:
    _active_tokens.discard(token)
