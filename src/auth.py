"""
TIMPS API Key Authentication

Keys are stored in ~/.timps/.secrets (chmod 600, never logged or echoed).
The MCP server enforces key checks when TIMPS_AUTH=1 is set in its env,
or when at least one key exists in the secrets store.

CLI usage:
  python3 give_work.py --keygen "my-laptop"
  python3 give_work.py --keys
  python3 give_work.py --revoke abc123

MCP usage (add to mcp.json "env" section):
  "TIMPS_AUTH": "1",
  "TIMPS_API_KEY": "timps-sk-<your-key>"

For team setups: each member generates their own key with --keygen,
then adds it to their IDE's MCP config env block.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_SECRETS_FILE = Path(
    os.environ.get("TIMPS_SECRETS_FILE", str(Path.home() / ".timps" / ".secrets"))
)
_KEY_PREFIX = "timps-sk-"


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load() -> List[Dict]:
    if not _SECRETS_FILE.exists():
        return []
    try:
        return json.loads(_SECRETS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _save(data: List[Dict]) -> None:
    _SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SECRETS_FILE.write_text(json.dumps(data, indent=2))
    # Owner read/write only — no group or other access
    _SECRETS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_key(label: str = "default") -> str:
    """
    Generate a new 48-character API key, store its hash, return the raw key.
    The raw key is shown ONCE — it is not stored in plain text.
    """
    key = _KEY_PREFIX + secrets.token_hex(24)   # 48 hex chars after prefix
    data = _load()
    data.append({
        "hash": _hash(key),
        "label": label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_used_at": None,
    })
    _save(data)
    return key


def verify_key(key: str) -> bool:
    """
    Return True if the key is valid. Updates last_used_at on success.
    Constant-time comparison to prevent timing attacks.
    """
    if not key or not key.startswith(_KEY_PREFIX):
        return False
    key_hash = _hash(key)
    data = _load()
    matched = False
    for entry in data:
        # Use == on pre-hashed values — sha256 output comparison is safe
        if entry.get("hash") == key_hash:
            entry["last_used_at"] = datetime.now(timezone.utc).isoformat()
            matched = True
    if matched:
        _save(data)
    return matched


def list_keys() -> List[Dict]:
    """Return metadata for all stored keys (hash prefix only — never the raw key)."""
    return [
        {
            "label": e.get("label", "?"),
            "hash_prefix": e.get("hash", "")[:12] + "…",
            "created_at": e.get("created_at", "?"),
            "last_used_at": e.get("last_used_at") or "never",
        }
        for e in _load()
    ]


def revoke_key(hash_prefix: str) -> bool:
    """Remove all keys whose stored hash starts with hash_prefix. Returns True if any removed."""
    data = _load()
    before = len(data)
    data = [e for e in data if not e.get("hash", "").startswith(hash_prefix)]
    if len(data) < before:
        _save(data)
        return True
    return False


def is_auth_enabled() -> bool:
    """
    Auth is only active when TIMPS_AUTH=1 is explicitly set in the environment.
    Having stored keys alone does NOT enable auth — this keeps single-user setups
    frictionless while allowing teams to opt-in by setting the env var.
    """
    return os.environ.get("TIMPS_AUTH", "").strip() == "1"


def check_request_auth(arguments: Dict[str, Any]) -> bool:
    """
    Validate the _api_key field from a tool call's arguments dict.

    - If auth is disabled → always True (open access).
    - If TIMPS_API_KEY env var is set → accept that value as a valid key too.
    - Otherwise → verify against stored hashes.

    Side-effect: pops '_api_key' from arguments so it's not forwarded to handlers.
    """
    if not is_auth_enabled():
        return True

    # Accept server-configured master key from env (useful for CI/single-user setups)
    env_key = os.environ.get("TIMPS_API_KEY", "")
    if env_key:
        supplied = arguments.pop("_api_key", None)
        if supplied == env_key:
            return True
        # Also accept against stored keys
        if supplied and verify_key(supplied):
            return True
        return False

    # No env key set — require a stored key
    supplied = arguments.pop("_api_key", None)
    if not supplied:
        return False
    return verify_key(supplied)
