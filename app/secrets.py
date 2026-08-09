from __future__ import annotations

import copy
import hashlib
import hmac
import re
from typing import Any

from .settings import settings

SECRET_PREFIX = "__HOMEPAGE_ADMIN_SECRET_"
SECRET_SUFFIX = "__"
SECRET_PLACEHOLDER = SECRET_PREFIX + "…" + SECRET_SUFFIX

_EXACT_SECRET_KEYS = {
    "key",
    "apikey",
    "api_key",
    "api-key",
    "token",
    "secret",
    "password",
    "passwd",
    "access_token",
    "accesstoken",
    "client_secret",
    "clientsecret",
    "authorization",
}
_SECRET_PATTERN = re.compile(r"(?:^|[_-])(password|passwd|secret|token|api[_-]?key)(?:$|[_-])", re.I)
_SECRET_CONTAINER_KEYS = {"providers"}


def is_secret_key(key: Any) -> bool:
    text = str(key).strip().lower()
    return text in _EXACT_SECRET_KEYS or bool(_SECRET_PATTERN.search(text))


def _placeholder(value: Any) -> str:
    digest = hmac.new(
        settings.session_secret.encode("utf-8"),
        repr(value).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]
    return f"{SECRET_PREFIX}{digest}{SECRET_SUFFIX}"


def _is_secret_container(key: Any) -> bool:
    return str(key).strip().lower() in _SECRET_CONTAINER_KEYS


def mask_secrets(value: Any) -> Any:
    masked = copy.deepcopy(value)
    _mask_in_place(masked)
    return masked


def _mask_in_place(value: Any, parent_key: Any = None) -> None:
    if isinstance(value, dict):
        secret_container = _is_secret_container(parent_key)
        for key in list(value.keys()):
            child = value[key]
            if (secret_container or is_secret_key(key)) and child not in (None, ""):
                value[key] = _placeholder(child)
            else:
                _mask_in_place(child, key)
    elif isinstance(value, list):
        for child in value:
            _mask_in_place(child, parent_key)


def _collect_secret_map(value: Any, result: dict[str, Any], parent_key: Any = None) -> None:
    if isinstance(value, dict):
        secret_container = _is_secret_container(parent_key)
        for key, child in value.items():
            if (secret_container or is_secret_key(key)) and child not in (None, ""):
                result[_placeholder(child)] = copy.deepcopy(child)
            else:
                _collect_secret_map(child, result, key)
    elif isinstance(value, list):
        for child in value:
            _collect_secret_map(child, result, parent_key)


def restore_masked_secrets(edited: Any, original: Any) -> Any:
    """Restore masked values by opaque token, so entries may safely be reordered."""
    secret_map: dict[str, Any] = {}
    _collect_secret_map(original, secret_map)
    return _restore_in_place(edited, secret_map)


def _restore_in_place(
    value: Any, secret_map: dict[str, Any], parent_key: Any = None, secret_context: bool = False
) -> Any:
    if isinstance(value, dict):
        child_secret_context = _is_secret_container(parent_key)
        for key in list(value.keys()):
            value[key] = _restore_in_place(value[key], secret_map, key, child_secret_context)
        return value
    if isinstance(value, list):
        for index, child in enumerate(list(value)):
            value[index] = _restore_in_place(child, secret_map, parent_key, secret_context)
        return value
    if isinstance(value, str) and value.startswith(SECRET_PREFIX) and value.endswith(SECRET_SUFFIX):
        if not (secret_context or is_secret_key(parent_key)):
            raise ValueError("敏感字段占位符只能保留在敏感字段中；请重新打开编辑器后再保存。")
        if value not in secret_map:
            raise ValueError("检测到无法对应原值的敏感字段占位符；请重新打开编辑器后再保存。")
        return copy.deepcopy(secret_map[value])
    return value
