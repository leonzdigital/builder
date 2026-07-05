"""Portable SEO/compliance helpers for LP Builder — aligned with Google deploy prompt."""
from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import Request, urlopen

REQ_PATH = Path(__file__).resolve().parent / 'build-requirements.json'

_TITLE_BANNED_DEFAULT = frozenset({
    'slot', 'gacor', 'maxwin', 'judi', 'togel', 'jackpot', 'casino', 'bandar', 'bet', 'taruhan', 'rtp',
})

_TITLE_NEUTRAL_PATTERNS: Tuple[str, ...] = (
    '{brand} | Portal Layanan Digital Berhadiah Optimal',
    '{brand} | Arena Permainan Andal & Bonus Harian Aktif',
    '{brand} | Destinasi Hiburan Terverifikasi Transaksi Cepat',
    '{brand} | Ruang Permainan Premium Payout Optimal Indonesia',
    '{brand} | Ekosistem Hiburan Andal Akses 24 Jam Non-Stop',
    '{brand} | Koleksi Permainan Terlengkap & Reward Nyata',
    '{brand} | Platform Gaming Digital Professional Terpercaya',
    '{brand} | Layanan Permainan Online Berhadiah Terpercaya',
    '{brand} | Pusat Hiburan Digital Transparan & Responsif',
    '{brand} | Portal Member Premium Deposit {deposit}',
)

_MANDATORY_FAQ: Tuple[Tuple[str, str], ...] = (
    (
        'Apa itu situs {brand} dan layanan utamanya?',
        'Situs {brand} adalah portal resmi yang merangkum akses member, informasi {kw_primary}, mirror alternatif, dan panduan transaksi mulai {deposit}. Semua navigasi dirancang agar member menemukan login, promo, dan bantuan CS dalam satu halaman.',
    ),
    (
        'Bagaimana cara {brand} login untuk member aktif?',
        'Buka halaman resmi {brand}, pilih menu masuk, lalu gunakan username dan password terdaftar. Jika domain utama lambat, gunakan mirror alternatif {brand} yang diperbarui harian — proses login tetap sama dan aman.',
    ),
    (
        'Di mana menemukan {brand} link alternatif yang aktif?',
        'Link alternatif {brand} tercantum di halaman resmi dan diperbarui rutin tanpa perlu VPN. Bookmark sekali cukup — member tidak perlu mencari link acak dari sumber tidak resmi.',
    ),
    (
        'Apakah RTP {brand} transparan dan dapat dipercaya?',
        '{brand} menampilkan data provider resmi agar member mengetahui persentase teoretis sebelum bermain. Informasi RTP diperbarui berkala dan disusun terpisah per kategori permainan.',
    ),
    (
        'Apa keunggulan website {brand} dibanding portal sejenis?',
        'Website {brand} menonjolkan antarmuka ringan, deposit mulai {deposit}, metode {payments}, CS {support}, dan struktur informasi yang mudah discan dari HP maupun desktop.',
    ),
    (
        'Bagaimana proses daftar {brand} untuk member baru?',
        'Klik tombol Daftar di halaman {brand}, isi nama dan nomor HP aktif, pilih metode pembayaran. Akun aktif dalam menit dan member bisa langsung deposit mulai {deposit}.',
    ),
)

_BREADCRUMB_LABELS: Tuple[str, ...] = (
    '{brand}',
    '{brand} Login',
    '{brand} Link',
    'Situs {brand}',
    'Link Alternatif {brand}',
    'RTP {brand}',
    'Website {brand}',
)

_AI_BANNED_PHRASES: Tuple[str, ...] = (
    'pada era digital',
    'tidak dapat dipungkiri',
    'dalam dunia modern',
    'penting untuk diketahui',
    'perlu dipahami',
)

_requirements_cache: Optional[Dict[str, Any]] = None


def load_requirements() -> Dict[str, Any]:
    global _requirements_cache
    if _requirements_cache is not None:
        return _requirements_cache
    if REQ_PATH.is_file():
        try:
            _requirements_cache = json.loads(REQ_PATH.read_text(encoding='utf-8'))
            return _requirements_cache
        except (json.JSONDecodeError, OSError):
            pass
    _requirements_cache = {}
    return _requirements_cache


def title_banned_words() -> frozenset:
    req = load_requirements()
    words = req.get('title', {}).get('banned_words') or list(_TITLE_BANNED_DEFAULT)
    return frozenset(w.lower() for w in words)


def title_min_len() -> int:
    return int(load_requirements().get('title', {}).get('min', 45))


def title_max_len() -> int:
    return int(load_requirements().get('title', {}).get('max', 60))


def desc_min_len() -> int:
    return int(load_requirements().get('description', {}).get('min', 130))


def desc_max_len() -> int:
    return int(load_requirements().get('description', {}).get('max', 155))


def faq_min_items() -> int:
    return int(load_requirements().get('faq', {}).get('min_items', 8))


def amp_robots_content() -> str:
    return str(load_requirements().get('amp', {}).get('robots', 'index, follow, max-image-preview:large'))


def trim_title(title: str, max_len: Optional[int] = None) -> str:
    m = max_len or title_max_len()
    t = re.sub(r'\s+', ' ', title.strip())
    if len(t) <= m:
        return t
    cut = t[:m]
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0]
    return cut.rstrip(' |,-')


def trim_desc(desc: str, max_len: Optional[int] = None) -> str:
    m = max_len or desc_max_len()
    d = re.sub(r'\s+', ' ', desc.strip())
    if len(d) <= m:
        return d
    cut = d[: m - 1].rsplit(' ', 1)[0]
    return cut + '…'


def title_has_banned_word(title: str) -> bool:
    low = title.lower()
    return any(re.search(rf'\b{re.escape(w)}\b', low) for w in title_banned_words())


def sanitize_title_neutral(title: str, brand: str, deposit: str = 'Rp10.000') -> str:
    """Ensure title uses neutral vocabulary and meets length/banned-word rules."""
    t = trim_title(title)
    if title_has_banned_word(t) or len(t) < title_min_len():
        import random
        rng = random.Random(hash(brand + t) & 0xFFFFFFFF)
        pattern = rng.choice(_TITLE_NEUTRAL_PATTERNS)
        t = trim_title(pattern.format(brand=brand, deposit=deposit))
    while len(t) < title_min_len():
        t = trim_title(f'{t} | Portal Digital Indonesia')
    return t


def gen_h1_text(brand: str, keyword_primary: str = 'permainan digital') -> str:
    primary = keyword_primary.strip() or 'permainan digital'
    candidates = (
        f'{brand} — Portal {primary.title()} Terpercaya Indonesia',
        f'{brand} | Situs Resmi {primary.title()} & Akses Member',
        f'{brand}: Pusat Informasi {primary.title()} & Layanan Digital',
    )
    import random
    rng = random.Random(hash(brand + primary) & 0xFFFFFFFF)
    h1 = rng.choice(candidates)
    return trim_title(h1, max_len=80)


def gen_breadcrumb_trail(brand: str) -> Tuple[List[str], List[Dict[str, str]]]:
    html = [x.format(brand=brand) for x in _BREADCRUMB_LABELS]
    schema = [{'name': x} for x in html]
    return html, schema


def gen_mandatory_brand_faqs(
    brand: str,
    kw_primary: str,
    dep: str,
    payments: str = 'Bank, QRIS, E-Wallet',
    support: str = '24 Jam',
) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for q_t, a_t in _MANDATORY_FAQ:
        items.append({
            'q': q_t.format(brand=brand, kw_primary=kw_primary),
            'a': a_t.format(
                brand=brand,
                kw_primary=kw_primary,
                deposit=dep,
                payments=payments,
                support=support,
            ),
        })
    return items


def limit_article_canonical_anchors(html: str, canon: str, max_anchors: int = 1) -> str:
    if not canon or max_anchors < 1:
        return html
    pattern = re.compile(
        rf'<a\b[^>]*href="{re.escape(canon)}"[^>]*>.*?</a>',
        flags=re.I | re.S,
    )
    matches = list(pattern.finditer(html))
    if len(matches) <= max_anchors:
        return html
    for m in reversed(matches[max_anchors:]):
        inner = re.sub(r'<[^>]+>', '', m.group(0))
        html = html[: m.start()] + inner + html[m.end() :]
    return html


def enforce_single_h1(html: str, h1_text: str) -> str:
    h1_matches = list(re.finditer(r'(<h1\b[^>]*>)([\s\S]*?)(</h1>)', html, flags=re.I))
    if not h1_matches:
        for tag in ('main', 'article'):
            if re.search(rf'<{tag}\b', html, flags=re.I):
                html = re.sub(
                    rf'(<{tag}\b[^>]*>)',
                    rf'\1\n<h1>{h1_text}</h1>\n',
                    html,
                    count=1,
                    flags=re.I,
                )
                return html
        html = re.sub(r'(<body\b[^>]*>)', rf'\1\n<h1>{h1_text}</h1>\n', html, count=1, flags=re.I)
        return html

    keep_idx = 0
    for i, m in enumerate(h1_matches):
        before = html[max(0, m.start() - 1200) : m.start()]
        if re.search(r'<(?:main|article)\b', before, flags=re.I):
            keep_idx = i
            break

    parts: List[str] = []
    pos = 0
    for i, m in enumerate(h1_matches):
        parts.append(html[pos : m.start()])
        if i == keep_idx:
            parts.append(f'<h1>{h1_text}</h1>')
        else:
            parts.append(f'<h2>{m.group(2).strip()}</h2>')
        pos = m.end()
    parts.append(html[pos:])
    return ''.join(parts)


def strip_production_comments(html: str, keep_amp_boilerplate: bool = False) -> str:
    if keep_amp_boilerplate:
        protected: List[str] = []

        def _save(m: re.Match) -> str:
            protected.append(m.group(0))
            return f'__AMP_BOILER_{len(protected) - 1}__'

        html = re.sub(r'<style amp-boilerplate>[\s\S]*?</style>', _save, html, flags=re.I)
        html = re.sub(r'<noscript><style amp-boilerplate>[\s\S]*?</style></noscript>', _save, html, flags=re.I)
        html = re.sub(r'<!--(?!__AMP_BOILER)[\s\S]*?-->', '', html)
        for i, block in enumerate(protected):
            html = html.replace(f'__AMP_BOILER_{i}__', block)
        return html
    return re.sub(r'<!--[\s\S]*?-->', '', html)


def ensure_hreflang(html: str, canon: str) -> str:
    if not canon or canon == '#LINKCANNO':
        return html
    html = re.sub(r'<link[^>]+hreflang="[^"]+"[^>]*>\s*', '', html, flags=re.I)
    insert = (
        f'<link rel="alternate" hreflang="id-ID" href="{canon}" />\n'
        f'    <link rel="alternate" hreflang="x-default" href="{canon}" />\n    '
    )
    if re.search(r'<link rel="canonical"', html, flags=re.I):
        html = re.sub(r'(<link rel="canonical"[^>]+>)', rf'\1\n    {insert}', html, count=1, flags=re.I)
    else:
        html = re.sub(r'(<head>)', rf'\1\n    {insert}', html, count=1, flags=re.I)
    return html


def ensure_og_type_website(html: str) -> str:
    if re.search(r'<meta property="og:type"', html, flags=re.I):
        html = re.sub(
            r'(<meta property="og:type" content=")[^"]*(")',
            r'\1website\2',
            html,
            count=1,
            flags=re.I,
        )
    else:
        html = re.sub(
            r'(<meta property="og:title"[^>]+>)',
            r'\1\n    <meta property="og:type" content="website">',
            html,
            count=1,
            flags=re.I,
        )
    return html


_DIM_CACHE: Dict[str, Tuple[int, int]] = {}


def fetch_image_dimensions(url: str, timeout: int = 5) -> Tuple[int, int]:
    if not url or url.startswith('#'):
        return 500, 500
    cached = _DIM_CACHE.get(url)
    if cached:
        return cached
    result = (500, 500)
    try:
        from PIL import Image
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; LPBuilder/2.1)'})
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read(512_000)
        img = Image.open(BytesIO(data))
        result = img.size
    except Exception:
        pass
    _DIM_CACHE[url] = result
    return result


def extract_css_palette(html: str) -> Dict[str, str]:
    defaults = {
        'body_bg': '#0d0f12',
        'body_bg2': '#1f242d',
        'card_bg': '#181c24',
        'card_bg2': '#0c0e12',
        'accent': '#e5ad61',
        'accent_dark': '#b87e2a',
        'border': '#9ca9b8',
        'text': '#e2e8f0',
        'btn_text': '#0c0e12',
    }
    body_m = re.search(r'body\s*\{[^}]*background[^:]*:\s*([^;}\n]+)', html, flags=re.I)
    if body_m:
        bg = body_m.group(1).strip()
        hexes = re.findall(r'#[0-9a-fA-F]{3,8}', bg)
        if hexes:
            defaults['body_bg2'] = hexes[0]
            if len(hexes) > 1:
                defaults['body_bg'] = hexes[-1]
            else:
                defaults['body_bg'] = hexes[0]
    accent_m = re.search(r'#(?:e5ad61|dcb869|c9a24b|f59e0b|eab308|d97706|fbbf24)[0-9a-fA-F]{0,6}', html, flags=re.I)
    if not accent_m:
        accent_m = re.search(
            r'(?:btn|cta|button|accent|livechat)[^{]*\{[^}]*(?:background|color)\s*:[^;#]*?(#[0-9a-fA-F]{3,8})',
            html,
            flags=re.I,
        )
    if accent_m:
        defaults['accent'] = accent_m.group(1) if accent_m.lastindex else accent_m.group(0)
        defaults['accent_dark'] = defaults['accent']
    return defaults


def extract_font_family(html: str) -> str:
    m = re.search(r'font-family\s*:\s*([^;}\n]+)', html, flags=re.I)
    if m:
        fam = m.group(1).strip().strip('"\'')
        if fam and 'system-ui' not in fam.lower():
            return fam.split(',')[0].strip().strip('"\'')
    return 'system-ui'


def gen_amp_promo(brand: str, kw_primary: str, dep: str) -> str:
    promo = (
        f'Portal {brand} dengan {kw_primary}, login cepat, RTP transparan, deposit mulai {dep}.'
    )
    words = promo.split()
    if len(words) > 20:
        promo = ' '.join(words[:20]) + '.'
    return promo


def gen_keyword_ticker(keywords: List[str], brand: str) -> str:
    kws = [k.strip() for k in keywords if k.strip()]
    if not kws:
        kws = [f'Situs {brand}', f'{brand} Login', f'Link Alternatif {brand}']
    items = kws + [f'RTP {brand}', f'Website {brand}', f'Daftar {brand}']
    seen: set = set()
    unique: List[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    text = ' · '.join(unique) + ' · '
    return (
        f'<div class="ticker-wrap"><div class="ticker">{text}{text}</div></div>'
    )


def build_organization_schema(
    brand: str,
    canon: str,
    logo: str,
    desc: str,
) -> str:
    return json.dumps({
        '@context': 'https://schema.org',
        '@type': 'Organization',
        'name': brand,
        'url': canon,
        'logo': {'@type': 'ImageObject', 'url': logo or canon},
        'description': desc[:160],
        'foundingDate': '2020',
        'contactPoint': {
            '@type': 'ContactPoint',
            'contactType': 'customer support',
            'availableLanguage': 'Indonesian',
            'areaServed': 'ID',
        },
        'sameAs': [canon] if canon and canon.startswith('http') else [],
    }, ensure_ascii=False)


def build_amp_webpage_schema(brand: str, canon: str, title: str, desc: str) -> str:
    return json.dumps({
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        'name': title,
        'description': desc[:160],
        'url': canon,
        'inLanguage': 'id-ID',
        'isPartOf': {'@type': 'WebSite', 'name': brand, 'url': canon},
    }, ensure_ascii=False)


def audit_link_policy(html: str, canon: str, cta: str) -> List[str]:
    warnings: List[str] = []
    if not cta or not canon:
        return warnings
    nav_patterns = (
        r'class="[^"]*(?:nav|breadcrumb|mega-cats|menu)[^"]*"',
        r'class="js-breadcrumb-category"',
    )
    for pat in nav_patterns:
        for m in re.finditer(rf'(<a\b[^>]*{pat}[^>]*href=")([^"]+)(")', html, flags=re.I | re.S):
            href = m.group(2)
            if href == cta or href.rstrip('/') == cta.rstrip('/'):
                warnings.append('Nav keyword memakai link referral — harus canonical')
    for m in re.finditer(
        r'<a\b[^>]*(?:login|daftar|register|popupBtn)[^>]*href="([^"]+)"',
        html,
        flags=re.I,
    ):
        href = m.group(1)
        if href == canon or href.rstrip('/') == canon.rstrip('/'):
            warnings.append('CTA login/daftar memakai canonical — harus link referral')
    return warnings


def audit_h1(html: str, brand: str) -> List[str]:
    warnings: List[str] = []
    h1s = re.findall(r'<h1\b[^>]*>([\s\S]*?)</h1>', html, flags=re.I)
    if len(h1s) != 1:
        warnings.append(f'H1 harus tepat 1 — ditemukan {len(h1s)}')
    elif brand and brand.upper() not in re.sub(r'<[^>]+>', '', h1s[0]).upper():
        warnings.append('H1 wajib mengandung nama brand')
    return warnings


def audit_images(html: str) -> List[str]:
    warnings: List[str] = []
    for m in re.finditer(r'<img\b[^>]*>', html, flags=re.I):
        tag = m.group(0)
        if not re.search(r'\balt="[^"]+"', tag, flags=re.I):
            warnings.append('Gambar tanpa alt deskriptif')
            break
        if not re.search(r'\bwidth="[0-9]+"', tag, flags=re.I):
            warnings.append('Gambar tanpa width')
            break
        if not re.search(r'\bheight="[0-9]+"', tag, flags=re.I):
            warnings.append('Gambar tanpa height')
            break
    return warnings


def audit_faq_schema_sync(html: str, faqs: List[Dict[str, str]]) -> List[str]:
    warnings: List[str] = []
    if not faqs:
        return warnings
    for item in faqs:
        q = item.get('q', '')
        if q and q not in html:
            warnings.append(f'FAQ HTML tidak sinkron schema: "{q[:40]}..."')
            break
    return warnings


def audit_ai_phrases(text: str) -> List[str]:
    low = text.lower()
    return [p for p in _AI_BANNED_PHRASES if p in low]


def build_compliance_checklist(
    html: str,
    cfg: Dict[str, Any],
    *,
    amp_html: str = '',
) -> Dict[str, bool]:
    brand = cfg.get('brand', '')
    title = cfg.get('title', '')
    desc = cfg.get('description', '')
    faqs = cfg.get('faq') or []
    reviews = cfg.get('reviews') or []
    article = cfg.get('article_html') or ''
    canon = cfg.get('canonical', '')
    cta = cfg.get('cta', '')
    para_count = len([p for p in article.split('\n') if p.strip()])

    h1_count = len(re.findall(r'<h1\b', html, flags=re.I))
    article_html = cfg.get('article_html') or ''
    article_anchors = len(re.findall(rf'href="{re.escape(canon)}"', article_html)) if canon and article_html else 0

    return {
        'unique_title': title_min_len() <= len(title) <= title_max_len() and not title_has_banned_word(title),
        'unique_description': desc_min_len() <= len(desc) <= desc_max_len(),
        'h1_single': h1_count == 1,
        'h1_has_brand': bool(brand) and brand.upper() in html.upper(),
        'canonical_set': bool(canon) and canon != '#LINKCANNO',
        'robots_index': 'max-snippet:-1' in html and 'noimageindex' in html,
        'hreflang_ok': 'hreflang="id-ID"' in html or "hreflang='id-ID'" in html,
        'og_type_ok': 'og:type' in html and 'website' in html,
        'faq_count_ok': len(faqs) >= faq_min_items(),
        'review_count_ok': len(reviews) >= int(load_requirements().get('reviews', {}).get('min_items', 6)),
        'article_paras_ok': para_count >= int(load_requirements().get('article', {}).get('min_paragraphs', 4)),
        'faq_schema_sync': not audit_faq_schema_sync(html, faqs),
        'link_policy_ok': not audit_link_policy(html, canon, cta),
        'article_anchor_ok': article_anchors <= int(load_requirements().get('article', {}).get('max_canonical_anchors', 1)),
        'no_html_comments': '<!--' not in html.replace('amp-boilerplate', ''),
        'user_assets': bool(cfg.get('logo') and cfg.get('banner')),
        'gsc_token_set': 'google-site-verification' in html,
        'amp_valid_structure': (
            not amp_html
            or (
                'FAQPage' not in amp_html
                and 'max-image-preview:large' in amp_html
                and 'WebPage' in amp_html
            )
        ),
    }


def client_url_allowlist(cfg: Dict[str, Any]) -> set:
    allowed: set = set()
    for key in ('canonical', 'amp_url', 'cta', 'logo', 'banner', 'favicon'):
        val = (cfg.get(key) or '').strip()
        if not val or val.startswith('#'):
            continue
        allowed.add(val)
        allowed.add(val.rstrip('/'))
        if val.endswith('/'):
            allowed.add(val.rstrip('/'))
    return allowed


def _url_is_allowed(url: str, allowed: set) -> bool:
    if not url or url.startswith('#') or url.startswith('data:') or url.startswith('mailto:'):
        return True
    u = url.strip()
    base = u.rstrip('/')
    if u in allowed or base in allowed:
        return True
    for item in allowed:
        ib = item.rstrip('/')
        if base == ib or u.startswith(ib + '/') or u.startswith(ib + '?'):
            return True
    return False


def sanitize_client_urls(html: str, cfg: Dict[str, Any]) -> Tuple[str, List[str]]:
    """Strip URLs from output that were not supplied in client config."""
    allowed = client_url_allowlist(cfg)
    warnings: List[str] = []
    if not allowed:
        return html, warnings

    banner = (cfg.get('banner') or '').strip()
    logo = (cfg.get('logo') or '').strip()
    favicon = (cfg.get('favicon') or '').strip()
    canon = (cfg.get('canonical') or '').strip()
    cta = (cfg.get('cta') or '').strip()

    def fallback_for(attr: str, tag: str) -> str:
        low = tag.lower()
        if 'icon' in low or 'favicon' in attr:
            return favicon or '#FAVICON'
        if 'logo' in low:
            return logo or banner or '#LOGO'
        return banner or logo or '#BANNER'

    for pat, attr in (
        (r'(<img\b[^>]*\bsrc=")([^"]+)(")', 'src'),
        (r'(<amp-img\b[^>]*\bsrc=")([^"]+)(")', 'src'),
        (r'(<link[^>]+href=")([^"]+)("[^>]*rel="[^"]*icon)', 'icon'),
        (r'(<meta property="og:image" content=")([^"]+)(")', 'og'),
        (r'(<meta name="twitter:image" content=")([^"]+)(")', 'tw'),
        (r'("url"\s*:\s*")(https?://[^"]+)(")', 'json-url'),
        (r'("logo"\s*:\s*\{\s*"@type"\s*:\s*"ImageObject"\s*,\s*"url"\s*:\s*")(https?://[^"]+)(")', 'json-logo'),
    ):
        def repl(m: re.Match) -> str:
            url = m.group(2)
            if _url_is_allowed(url, allowed):
                return m.group(0)
            new_url = fallback_for(attr, m.group(0))
            if attr == 'json-url' and canon:
                new_url = canon
            elif attr == 'json-logo' and logo:
                new_url = logo
            warnings.append(f'URL vendor diganti ({attr}): {url[:72]}')
            return f'{m.group(1)}{new_url}{m.group(3)}'

        html = re.sub(pat, repl, html, flags=re.I)

    for pat in (
        r'(<a\b[^>]*\bhref=")(https?://[^"]+)(")',
    ):
        def repl_href(m: re.Match) -> str:
            url = m.group(2)
            if _url_is_allowed(url, allowed):
                return m.group(0)
            tag = m.group(0).lower()
            if any(x in tag for x in ('login', 'daftar', 'register', 'popupbtn')):
                new_url = cta or '#LINKREF'
            else:
                new_url = canon or '#LINKCANNO'
            warnings.append(f'href vendor diganti: {url[:72]}')
            return f'{m.group(1)}{new_url}{m.group(3)}'

        html = re.sub(pat, repl_href, html, flags=re.I)

    return html, warnings
