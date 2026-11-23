# -*- coding: utf-8 -*-
"""
auth.py — модуль аутентификации на Python.
Управляет сессиями (cookie-подобные токены) поверх БД из db.py.
"""

import secrets
import time

import db

# token -> {"user_id": int, "expires": float}
_sessions = {}
SESSION_TTL = 8 * 60 * 60  # 8 часов


def login(login_name: str, password: str):
    """Проверяет логин/пароль. Возвращает (token, user_dict) или (None, None)."""
    user = db.check_login((login_name or "").strip(), password or "")
    if not user:
        return None, None
    token = secrets.token_hex(16)
    _sessions[token] = {"user_id": user["id"], "expires": time.time() + SESSION_TTL}
    return token, user


def logout(token: str):
    _sessions.pop(token, None)


def get_session_user(token: str):
    """Возвращает dict пользователя по токену сессии либо None."""
    sess = _sessions.get(token or "")
    if not sess:
        return None
    if sess["expires"] < time.time():
        _sessions.pop(token, None)
        return None
    return db.get_user(sess["user_id"])
