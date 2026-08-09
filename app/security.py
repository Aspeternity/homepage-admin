from __future__ import annotations

import hmac
import secrets
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Deque

import bcrypt
from fastapi import HTTPException, Request, status

from .settings import settings


class LoginLimiter:
    def __init__(self, max_attempts: int = 8, window_minutes: int = 10) -> None:
        self.max_attempts = max_attempts
        self.window = timedelta(minutes=window_minutes)
        self.attempts: dict[str, Deque[datetime]] = defaultdict(deque)

    def _prune(self, key: str) -> None:
        now = datetime.now(timezone.utc)
        q = self.attempts[key]
        while q and now - q[0] > self.window:
            q.popleft()

    def allowed(self, key: str) -> bool:
        self._prune(key)
        return len(self.attempts[key]) < self.max_attempts

    def record_failure(self, key: str) -> None:
        self._prune(key)
        self.attempts[key].append(datetime.now(timezone.utc))

    def clear(self, key: str) -> None:
        self.attempts.pop(key, None)


login_limiter = LoginLimiter()


def verify_password(candidate: str) -> bool:
    if settings.password_hash:
        try:
            return bcrypt.checkpw(candidate.encode("utf-8"), settings.password_hash.encode("utf-8"))
        except ValueError:
            return False
    return bool(settings.password) and hmac.compare_digest(candidate, settings.password)


def require_auth(request: Request) -> None:
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})


def ensure_csrf(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


def verify_csrf(request: Request, token: str | None) -> None:
    expected = request.session.get("csrf")
    if not expected or not token or not hmac.compare_digest(expected, token):
        raise HTTPException(status_code=403, detail="CSRF 校验失败，请刷新页面后重试。")
