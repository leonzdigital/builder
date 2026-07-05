"""SERP content enrichment — SerpAPI (PAA) + Google Custom Search. Rewrites only, no raw SERP paste."""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

SERP_CACHE_DIR = Path(__file__).resolve().parent / 'content' / 'cache' / 'serp'
DEFAULT_CACHE_TTL = 86400 * 7


def _fetch_json(url: str, timeout: int = 15) -> Optional[Dict[str, Any]]:
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; LPBuilder/2.2; content-enricher)'})
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _cache_key(keyword: str) -> str:
    return hashlib.md5(keyword.strip().lower().encode()).hexdigest()


def _load_cache(keyword: str, ttl: int) -> Optional[Dict[str, Any]]:
    path = SERP_CACHE_DIR / f'{_cache_key(keyword)}.json'
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if time.time() - float(data.get('fetched_at', 0)) < ttl:
            en = data.get('enrichment')
            return en if isinstance(en, dict) else None
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        pass
    return None


def _write_cache(keyword: str, enrichment: Dict[str, Any]) -> None:
    SERP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = SERP_CACHE_DIR / f'{_cache_key(keyword)}.json'
    path.write_text(
        json.dumps({'keyword': keyword, 'fetched_at': time.time(), 'enrichment': enrichment}, ensure_ascii=False, indent=2)
        + '\n',
        encoding='utf-8',
    )


def _clean_text(text: str, max_len: int = 200) -> str:
    t = re.sub(r'\s+', ' ', (text or '').strip())
    t = re.sub(r'https?://\S+', '', t)
    if len(t) > max_len:
        t = t[: max_len - 1].rsplit(' ', 1)[0] + '…'
    return t


def _rewrite_question(question: str, keyword: str) -> str:
    q = _clean_text(question, 140)
    if not q:
        return f'Bagaimana {{brand}} membantu pencarian {keyword}?'
    q = re.sub(r'\?\s*$', '', q).strip()
    q = re.sub(r'\b(situs|portal|platform|website)\s+[A-Za-z0-9\-]+', r'\1 {brand}', q, count=1, flags=re.I)
    if '{brand}' not in q:
        q = f'{q} di {{brand}}'
    if not q.endswith('?'):
        q += '?'
    return q


def _rewrite_answer(snippet: str, keyword: str) -> str:
    s = _clean_text(snippet, 260)
    if len(s) < 50:
        s = (
            f'{{brand}} merangkum informasi seputar {keyword} — deposit mulai {{deposit}}, '
            f'mirror alternatif diperbarui rutin, dan CS {{support}}.'
        )
    if '{brand}' not in s:
        s = f'{{brand}} — {s}'
    if '{deposit}' not in s and len(s) < 200:
        s = s.rstrip('.') + '. Deposit minimal {{deposit}}.'
    return s


def fetch_serpapi(keyword: str, api_key: str) -> Dict[str, Any]:
    url = (
        'https://serpapi.com/search.json?engine=google'
        f'&q={quote_plus(keyword)}&hl=id&gl=id&api_key={quote_plus(api_key)}'
    )
    data = _fetch_json(url)
    if not data:
        return {'faq': [], 'titles': [], 'descriptions': [], 'synonyms': []}

    faq: List[Dict[str, str]] = []
    for item in (data.get('related_questions') or [])[:14]:
        if not isinstance(item, dict):
            continue
        q = _rewrite_question(item.get('question') or '', keyword)
        a = _rewrite_answer(item.get('snippet') or item.get('title') or '', keyword)
        faq.append({'q': q, 'a': a})

    synonyms: List[str] = []
    for item in (data.get('related_searches') or [])[:10]:
        if isinstance(item, dict):
            q = _clean_text(item.get('query') or '', 80)
            if q and q.lower() != keyword.lower():
                synonyms.append(q)

    titles = [
        f'{{brand}} | {syn.title()} & Portal Member Stabil'
        for syn in synonyms[:6]
    ]
    descriptions = [
        f'{{brand}} — panduan {syn}, deposit {{deposit}}, mirror harian, layanan {{support}}.'
        for syn in synonyms[:6]
    ]
    return {'faq': faq, 'titles': titles, 'descriptions': descriptions, 'synonyms': synonyms}


def fetch_google_cse(keyword: str, api_key: str, cx: str) -> Dict[str, Any]:
    url = (
        f'https://www.googleapis.com/customsearch/v1?key={quote_plus(api_key)}'
        f'&cx={quote_plus(cx)}&q={quote_plus(keyword)}&hl=id&num=8'
    )
    data = _fetch_json(url)
    if not data:
        return {'faq': [], 'titles': [], 'descriptions': [], 'synonyms': []}

    faq: List[Dict[str, str]] = []
    descriptions: List[str] = []
    for i, item in enumerate((data.get('items') or [])[:8]):
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get('title') or '', 90)
        snippet = _clean_text(item.get('snippet') or '', 200)
        if not snippet:
            continue
        if i == 0:
            q = f'Apa keunggulan {{brand}} untuk {keyword}?'
        else:
            q = f'Bagaimana {{brand}} merespons kebutuhan seputar {title[:50]}?'
        faq.append({'q': q, 'a': _rewrite_answer(snippet, keyword)})
        descriptions.append(f'{{brand}} — {snippet[:120]}. Deposit {{deposit}}, akses stabil.')

    return {'faq': faq, 'titles': [], 'descriptions': descriptions, 'synonyms': []}


def merge_enrichments(*parts: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {'faq': [], 'titles': [], 'descriptions': [], 'synonyms': []}
    seen_q: set = set()
    seen_t: set = set()
    for part in parts:
        for item in part.get('faq') or []:
            if not isinstance(item, dict):
                continue
            key = (item.get('q') or '').lower()[:90]
            if key and key not in seen_q:
                seen_q.add(key)
                out['faq'].append(item)
        for text in part.get('titles') or []:
            if text and text not in seen_t:
                seen_t.add(text)
                out['titles'].append(text)
        for text in part.get('descriptions') or []:
            if text:
                out['descriptions'].append(text)
        for syn in part.get('synonyms') or []:
            if syn and syn not in out['synonyms']:
                out['synonyms'].append(syn)
    return out


def get_serp_enrichment(
    keyword: str,
    *,
    serpapi_key: str = '',
    google_cse_key: str = '',
    google_cse_cx: str = '',
    force: bool = False,
    cache_ttl: int = DEFAULT_CACHE_TTL,
) -> Dict[str, Any]:
    primary = (keyword.split(',')[0] if keyword else '').strip()
    empty: Dict[str, Any] = {'faq': [], 'titles': [], 'descriptions': [], 'synonyms': [], 'source': 'none'}
    if not primary:
        return empty

    has_serp = bool((serpapi_key or '').strip())
    has_cse = bool((google_cse_key or '').strip() and (google_cse_cx or '').strip())
    if not has_serp and not has_cse:
        return empty

    if not force:
        cached = _load_cache(primary, cache_ttl)
        if cached:
            cached = dict(cached)
            cached.setdefault('source', 'cache')
            return cached

    parts: List[Dict[str, Any]] = []
    sources: List[str] = []
    if has_serp:
        parts.append(fetch_serpapi(primary, serpapi_key.strip()))
        sources.append('serpapi')
    if has_cse:
        parts.append(fetch_google_cse(primary, google_cse_key.strip(), google_cse_cx.strip()))
        sources.append('google_cse')

    merged = merge_enrichments(*parts)
    merged['source'] = '+'.join(sources) if sources else 'none'
    merged['keyword'] = primary
    _write_cache(primary, merged)
    return merged


def enrichment_to_pools(enrichment: Dict[str, Any], cat: str) -> Dict[str, List[Dict[str, Any]]]:
    faq_pool: List[Dict[str, Any]] = []
    for i, item in enumerate(enrichment.get('faq') or []):
        if not isinstance(item, dict):
            continue
        faq_pool.append({
            'id': f'serp-faq-{cat}-{i}',
            'q': item.get('q', ''),
            'a': item.get('a', ''),
            '_intent': 'general',
            '_serp': True,
        })

    title_pool = [
        {'id': f'serp-title-{cat}-{i}', 'text': text, '_serp': True}
        for i, text in enumerate(enrichment.get('titles') or [])
        if text
    ]
    desc_pool = [
        {'id': f'serp-desc-{cat}-{i}', 'text': text, '_serp': True}
        for i, text in enumerate(enrichment.get('descriptions') or [])
        if text
    ]
    return {'faq': faq_pool, 'titles': title_pool, 'descriptions': desc_pool}


def serp_configured(cfg: Dict[str, Any]) -> bool:
    return bool((cfg.get('serpapi_key') or '').strip()) or bool(
        (cfg.get('google_cse_key') or '').strip() and (cfg.get('google_cse_cx') or '').strip()
    )
