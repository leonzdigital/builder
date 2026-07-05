"""Local secrets for SerpAPI / Google CSE — gitignored, shared for developer & client enrich."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

from lp_content_enricher import normalize_serpapi_keys

ROOT = Path(__file__).resolve().parent
SECRETS_DIR = ROOT / 'secrets'
SERP_SECRETS_PATH = SECRETS_DIR / 'serp-keys.json'
SERP_SECRETS_EXAMPLE = SECRETS_DIR / 'serp-keys.example.json'


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def ensure_serp_secrets_file() -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    if SERP_SECRETS_PATH.is_file():
        return
    if SERP_SECRETS_EXAMPLE.is_file():
        try:
            shutil.copy2(SERP_SECRETS_EXAMPLE, SERP_SECRETS_PATH)
        except OSError:
            pass


def migrate_serp_from_brand_links(brand_links: Dict[str, Any]) -> None:
    """One-time: move keys from brand-links global into secrets file if secrets empty."""
    if SERP_SECRETS_PATH.is_file():
        existing = load_serp_secrets()
        if existing.get('serpapi_keys') or existing.get('google_cse_key'):
            return
    g = brand_links.get('global') or {}
    keys = normalize_serpapi_keys(g.get('serpapi_keys') or g.get('serpapi_key') or '')
    cse_key = (g.get('google_cse_key') or '').strip()
    cse_cx = (g.get('google_cse_cx') or '').strip()
    enabled = g.get('serp_enrich_enabled', True)
    if not keys and not (cse_key and cse_cx):
        return
    save_serp_secrets({
        'serpapi_keys': keys,
        'google_cse_key': cse_key,
        'google_cse_cx': cse_cx,
        'serp_enrich_enabled': enabled,
    })


def load_serp_secrets() -> Dict[str, Any]:
    ensure_serp_secrets_file()
    raw = _read_json(SERP_SECRETS_PATH)
    keys = normalize_serpapi_keys(raw.get('serpapi_keys') or raw.get('serpapi_key') or '')
    enabled = raw.get('serp_enrich_enabled', True)
    return {
        'serpapi_keys': keys,
        'serpapi_key': keys[0] if keys else '',
        'google_cse_key': (raw.get('google_cse_key') or '').strip(),
        'google_cse_cx': (raw.get('google_cse_cx') or '').strip(),
        'serp_enrich_enabled': str(enabled).lower() not in ('0', 'false', 'no', ''),
        '_source': 'secrets/serp-keys.json' if SERP_SECRETS_PATH.is_file() else 'none',
    }


def save_serp_secrets(data: Dict[str, Any]) -> None:
    keys = normalize_serpapi_keys(data.get('serpapi_keys') or data.get('serpapi_key') or '')
    current = load_serp_secrets() if SERP_SECRETS_PATH.is_file() else {}
    out = {
        'serpapi_keys': keys or current.get('serpapi_keys') or [],
        'google_cse_key': (data.get('google_cse_key') or current.get('google_cse_key') or '').strip(),
        'google_cse_cx': (data.get('google_cse_cx') or current.get('google_cse_cx') or '').strip(),
        'serp_enrich_enabled': data.get(
            'serp_enrich_enabled',
            current.get('serp_enrich_enabled', True),
        ),
    }
    _write_json(SERP_SECRETS_PATH, out)


def set_serp_enrich_enabled(enabled: bool) -> None:
    current = load_serp_secrets()
    save_serp_secrets({**current, 'serp_enrich_enabled': enabled})


def serp_secrets_summary() -> Dict[str, Any]:
    s = load_serp_secrets()
    key_count = len(s.get('serpapi_keys') or [])
    has_cse = bool(s.get('google_cse_key') and s.get('google_cse_cx'))
    configured = key_count > 0 or has_cse
    return {
        'configured': configured,
        'key_count': key_count,
        'has_cse': has_cse,
        'enabled': bool(s.get('serp_enrich_enabled', True)),
        'source': s.get('_source', 'none'),
    }
