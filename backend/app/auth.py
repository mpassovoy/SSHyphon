from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config_store
from .activity_log import log_error, log_event
from .models import AuthResponse, AuthStatus

SESSION_TTL_SECONDS = 24 * 60 * 60
REMEMBER_ME_TTL_SECONDS = 30 * 24 * 60 * 60
_http_bearer = HTTPBearer(auto_error=False)
_sessions: dict[str, "SessionInfo"] = {}
_sessions_lock = threading.RLock()


@dataclass
class SessionInfo:
    username: str
    token: str
    expires_at: float


def _hash_password(password: str, salt: str) -> str:
    message = f"{salt}:{password}".encode("utf-8")
    return hashlib.sha256(message).hexdigest()


def _get_credentials() -> tuple[str, str, str]:
    record = config_store.get_auth_record()
    username = (record.get("username") or "").strip()
    salt = record.get("salt") or ""
    password_hash = record.get("password_hash") or ""
    return username, salt, password_hash


def _store_credentials(username: str, password: str) -> None:
    username = username.strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    config_store.save_auth_record({"username": username, "salt": salt, "password_hash": password_hash})


def is_configured() -> bool:
    username, salt, password_hash = _get_credentials()
    return bool(username and salt and password_hash)


def _create_session(username: str, remember_me: bool = False) -> AuthResponse:
    token = secrets.token_urlsafe(32)
    ttl = REMEMBER_ME_TTL_SECONDS if remember_me else SESSION_TTL_SECONDS
    expires_at = time.time() + ttl
    session = SessionInfo(username=username, token=token, expires_at=expires_at)
    with _sessions_lock:
        _sessions[token] = session
    return AuthResponse(token=token, expires_at=expires_at)


def setup_credentials(username: str, password: str, remember_me: bool = False) -> AuthResponse:
    if is_configured():
        raise HTTPException(status_code=400, detail="Authentication is already configured")
    _store_credentials(username, password)
    return _create_session(username, remember_me)


def login(username: str, password: str, remember_me: bool = False) -> AuthResponse:
    stored_username, salt, password_hash = _get_credentials()
    if not stored_username or not salt or not password_hash:
        log_error("auth.login_failed", username=username.strip(), reason="not_configured")
        raise HTTPException(status_code=400, detail="Authentication is not configured yet")
    username = username.strip()
    if username != stored_username:
        log_error("auth.login_failed", username=username, reason="invalid_username")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if _hash_password(password, salt) != password_hash:
        log_error("auth.login_failed", username=username, reason="invalid_password")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    response = _create_session(username, remember_me)
    log_event("auth.login", username=username, remember_me=remember_me)
    return response


def _get_session(token: str | None) -> Optional[SessionInfo]:
    if not token:
        return None
    with _sessions_lock:
        session = _sessions.get(token)
        if not session:
            return None
        if session.expires_at <= time.time():
            _sessions.pop(token, None)
            return None
        return session


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
) -> SessionInfo:
    token = credentials.credentials if credentials else None
    session = _get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required")
    return session


def optional_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
) -> str | None:
    return credentials.credentials if credentials else None


def get_status(token: str | None) -> AuthStatus:
    session = _get_session(token)
    return AuthStatus(
        configured=is_configured(),
        authenticated=bool(session),
        session_expires_at=session.expires_at if session else None,
    )


def logout(token: str | None) -> None:
    if not token:
        return
    with _sessions_lock:
        _sessions.pop(token, None)
