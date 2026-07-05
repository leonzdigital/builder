"""Developer vs client build mode — controls exposure of secret API fields."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent
BUILD_MODE_FILE = ROOT / 'builder-mode.json'
BUILD_MODE_EXAMPLE = ROOT / 'builder-mode.example.json'


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def ensure_build_mode_file() -> None:
    if BUILD_MODE_FILE.is_file() or not BUILD_MODE_EXAMPLE.is_file():
        return
    try:
        BUILD_MODE_FILE.write_text(BUILD_MODE_EXAMPLE.read_text(encoding='utf-8'), encoding='utf-8')
    except OSError:
        pass


def resolve_build_mode() -> str:
    env = (os.environ.get('LP_BUILD_MODE') or '').strip().lower()
    if env in ('developer', 'dev'):
        return 'developer'
    if env == 'client':
        return 'client'
    ensure_build_mode_file()
    data = _read_json(BUILD_MODE_FILE) or _read_json(BUILD_MODE_EXAMPLE) or {}
    mode = str(data.get('mode', 'client')).strip().lower()
    return 'developer' if mode in ('developer', 'dev') else 'client'


def is_developer_mode() -> bool:
    return resolve_build_mode() == 'developer'


def build_mode_label() -> str:
    return 'Developer' if is_developer_mode() else 'Client'
