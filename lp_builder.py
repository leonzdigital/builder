#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import glob
import hashlib
import json
import os
import random
import re
import shutil
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import Request, urlopen

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

AUTOLANDING_DIR = Path(__file__).resolve().parent
LP_ROOT = AUTOLANDING_DIR.parent
_LOCAL_BRAND_LINKS = AUTOLANDING_DIR / 'brand-links.json'
BRAND_LINKS_EXAMPLE = AUTOLANDING_DIR / 'brand-links.example.json'
BRAND_LINKS_PATH = _LOCAL_BRAND_LINKS if _LOCAL_BRAND_LINKS.is_file() else LP_ROOT / 'brand-links.json'
from lp_compliance import (
    amp_robots_content,
    audit_ai_phrases,
    audit_faq_schema_sync,
    audit_h1,
    audit_images,
    audit_link_policy,
    build_amp_webpage_schema,
    build_compliance_checklist,
    build_organization_schema,
    desc_max_len,
    desc_min_len,
    ensure_hreflang,
    ensure_og_type_website,
    enforce_single_h1,
    extract_css_palette,
    extract_font_family,
    faq_min_items,
    fetch_image_dimensions,
    gen_amp_promo,
    gen_breadcrumb_trail,
    gen_h1_text,
    gen_keyword_ticker,
    gen_mandatory_brand_faqs,
    limit_article_canonical_anchors,
    sanitize_client_urls,
    sanitize_title_neutral,
    strip_production_comments,
    title_has_banned_word,
    title_max_len,
    title_min_len,
    trim_desc as _compliance_trim_desc,
    trim_title as _compliance_trim_title,
)

from lp_build_mode import build_mode_label, is_developer_mode, ensure_build_mode_file
from lp_secrets import (
    ensure_serp_secrets_file,
    load_serp_secrets,
    migrate_serp_from_brand_links,
    serp_secrets_summary,
    set_serp_enrich_enabled,
)
from lp_content_enricher import enrichment_to_pools, get_serp_enrichment, normalize_serpapi_keys, serp_configured

AMP_TEMPLATE_DIR = AUTOLANDING_DIR / 'templates' / 'amp'
AMP_TEMPLATE_PATH = AMP_TEMPLATE_DIR / 'index.html'
AMP_TEMPLATE_DEFAULT = 'index.html'
CONFIGS_DIR = AUTOLANDING_DIR / 'configs'
LANDING_DIR = AUTOLANDING_DIR / 'landing'
PREVIEW_DIR = AUTOLANDING_DIR / 'preview'
OUTPUT_DIR = LANDING_DIR
for _init_dir in (CONFIGS_DIR, LANDING_DIR):
    _init_dir.mkdir(parents=True, exist_ok=True)

ROBOTS_CONTENT = 'index, follow, noimageindex, max-snippet:-1, max-video-preview:-1'

_CITIES = ['Jakarta', 'Surabaya', 'Bandung', 'Medan', 'Semarang', 'Makassar', 'Denpasar', 'Palembang']
_DEVICES = ['Android', 'iPhone', 'laptop', 'tablet']
_PAYMENTS = ['QRIS', 'transfer bank', 'OVO', 'GoPay', 'Dana']
_TIME_SPANS = ['dua minggu', 'sebulan', 'beberapa hari', 'tiga minggu terakhir']

_REVIEWER_NAMES = [
    'WAHYU', 'BAGAS', 'DENI', 'ARIF', 'IVAN', 'HENDRA', 'REZA', 'YOGI',
    'FARID', 'ANDI', 'BUDI', 'SONI', 'RIZKY', 'AGUS', 'FERRY', 'CLARA',
    'PUTRI', 'AMEL', 'DINA', 'RINA',
]

_REVIEW_OPEN = [
    'Baru coba {brand} minggu lalu — alur daftar singkat dan halaman terasa rapi.',
    'Login pertama ke {brand} langsung terasa beda: antarmuka ringan dari {device}.',
    'Saya dari {city} mulai pakai {brand} setelah teman rekomendasikan portal resminya.',
    'Awalnya skeptis, tapi {brand} terbukti praktis untuk cek akses sebelum sesi {kw_short}.',
]

_REVIEW_MIDDLE = [
    'Deposit {deposit} via {payment} masuk cepat; lanjut {kw_short} tanpa menunggu lama.',
    'Informasi {kw_short} dan mirror {brand} tersusun rapi sehingga tidak perlu cari link acak.',
    'CS {brand} merespons chat dalam beberapa menit — membantu saat lupa jalur login.',
    'Navigasi {brand} enak di {device}; tombol daftar tidak perlu scroll panjang.',
    'Panduan singkat di halaman {brand} membantu atur ritme awal sebelum naik taruhan.',
]

_REVIEW_CLOSE = [
    'Overall, {brand} layak di-bookmark untuk akses {kw_short} harian.',
    'Saya rekomendasikan {brand} untuk yang cari portal rapi dan transaksi cepat.',
    'Setelah {span}, {brand} jadi pilihan utama saya di {city}.',
    'Buat pemain baru, {brand} punya alur yang jelas tanpa ribet.',
]

_FAQ_BANK: Dict[str, List[Dict[str, str]]] = {
    'mahjong': [
        {'q': 'Apa keunggulan permainan Mahjong Ways di {brand}?',
         'a': '{brand} menghadirkan Mahjong Ways dari server PG Soft resmi dengan mekanisme Ways-to-Win luas, multiplier bertumpuk, dan free spin cascade. Member bisa mulai dari deposit {deposit} lewat bank, e-wallet, atau pulsa dengan proses otomatis.'},
        {'q': 'Bagaimana cara daftar dan login {brand} untuk Mahjong Ways?',
         'a': 'Buka halaman resmi {brand}, klik Daftar, isi nama dan nomor HP aktif, pilih metode pembayaran. Akun aktif dalam menit. Login bisa lewat domain utama atau mirror alternatif {brand} yang diperbarui rutin.'},
        {'q': 'Berapa minimal deposit Mahjong Ways di {brand}?',
         'a': 'Deposit minimal di {brand} mulai {deposit}. Semua nominal masuk saldo tanpa potongan tersembunyi sehingga member bisa langsung memulai sesi Mahjong Ways.'},
        {'q': 'Apakah {brand} menyediakan link alternatif untuk Mahjong Ways?',
         'a': 'Ya, {brand} memperbarui mirror alternatif secara berkala agar akses tetap lancar saat domain utama sibuk. Tidak perlu VPN — cukup bookmark halaman resmi {brand}.'},
        {'q': 'Tips bermain Mahjong Ways lebih stabil di {brand}?',
         'a': 'Mulai bet rendah 5–10 putaran untuk membaca ritme, manfaatkan info pola harian {brand}, tetapkan batas kerugian, dan gunakan fitur buy spin saat multiplier board terlihat aktif.'},
        {'q': 'Mengapa member memilih {brand} untuk Mahjong Ways?',
         'a': '{brand} unggul di server original, RTP transparan, bonus aktif, CS 24 jam, dan update informasi permainan harian — kombinasi yang sulit ditemukan di portal sejenis.'},
    ],
    'zeus': [
        {'q': 'Apa fitur utama Gates of Olympus di {brand}?',
         'a': 'Gates of Olympus di {brand} memakai server Pragmatic Play resmi dengan tumbling reels dan multiplikator Zeus. Deposit mulai {deposit}, buy spin tersedia, dan CS siap 24 jam.'},
        {'q': 'Berapa modal awal main Zeus di {brand}?',
         'a': 'Cukup {deposit} untuk memulai. Bet bisa disesuaikan modal sehingga sesi Gates of Olympus tetap terkontrol di {brand}.'},
        {'q': 'Bagaimana mendapat free spin Zeus di {brand}?',
         'a': 'Kumpulkan 4 scatter dalam satu putaran. Selama free spin, multiplikator Zeus bisa melonjak — {brand} juga menyediakan buy spin untuk langsung masuk bonus.'},
        {'q': 'Apakah {brand} aman untuk transaksi Zeus?',
         'a': '{brand} memakai enkripsi SSL, proses withdraw transparan, dan verifikasi akun sederhana. Ribuan member aktif membuktikan keandalan sistem keuangan portal ini.'},
        {'q': 'Bagaimana daftar {brand} untuk slot Zeus?',
         'a': 'Kunjungi link resmi, klik Daftar, isi data dasar — akun aktif dalam hitungan menit. Login kapan saja via website atau mirror {brand}.'},
        {'q': 'Kenapa {brand} populer untuk Gates of Olympus?',
         'a': 'Server original, info pola harian, bonus new member, cashback mingguan, dan dukungan CS responsif menjadikan {brand} favorit pecinta permainan Zeus.'},
    ],
    'slot': [
        {'q': 'Apa itu {brand} dan keunggulan utamanya?',
         'a': '{brand} adalah platform permainan digital terpercaya dengan ratusan judul dari PG Soft, Pragmatic Play, Habanero, dan provider resmi lain. Transaksi cepat, CS 24 jam, deposit mulai {deposit}.'},
        {'q': 'Berapa minimal deposit di {brand}?',
         'a': 'Deposit minimal {deposit} via bank, QRIS, e-wallet, atau pulsa. Tidak ada biaya tersembunyi — saldo langsung masuk setelah konfirmasi.'},
        {'q': 'Bagaimana cara daftar dan login {brand}?',
         'a': 'Tiga langkah: buka halaman resmi, klik Daftar, isi nama dan HP. Login via domain utama atau mirror alternatif {brand} yang aktif 24 jam.'},
        {'q': 'Permainan apa yang populer di {brand}?',
         'a': 'Mahjong Ways 2, Gates of Olympus, Starlight Princess, Sweet Bonanza, dan Wild West Gold konsisten diminati. {brand} rutin membagikan info RTP dan jadwal permainan harian.'},
        {'q': 'Apakah {brand} aman untuk member Indonesia?',
         'a': 'Ya — enkripsi SSL, privasi data terjaga, withdraw rata-rata 3–5 menit, tanpa potongan tersembunyi. Komunitas member aktif menjadi bukti kepercayaan.'},
        {'q': 'Mengapa memilih {brand} di {year}?',
         'a': '{brand} menawarkan server fair, deposit {deposit}, bonus rutin, mirror alternatif stabil, dan tim support profesional — paket lengkap untuk pengalaman permainan digital terarah.'},
    ],
}
_FAQ_BANK['starlight'] = _FAQ_BANK['slot']
_FAQ_BANK['bonanza'] = _FAQ_BANK['slot']

_BREADCRUMB_BANK: Dict[str, List[List[str]]] = {
    'mahjong': [
        ['{brand}', 'Mahjong Ways', 'Permainan Digital', 'Portal Resmi', 'Login {brand}'],
        ['{brand}', 'Platform Mahjong', 'Akses Member', 'Mirror Aktif', 'Daftar {brand}'],
    ],
    'zeus': [
        ['{brand}', 'Gates of Olympus', 'Arena Digital', 'Portal Masuk', 'Login {brand}'],
        ['{brand}', 'Permainan Zeus', 'Akses 24 Jam', 'Member Area', 'Daftar {brand}'],
    ],
    'slot': [
        ['{brand}', 'Platform Digital', 'Permainan Online', 'Portal Resmi', 'Login {brand}'],
        ['{brand}', 'Layanan Member', 'Akses Cepat', 'Mirror Alternatif', 'Daftar {brand}'],
    ],
}
_BREADCRUMB_BANK['starlight'] = _BREADCRUMB_BANK['slot']
_BREADCRUMB_BANK['bonanza'] = _BREADCRUMB_BANK['slot']

_TITLE_BANK: Dict[str, List[str]] = {
    'mahjong': [
        '{brand} | Platform Mahjong Ways & Akses Member 24 Jam',
        '{brand} | Portal Permainan Mahjong Digital Terpercaya',
        '{brand} | Layanan Mahjong Ways Fair Play & Bonus Aktif',
    ],
    'zeus': [
        '{brand} | Arena Gates of Olympus & Portal Member 24 Jam',
        '{brand} | Platform Permainan Zeus Digital Terpercaya',
        '{brand} | Portal Olympus Fair Play & Akses Stabil',
    ],
    'slot': [
        '{brand} | Platform Permainan Digital & Akses Member 24 Jam',
        '{brand} | Portal Layanan Berhadiah Optimal Terpercaya',
        '{brand} | Arena Gaming Digital Premium & Fair Play',
    ],
}
_TITLE_BANK['starlight'] = _TITLE_BANK['slot']
_TITLE_BANK['bonanza'] = _TITLE_BANK['slot']
_TITLE_DYNAMIC_PATTERNS: Tuple[str, ...] = (
    '{brand} | {kw_primary} Terpercaya & Akses 24 Jam',
    '{brand} | Portal {kw_primary} & Transaksi Cepat',
    '{brand} — {kw_primary} Resmi, Deposit {deposit}',
    '{kw_primary} di {brand} | Mirror Aktif & CS Sigap',
    '{brand} | {kw_primary} & {kw_secondary} | Member Stabil',
    '{brand} — Akses {kw_primary}, Deposit {deposit}',
    '{brand} | {kw_primary} Stabil & Withdraw {withdraw}',
    '{brand} — {kw_primary}, {kw_secondary} & CS {support}',
    '{kw_primary} | {brand} Resmi & Deposit {deposit}',
)

_DESC_DYNAMIC_PATTERNS: Tuple[str, ...] = (
    'Butuh {kw_primary}? {brand} kumpulkan akses resmi, deposit {deposit}, dan info {kw_list} dalam satu halaman.',
    '{brand} fokus {kw_primary} — transaksi mulai {deposit}, mirror rutin diperbarui, CS siap bantu login.',
    'Portal {brand} untuk {kw_primary}: provider resmi, withdraw {withdraw}, plus topik {kw_secondary} yang relevan.',
    'Akses {kw_primary} lewat {brand}: daftar singkat, deposit {deposit}, navigasi enak dibaca di HP.',
    'Lagi cari {kw_primary}? {brand} sediakan mirror aktif, deposit {deposit}, dan panduan singkat {kw_list}.',
    '{brand} — {kw_primary} dengan transaksi {withdraw}, metode {payments}, dukungan {support}.',
    'Cari {kw_primary}? {brand} siapkan akses resmi, {kw_secondary}, deposit {deposit}, withdraw {withdraw}.',
    'Di {brand}, {kw_primary} jadi fokus utama — metode {payments}, dukungan {support}, mirror aktif tiap hari.',
)

_DESC_OPENERS: Tuple[str, ...] = (
    'Butuh {primary}? ',
    'Lagi cari {primary}? ',
    'Untuk {primary}, ',
    '',
)

_AI_PHRASE_SWAPS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ('menghadirkan', ('menyediakan', 'menyiapkan', 'mengusung')),
    ('merangkum', ('mengumpulkan', 'menampung', 'mencantumkan')),
    ('dirancang sebagai', ('jadi', 'berperan sebagai', 'dipakai sebagai')),
    ('profesional', ('sigap', 'responsif', 'profesional')),
    ('terpercaya', ('andalan', 'stabil', 'terpercaya')),
)

_DESC_BANK: Dict[str, List[str]] = {
    'mahjong': [
        '{brand} portal Mahjong Ways dengan payout transparan, bonus aktif, deposit {deposit}, dan mirror alternatif diperbarui rutin untuk member Indonesia.',
        'Nikmati Mahjong Ways di {brand} — server PG Soft resmi, CS 24 jam, deposit {deposit}, dan pengalaman permainan digital yang fair.',
    ],
    'zeus': [
        '{brand} menghadirkan Gates of Olympus dengan server Pragmatic Play original, deposit {deposit}, bonus member, dan akses portal stabil 24 jam.',
        'Main Zeus di {brand} dengan RTP transparan, mirror alternatif aktif, deposit {deposit}, dan dukungan CS responsif.',
    ],
    'slot': [
        '{brand} platform permainan digital terpercaya — provider resmi, deposit {deposit}, bonus rutin, dan portal akses member 24 jam non-stop.',
        'Akses {brand} untuk pengalaman gaming digital fair play, transaksi cepat mulai {deposit}, dan layanan pelanggan profesional.',
    ],
}
_DESC_BANK['starlight'] = _DESC_BANK['slot']
_DESC_BANK['bonanza'] = _DESC_BANK['slot']

_ARTICLE_OPEN = [
    '<p>{brand} menghadirkan portal permainan digital untuk member Indonesia — domain resmi, mirror alternatif, dan tombol aksi tersusun rapi dalam satu halaman.</p>',
    '<p>{brand} dirancang sebagai pusat akses member dengan antarmuka responsif, informasi promo terkini, dan jalur login yang mudah ditemukan dari HP maupun laptop.</p>',
    '<p>Sebagai platform digital terpercaya, {brand} fokus pada pengalaman member: transaksi cepat, CS responsif, dan konten informasi yang selalu diperbarui.</p>',
]

_ARTICLE_MID = [
    '<p>Minimal deposit {deposit} membuat {brand} terjangkau untuk pemula. Metode pembayaran lengkap — bank, QRIS, e-wallet — diproses otomatis tanpa potongan tersembunyi.</p>',
    '<p>Keunggulan {brand} terletak pada stabilitas akses: mirror alternatif diperbarui rutin sehingga member tidak perlu mencari link dari sumber tidak resmi.</p>',
    '<p>Tim support {brand} aktif 24 jam lewat live chat. Pertanyaan seputar login, deposit, atau mirror alternatif dijawab cepat dan jelas.</p>',
]

_ARTICLE_CLOSE = [
    '<p>Halaman ini merangkum fitur utama {brand}, testimoni member, dan FAQ — bookmark sekali cukup untuk cek akses harian tanpa buka banyak tab.</p>',
    '<p>Dengan struktur informasi yang rapi, {brand} membantu member fokus pada permainan digital tanpa distraksi navigasi yang membingungkan.</p>',
    '<p>Informasi terbaru seputar promo, mirror aktif, dan panduan singkat permainan populer tersedia di <a href="{canon}">{brand}</a>.</p>',
]

GENERIC_SITE_NAME_SKIP = frozenset({
    'website', 'home', 'default', 'samsung', 'plaza', 'themeforest', 'envato',
    'woocommerce', 'wordpress', 'tokopress', 'marketplace', 'template', 'item details',
    'user verified', 'author', 'seller', 'organization',
})

MARKETPLACE_MARKERS = ('cok-faq', 'info-box-', 'testi-grid', 'item-header__author-details')

_TEMPLATE_JUNK_MARKERS = frozenset({
    'agen voucher', 'samsung galaxy', 'demo - lihat', 'topcer', 'topcer88', 'googletagmanager',
})

CONTENT_DIR = AUTOLANDING_DIR / 'content'
CONTENT_CACHE_DIR = CONTENT_DIR / 'cache'
CONTENT_LOCAL_PACK = CONTENT_DIR / 'pack.json'
CONTENT_MANIFEST = CONTENT_DIR / 'manifest.json'
CONTENT_CACHE_FILE = CONTENT_CACHE_DIR / 'pack.json'
CONTENT_META_FILE = CONTENT_CACHE_DIR / 'meta.json'
CONTENT_USED_PATH = CONTENT_DIR / 'content-used.json'
CONTENT_TTL_SEC = 86400
CONTENT_SIMILARITY_MAX = 0.68
FAQ_PICK_COUNT = 8
ARTICLE_MIN_PARAS = 4
REVIEW_PICK_COUNT = 6
FAQ_KW_SLOTS = 2
TITLE_MIN_LEN = 45
TITLE_MAX_LEN = 60
DESC_MIN_LEN = 130
DESC_MAX_LEN = 155
BRAND_MAX_PER_PARAGRAPH = 2
KEYWORD_MAX_OCCURRENCES = 12
BRAND_DENSITY_WARN = 0.018
FAQ_INTENT_MIN = 3

CATEGORY_HINT_TERMS: Dict[str, Tuple[str, ...]] = {
    'gacor': ('gacor', 'rtp', 'anti rungkad', 'pola', 'jam gacor', 'slot gacor', 'mudah menang'),
    'maxwin': ('maxwin', 'max win', 'jackpot', 'x500', 'x1000', 'scatter', 'super scatter'),
    'slot': ('slot', 'slot88', 'slot online', 'spin', 'pragmatic', 'habanero', 'pg soft', 'provider'),
    'mahjong': ('mahjong', 'ways', 'cascade', 'tile'),
    'zeus': ('zeus', 'olympus', 'gates', 'olympus'),
    'togel': ('togel', 'toto', '4d', 'pasaran', 'macau', 'hongkong'),
    'casino': ('casino', 'baccarat', 'roulette', 'live casino', 'sic bo', 'dealer'),
}

GSC_GATE_REQUIRED_KEYS: Tuple[str, ...] = (
    'unique_title',
    'unique_description',
    'h1_single',
    'canonical_set',
    'robots_index',
    'hreflang_ok',
    'og_type_ok',
    'faq_count_ok',
    'faq_schema_sync',
    'review_count_ok',
    'article_paras_ok',
    'link_policy_ok',
    'no_template_brand',
    'no_html_comments',
    'user_assets',
    'gsc_token_set',
)

GSC_GATE_LABELS: Dict[str, str] = {
    'unique_title': 'title 45–60 char, tanpa kata terlarang',
    'unique_description': 'description 130–155 char',
    'h1_single': 'H1 tepat satu + brand',
    'canonical_set': 'canonical URL final',
    'robots_index': 'robots meta lengkap',
    'hreflang_ok': 'hreflang id-ID + x-default',
    'og_type_ok': 'og:type website',
    'faq_count_ok': 'FAQ ≥ 8 item',
    'faq_schema_sync': 'FAQPage sinkron HTML',
    'review_count_ok': 'review ≥ 6 item',
    'article_paras_ok': 'artikel ≥ 4 paragraf',
    'link_policy_ok': 'nav→canon, CTA→ref',
    'no_template_brand': 'brand template tersisa',
    'no_html_comments': 'tanpa komentar HTML',
    'user_assets': 'logo & banner user',
    'gsc_token_set': 'token GSC terpasang',
    'amp_valid_structure': 'AMP valid (WebPage saja)',
}

BATCH_REPORT_PATH = AUTOLANDING_DIR / 'batch-report.json'


class GSCGateError(Exception):
    pass

_FAQ_INTENT_SIGNALS: Dict[str, Tuple[str, ...]] = {
    'login': ('daftar', 'login', 'akun', 'masuk', 'register'),
    'deposit': ('deposit', 'minimal', 'pembayaran', 'bayar', 'qris', 'e-wallet'),
    'rtp': ('rtp', 'fair', 'original', 'server', 'gacor', 'maxwin'),
    'mirror': ('mirror', 'alternatif', 'link alternatif', 'anti blokir', 'vpn'),
    'withdraw': ('withdraw', 'tarik', 'penarikan', 'cair'),
    'bonus': ('bonus', 'cashback', 'promo', 'new member'),
}

_INTENT_KW_MAP: Dict[str, Tuple[str, ...]] = {
    'login': ('login', 'daftar', 'akses member', 'link login'),
    'deposit': ('deposit', 'murah', 'rp', 'minimal', 'deposit murah'),
    'rtp': ('gacor', 'rtp', 'maxwin', 'slot gacor', 'cara menang'),
    'mirror': ('link alternatif', 'mirror', 'alternatif', 'anti blokir', 'link alternatif'),
    'withdraw': ('withdraw', 'tarik', 'cepat', 'wd cepat'),
    'bonus': ('bonus', 'promo', 'cashback', 'new member'),
}

_INTENT_FAQ_TEMPLATES: Dict[str, Tuple[str, str]] = {
    'login': (
        'Bagaimana login {brand} untuk {kw_primary}?',
        'Buka halaman resmi {brand}, pilih menu masuk, lalu gunakan akun terdaftar. Jika domain utama lambat, pakai mirror aktif — semua jalur diperbarui harian untuk akses {kw_primary}.',
    ),
    'deposit': (
        'Berapa deposit minimal {brand} untuk {kw_primary}?',
        'Mulai dari {deposit} via {payments}. Saldo masuk otomatis sehingga member bisa langsung fokus ke {kw_primary} tanpa menunggu jam kantor.',
    ),
    'rtp': (
        'Apakah info {kw_primary} dan RTP di {brand} transparan?',
        '{brand} menampilkan data provider resmi agar member tahu persentase teoretis sebelum bermain. Informasi {kw_list} disusun terpisah supaya mudah dibaca.',
    ),
    'mirror': (
        'Di mana cek link alternatif {brand} untuk {kw_primary}?',
        'Mirror {brand} diperbarui rutin di halaman resmi — cukup bookmark sekali. Member tidak perlu cari link acak saat akses {kw_primary} terblokir.',
    ),
    'withdraw': (
        'Berapa lama withdraw {brand} setelah sesi {kw_primary}?',
        'Rata-rata {withdraw} setelah verifikasi. Proses transparan tanpa potongan tersembunyi — status permintaan bisa dipantau langsung di akun {brand}.',
    ),
    'bonus': (
        'Bonus apa yang bisa dipakai untuk {kw_primary} di {brand}?',
        'New member, cashback mingguan, dan promo deposit berkala aktif di {brand}. Detail selalu diperbarui agar member {kw_primary} tidak ketinggalan penawaran.',
    ),
}

_banks_cache: Optional[Dict[str, Any]] = None
_banks_source = 'embedded'
_serp_pool_cache: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}


def _embedded_banks() -> Dict[str, Any]:
    return {
        'faq': dict(_FAQ_BANK),
        'titles': dict(_TITLE_BANK),
        'descriptions': dict(_DESC_BANK),
        'breadcrumbs': dict(_BREADCRUMB_BANK),
        'reviews': {'open': list(_REVIEW_OPEN), 'middle': list(_REVIEW_MIDDLE), 'close': list(_REVIEW_CLOSE)},
        'articles': {'open': list(_ARTICLE_OPEN), 'mid': list(_ARTICLE_MID), 'close': list(_ARTICLE_CLOSE)},
        'meta': {
            'cities': list(_CITIES),
            'devices': list(_DEVICES),
            'payments': list(_PAYMENTS),
            'time_spans': list(_TIME_SPANS),
            'reviewer_names': list(_REVIEWER_NAMES),
        },
    }


def _normalize_banks(raw: Dict[str, Any]) -> Dict[str, Any]:
    banks = {
        'version': raw.get('version', ''),
        'faq': dict(raw.get('faq') or {}),
        'titles': dict(raw.get('titles') or {}),
        'descriptions': dict(raw.get('descriptions') or {}),
        'breadcrumbs': dict(raw.get('breadcrumbs') or {}),
        'reviews': dict(raw.get('reviews') or {}),
        'articles': dict(raw.get('articles') or {}),
        'meta': dict(raw.get('meta') or {}),
        'faq_intents': dict(raw.get('faq_intents') or {}),
    }
    for cat in ('starlight', 'bonanza', 'togel', 'casino', 'gacor', 'maxwin'):
        for key in ('faq', 'titles', 'descriptions', 'breadcrumbs'):
            if 'slot' in banks[key] and cat not in banks[key]:
                banks[key][cat] = banks[key]['slot']
    emb = _embedded_banks()
    for section in banks:
        if section == 'meta':
            for mk, mv in emb['meta'].items():
                banks['meta'].setdefault(mk, mv)
        elif section == 'faq_intents':
            if not banks[section]:
                banks[section] = {}
        elif not banks[section]:
            banks[section] = emb[section]
    return banks


def _read_json_file(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def _cache_is_fresh() -> bool:
    meta = _read_json_file(CONTENT_META_FILE)
    if not meta or not CONTENT_CACHE_FILE.is_file():
        return False
    try:
        fetched = float(meta.get('fetched_at', 0))
    except (TypeError, ValueError):
        return False
    ttl = int(meta.get('ttl_sec', CONTENT_TTL_SEC))
    return (time.time() - fetched) < ttl


def _write_content_cache(pack: Dict[str, Any], source: str, ttl_sec: int) -> None:
    CONTENT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CONTENT_CACHE_FILE.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding='utf-8')
    CONTENT_META_FILE.write_text(json.dumps({
        'fetched_at': time.time(),
        'source': source,
        'version': pack.get('version', ''),
        'ttl_sec': ttl_sec,
    }, ensure_ascii=False, indent=2), encoding='utf-8')


def load_content_banks(force: bool = False) -> Tuple[Dict[str, Any], str]:
    global _banks_cache, _banks_source
    if _banks_cache is not None and not force:
        return _banks_cache, _banks_source

    manifest = _read_json_file(CONTENT_MANIFEST) or {}
    ttl_sec = int(manifest.get('cache_ttl_hours', 24)) * 3600
    remote_url = (manifest.get('remote_url') or '').strip()

    if not remote_url:
        local_pack = _read_json_file(CONTENT_LOCAL_PACK)
        if local_pack and local_pack.get('faq'):
            _banks_cache = _normalize_banks(local_pack)
            _banks_source = 'local'
            return _banks_cache, _banks_source
        _banks_cache = _normalize_banks(_embedded_banks())
        _banks_source = 'embedded'
        return _banks_cache, _banks_source

    if not force and _cache_is_fresh():
        cached = _read_json_file(CONTENT_CACHE_FILE)
        if cached:
            _banks_cache = _normalize_banks(cached)
            meta = _read_json_file(CONTENT_META_FILE) or {}
            _banks_source = str(meta.get('source', 'cache'))
            return _banks_cache, _banks_source

    if remote_url:
        raw_text = fetch_url(remote_url)
        if raw_text:
            try:
                remote_pack = json.loads(raw_text)
                if isinstance(remote_pack, dict) and remote_pack.get('faq'):
                    _write_content_cache(remote_pack, 'remote', ttl_sec)
                    _banks_cache = _normalize_banks(remote_pack)
                    _banks_source = 'remote'
                    return _banks_cache, _banks_source
            except json.JSONDecodeError:
                pass

    local_pack = _read_json_file(CONTENT_LOCAL_PACK)
    if local_pack and local_pack.get('faq'):
        _banks_cache = _normalize_banks(local_pack)
        _banks_source = 'local'
        return _banks_cache, _banks_source

    if CONTENT_CACHE_FILE.is_file():
        cached = _read_json_file(CONTENT_CACHE_FILE)
        if cached:
            _banks_cache = _normalize_banks(cached)
            _banks_source = 'cache-stale'
            return _banks_cache, _banks_source

    _banks_cache = _normalize_banks(_embedded_banks())
    _banks_source = 'embedded'
    return _banks_cache, _banks_source


def get_banks() -> Dict[str, Any]:
    banks, _ = load_content_banks()
    return banks


def load_content_manifest() -> Dict[str, Any]:
    data = _read_json_file(CONTENT_MANIFEST)
    if not data:
        return {'version': '2.0.0', 'remote_url': '', 'cache_ttl_hours': 24}
    data.setdefault('version', '2.0.0')
    data.setdefault('remote_url', '')
    data.setdefault('cache_ttl_hours', 24)
    return data


def save_content_manifest(manifest: Dict[str, Any]) -> None:
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    out = {
        'version': str(manifest.get('version') or '2.0.0'),
        'remote_url': (manifest.get('remote_url') or '').strip(),
        'cache_ttl_hours': max(1, int(manifest.get('cache_ttl_hours') or 24)),
    }
    CONTENT_MANIFEST.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def content_pack_summary() -> Dict[str, Any]:
    banks, source = load_content_banks()
    manifest = load_content_manifest()
    faq_total = sum(len(v) for v in (banks.get('faq') or {}).values() if isinstance(v, list))
    return {
        'pack_version': str(banks.get('version') or '—'),
        'source': source,
        'faq_total': faq_total,
        'remote_url': manifest.get('remote_url') or '',
        'cache_ttl_hours': int(manifest.get('cache_ttl_hours') or 24),
    }


def _stable_seed(brand: str, keyword: str, slot: int) -> random.Random:
    h = hashlib.md5(f'{brand}|{keyword}|{slot}|stable'.encode()).hexdigest()
    return random.Random(int(h, 16))


def _vary_seed(brand: str, keyword: str, slot: int) -> random.Random:
    ts = str(int(time.time() * 1000))
    h = hashlib.md5(f'{brand}|{keyword}|{slot}|{ts}'.encode()).hexdigest()
    return random.Random(int(h, 16))


def _regen_seed(brand: str, keyword: str, slot: int, nonce: int = 0) -> random.Random:
    ts = str(int(time.time() * 1000))
    h = hashlib.md5(f'{brand}|{keyword}|{slot}|r{nonce}|{ts}'.encode()).hexdigest()
    return random.Random(int(h, 16))


def _seed(brand: str, keyword: str, slot: int) -> random.Random:
    return _stable_seed(brand, keyword, slot)


def _normalize_compare_text(text: str, brand: str = '') -> str:
    t = re.sub(r'\s+', ' ', text.lower()).strip()
    if brand:
        t = re.sub(re.escape(brand.lower()), '', t)
    t = re.sub(r'rp[\d.,]+', 'dep', t)
    t = re.sub(r'\d{4}', 'yr', t)
    return t


def _text_fingerprint(text: str, brand: str = '') -> str:
    return hashlib.md5(_normalize_compare_text(text, brand).encode()).hexdigest()


def _ngram_set(text: str, n: int = 4) -> set:
    words = _normalize_compare_text(text).split()
    if len(words) < n:
        return {' '.join(words)} if words else set()
    return {' '.join(words[i:i + n]) for i in range(len(words) - n + 1)}


def _similarity_ratio(a: str, b: str) -> float:
    sa, sb = _ngram_set(a), _ngram_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _too_similar_text(text: str, blocked: set, brand: str = '', threshold: float = CONTENT_SIMILARITY_MAX) -> bool:
    fp = _text_fingerprint(text, brand)
    if fp in blocked:
        return True
    norm = _normalize_compare_text(text, brand)
    for other in blocked:
        if isinstance(other, str) and len(other) > 24 and other in norm:
            return True
    return False


def _too_similar_pair(a: str, b: str, brand: str = '', threshold: float = CONTENT_SIMILARITY_MAX) -> bool:
    return _similarity_ratio(a, b) >= threshold


def load_content_used() -> Dict[str, Any]:
    data = _read_json_file(CONTENT_USED_PATH)
    if not data:
        return {'brands': {}, 'version': 1}
    data.setdefault('brands', {})
    return data


def save_content_used(data: Dict[str, Any]) -> None:
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    CONTENT_USED_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def get_content_reservations(exclude_brand: str = '') -> Dict[str, set]:
    used = load_content_used()
    ex = _slugify(exclude_brand) if exclude_brand else ''
    out: Dict[str, set] = {
        'faq_ids': set(),
        'title_ids': set(),
        'desc_ids': set(),
        'review_combos': set(),
        'review_fps': set(),
        'article_combos': set(),
        'text_fps': set(),
    }
    for slug, entry in used.get('brands', {}).items():
        if slug == ex:
            continue
        out['faq_ids'].update(entry.get('faq_ids', []))
        tid = entry.get('title_id')
        if tid:
            out['title_ids'].add(tid)
        did = entry.get('desc_id')
        if did:
            out['desc_ids'].add(did)
        out['review_combos'].update(entry.get('review_combos', []))
        out['review_fps'].update(entry.get('review_fps', []))
        ac = entry.get('article_combo')
        if ac:
            out['article_combos'].add(ac)
        out['text_fps'].update(entry.get('text_fps', []))
    return out


def record_brand_content(brand: str, meta: Dict[str, Any]) -> None:
    if not brand or not meta:
        return
    used = load_content_used()
    key = _slugify(brand)
    payload = {k: v for k, v in meta.items() if v}
    payload['brand'] = brand
    payload['updated_at'] = datetime.now().isoformat(timespec='seconds')
    used['brands'][key] = payload
    save_content_used(used)


def _pool_with_ids(items: Any, prefix: str, cat: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not items:
        return out
    for i, item in enumerate(items):
        if isinstance(item, dict) and 'q' in item:
            cid = item.get('id') or f'{prefix}-{cat}-{i}'
            out.append({**item, 'id': cid})
        elif isinstance(item, dict) and 'text' in item:
            cid = item.get('id') or f'{prefix}-{cat}-{i}'
            out.append({**item, 'id': cid})
        else:
            out.append({'id': f'{prefix}-{cat}-{i}', 'text': str(item)})
    return out


def build_fill_context(cfg: Dict[str, Any]) -> Dict[str, str]:
    brand = cfg.get('brand', '').strip()
    si = cfg.get('short_info') if isinstance(cfg.get('short_info'), dict) else {}
    entry = find_brand_entry(brand) or {}
    kw = cfg.get('keyword_focus') or f'{brand.lower()} platform permainan digital'
    parsed = parse_keyword_focus(kw)
    rng = _stable_seed(brand, kw, 99)
    meta = get_banks().get('meta', {})
    usp_pool = meta.get('usp_lines') or [
        'transaksi cepat tanpa potongan tersembunyi',
        'mirror alternatif diperbarui setiap hari',
        'CS responsif via live chat 24 jam',
        'server fair play dari provider resmi',
        'proses withdraw rata-rata di bawah 10 menit',
    ]
    withdraw_opts = meta.get('withdraw_times') or ['3–5 menit', '5–10 menit', 'kurang dari 10 menit']
    return {
        'usp': str(entry.get('usp') or rng.choice(usp_pool)),
        'provider': si.get('provider', 'PG Soft, Pragmatic Play, Habanero'),
        'withdraw': str(entry.get('withdraw') or rng.choice(withdraw_opts)),
        'payments': si.get('metode_bayar', 'Bank, QRIS, e-wallet'),
        'support': si.get('jam_operasional', '24 jam'),
        'kw_primary': parsed['primary'],
        'kw_list': parsed['kw_list'],
    }


def _pick_unique_items(
    pool: List[Dict[str, Any]],
    brand: str,
    keyword: str,
    slot: int,
    count: int,
    reserved_ids: set,
    blocked_fps: set,
    text_fn: Any,
    *,
    vary: bool = False,
    id_key: str = 'id',
    regen_nonce: int = 0,
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    if vary:
        rng = _regen_seed(brand, keyword, slot, regen_nonce)
    else:
        rng = _stable_seed(brand, keyword, slot)
    fresh = [x for x in pool if x.get(id_key) not in reserved_ids]
    candidates = fresh if len(fresh) >= count else list(pool)
    rng.shuffle(candidates)
    picked: List[Dict[str, Any]] = []
    picked_ids: List[str] = []
    picked_fps: List[str] = []
    local_texts: List[str] = []
    for item in candidates:
        if len(picked) >= count:
            break
        rendered = text_fn(item)
        fp = _text_fingerprint(rendered, brand)
        if fp in blocked_fps or fp in picked_fps:
            continue
        if any(_too_similar_pair(rendered, t, brand) for t in local_texts):
            continue
        picked.append(item)
        picked_ids.append(str(item.get(id_key, '')))
        picked_fps.append(fp)
        local_texts.append(rendered)
    if len(picked) < count:
        usage = _content_id_usage()
        fallback = sorted(
            [x for x in pool if x not in picked and x.get(id_key) not in reserved_ids],
            key=lambda x: usage.get(str(x.get(id_key, '')), 0),
        )
        for item in fallback:
            if len(picked) >= count:
                break
            rendered = text_fn(item)
            fp = _text_fingerprint(rendered, brand)
            if fp in picked_fps:
                continue
            if any(_too_similar_pair(rendered, t, brand) for t in local_texts):
                continue
            picked.append(item)
            picked_ids.append(str(item.get(id_key, '')))
            picked_fps.append(fp)
            local_texts.append(rendered)
    return picked, picked_ids, picked_fps


def _content_id_usage() -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in load_content_used().get('brands', {}).values():
        for key in ('faq_ids',):
            for cid in entry.get(key, []):
                counts[str(cid)] = counts.get(str(cid), 0) + 1
        for cid in (entry.get('title_id'), entry.get('desc_id')):
            if cid:
                counts[str(cid)] = counts.get(str(cid), 0) + 1
    return counts


def _slugify(brand: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', brand.strip().lower()).strip('-')
    return slug or 'brand'


def default_output_folder(slug: str) -> str:
    return f'landing/{slug}'


def resolve_output_base(output_folder: str = '', slug: str = 'brand') -> Path:
    raw = (output_folder or '').strip() or default_output_folder(slug)
    p = Path(raw)
    if p.is_absolute():
        return p
    return (AUTOLANDING_DIR / raw.replace('/', os.sep)).resolve()


def _json_esc(text: str) -> str:
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').strip()


def _trim_title(title: str, max_len: int = 0) -> str:
    return _compliance_trim_title(title, max_len or title_max_len())


def _trim_desc(desc: str, max_len: int = 0) -> str:
    trimmed = _compliance_trim_desc(desc, max_len or desc_max_len())
    while len(trimmed) < desc_min_len() and len(trimmed) < (max_len or desc_max_len()):
        trimmed = _compliance_trim_desc(trimmed + ' Akses member stabil, CS responsif, transaksi aman.', max_len or desc_max_len())
        if len(trimmed) >= desc_min_len():
            break
    return trimmed


def ensure_brand_links_file() -> None:
    if _LOCAL_BRAND_LINKS.is_file():
        return
    if not BRAND_LINKS_EXAMPLE.is_file():
        return
    try:
        shutil.copy2(BRAND_LINKS_EXAMPLE, _LOCAL_BRAND_LINKS)
    except OSError:
        pass


def load_brand_links() -> Dict[str, Any]:
    ensure_brand_links_file()
    if not BRAND_LINKS_PATH.is_file():
        return {'brands': {}, 'global': {}}
    try:
        return json.loads(BRAND_LINKS_PATH.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return {'brands': {}, 'global': {}}


def upsert_brand_links(cfg: Dict[str, Any]) -> None:
    brand = (cfg.get('brand') or '').strip().upper()
    if not brand:
        return
    slug = cfg.get('slug') or _slugify(brand)
    path = BRAND_LINKS_WRITE_PATH
    if path.is_file():
        data = load_brand_links()
    else:
        data = {'brands': {}, 'global': get_global_config()}
    if not isinstance(data.get('brands'), dict):
        data['brands'] = {}
    data['brands'][slug] = {
        'brand': brand,
        'linkref': cfg.get('cta', ''),
        'linkcanno': cfg.get('canonical', '#LINKCANNO'),
        'linkamp': cfg.get('amp_url', '#LINKAMP'),
        'logo': cfg.get('logo', ''),
        'banner': cfg.get('banner', ''),
        'keyword_focus': cfg.get('keyword_focus', ''),
        'minimal_deposit': (cfg.get('short_info') or {}).get('minimal_deposit', 'Rp10.000'),
        'output_folder': cfg.get('output_folder', default_output_folder(slug)),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def get_global_config() -> Dict[str, Any]:
    data = load_brand_links()
    g = data.get('global', {})
    serp = load_serp_secrets()
    return {
        'gsc_token': (g.get('gsc_token') or '').strip(),
        'cf_token': (g.get('cf_token') or '').strip(),
        'favicon': (g.get('favicon') or '').strip(),
        'serpapi_keys': serp.get('serpapi_keys') or [],
        'serpapi_key': serp.get('serpapi_key') or '',
        'google_cse_key': serp.get('google_cse_key') or '',
        'google_cse_cx': serp.get('google_cse_cx') or '',
        'serp_enrich_enabled': bool(serp.get('serp_enrich_enabled', True)),
    }


def clear_serp_pool_cache() -> None:
    global _serp_pool_cache
    _serp_pool_cache = {}


def _get_serp_pools(keyword: str, cat: str) -> Dict[str, List[Dict[str, Any]]]:
    global _serp_pool_cache
    g = get_global_config()
    if not g.get('serp_enrich_enabled', True) or not serp_configured(g):
        return {'faq': [], 'titles': [], 'descriptions': []}
    cache_key = f'{cat}|{keyword.strip().lower()}'
    if cache_key in _serp_pool_cache:
        return _serp_pool_cache[cache_key]
    enrich = get_serp_enrichment(
        keyword,
        serpapi_keys=g.get('serpapi_keys') or [],
        google_cse_key=g.get('google_cse_key', ''),
        google_cse_cx=g.get('google_cse_cx', ''),
    )
    pools = enrichment_to_pools(enrich, cat)
    _serp_pool_cache[cache_key] = pools
    return pools


def find_brand_entry(brand: str) -> Optional[Dict[str, str]]:
    data = load_brand_links()
    key = brand.strip().lower().replace(' ', '').replace('-', '')
    for slug, entry in data.get('brands', {}).items():
        norm = slug.lower().replace(' ', '').replace('-', '')
        if norm == key or slug.lower() == brand.strip().lower():
            return dict(entry)
    return None


def merge_brand_defaults(cfg: Dict[str, Any]) -> Dict[str, Any]:
    brand = cfg.get('brand', '').strip()
    entry = find_brand_entry(brand)
    global_cfg = get_global_config()
    out = dict(cfg)
    if entry:
        out.setdefault('cta', entry.get('linkref', ''))
        out.setdefault('canonical', entry.get('linkcanno', '#LINKCANNO'))
        out.setdefault('amp_url', entry.get('linkamp', '#LINKAMP'))
        if entry.get('logo'):
            out.setdefault('logo', entry['logo'])
        if entry.get('banner'):
            out.setdefault('banner', entry['banner'])
    if global_cfg.get('favicon'):
        out.setdefault('favicon', global_cfg['favicon'])
    out.setdefault('bottom_nav_icon', out.get('favicon') or '')
    if global_cfg.get('gsc_token'):
        out.setdefault('gsc_token', global_cfg['gsc_token'])
    if global_cfg.get('cf_token'):
        out.setdefault('cf_token', global_cfg['cf_token'])
    out.setdefault('slug', _slugify(brand))
    out.setdefault('output_folder', default_output_folder(out['slug']))
    return out


def _detect_cat(keyword: str) -> str:
    parts = parse_keyword_focus(keyword)['all']
    for part in parts:
        kl = part.lower()
        if 'mahjong' in kl:
            return 'mahjong'
        if any(x in kl for x in ('zeus', 'olympus', 'gates')):
            return 'zeus'
        if any(x in kl for x in ('starlight', 'princess')):
            return 'starlight'
        if any(x in kl for x in ('bonanza', 'sweet')):
            return 'bonanza'
        if any(x in kl for x in ('togel', 'toto', 'macau', 'hongkong', 'pasaran', '4d')):
            return 'togel'
        if any(x in kl for x in ('casino', 'baccarat', 'roulette', 'live casino', 'sic bo')):
            return 'casino'
        if any(x in kl for x in CATEGORY_HINT_TERMS['maxwin']):
            return 'maxwin'
        if any(x in kl for x in CATEGORY_HINT_TERMS['gacor']):
            return 'gacor'
        if any(x in kl for x in ('slot88', 'slot online', 'slot gacor', 'slot maxwin')):
            if 'maxwin' in kl or 'max win' in kl:
                return 'maxwin'
            if 'gacor' in kl:
                return 'gacor'
            return 'slot'
        if 'slot' in kl:
            return 'slot'
    return 'slot'


def _category_hint_score(text: str, cat: str) -> int:
    if not cat or not text:
        return 0
    tl = text.lower()
    terms = CATEGORY_HINT_TERMS.get(cat, ())
    return sum(10 for term in terms if term in tl)


def parse_keyword_focus(raw: str) -> Dict[str, Any]:
    parts = [x.strip() for x in (raw or '').split(',') if x.strip()]
    if not parts:
        parts = ['platform permainan digital']
    primary = parts[0]
    secondary = parts[1:]
    if len(parts) == 1:
        kw_list = primary
    elif len(parts) == 2:
        kw_list = f'{parts[0]} dan {parts[1]}'
    else:
        kw_list = ', '.join(parts[:-1]) + f', dan {parts[-1]}'
    return {
        'raw': ', '.join(parts),
        'all': parts,
        'primary': primary,
        'secondary': secondary,
        'kw_list': kw_list,
        'primary_title': primary.title(),
    }


def _keyword_template_score(text: str, parsed: Dict[str, Any]) -> int:
    score = 0
    if any(p in text for p in ('{keyword}', '{kw_short}', '{kw_primary}', '{kw_list}', '{kw_secondary}')):
        score += 12
    tl = text.lower()
    for kw in parsed['all']:
        kl = kw.lower()
        if kl in tl:
            score += 6
        for word in kl.split():
            if len(word) > 3 and word in tl:
                score += 2
    return score


def _sort_pool_by_keywords(
    pool: List[Dict[str, Any]],
    parsed: Dict[str, Any],
    text_keys: Tuple[str, ...] = ('text',),
    cat: str = '',
) -> List[Dict[str, Any]]:
    def item_score(item: Dict[str, Any]) -> int:
        total = 0
        for key in text_keys:
            val = item.get(key, '')
            if isinstance(val, str):
                total += _keyword_template_score(val, parsed)
                total += _category_hint_score(val, cat)
        return total

    return sorted(pool, key=item_score, reverse=True)


def _text_has_user_keyword(text: str, parsed: Dict[str, Any]) -> bool:
    tl = text.lower()
    return any(k.lower() in tl for k in parsed['all'])


def _weave_keyword_clause(
    text: str,
    brand: str,
    parsed: Dict[str, Any],
    dep: str,
    slot: int,
) -> str:
    if _text_has_user_keyword(text, parsed):
        return text
    rng = _stable_seed(brand, parsed['raw'], slot)
    primary = parsed['primary']
    clauses = [
        f' Topik {primary} menjadi salah satu fokus informasi di {brand}.',
        f' Layanan {brand} dirancang untuk kebutuhan pencarian seputar {primary}.',
        f' Member yang fokus pada {primary} bisa memulai dari deposit {dep}.',
    ]
    if parsed['secondary']:
        sec = parsed['secondary'][0]
        clauses.append(f' Aspek {sec} juga tersedia sebagai pelengkap {primary} di {brand}.')
    suffix = rng.choice(clauses)
    base = text.rstrip()
    if base.endswith('</p>'):
        return base[:-4] + suffix + '</p>'
    if base.endswith('.'):
        return base + suffix
    return base + '.' + suffix


def _ensure_faq_keywords(
    q: str,
    a: str,
    brand: str,
    parsed: Dict[str, Any],
    dep: str,
    slot: int,
) -> Tuple[str, str]:
    if _text_has_user_keyword(q + ' ' + a, parsed):
        return q, a
    primary = parsed['primary']
    if primary.lower() not in q.lower():
        q_clean = q.rstrip('?').strip()
        q = f'{q_clean} seputar {primary}?' if len(q_clean) <= 72 else f'Apakah {brand} mendukung {primary}?'
    a = _weave_keyword_clause(a, brand, parsed, dep, slot + 100)
    return q, a


def _ensure_title_keyword(title: str, parsed: Dict[str, Any]) -> str:
    if _text_has_user_keyword(title, parsed):
        return _trim_title(title)
    primary = parsed['primary_title']
    parts = [p.strip() for p in title.split('|') if p.strip()]
    if len(parts) >= 2:
        candidate = _trim_title(f'{parts[0]} | {primary} | {" | ".join(parts[1:])}')
        if _text_has_user_keyword(candidate, parsed):
            return candidate
    for fmt in (f'{title} | {primary}', f'{primary} — {title}'):
        candidate = _trim_title(fmt)
        if _text_has_user_keyword(candidate, parsed):
            return candidate
    if parts:
        return _trim_title(f'{parts[0]} | {primary}')
    return _trim_title(title)


def _ensure_description_keyword(desc: str, brand: str, parsed: Dict[str, Any], dep: str) -> str:
    if _text_has_user_keyword(desc, parsed):
        return _trim_desc(desc)
    woven = _weave_keyword_clause(desc, brand, parsed, dep, 7)
    return _trim_desc(woven)


def _gen_keyword_faq_items(
    brand: str,
    parsed: Dict[str, Any],
    dep: str,
    canon: str,
    ctx: Optional[Dict[str, str]],
    count: int = 2,
) -> List[Dict[str, str]]:
    primary = parsed['primary']
    kw_list = parsed['kw_list']
    templates: List[Tuple[str, str]] = [
        (
            f'Apa keunggulan {{brand}} untuk pencarian {primary}?',
            f'{{brand}} menyusun informasi {primary} dalam satu halaman — termasuk akses mirror, deposit mulai {{deposit}}, dan panduan untuk {{keyword}}.',
        ),
        (
            f'Bagaimana memulai di {{brand}} jika fokus saya {primary}?',
            f'Daftar di {{brand}}, deposit minimal {{deposit}}, lalu manfaatkan navigasi yang mengarah ke konten seputar {kw_list}.',
        ),
    ]
    if parsed['secondary']:
        sec = parsed['secondary'][0]
        templates.append((
            f'Apakah {{brand}} juga membahas {sec}?',
            f'Ya — selain {primary}, portal {{brand}} merangkum {sec} dan topik terkait {{keyword}}.',
        ))
    rng = _stable_seed(brand, parsed['raw'], 50)
    rng.shuffle(templates)
    items: List[Dict[str, str]] = []
    for i, (q_t, a_t) in enumerate(templates[:count]):
        items.append({
            'q': _fill(q_t, brand, parsed['raw'], dep, canon, ctx),
            'a': _fill(a_t, brand, parsed['raw'], dep, canon, ctx),
        })
    return items


def _faq_item_intent(q: str, a: str) -> str:
    text = f'{q} {a}'.lower()
    scores: Dict[str, int] = {}
    for intent, signals in _FAQ_INTENT_SIGNALS.items():
        scores[intent] = sum(1 for s in signals if s in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'general'


def _detect_faq_intents_from_kw(keyword: str) -> List[str]:
    parsed = parse_keyword_focus(keyword)
    intents: List[str] = []
    blob = keyword.lower()
    for part in parsed['all']:
        blob += ' ' + part.lower()
    for intent, signals in _INTENT_KW_MAP.items():
        if any(s in blob for s in signals):
            intents.append(intent)
    if not intents:
        intents = ['deposit', 'login', 'mirror']
    if 'general' not in intents:
        intents.append('general')
    return list(dict.fromkeys(intents))[:FAQ_INTENT_MIN + 1]


def _build_faq_pool(cat: str, keyword: str) -> List[Dict[str, Any]]:
    banks = get_banks()
    parsed = parse_keyword_focus(keyword)
    pool = list(_pool_with_ids(banks['faq'].get(cat, banks['faq']['slot']), 'faq', cat))
    intent_bank = banks.get('faq_intents') or {}
    for intent_name, items in intent_bank.items():
        if isinstance(items, list):
            tagged = _pool_with_ids(items, f'faq-{intent_name}', intent_name)
            for item in tagged:
                item['_intent'] = intent_name
            pool.extend(tagged)
    for intent_name, tpl in _INTENT_FAQ_TEMPLATES.items():
        pool.append({
            'id': f'faq-tpl-{intent_name}',
            'q': tpl[0],
            'a': tpl[1],
            '_intent': intent_name,
        })
    serp = _get_serp_pools(keyword, cat)
    if serp.get('faq'):
        pool.extend(serp['faq'])
    return _sort_pool_by_keywords(pool, parsed, ('q', 'a'), cat)


def _gen_intent_faq_item(
    intent: str,
    brand: str,
    keyword: str,
    dep: str,
    canon: str,
    ctx: Optional[Dict[str, str]],
) -> Optional[Dict[str, str]]:
    tpl = _INTENT_FAQ_TEMPLATES.get(intent)
    if not tpl:
        return None
    q = _fill(tpl[0], brand, keyword, dep, canon, ctx)
    a = _fill(tpl[1], brand, keyword, dep, canon, ctx)
    parsed = parse_keyword_focus(keyword)
    q, a = _ensure_faq_keywords(q, a, brand, parsed, dep, hash(intent) % 50)
    return {'q': q, 'a': a}


def audit_keyword_coverage(
    brand: str,
    keyword_focus: str,
    *,
    title: str = '',
    description: str = '',
    faqs: Optional[List[Dict[str, str]]] = None,
    reviews: Optional[List[Dict[str, Any]]] = None,
    article_html: str = '',
) -> Dict[str, Any]:
    parsed = parse_keyword_focus(keyword_focus)
    faqs = faqs or []
    reviews = reviews or []

    def hit(text: str) -> bool:
        return _text_has_user_keyword(text, parsed) if text.strip() else False

    faq_hits = sum(1 for f in faqs if hit(f.get('q', '') + ' ' + f.get('a', '')))
    rev_hits = sum(1 for r in reviews if hit(r.get('text', '')))
    primary_low = parsed['primary'].lower()
    title_ok = hit(title) or primary_low in title.lower()
    desc_ok = hit(description)
    faq_ok = faq_hits >= min(3, len(faqs)) if faqs else False
    rev_ok = rev_hits >= min(2, len(reviews)) if reviews else False
    art_ok = hit(article_html) if article_html.strip() else False
    score = sum((title_ok, desc_ok, faq_ok, rev_ok, art_ok))
    return {
        'title_ok': title_ok,
        'desc_ok': desc_ok,
        'faq_ok': faq_ok,
        'faq_hits': faq_hits,
        'faq_total': len(faqs),
        'reviews_ok': rev_ok,
        'review_hits': rev_hits,
        'review_total': len(reviews),
        'article_ok': art_ok,
        'score': score,
        'max_score': 5,
        'primary': parsed['primary'],
    }


def _weighted_review_part(
    rng: random.Random,
    items: List[Dict[str, Any]],
    parsed: Dict[str, Any],
) -> Dict[str, Any]:
    weights = [_keyword_template_score(x.get('text', ''), parsed) + 1 for x in items]
    return rng.choices(items, weights=weights, k=1)[0]


def _fill(
    t: str,
    brand: str,
    kw: str,
    dep: str = 'Rp10.000',
    canon: str = '#LINKCANNO',
    ctx: Optional[Dict[str, str]] = None,
) -> str:
    ctx = ctx or {}
    parsed = parse_keyword_focus(kw)
    yr = datetime.now().year
    repl = {
        '{brand}': brand,
        '{keyword}': parsed['raw'],
        '{kw_short}': parsed['primary_title'],
        '{kw_primary}': parsed['primary_title'],
        '{kw_secondary}': parsed['secondary'][0].title() if parsed['secondary'] else parsed['primary_title'],
        '{kw_list}': parsed['kw_list'],
        '{deposit}': dep,
        '{canon}': canon,
        '{year}': str(yr),
        '{usp}': ctx.get('usp', 'transaksi cepat dan akses stabil'),
        '{provider}': ctx.get('provider', 'PG Soft, Pragmatic Play, Habanero'),
        '{withdraw}': ctx.get('withdraw', '3–5 menit'),
        '{payments}': ctx.get('payments', 'Bank, QRIS, e-wallet'),
        '{support}': ctx.get('support', '24 jam'),
        '{city}': ctx.get('city', 'Jakarta'),
        '{device}': ctx.get('device', 'Android'),
        '{payment}': ctx.get('payment', 'QRIS'),
        '{span}': ctx.get('span', 'sebulan'),
    }
    for key, val in repl.items():
        t = t.replace(key, val)
    return t


def _humanize_text(text: str, rng: random.Random) -> str:
    t = text
    for needle, options in _AI_PHRASE_SWAPS:
        if needle in t.lower():
            repl = rng.choice(options)
            t = re.sub(re.escape(needle), repl, t, count=1, flags=re.I)
    return re.sub(r'\s+', ' ', t).strip()


def _vary_desc_opener(desc: str, parsed: Dict[str, Any], rng: random.Random) -> str:
    primary = parsed['primary']
    if _text_has_user_keyword(desc[:48], parsed):
        return desc
    opener = rng.choice(_DESC_OPENERS).format(primary=primary)
    if not opener:
        return desc
    body = desc.strip()
    if body and body[0].isupper():
        body = body[0].lower() + body[1:]
    return (opener + body).strip()


def _build_title_pool(cat: str, keyword: str) -> List[Dict[str, Any]]:
    titles = get_banks()['titles']
    base = _pool_with_ids(titles.get(cat, titles['slot']), 'title', cat)
    parsed = parse_keyword_focus(keyword)
    pool = _sort_pool_by_keywords(base, parsed, cat=cat)
    serp = _get_serp_pools(keyword, cat)
    if serp.get('titles'):
        pool = list(pool) + serp['titles']
        pool = _sort_pool_by_keywords(pool, parsed, cat=cat)
    return pool


def _build_desc_pool(cat: str, keyword: str) -> List[Dict[str, Any]]:
    descs = get_banks()['descriptions']
    base = _pool_with_ids(descs.get(cat, descs['slot']), 'desc', cat)
    parsed = parse_keyword_focus(keyword)
    dynamic: List[Dict[str, Any]] = []
    for i, pattern in enumerate(_DESC_DYNAMIC_PATTERNS):
        if '{kw_secondary}' in pattern and not parsed['secondary']:
            continue
        dynamic.append({'id': f'desc-dyn-{cat}-{i}', 'text': pattern})
    pool = _sort_pool_by_keywords(base + dynamic, parsed, cat=cat)
    serp = _get_serp_pools(keyword, cat)
    if serp.get('descriptions'):
        pool = list(pool) + serp['descriptions']
        pool = _sort_pool_by_keywords(pool, parsed, cat=cat)
    return pool


def gen_title(
    brand: str,
    keyword: str = 'platform permainan digital',
    reservations: Optional[Dict[str, set]] = None,
    fill_ctx: Optional[Dict[str, str]] = None,
    *,
    vary: bool = False,
    exclude_fps: Optional[set] = None,
    regen_nonce: int = 0,
) -> Tuple[str, str]:
    cat = _detect_cat(keyword)
    pool = _build_title_pool(cat, keyword)
    reserved = reservations or get_content_reservations(exclude_brand=brand)
    blocked = set(reserved.get('text_fps', set())) | set(exclude_fps or set())
    parsed = parse_keyword_focus(keyword)
    ctx = fill_ctx or {}
    rng = _regen_seed(brand, keyword, 3, regen_nonce) if vary else _stable_seed(brand, keyword, 3)

    def text_fn(item: Dict[str, Any]) -> str:
        raw = _fill(item['text'], brand, keyword, ctx=ctx)
        if vary:
            raw = _humanize_text(raw, rng)
        dep = (fill_ctx or {}).get('deposit', 'Rp10.000')
        return sanitize_title_neutral(_trim_title(raw), brand, dep)

    picked, ids, _ = _pick_unique_items(
        pool, brand, keyword, 3, 1, reserved.get('title_ids', set()), blocked, text_fn,
        vary=vary, regen_nonce=regen_nonce,
    )
    if not picked:
        item = rng.choice(pool)
        raw = _fill(item['text'], brand, keyword, ctx=ctx)
        if vary:
            raw = _humanize_text(raw, rng)
        return sanitize_title_neutral(_trim_title(raw), brand, (fill_ctx or {}).get('deposit', 'Rp10.000')), str(item.get('id', ''))
    return text_fn(picked[0]), ids[0] if ids else ''


def gen_description(
    brand: str,
    keyword: str = 'platform permainan digital',
    dep: str = 'Rp10.000',
    reservations: Optional[Dict[str, set]] = None,
    fill_ctx: Optional[Dict[str, str]] = None,
    *,
    vary: bool = False,
    exclude_fps: Optional[set] = None,
    regen_nonce: int = 0,
) -> Tuple[str, str]:
    cat = _detect_cat(keyword)
    pool = _build_desc_pool(cat, keyword)
    reserved = reservations or get_content_reservations(exclude_brand=brand)
    blocked = set(reserved.get('text_fps', set())) | set(exclude_fps or set())
    ctx = fill_ctx or {}
    parsed = parse_keyword_focus(keyword)
    rng = _regen_seed(brand, keyword, 4, regen_nonce) if vary else _stable_seed(brand, keyword, 4)

    def text_fn(item: Dict[str, Any]) -> str:
        raw = _fill(item['text'], brand, keyword, dep, ctx=ctx)
        if vary:
            raw = _vary_desc_opener(raw, parsed, rng)
            raw = _humanize_text(raw, rng)
        return _ensure_description_keyword(raw, brand, parsed, dep)

    picked, ids, _ = _pick_unique_items(
        pool, brand, keyword, 4, 1, reserved.get('desc_ids', set()), blocked, text_fn,
        vary=vary, regen_nonce=regen_nonce,
    )
    if not picked:
        item = rng.choice(pool)
        raw = _fill(item['text'], brand, keyword, dep, ctx=ctx)
        if vary:
            raw = _vary_desc_opener(raw, parsed, rng)
            raw = _humanize_text(raw, rng)
        return _ensure_description_keyword(raw, brand, parsed, dep), str(item.get('id', ''))
    return text_fn(picked[0]), ids[0] if ids else ''


def gen_faq(
    brand: str,
    keyword: str,
    dep: str = 'Rp10.000',
    canon: str = '#LINKCANNO',
    reservations: Optional[Dict[str, set]] = None,
    fill_ctx: Optional[Dict[str, str]] = None,
    *,
    vary: bool = False,
    exclude_fps: Optional[set] = None,
    regen_nonce: int = 0,
) -> Tuple[List[Dict[str, str]], List[str]]:
    cat = _detect_cat(keyword)
    parsed = parse_keyword_focus(keyword)
    pool = _build_faq_pool(cat, keyword)
    reserved = reservations or get_content_reservations(exclude_brand=brand)
    blocked = set(reserved.get('text_fps', set())) | set(exclude_fps or set())
    ctx = fill_ctx or {}
    pick = FAQ_PICK_COUNT
    kw_slots = FAQ_KW_SLOTS
    intents = _detect_faq_intents_from_kw(keyword)
    rng = _regen_seed(brand, keyword, 0, regen_nonce) if vary else _stable_seed(brand, keyword, 0)
    ctx_payments = (fill_ctx or {}).get('payments', 'Bank, QRIS, E-Wallet')
    ctx_support = (fill_ctx or {}).get('support', '24 Jam')

    faqs: List[Dict[str, str]] = []
    picked_ids: List[str] = []
    local_fps: List[str] = []

    for item in gen_mandatory_brand_faqs(brand, parsed['primary'], dep, ctx_payments, ctx_support):
        fp = _text_fingerprint(item['q'] + ' ' + item['a'], brand)
        if fp in blocked:
            continue
        faqs.append(item)
        local_fps.append(item['q'] + ' ' + item['a'])

    def render_item(item: Dict[str, Any]) -> Tuple[str, str, str]:
        q = _fill(item['q'], brand, keyword, dep, canon, ctx)
        a = _fill(item['a'], brand, keyword, dep, canon, ctx)
        q, a = _ensure_faq_keywords(q, a, brand, parsed, dep, len(q))
        fp = _text_fingerprint(q + ' ' + a, brand)
        return q, a, fp

    for item in _gen_keyword_faq_items(brand, parsed, dep, canon, ctx, count=kw_slots):
        fp = _text_fingerprint(item['q'] + ' ' + item['a'], brand)
        if fp in blocked or any(_too_similar_pair(item['q'] + ' ' + item['a'], t, brand) for t in local_fps):
            continue
        faqs.append(item)
        local_fps.append(item['q'] + ' ' + item['a'])

    by_intent: Dict[str, List[Dict[str, Any]]] = {}
    for item in pool:
        intent = item.get('_intent') or _faq_item_intent(item.get('q', ''), item.get('a', ''))
        by_intent.setdefault(intent, []).append(item)

    intent_order = [i for i in intents if i != 'general'] + ['general']
    rng.shuffle(intent_order)
    for intent in intent_order:
        if len(faqs) >= pick:
            break
        candidates = list(by_intent.get(intent, []))
        rng.shuffle(candidates)
        intent_added = False
        for item in candidates:
            if len(faqs) >= pick:
                break
            iid = str(item.get('id', ''))
            if iid and iid in reserved.get('faq_ids', set()):
                continue
            q, a, fp = render_item(item)
            if fp in blocked or fp in {_text_fingerprint(t, brand) for t in local_fps}:
                continue
            if any(_too_similar_pair(q + ' ' + a, t, brand) for t in local_fps):
                continue
            faqs.append({'q': q, 'a': a})
            if iid:
                picked_ids.append(iid)
            local_fps.append(q + ' ' + a)
            intent_added = True
            break
        if not intent_added and intent in _INTENT_FAQ_TEMPLATES and len(faqs) < pick:
            extra = _gen_intent_faq_item(intent, brand, keyword, dep, canon, ctx)
            if extra:
                fp = _text_fingerprint(extra['q'] + ' ' + extra['a'], brand)
                if fp not in blocked and not any(_too_similar_pair(extra['q'] + ' ' + extra['a'], t, brand) for t in local_fps):
                    faqs.append(extra)
                    local_fps.append(extra['q'] + ' ' + extra['a'])

    if len(faqs) < pick:
        def text_fn(item: Dict[str, Any]) -> str:
            q, a, _ = render_item(item)
            return q + ' ' + a

        need = pick - len(faqs)
        extra_picked, extra_ids, _ = _pick_unique_items(
            pool, brand, keyword, 0, need, reserved.get('faq_ids', set()), blocked | {_text_fingerprint(t, brand) for t in local_fps},
            text_fn, vary=vary, regen_nonce=regen_nonce,
        )
        for item in extra_picked:
            q, a, _ = render_item(item)
            faqs.append({'q': q, 'a': a})
            iid = str(item.get('id', ''))
            if iid:
                picked_ids.append(iid)

    return faqs[:pick], picked_ids


def extract_template_fingerprints(html: str) -> set:
    fps: set = set()
    if not html:
        return fps
    for pat in (
        r'reviewBody"\s*:\s*"([^"]{20,})"',
        r'class="sgt-review"[^>]*>\s*<div class="sgt-name">[^<]+</div>\s*([^<]{20,})',
        r'acceptedAnswer"\s*:\s*\{\s*"@type":\s*"Answer",\s*"text":\s*"([^"]{20,})"',
        r'class="sgt-answer">([^<]{20,})',
    ):
        for m in re.finditer(pat, html, flags=re.I | re.S):
            chunk = re.sub(r'\s+', ' ', m.group(1)).strip().lower()
            if len(chunk) >= 20:
                fps.add(chunk[:120])
    banned = ('agen voucher', 'samsung galaxy', 'demo - lihat', 'topcer')
    for b in banned:
        fps.add(b)
    return fps


def _too_similar(text: str, fps: set) -> bool:
    low = re.sub(r'\s+', ' ', text.lower()).strip()
    if any(len(fp) > 18 and fp in low for fp in fps):
        return True
    return _too_similar_text(text, fps)


def _compose_review(
    rng: random.Random,
    brand: str,
    kw: str,
    dep: str,
    opens: List[Dict[str, Any]],
    middles: List[Dict[str, Any]],
    closes: List[Dict[str, Any]],
    meta: Dict[str, Any],
) -> Tuple[str, str]:
    parsed = parse_keyword_focus(kw)
    rev_ctx = {
        'city': rng.choice(meta.get('cities') or _CITIES),
        'device': rng.choice(meta.get('devices') or _DEVICES),
        'payment': rng.choice(meta.get('payments') or _PAYMENTS),
        'span': rng.choice(meta.get('time_spans') or _TIME_SPANS),
    }
    o = _weighted_review_part(rng, opens, parsed)
    m = _weighted_review_part(rng, middles, parsed)
    c = _weighted_review_part(rng, closes, parsed)
    combo = f'{o["id"]}|{m["id"]}|{c["id"]}'
    text = ' '.join((
        _fill(o['text'], brand, kw, dep, ctx=rev_ctx),
        _fill(m['text'], brand, kw, dep, ctx=rev_ctx),
        _fill(c['text'], brand, kw, dep, ctx=rev_ctx),
    ))
    if not _text_has_user_keyword(text, parsed):
        text = _weave_keyword_clause(text, brand, parsed, dep, rng.randint(0, 999))
    return text, combo


def gen_reviews(
    brand: str,
    kw: str,
    dep: str = 'Rp10.000',
    count: int = REVIEW_PICK_COUNT,
    template_html: str = '',
    reservations: Optional[Dict[str, set]] = None,
    *,
    vary: bool = False,
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    fps = extract_template_fingerprints(template_html)
    rng = _vary_seed(brand, kw, 1) if vary else _stable_seed(brand, kw, 1)
    banks = get_banks()
    meta = banks['meta']
    rev = banks['reviews']
    cat = _detect_cat(kw)
    opens = _pool_with_ids(rev.get('open') or _REVIEW_OPEN, 'rev-o', cat)
    middles = _pool_with_ids(rev.get('middle') or _REVIEW_MIDDLE, 'rev-m', cat)
    closes = _pool_with_ids(rev.get('close') or _REVIEW_CLOSE, 'rev-c', cat)
    reserved = reservations or get_content_reservations(exclude_brand=brand)
    blocked_combos = set(reserved.get('review_combos', set()))
    blocked_fps = set(reserved.get('review_fps', set())) | fps
    names = list(meta.get('reviewer_names') or _REVIEWER_NAMES)
    rng.shuffle(names)
    reviews: List[Dict[str, Any]] = []
    combos: List[str] = []
    review_fps: List[str] = []
    seen: set = set()
    attempts = 0
    while len(reviews) < count and attempts < count * 25:
        attempts += 1
        text, combo = _compose_review(rng, brand, kw, dep, opens, middles, closes, meta)
        key = text[:80].lower()
        fp = _text_fingerprint(text, brand)
        if key in seen or combo in blocked_combos or combo in combos:
            continue
        if _too_similar(text, blocked_fps) or fp in review_fps:
            continue
        if any(_too_similar_pair(text, r['text'], brand) for r in reviews):
            continue
        seen.add(key)
        combos.append(combo)
        review_fps.append(fp)
        reviews.append({
            'name': names[len(reviews) % len(names)],
            'text': text,
            'rating': rng.choice([5, 5, 5, 4, 4]),
            'date': (datetime.now() - timedelta(days=rng.randint(3, 180))).strftime('%Y-%m-%d'),
        })
    return reviews, combos, review_fps


def gen_breadcrumbs(brand: str, kw: str) -> Tuple[List[str], List[Dict[str, str]]]:
    return gen_breadcrumb_trail(brand)


def gen_nav_categories(brand: str, kw: str) -> List[str]:
    parsed = parse_keyword_focus(kw)
    cat = _detect_cat(kw)
    rng = _seed(brand, kw, 5)
    extras = {
        'mahjong': ['Mahjong Ways', 'Portal Digital', 'Login Member'],
        'zeus': ['Gates of Olympus', 'Arena Digital', 'Akses 24 Jam'],
        'slot': ['Platform Digital', 'Permainan Online', 'Mirror Aktif'],
    }
    base = [brand, parsed['primary_title']]
    base.extend(k.title() for k in parsed['secondary'][:2])
    base.extend(extras.get(cat, extras['slot']))
    seen: set = set()
    unique: List[str] = []
    for item in base:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    rng.shuffle(unique)
    return unique[:6]


def gen_article_html(
    brand: str,
    kw: str,
    dep: str,
    canon: str,
    reservations: Optional[Dict[str, set]] = None,
    fill_ctx: Optional[Dict[str, str]] = None,
    *,
    vary: bool = False,
) -> Tuple[str, str]:
    cat = _detect_cat(kw)
    parsed = parse_keyword_focus(kw)
    arts = get_banks()['articles']
    opens = _sort_pool_by_keywords(_pool_with_ids(arts.get('open') or _ARTICLE_OPEN, 'art-o', cat), parsed, cat=cat)
    mids = _sort_pool_by_keywords(_pool_with_ids(arts.get('mid') or _ARTICLE_MID, 'art-m', cat), parsed, cat=cat)
    closes = _sort_pool_by_keywords(_pool_with_ids(arts.get('close') or _ARTICLE_CLOSE, 'art-c', cat), parsed, cat=cat)
    reserved = reservations or get_content_reservations(exclude_brand=brand)
    blocked = set(reserved.get('text_fps', set()))
    ctx = fill_ctx or {}
    rng = _vary_seed(brand, kw, 6) if vary else _stable_seed(brand, kw, 6)

    o_picked, o_ids, _ = _pick_unique_items(
        opens, brand, kw, 60, 1, set(), blocked, lambda i: _fill(i['text'], brand, kw, dep, canon, ctx), vary=vary,
    )
    m_picked, m_ids, _ = _pick_unique_items(
        mids, brand, kw, 61, 2, set(), blocked,
        lambda i: _fill(i['text'], brand, kw, dep, canon, ctx), vary=vary,
    )
    c_picked, c_ids, _ = _pick_unique_items(
        closes, brand, kw, 62, 1, set(), blocked, lambda i: _fill(i['text'], brand, kw, dep, canon, ctx), vary=vary,
    )
    if not o_picked:
        o_picked = [rng.choice(opens)]
        o_ids = [o_picked[0]['id']]
    while len(m_picked) < 2 and mids:
        extra = rng.choice(mids)
        if extra not in m_picked:
            m_picked.append(extra)
            m_ids.append(extra['id'])
    if not c_picked:
        c_picked = [rng.choice(closes)]
        c_ids = [c_picked[0]['id']]
    parts = (
        [_fill(o_picked[0]['text'], brand, kw, dep, canon, ctx)]
        + [_fill(x['text'], brand, kw, dep, canon, ctx) for x in m_picked[:2]]
        + [_fill(c_picked[0]['text'], brand, kw, dep, canon, ctx)]
    )
    if parts and not _text_has_user_keyword(parts[0], parsed):
        parts[0] = _weave_keyword_clause(parts[0], brand, parsed, dep, 6)
    combo = '|'.join(o_ids + m_ids[:2] + c_ids[:1])
    if combo in reserved.get('article_combos', set()):
        rng.shuffle(mids)
        if len(mids) >= 2:
            m_picked = mids[:2]
            m_ids = [x['id'] for x in m_picked]
            parts = parts[:1] + [_fill(x['text'], brand, kw, dep, canon, ctx) for x in m_picked] + parts[-1:]
            combo = '|'.join(o_ids + m_ids + c_ids[:1])
    return '\n'.join(parts), combo


def _strip_article_extra_anchors(article: str, canon: str) -> str:
    if not article or not canon:
        return article
    return limit_article_canonical_anchors(article, canon, 1)


def enrich_config(cfg: Dict[str, Any], template_html: str = '', *, vary: bool = False) -> Dict[str, Any]:
    out = merge_brand_defaults(cfg)
    brand = out['brand'].strip()
    kw = out.get('keyword_focus') or f'{brand.lower()} platform permainan digital'
    dep = out.get('short_info', {}).get('minimal_deposit', 'Rp10.000') if isinstance(out.get('short_info'), dict) else 'Rp10.000'
    if not out.get('short_info'):
        parsed_kw = parse_keyword_focus(kw)
        out['short_info'] = {
            'minimal_deposit': dep,
            'jenis_permainan': parsed_kw['primary_title'],
            'provider': 'PG Soft, Pragmatic Play, Habanero',
            'metode_bayar': 'Bank, QRIS, E-Wallet',
            'jam_operasional': '24 Jam Nonstop',
            'rtp_info': 'Transparan & Fair',
        }
    canon = out.get('canonical', '#LINKCANNO')
    fill_ctx = build_fill_context(out)
    reservations = get_content_reservations(exclude_brand=brand)
    content_meta: Dict[str, Any] = {
        'pack_version': str(get_banks().get('version', _banks_source)),
    }
    text_fps: List[str] = []

    if not out.get('title'):
        title, tid = gen_title(brand, kw, reservations, fill_ctx, vary=vary)
        out['title'] = title
        if tid:
            content_meta['title_id'] = tid
            text_fps.append(_text_fingerprint(title, brand))
    else:
        out['title'] = sanitize_title_neutral(
            _trim_title(out['title']), brand, dep,
        )

    parsed_kw = parse_keyword_focus(kw)
    out.setdefault('h1', gen_h1_text(brand, parsed_kw['primary']))

    if not out.get('description'):
        desc, did = gen_description(brand, kw, dep, reservations, fill_ctx, vary=vary)
        out['description'] = desc
        if did:
            content_meta['desc_id'] = did
            text_fps.append(_text_fingerprint(desc, brand))
    else:
        out['description'] = _ensure_description_keyword(
            _trim_desc(out['description']), brand, parse_keyword_focus(kw), dep,
        )

    if not out.get('faq'):
        faqs, faq_ids = gen_faq(brand, kw, dep, canon, reservations, fill_ctx, vary=vary)
        out['faq'] = faqs
        content_meta['faq_ids'] = faq_ids
        for item in faqs:
            text_fps.append(_text_fingerprint(item['q'] + ' ' + item['a'], brand))

    if not out.get('reviews'):
        reviews, combos, r_fps = gen_reviews(
            brand, kw, dep, count=REVIEW_PICK_COUNT, template_html=template_html,
            reservations=reservations, vary=vary,
        )
        out['reviews'] = reviews
        content_meta['review_combos'] = combos
        content_meta['review_fps'] = r_fps
        text_fps.extend(r_fps)

    if not out.get('breadcrumb_html') or not out.get('breadcrumb_schema'):
        bc_html, bc_schema = gen_breadcrumbs(brand, kw)
        out.setdefault('breadcrumb_html', bc_html)
        out.setdefault('breadcrumb_schema', bc_schema)

    out.setdefault('nav_categories', gen_nav_categories(brand, kw))

    if not out.get('article_html'):
        article, art_combo = gen_article_html(brand, kw, dep, canon, reservations, fill_ctx, vary=vary)
        out['article_html'] = _strip_article_extra_anchors(article, canon)
        content_meta['article_combo'] = art_combo
        for para in article.split('\n'):
            text_fps.append(_text_fingerprint(para, brand))

    out.setdefault('footer', f'© {datetime.now().year} {brand}. All rights reserved.')
    out.setdefault('template_type', detect_tpl_type(template_html) if template_html else 'generic')
    content_meta['text_fps'] = list(dict.fromkeys(text_fps))
    out['_content_meta'] = content_meta
    return out


def fetch_url(url: str, timeout: int = 20) -> Optional[str]:
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; LPBuilder/2.0)'})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception:
        return None


def _is_skip_brand_name(name: str) -> bool:
    low = name.lower().strip()
    if not low or len(low) < 2 or len(low) > 32:
        return True
    if low in GENERIC_SITE_NAME_SKIP:
        return True
    if low in ('template', 'templatebrand', 'brandname', 'yourbrand', 'placeholder'):
        return False
    if any(x in low for x in ('theme', 'envato', 'woo', 'wordpres', 'marketplace')) and 'brand' not in low:
        return True
    if low == 'template' or low.startswith('demo '):
        return True
    return False


def detect_brand_candidates(html: str) -> List[str]:
    found: List[str] = []
    for pat in (
        r'"@type"\s*:\s*"Brand"\s*,\s*"name"\s*:\s*"([^"]+)"',
        r'"sku"\s*:\s*"([^"]+)"',
        r'"@type"\s*:\s*"Organization"\s*,\s*"name"\s*:\s*"([^"]+)"',
        r'class="info-value-[^"]*"[^>]*>\s*([^<\s][^<]{1,30}?)\s*<',
        r'alt="([A-Z0-9][A-Z0-9\s]{1,22})"',
        r'TENTANG\s+([A-Z0-9][A-Z0-9\s]{1,22})\s*<',
        r'FAQ\s+([A-Z0-9][A-Z0-9\s]{1,22})\s*<',
        r'TESTIMONI\s+([A-Z0-9][A-Z0-9\s]{1,22})\s*<',
    ):
        for m in re.finditer(pat, html, flags=re.I):
            found.append(m.group(1).strip())
    m = re.search(r'<title>([^<⭐|—\-]+)', html, flags=re.I)
    if m:
        found.append(m.group(1).strip().split()[0])
    for m in re.finditer(r'<h1[^>]*>([^<⭐]{2,40})', html, flags=re.I):
        found.append(m.group(1).strip().split()[0])
    m = re.search(r'<meta property="og:site_name" content="([^"]+)"', html, flags=re.I)
    if m:
        found.append(m.group(1).strip())
    return found


def detect_source_brand(html: str) -> str:
    scores: Dict[str, int] = {}
    for raw in detect_brand_candidates(html):
        name = re.sub(r'\s+', ' ', raw).strip()
        if _is_skip_brand_name(name):
            continue
        key = name.upper()
        scores[key] = scores.get(key, 0) + 1
    if scores:
        return max(scores, key=lambda k: (scores[k], len(k)))
    m = re.search(r'<title>([^<|—\-⭐]+)', html, flags=re.I)
    if m:
        chunk = m.group(1).strip().split()[0]
        if not _is_skip_brand_name(chunk):
            return chunk.upper()
    return ''


def is_marketplace_template(html: str) -> bool:
    return any(marker in html for marker in MARKETPLACE_MARKERS)


def detect_tpl_type(html: str) -> str:
    if 'pd-title' in html and 'sgt-faq' in html:
        return 'product-detail'
    if '<html amp' in html.lower() or 'amp-boilerplate' in html:
        return 'amp'
    return 'generic'


def extract_template_urls(html: str) -> List[str]:
    urls: List[str] = []
    for pat in (
        r'<link rel="canonical" href="([^"]+)"',
        r'<meta property="og:url" content="([^"]+)"',
        r'<link rel="amphtml" href="([^"]+)"',
        r'hreflang="[^"]+" href="([^"]+)"',
    ):
        for m in re.finditer(pat, html, flags=re.I):
            u = m.group(1).strip()
            if u and not u.startswith('#'):
                urls.append(u)
    return list(dict.fromkeys(urls))


def _swap_url_variants(html: str, old: str, new: str) -> str:
    if not old or not new or old == new:
        return html
    old_base = old.rstrip('/')
    new_base = new.rstrip('/')
    for src, dst in (
        (old, new),
        (old_base, new_base),
        (old_base + '/', new_base + '/'),
    ):
        html = html.replace(src, dst)
    return html


def apply_template_url_swaps(html: str, template_html: str, canon: str, amp: str) -> str:
    if not template_html:
        return html
    canon_base = canon.rstrip('/') if canon and canon != '#LINKCANNO' else ''
    amp_base = amp.rstrip('/') if amp and amp != '#LINKAMP' else ''

    old_canon = ''
    m = re.search(r'<link rel="canonical" href="([^"]+)"', template_html, flags=re.I)
    if m:
        old_canon = m.group(1).strip()
        if canon_base:
            html = _swap_url_variants(html, old_canon, canon_base)

    m = re.search(r'<meta property="og:url" content="([^"]+)"', template_html, flags=re.I)
    if m and canon_base:
        html = _swap_url_variants(html, m.group(1).strip(), canon_base)

    old_amp = ''
    m = re.search(r'<link rel="amphtml" href="([^"]+)"', template_html, flags=re.I)
    if m:
        old_amp = m.group(1).strip()
        if amp_base:
            html = _swap_url_variants(html, old_amp, amp_base)

    for m in re.finditer(r'hreflang="[^"]+" href="([^"]+)"', template_html, flags=re.I):
        u = m.group(1).strip()
        if old_amp and u.rstrip('/') == old_amp.rstrip('/') and amp_base:
            html = _swap_url_variants(html, u, amp_base)
        elif old_canon and u.rstrip('/') == old_canon.rstrip('/') and canon_base:
            html = _swap_url_variants(html, u, canon_base)
        elif canon_base and u.startswith('http'):
            html = _swap_url_variants(html, u, canon_base)

    return html


def collect_template_image_urls(html: str) -> List[str]:
    urls: List[str] = []
    for pat in (
        r'<meta property="og:image" content="([^"]+)"',
        r'<meta name="twitter:image" content="([^"]+)"',
        r'(?:src|href)="([^"]+\.(?:png|jpe?g|gif|webp|ico)(?:\?[^"]*)?)"',
        r'srcset="([^"\s,]+)"',
    ):
        for m in re.finditer(pat, html, flags=re.I):
            u = m.group(1).strip()
            if u.startswith('http'):
                urls.append(u)
    return list(dict.fromkeys(urls))


def extract_assets_from_html(html: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    m = re.search(r'<meta property="og:image" content="([^"]+)"', html, flags=re.I)
    if m:
        out['banner'] = m.group(1).strip()
    for pat in (
        r'<link[^>]+rel="(?:shortcut )?icon"[^>]+href="([^"]+)"',
        r'<link[^>]+href="([^"]+)"[^>]+rel="(?:shortcut )?icon"',
    ):
        m = re.search(pat, html, flags=re.I)
        if m:
            out['favicon'] = m.group(1).strip()
            break
    for pat in (
        r'src="([^"]*logo[^"]*\.(?:gif|png|jpg|webp))"',
        r'"image"\s*:\s*"([^"]+\.(?:gif|png|jpg|webp))"',
        r'src="([^"]*icon[^"]*\.(?:gif|png|jpg|webp))"',
        r'item-header__cart-button-icon[^>]*>[\s\S]{0,120}?src="([^"]+)"',
    ):
        m = re.search(pat, html, flags=re.I)
        if m:
            out['logo'] = m.group(1).strip()
            break
    if 'banner' in out and 'logo' not in out:
        out['logo'] = out['banner']
    return out


def apply_user_assets(
    html: str,
    template_html: str,
    banner: str,
    logo: str,
    favicon: str,
    source_brand: str = '',
) -> str:
    if not template_html:
        return html
    orig = extract_assets_from_html(template_html)
    all_imgs = collect_template_image_urls(template_html)
    src_low = source_brand.lower() if source_brand else ''

    if banner:
        html = re.sub(
            r'(<meta property="og:image" content=")[^"]*(")',
            rf'\g<1>{banner}\2',
            html,
            flags=re.I,
        )
        html = re.sub(
            r'(<meta name="twitter:image" content=")[^"]*(")',
            rf'\g<1>{banner}\2',
            html,
            flags=re.I,
        )
        for u in all_imgs:
            low = u.lower()
            if u == orig.get('banner'):
                html = html.replace(u, banner)
            elif any(x in low for x in ('banner', 'penyiar', 'hero', 'preview', 'screenshot')):
                html = html.replace(u, banner)
            elif src_low and src_low in low and any(x in low for x in ('.png', '.jpg', '.gif', '.webp')):
                if 'icon' not in low and 'logo' not in low:
                    html = html.replace(u, banner)

    logo_target = logo or favicon
    if logo_target:
        for u in all_imgs:
            low = u.lower()
            if u == orig.get('logo') or u == orig.get('favicon'):
                html = html.replace(u, logo_target)
            elif any(x in low for x in ('logo', 'icon', 'favicon', 'gif-logo')):
                if u != banner:
                    html = html.replace(u, logo_target)

    if favicon:
        html = re.sub(
            r'(<link[^>]+rel="(?:shortcut )?icon"[^>]+href=")[^"]*(")',
            rf'\g<1>{favicon}\2',
            html,
            flags=re.I,
        )
        html = re.sub(
            r'(<link[^>]+href=")[^"]*(")([^>]*rel="(?:shortcut )?icon")',
            rf'\g<1>{favicon}\2\3',
            html,
            flags=re.I,
        )
        for u in all_imgs:
            if 'icon' in u.lower() or u.endswith('.ico'):
                html = html.replace(u, favicon)

    for placeholder, val in (('#BANNER', banner), ('#LOGO', logo), ('#FAVICON', favicon), ('#LINKCANNO', ''), ('#LINKREF', '')):
        if val and placeholder in html:
            html = html.replace(placeholder, val)
    return html


def _patch_schema_graph(
    html: str,
    brand: str,
    canon: str,
    desc: str,
    bc_schema: List[Dict[str, str]],
    faqs: List[Dict[str, str]],
) -> str:
    html = re.sub(
        r'("@type"\s*:\s*"WebSite"[\s\S]*?"name"\s*:\s*")[^"]*(")',
        rf'\g<1>{brand}\2',
        html,
        count=1,
        flags=re.I,
    )
    html = re.sub(
        r'("@type"\s*:\s*"WebSite"[\s\S]*?"url"\s*:\s*")[^"]*(")',
        rf'\g<1>{canon}\2',
        html,
        count=1,
        flags=re.I,
    )
    if bc_schema:
        items_json = ',\n        '.join([
            f'{{\n          "@type": "ListItem",\n          "position": {i + 1},\n          "name": "{_json_esc(x["name"])}",\n          "item": "{canon}"\n        }}'
            for i, x in enumerate(bc_schema)
        ])
        html = re.sub(
            r'("@type"\s*:\s*"BreadcrumbList"[\s\S]*?"itemListElement"\s*:\s*)\[[^\]]*\]',
            rf'\1[\n        {items_json}\n      ]',
            html,
            count=1,
            flags=re.I,
        )
    if faqs:
        faq_entities = ',\n        '.join([
            f'{{\n          "@type": "Question",\n          "name": "{_json_esc(x["q"])}",\n          "acceptedAnswer": {{\n            "@type": "Answer",\n            "text": "{_json_esc(x["a"])}"\n          }}\n        }}'
            for x in faqs
        ])
        html = re.sub(
            r'("@type"\s*:\s*"FAQPage"[\s\S]*?"mainEntity"\s*:\s*)\[[^\]]*\]',
            rf'\1[\n        {faq_entities}\n      ]',
            html,
            count=1,
            flags=re.I,
        )
    return html


def replace_source_brand(html: str, brand: str, source_brand: str) -> str:
    if not source_brand or source_brand.upper() == brand.upper():
        return html
    html = re.sub(r'\b' + re.escape(source_brand) + r'\b', brand, html, flags=re.IGNORECASE)
    return html


def _build_cok_faq_html(faqs: List[Dict[str, str]]) -> str:
    items = []
    for item in faqs:
        items.append(
            f'<div class="cok-faq-item">\n'
            f'<button class="cok-faq-q">{item["q"]}</button>\n'
            f'<div class="cok-faq-a">{item["a"]}</div>\n'
            f'</div>'
        )
    return '\n\n                '.join(items)


def _build_testimonial_html(reviews: List[Dict[str, Any]]) -> str:
    cards = []
    for r in reviews:
        name = r.get('name', 'Member')
        city = r.get('city', 'Indonesia')
        text = r.get('text', '')
        initials = ''.join(part[0] for part in name.split()[:2]).upper() or 'MB'
        cards.append(
            f'<article class="testi-card">\n'
            f'                    <div class="testi-head">\n'
            f'                        <div class="avatar">{initials}</div>\n'
            f'                        <div>\n'
            f'                            <div itemprop="author" itemscope itemtype="https://schema.org/Person">\n'
            f'                                <h3 class="name"><span itemprop="name">{name}</span></h3>\n'
            f'                                <p class="meta">\n'
            f'                                    <span itemprop="homeLocation" itemscope itemtype="https://schema.org/Place">\n'
            f'                                        <span itemprop="name">{city}</span>\n'
            f'                                    </span>\n'
            f'                                </p>\n'
            f'                            </div>\n'
            f'                        </div>\n'
            f'                    </div>\n'
            f'                    <p class="quote" itemprop="reviewBody">{text}</p>\n'
            f'                    <div itemprop="reviewRating" itemscope itemtype="https://schema.org/Rating">\n'
            f'                        <meta itemprop="ratingValue" content="5">\n'
            f'                        <meta itemprop="bestRating" content="5">\n'
            f'                        <meta itemprop="worstRating" content="1">\n'
            f'                    </div>\n'
            f'                </article>'
        )
    return '\n\n                '.join(cards)


def _build_info_box_html(brand: str, si: Dict[str, Any], cta: str, class_prefix: str = 'olxtoto') -> str:
    dep = si.get('minimal_deposit', 'Rp10.000')
    provider = si.get('provider', 'Provider Resmi')
    withdraw = si.get('min_withdraw', 'Rp50.000')
    payments = si.get('metode_bayar', 'Bank, QRIS, E-Wallet')
    cp = class_prefix
    return (
        f'<div class="info-box-{cp}">\n'
        f'                            <div class="info-header-{cp}">TENTANG {brand}</div>\n'
        f'                            <div class="info-row-{cp}">\n'
        f'                                <span class="info-label-{cp}">Nama Situs</span>\n'
        f'                                <span class="info-value-{cp}">{brand}</span>\n'
        f'                            </div>\n'
        f'                            <div class="info-row-{cp}">\n'
        f'                                <span class="info-label-{cp}">Jenis Provider</span>\n'
        f'                                <span class="info-value-{cp}">{provider}</span>\n'
        f'                            </div>\n'
        f'                            <div class="info-row-{cp}">\n'
        f'                                <span class="info-label-{cp}">Min Deposit</span>\n'
        f'                                <span class="info-value-{cp}">{dep}</span>\n'
        f'                            </div>\n'
        f'                            <div class="info-row-{cp}">\n'
        f'                                <span class="info-label-{cp}">Min Withdraw</span>\n'
        f'                                <span class="info-value-{cp}">{withdraw}</span>\n'
        f'                            </div>\n'
        f'                            <div class="info-row-{cp}">\n'
        f'                                <span class="info-label-{cp}">Metode Transaksi</span>\n'
        f'                                <span class="info-value-{cp}">{payments}</span>\n'
        f'                            </div>\n'
        f'                            <div class="info-row-{cp}">\n'
        f'                                <span class="info-label-{cp}">Daftar</span>\n'
        f'                                <span class="info-value-{cp}"><a href="{cta}">Klik Disini</a></span>\n'
        f'                            </div>\n'
        f'                        </div>'
    )


def apply_marketplace_template(html: str, cfg: Dict[str, Any]) -> str:
    brand = cfg['brand']
    title = cfg['title']
    h1 = cfg.get('h1', title)
    desc = cfg['description']
    canon = cfg.get('canonical', '#LINKCANNO')
    cta = cfg.get('cta', '')
    faqs = cfg.get('faq') or []
    reviews = cfg.get('reviews') or []
    article = cfg.get('article_html') or ''
    si = cfg.get('short_info') or {}

    html = re.sub(r'(<meta name="description" content=")[^"]*(")', rf'\g<1>{desc}\2', html)
    html = re.sub(r'(<meta property="og:description" content=")[^"]*(")', rf'\g<1>{desc}\2', html)
    html = re.sub(r'(<meta name="twitter:description" content=")[^"]*(")', rf'\g<1>{desc}\2', html)

    html = re.sub(
        r'<h1([^>]*class="[^"]*t-heading[^"]*"[^>]*)>[^<]*</h1>',
        rf'<h2\1>{title}</h2>',
        html,
        flags=re.I,
        count=1,
    )
    html = re.sub(
        r'(<h1[^>]*class="[^"]*cok-faq-title2[^"]*"[^>]*>)[^<]*(</h1>)',
        rf'\g<1>{h1}\2',
        html,
        flags=re.I,
        count=1,
    )

    if article:
        article_block = article if article.strip().startswith('<p') else '\n'.join(
            f'<p>{p.strip()}</p>' for p in article.split('\n') if p.strip()
        )
        html = re.sub(
            r'(<h1[^>]*class="[^"]*cok-faq-title2[^"]*"[^>]*>[^<]*</h1>\s*)(?:<p>[\s\S]*?</p>\s*)+',
            rf'\1{article_block}\n            ',
            html,
            count=1,
            flags=re.I,
        )

    box_m = re.search(r'<div class="info-box-([^"]+)"', html, flags=re.I)
    box_prefix = box_m.group(1) if box_m else 'site'
    html = re.sub(
        r'<div class="info-box-[^"]+">[\s\S]*?</div>\s*(?=<style>)',
        _build_info_box_html(brand, si, cta, box_prefix) + '\n                        ',
        html,
        count=1,
        flags=re.I,
    )

    if faqs:
        faq_body = _build_cok_faq_html(faqs)
        html = re.sub(
            r'(<h2 class="cok-faq-title">FAQ[^<]*</h2>\s*<div class="cok-faq">)[\s\S]*?(</div>)',
            rf'\1\n\n                {faq_body}\n\n            \2',
            html,
            count=1,
            flags=re.I,
        )
        html = re.sub(r'(<h2 class="cok-faq-title">)FAQ[^<]*(</h2>)', rf'\1FAQ {brand}\2', html, count=1, flags=re.I)

    if reviews:
        testi_body = _build_testimonial_html(reviews)
        html = re.sub(
            r'(<h2 class="cok-faq-title">TESTIMONI[^<]*</h2>\s*<div class="testi-grid">)[\s\S]*?(</div>\s*<style>)',
            rf'\1\n                {testi_body}\n            \2',
            html,
            count=1,
            flags=re.I,
        )
        html = re.sub(
            r'(<h2 class="cok-faq-title">)TESTIMONI[^<]*(</h2>)',
            rf'\1TESTIMONI {brand}\2',
            html,
            count=1,
            flags=re.I,
        )

    bc_html = cfg.get('breadcrumb_html') or [brand]
    if bc_html:
        first = bc_html[0]
        html = re.sub(
            r'(<a class="js-breadcrumb-category" href="[^"]*">)[^<]+(</a>)',
            rf'\g<1>{first}\2',
            html,
            count=1,
            flags=re.I,
        )
        html = re.sub(
            r'(<a href="[^"]*">\s*)' + re.escape(bc_html[0] if len(bc_html) == 1 else brand) + r'(\s*</a>)',
            rf'\g<1>{first}\2',
            html,
            count=1,
            flags=re.I,
        )

    html = re.sub(
        r'(By\s+<a rel="author"[^>]*>)[^<]+(</a>)',
        rf'\g<1>{brand}\2',
        html,
        count=1,
        flags=re.I,
    )
    html = re.sub(
        r'(<div class="popup-footer"[^>]*>[\s\S]*?)(Copyright \d{4}\s*<a[^>]*>)[^<]+(</a>)',
        rf'\g<1>{title}\n                \g<2>{brand}\3',
        html,
        count=1,
        flags=re.I,
    )
    html = re.sub(
        r'(<img[^>]+class="popupBanner"[^>]+alt=")[^"]*(")',
        rf'\g<1>{title}\2',
        html,
        count=1,
        flags=re.I,
    )

    html = re.sub(
        r'("name"\s*:\s*")[^"]*("(?:\s*,\s*"@type"\s*:\s*"Product"|,\s*"image"))',
        rf'\g<1>{_json_esc(title)}\2',
        html,
        count=1,
        flags=re.I,
    )
    html = re.sub(
        r'("description"\s*:\s*")[^"]*("(?:\s*,\s*"brand"))',
        rf'\g<1>{_json_esc(desc)}\2',
        html,
        count=1,
        flags=re.I,
    )
    return html


def _build_generic_faq_html(faqs: List[Dict[str, str]], brand: str) -> str:
    items = []
    for item in faqs:
        items.append(
            f'<details class="lp-faq-item">\n'
            f'<summary>{item["q"]}</summary>\n'
            f'<p>{item["a"]}</p>\n'
            f'</details>'
        )
    body = '\n'.join(items)
    return f'<section class="lp-faq" aria-label="FAQ {brand}">\n<h2>FAQ {brand}</h2>\n{body}\n</section>'


def _build_generic_reviews_html(reviews: List[Dict[str, Any]], brand: str) -> str:
    cards = []
    for r in reviews:
        cards.append(
            f'<article class="lp-review">\n'
            f'<strong>{r.get("name", "Member")}</strong>\n'
            f'<p>{r.get("text", "")}</p>\n'
            f'</article>'
        )
    body = '\n'.join(cards)
    return f'<section class="lp-reviews" aria-label="Review {brand}">\n<h2>Review Pemain {brand}</h2>\n{body}\n</section>'


def apply_product_detail_template(html: str, cfg: Dict[str, Any]) -> str:
    brand = cfg['brand']
    title = cfg['title']
    h1 = cfg.get('h1', title)
    canon = cfg.get('canonical', '#LINKCANNO')
    cta = cfg.get('cta', '')
    faqs = cfg.get('faq') or []
    reviews = cfg.get('reviews') or []
    article = cfg.get('article_html') or ''
    si = cfg.get('short_info') or {}
    favicon = (cfg.get('favicon') or '').strip()
    nav_icon = cfg.get('bottom_nav_icon', favicon)
    footer_text = cfg.get('footer', f'©{datetime.now().year} {brand}')

    if si:
        info_items = (
            f'<li>Minimal Deposit: {si.get("minimal_deposit", "Rp10.000")}</li>'
            f'<li>Jenis Permainan: {si.get("jenis_permainan", "Permainan Digital")}</li>'
            + (f'<li>Provider Unggulan: {si["provider"]}</li>' if si.get('provider') else '')
            + f'<li>Metode Pembayaran: {si.get("metode_bayar", "Bank, QRIS, E-Wallet")}</li>'
            f'<li>Jam Operasional: {si.get("jam_operasional", "24 Jam")}</li>'
            f'<li>Rating: ⭐⭐⭐⭐⭐</li>'
            f'<li>Daftar: <a href="{cta}">Klik Disini</a></li>'
        )
        new_short = f'<div class="pd-short-desc"><p><strong>Informasi {brand} :</strong></p><ul>{info_items}</ul></div>'
        html = re.sub(r'<div class="pd-short-desc">.*?</div>', new_short, html, flags=re.DOTALL, count=1)

    bc_html = cfg.get('breadcrumb_html', [brand])
    crumbs = ''.join([f'<a href="{canon}">{item}</a><span>/</span>' for item in bc_html])
    crumbs += f'<span class="current">{title}'
    html = re.sub(
        r'<nav class="pd-breadcrumb"[^>]*>.*?<span class="current">[^<]*',
        f'<nav class="pd-breadcrumb" aria-label="breadcrumb">{crumbs}',
        html, flags=re.DOTALL, count=1,
    )

    nav_cats = cfg.get('nav_categories', [brand])
    nav_links = '\n'.join([
        f'                        <a class="" href="{canon}">\n                {cat}            </a>'
        for cat in nav_cats
    ])
    html = re.sub(
        r'(<div class="mega-cats container"[^>]*>).*?(</div>\s*\n\s*<div class="mega-cats-fade")',
        rf'\1\n{nav_links}\n                    \2',
        html, flags=re.DOTALL, count=1,
    )

    if faqs:
        faq_html_items = '\n\n'.join([
            f'<div class="sgt-faq">\n<div class="sgt-question">{x["q"]}<span class="sgt-icon">▼</span></div>\n<div class="sgt-answer">{x["a"]}</div>\n</div>'
            for x in faqs
        ])
        new_faq_section = f'<h3 class="sgt-title">FAQ SEPUTARAN PEMAIN {brand}</h3>\n\n{faq_html_items}'
        html = re.sub(
            r'<h3 class="sgt-title">FAQ SEPUTARAN PEMAIN [^<]+</h3>.*?(?=<h3 class="sgt-title">REVIEW)',
            new_faq_section + '\n\n',
            html, flags=re.DOTALL, count=1,
        )

    if reviews:
        review_html = '\n\n'.join([
            f'<div class="sgt-review"><div class="sgt-name">{r["name"]}</div>{r["text"]}</div>'
            for r in reviews
        ])
        new_review_section = f'<h3 class="sgt-title">REVIEW PEMAIN {brand}</h3>\n\n{review_html}'
        html = re.sub(
            r'<h3 class="sgt-title">REVIEW PEMAIN [^<]+</h3>.*?(?=<div class="sgt-footer">)',
            new_review_section + '\n\n',
            html, flags=re.DOTALL, count=1,
        )
        rev_json = _build_review_json_ld(reviews)
        html = re.sub(
            r'"review"\s*:\s*\[\s*(?:\{.*?\}\s*,?\s*)+\]',
            f'"review": [\n          {rev_json}\n        ]',
            html, flags=re.DOTALL, count=1,
        )

    if article:
        html = re.sub(
            r'(<div class="pd-desc"|class="product-description"|class="article-body"|id="article-body")',
            article + r'\1',
            html,
            count=1,
        )

    html = re.sub(r'<div class="sgt-footer">.*?</div>', f'<div class="sgt-footer">{footer_text}</div>', html, flags=re.DOTALL, count=1)

    def replace_nav_icons(match: re.Match) -> str:
        block = match.group(0)
        return re.sub(r'(<img src=")[^"]*(")', rf'\g<1>{nav_icon}\2', block)

    html = re.sub(r'<div class="[^"]*fixed-footer[^"]*"[^>]*>.*?</div>', replace_nav_icons, html, flags=re.DOTALL, count=1)

    html = re.sub(r'Bisa ber https?://\S+ sesuai', 'Bisa berbeda sesuai', html)
    html = re.sub(r'(class="popup-footer"[^>]*>)\s*[^\n<]*<br/>', rf'\1\n                  {title}', html)
    html = re.sub(
        r'(class="topbar-left"[^>]*>)\s*[^\n<]*',
        rf'\1\n        {brand} • Platform Permainan Digital & Akses Member 24 Jam',
        html,
        count=1,
    )
    html = re.sub(r'(class="pd-title"[^>]*id="pd-title">)[^<]*(</h1>)', rf'\g<1>{h1}\2', html, count=1)
    html = re.sub(r'(id="pd-sticky-title">)[^<]*(</h2>)', rf'\g<1>{title}\2', html, count=1)
    html = re.sub(r'(<link rel="canonical"[^>]+>)\s*\1', r'\1', html)
    return html


def apply_generic_template(html: str, cfg: Dict[str, Any]) -> str:
    brand = cfg['brand']
    title = cfg['title']
    h1 = cfg.get('h1', title)
    desc = cfg.get('description', '')
    faqs = cfg.get('faq') or []
    reviews = cfg.get('reviews') or []
    article = cfg.get('article_html') or ''

    html = re.sub(r'(<meta name="description" content=")[^"]*(")', rf'\g<1>{desc}\2', html)
    html = re.sub(r'(<h1[^>]*>)[^<]*(</h1>)', rf'\g<1>{h1}\2', html, count=1, flags=re.I)

    if article:
        article_block = article if article.strip().startswith('<p') else '\n'.join(
            f'<p>{p.strip()}</p>' for p in article.split('\n') if p.strip()
        )
        if re.search(r'class="(?:product-description|article-body|pd-desc)"|id="article-body"', html, flags=re.I):
            html = re.sub(
                r'(<(?:div|section)[^>]*(?:class="(?:product-description|article-body|pd-desc)"|id="article-body")[^>]*>)',
                rf'\1\n{article_block}\n',
                html,
                count=1,
                flags=re.I,
            )
        elif re.search(r'</main>', html, flags=re.I):
            html = re.sub(r'(</main>)', f'{article_block}\n\\1', html, count=1, flags=re.I)
        elif re.search(r'</body>', html, flags=re.I):
            html = re.sub(r'(</body>)', f'{article_block}\n\\1', html, count=1, flags=re.I)

    if faqs:
        faq_block = _build_generic_faq_html(faqs, brand)
        if re.search(r'class="[^"]*faq[^"]*"', html, flags=re.I):
            html = re.sub(
                r'(<(?:section|div)[^>]*class="[^"]*faq[^"]*"[^>]*>)[\s\S]*?(</(?:section|div)>)',
                rf'\1\n{faq_block}\n\2',
                html,
                count=1,
                flags=re.I,
            )
        elif re.search(r'</main>', html, flags=re.I):
            html = re.sub(r'(</main>)', f'{faq_block}\n\\1', html, count=1, flags=re.I)
        elif re.search(r'</body>', html, flags=re.I):
            html = re.sub(r'(</body>)', f'{faq_block}\n\\1', html, count=1, flags=re.I)

    if reviews:
        rev_block = _build_generic_reviews_html(reviews, brand)
        if re.search(r'class="[^"]*review[^"]*"', html, flags=re.I):
            html = re.sub(
                r'(<(?:section|div)[^>]*class="[^"]*review[^"]*"[^>]*>)[\s\S]*?(</(?:section|div)>)',
                rf'\1\n{rev_block}\n\2',
                html,
                count=1,
                flags=re.I,
            )
        elif re.search(r'</body>', html, flags=re.I):
            html = re.sub(r'(</body>)', f'{rev_block}\n\\1', html, count=1, flags=re.I)

    return html


def apply_content_template(html: str, cfg: Dict[str, Any], template_snapshot: str) -> str:
    if is_marketplace_template(template_snapshot):
        return apply_marketplace_template(html, cfg)
    if detect_tpl_type(template_snapshot) == 'product-detail':
        return html
    return apply_generic_template(html, cfg)


def apply_cta_links(html: str, cta: str, canon: str = '', amp: str = '') -> str:
    if not cta:
        return html

    protected = {u.strip() for u in (canon, amp) if u and u.startswith('http')}

    html = html.replace('#LINKREFF', cta).replace('#linkref', cta).replace('#LINKREF', cta)

    def _swap_href(tag: str) -> str:
        m = re.search(r'href="([^"]+)"', tag, flags=re.I)
        if not m:
            return tag
        href = m.group(1).strip()
        if href.startswith('#') or href in protected:
            return tag
        if href.rstrip('/') in {p.rstrip('/') for p in protected}:
            return tag
        return re.sub(r'href="[^"]*"', f'href="{cta}"', tag, count=1, flags=re.I)

    def _anchor_label(tag: str) -> str:
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', tag)).strip().lower()

    def _is_login_daftar(tag: str) -> bool:
        label = _anchor_label(tag)
        if re.search(r'\b(login|daftar|register|sign\s*up|sign\s*in)\b', label):
            return True
        cls = re.search(r'class="([^"]+)"', tag, flags=re.I)
        if cls and re.search(r'\b(login|register|daftar|popupBtn)\b', cls.group(1), flags=re.I):
            return True
        return False

    def _rewrite_block(block: str) -> str:
        def repl_anchor(am: re.Match) -> str:
            tag = am.group(0)
            return _swap_href(tag) if _is_login_daftar(tag) else tag
        return re.sub(r'<a\b[^>]*>.*?</a>', repl_anchor, block, flags=re.I | re.S)

    for block_pat in (
        r'<div class="button-login-daftar"[^>]*>.*?</div>',
        r'<div class="buttonArea"[^>]*>.*?</div>',
        r'<div class="[^"]*fixed-footer[^"]*"[^>]*>.*?</div>',
    ):
        html = re.sub(block_pat, lambda m: _rewrite_block(m.group(0)), html, flags=re.I | re.S)

    html = re.sub(
        r'(<a[^>]*class="[^"]*\b(?:login|register|daftar|popupBtn)\b[^"]*"[^>]*href=")[^"]*(")',
        rf'\g<1>{cta}\2',
        html,
        flags=re.I,
    )
    html = re.sub(
        r'(<a[^>]*href=")[^"]*("[^>]*class="[^"]*\b(?:login|register|daftar|popupBtn)\b[^"]*")',
        rf'\g<1>{cta}\2',
        html,
        flags=re.I,
    )

    return html


CONFIG_RUNTIME_KEYS = frozenset({'template_html', '_content_meta', '_runtime_template_html'})
SECRET_CONFIG_KEYS = frozenset({
    'serpapi_key', 'serpapi_keys', 'google_cse_key', 'google_cse_cx', 'serp_enrich_enabled',
    'gsc_token', 'cf_token',
})


def resolve_template_path(name: str) -> Optional[Path]:
    name = (name or '').strip()
    if not name or name.startswith('('):
        return None
    candidates = [name, Path(name).name]
    if not name.endswith('.html'):
        candidates.append(f'{name}.html')
    seen: set = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        for folder in (CACHE_DIR, TEMPLATES_DIR, AUTOLANDING_DIR, LP_ROOT):
            p = folder / cand
            if p.is_file():
                return p
    return None


def slim_config_for_storage(cfg: Dict[str, Any], template_file: str = '') -> Dict[str, Any]:
    blocked = CONFIG_RUNTIME_KEYS | SECRET_CONFIG_KEYS
    out = {k: v for k, v in cfg.items() if k not in blocked}
    out.pop('template_html', None)
    tf = (template_file or cfg.get('template_file') or cfg.get('template') or '').strip()
    if tf and not tf.startswith('('):
        out['template_file'] = Path(tf).name
    return out


def migrate_legacy_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(cfg)
    if out.get('template_html') and not out.get('template_file'):
        slug = out.get('slug') or _slugify(out.get('brand', 'legacy'))
        fname = f'tpl_legacy_{slug}.html'
        legacy_path = CACHE_DIR / fname
        if not legacy_path.is_file():
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            legacy_path.write_text(out['template_html'], encoding='utf-8')
        out['template_file'] = fname
        del out['template_html']
    for key in SECRET_CONFIG_KEYS:
        out.pop(key, None)
    return out


def resolve_template_html(cfg: Dict[str, Any]) -> str:
    html = cfg.get('template_html') or cfg.get('_runtime_template_html') or ''
    if html:
        return html
    for key in ('template_file', 'template'):
        name = cfg.get(key) or ''
        path = resolve_template_path(name)
        if path:
            return path.read_text(encoding='utf-8')
    tpl_file = cfg.get('template') or ''
    if tpl_file:
        paths = [
            AUTOLANDING_DIR / tpl_file,
            LP_ROOT / tpl_file,
            LP_ROOT / 'lptemplate.html',
        ]
        for p in paths:
            if p.is_file():
                return p.read_text(encoding='utf-8')
    url = cfg.get('template_url') or ''
    if url:
        fetched = fetch_url(url)
        if fetched:
            return fetched
    default = AUTOLANDING_DIR / 'index.html'
    if default.is_file():
        return default.read_text(encoding='utf-8')
    legacy = LP_ROOT / 'lptemplate.html'
    if legacy.is_file():
        return legacy.read_text(encoding='utf-8')
    return ''


def _build_review_json_ld(reviews: List[Dict[str, Any]]) -> str:
    rows = []
    for r in reviews:
        rows.append(
            '{\n            "@type": "Review",\n'
            f'            "author": {{"@type": "Person", "name": "{_json_esc(r["name"])}"}},\n'
            f'            "datePublished": "{r.get("date", datetime.now().strftime("%Y-%m-%d"))}",\n'
            f'            "reviewBody": "{_json_esc(r["text"])}",\n'
            f'            "name": "{_json_esc(r["name"])}",\n'
            '            "reviewRating": {\n'
            '              "@type": "Rating",\n'
            f'              "ratingValue": "{int(r.get("rating", 5))}",\n'
            '              "bestRating": "5",\n'
            '              "worstRating": "1"\n'
            '            }\n          }'
        )
    return ',\n          '.join(rows)


def _visible_text(html: str) -> str:
    text = re.sub(r'<script[\s\S]*?</script>', ' ', html, flags=re.I)
    text = re.sub(r'<style[\s\S]*?</style>', ' ', text, flags=re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def extract_template_snippets(template_html: str) -> List[str]:
    snippets: List[str] = []
    for pat in (
        r'<meta name="description" content="([^"]{30,})"',
        r'<title>([^<]{15,})</title>',
        r'"description"\s*:\s*"([^"]{30,})"',
    ):
        for m in re.finditer(pat, template_html, flags=re.I):
            snippets.append(m.group(1).strip())
    m = re.search(r'<h1[^>]*>([^<]{20,})', template_html, flags=re.I)
    if m:
        snippets.append(re.sub(r'\s+', ' ', m.group(1)).strip())
    return list(dict.fromkeys(snippets))


def audit_plagiarism_bleed(html: str, template_html: str, cfg: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    if not template_html:
        return warnings
    visible = _normalize_compare_text(_visible_text(html), cfg.get('brand', ''))
    user_desc = _normalize_compare_text(cfg.get('description', ''), cfg.get('brand', ''))
    for snippet in extract_template_snippets(template_html):
        norm = _normalize_compare_text(snippet, cfg.get('brand', ''))
        if len(norm) < 24:
            continue
        if norm == user_desc:
            continue
        chunk = norm[:48]
        if chunk and chunk in visible:
            warnings.append('Cuplikan teks template masih ada di output — risiko duplikat/plagiarism')
            break
    source = cfg.get('source_brand', '')
    brand = cfg.get('brand', '')
    if source and brand and source.upper() != brand.upper() and count_term(html, source):
        warnings.append(f'Brand template "{source}" masih tersisa — output belum fresh')
    old_urls = [u for u in extract_template_urls(template_html) if u.startswith('http')]
    protected = {
        u.rstrip('/') for u in (
            cfg.get('canonical'), cfg.get('amp_url'), cfg.get('cta'),
            cfg.get('logo'), cfg.get('banner'), cfg.get('favicon'),
        ) if u and str(u).startswith('http')
    }
    for u in old_urls:
        if u.rstrip('/') not in protected and count_term(html, u) > 2:
            warnings.append(f'URL template lama masih {count_term(html, u)}x — ganti ke canonical user')
            break
    return warnings


def audit_spam_signals(html: str, cfg: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    brand = cfg.get('brand', '')
    if brand:
        for para in re.findall(r'<p[^>]*>([\s\S]*?)</p>', html, flags=re.I):
            plain = re.sub(r'<[^>]+>', ' ', para)
            if plain.lower().count(brand.lower()) > BRAND_MAX_PER_PARAGRAPH:
                warnings.append(
                    f'Brand "{brand}" >{BRAND_MAX_PER_PARAGRAPH}x dalam satu paragraf — risiko keyword stuffing',
                )
                break
        visible = _visible_text(html)
        if visible and count_term(html, brand) / max(len(visible), 1) > BRAND_DENSITY_WARN:
            warnings.append(
                f'Kepadatan brand tinggi ({count_term(html, brand)}x) — pastikan teks natural untuk Google',
            )
    parsed = parse_keyword_focus(cfg.get('keyword_focus', ''))
    for term in parsed.get('all', [])[:3]:
        n = count_term(_visible_text(html), term)
        if n > KEYWORD_MAX_OCCURRENCES:
            warnings.append(f'Keyword "{term}" muncul {n}x — kurangi agar tidak dianggap spam')
    return warnings


def enforce_user_metadata(html: str, cfg: Dict[str, Any]) -> str:
    brand = cfg['brand']
    title = cfg['title']
    desc = cfg['description']
    canon = cfg.get('canonical', '')
    amp = cfg.get('amp_url', '')
    banner = cfg.get('banner', '')
    favicon = cfg.get('favicon', '')
    html = re.sub(r'<title>[^<]*</title>', f'<title>{title}</title>', html, count=1)
    for pat, val in (
        (r'(<meta name="description" content=")[^"]*(")', desc),
        (r'(<meta property="og:description" content=")[^"]*(")', desc),
        (r'(<meta name="twitter:description" content=")[^"]*(")', desc),
        (r'(<meta property="og:title" content=")[^"]*(")', title),
        (r'(<meta name="twitter:title" content=")[^"]*(")', title),
        (r'(<meta property="og:site_name" content=")[^"]*(")', brand),
        (r'(<meta property="og:image:alt" content=")[^"]*(")', title),
    ):
        html = re.sub(pat, rf'\g<1>{val}\2', html)
    if canon and canon != '#LINKCANNO':
        html = re.sub(r'(<link rel="canonical" href=")[^"]*(")', rf'\1{canon}\2', html)
        html = re.sub(r'(<meta property="og:url" content=")[^"]*(")', rf'\1{canon}\2', html)
        html = re.sub(r'hreflang="id-id"[^>]+href="[^"]*"', f'hreflang="id-id" href="{canon}"', html)
        html = re.sub(r'hreflang="id"[^>]+href="[^"]*"', f'hreflang="id" href="{canon}"', html)
    if amp and amp != '#LINKAMP':
        html = re.sub(r'(<link rel="amphtml" href=")[^"]*(")', rf'\1{amp}\2', html)
    if banner:
        html = re.sub(r'(<meta property="og:image" content=")[^"]*(")', rf'\1{banner}\2', html)
        html = re.sub(r'(<meta name="twitter:image" content=")[^"]*(")', rf'\1{banner}\2', html)
    if favicon:
        html = re.sub(
            r'(<link[^>]+rel="(?:shortcut )?icon"[^>]+href=")[^"]*(")',
            rf'\g<1>{favicon}\2',
            html,
            flags=re.I,
        )
    return html


def finalize_user_rewrite(html: str, cfg: Dict[str, Any], template_html: str) -> str:
    protected = {
        u.rstrip('/')
        for u in (
            cfg.get('canonical'), cfg.get('amp_url'), cfg.get('cta'),
            cfg.get('logo'), cfg.get('banner'), cfg.get('favicon'),
        )
        if u and str(u).startswith('http')
    }
    canon = cfg.get('canonical', '')
    if template_html and canon and canon != '#LINKCANNO':
        for u in extract_template_urls(template_html):
            if u.startswith('http') and u.rstrip('/') not in protected:
                html = _swap_url_variants(html, u, canon)
    for snippet in extract_template_snippets(template_html):
        if snippet and snippet != cfg.get('description') and snippet != cfg.get('title'):
            html = html.replace(snippet, cfg.get('description', ''))
    html = enforce_user_metadata(html, cfg)
    source = cfg.get('source_brand', '')
    if source:
        html = replace_source_brand(html, cfg['brand'], source)
    return html


def generate_seo_report(
    cfg: Dict[str, Any],
    html: str,
    warnings: List[str],
    template_html: str = '',
    amp_html: str = '',
) -> Dict[str, Any]:
    audit = audit_keyword_coverage(
        cfg.get('brand', ''),
        cfg.get('keyword_focus', ''),
        title=cfg.get('title', ''),
        description=cfg.get('description', ''),
        faqs=cfg.get('faq') or [],
        reviews=cfg.get('reviews') or [],
        article_html=cfg.get('article_html') or '',
    )
    gsc_ready = bool(cfg.get('gsc_token') or get_global_config().get('gsc_token'))
    checklist = build_compliance_checklist(html, cfg, amp_html=amp_html)
    checklist['no_template_brand'] = not (cfg.get('source_brand') and count_term(html, cfg.get('source_brand', '')))
    if amp_html:
        checklist['amp_valid_structure'] = (
            'FAQPage' not in amp_html
            and 'max-image-preview:large' in amp_html
            and 'WebPage' in amp_html
        )
    return {
        'brand': cfg.get('brand'),
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'source_brand': cfg.get('source_brand', ''),
        'keyword_score': f'{audit["score"]}/{audit["max_score"]}',
        'keyword_audit': audit,
        'brand_mentions': count_term(html, cfg.get('brand', '')),
        'canonical': cfg.get('canonical'),
        'amp_url': cfg.get('amp_url'),
        'gsc_token_set': gsc_ready,
        'warnings': warnings,
        'gsc_checklist': checklist,
        'content_meta': cfg.get('_content_meta') or {},
    }


def gsc_checklist_failures(report: Dict[str, Any]) -> List[str]:
    checklist = report.get('gsc_checklist') or {}
    failed: List[str] = []
    for key in GSC_GATE_REQUIRED_KEYS:
        if not checklist.get(key):
            failed.append(GSC_GATE_LABELS.get(key, key))
    return failed


def evaluate_gsc_gate(report: Dict[str, Any], mode: str = 'warn') -> Tuple[bool, List[str]]:
    if mode == 'off':
        return True, []
    failures = gsc_checklist_failures(report)
    return len(failures) == 0, failures


def sync_configs_from_brand_links(template_file: str = '', force: bool = False) -> List[Path]:
    data = load_brand_links()
    brands = data.get('brands') or {}
    global_cfg = get_global_config()
    paths: List[Path] = []
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    for slug, entry in brands.items():
        if not isinstance(entry, dict):
            continue
        brand = (entry.get('brand') or slug).upper()
        cfg: Dict[str, Any] = {
            'brand': brand,
            'slug': slug,
            'keyword_focus': entry.get('keyword_focus') or f'{brand.lower()} platform permainan digital',
            'canonical': entry.get('linkcanno') or entry.get('canonical') or '#LINKCANNO',
            'amp_url': entry.get('linkamp') or entry.get('amp_url') or '#LINKAMP',
            'cta': entry.get('linkref') or entry.get('cta') or '',
            'logo': entry.get('logo', ''),
            'banner': entry.get('banner', ''),
            'output_folder': entry.get('output_folder') or default_output_folder(slug),
            'short_info': {'minimal_deposit': entry.get('minimal_deposit', 'Rp10.000')},
        }
        if global_cfg.get('favicon'):
            cfg['favicon'] = global_cfg['favicon']
        if global_cfg.get('gsc_token'):
            cfg['gsc_token'] = global_cfg['gsc_token']
        if global_cfg.get('cf_token'):
            cfg['cf_token'] = global_cfg['cf_token']
        tf = template_file or entry.get('template_file') or ''
        if tf:
            cfg['template_file'] = Path(tf).name
        path = CONFIGS_DIR / f'{slug}.json'
        if path.is_file() and not force:
            paths.append(path)
            continue
        slim = slim_config_for_storage(cfg, tf)
        path.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding='utf-8')
        paths.append(path)
    return paths


def batch_deploy(
    config_sources: Optional[List[Any]] = None,
    *,
    write_amp: bool = True,
    write_seo_files: bool = True,
    fresh_content: bool = True,
    gsc_gate: str = 'warn',
    sync_brands: bool = False,
    template_file: str = '',
) -> Dict[str, Any]:
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    if sync_brands:
        sync_configs_from_brand_links(template_file=template_file)

    paths: List[Path] = []
    if config_sources:
        for item in config_sources:
            if isinstance(item, (str, Path)):
                paths.append(Path(item))
            elif isinstance(item, dict):
                slug = item.get('slug') or _slugify(item.get('brand', 'brand'))
                p = CONFIGS_DIR / f'{slug}.json'
                slim = slim_config_for_storage(item, item.get('template_file', ''))
                p.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding='utf-8')
                paths.append(p)
    else:
        paths = sorted(CONFIGS_DIR.glob('*.json'))

    items: List[Dict[str, Any]] = []
    seen_titles: Dict[str, str] = {}
    seen_descs: Dict[str, str] = {}
    ok_count = 0
    blocked_count = 0
    error_count = 0

    for path in paths:
        brand = path.stem
        entry: Dict[str, Any] = {
            'config': path.name,
            'brand': brand,
            'status': 'pending',
        }
        try:
            cfg = migrate_legacy_config(json.loads(path.read_text(encoding='utf-8')))
            cfg = merge_brand_defaults(cfg)
            brand = cfg.get('brand', brand)
            entry['brand'] = brand
            result = deploy(
                cfg,
                write_amp=write_amp,
                write_seo_files=write_seo_files,
                fresh_content=fresh_content,
                gsc_gate=gsc_gate,
            )
            report = result.get('seo_report_data') or {}
            title = (result.get('cfg') or {}).get('title') or cfg.get('title', '')
            desc = (result.get('cfg') or {}).get('description') or cfg.get('description', '')
            dup_notes: List[str] = []
            if title:
                if title in seen_titles:
                    dup_notes.append(f'title duplikat dengan {seen_titles[title]}')
                else:
                    seen_titles[title] = brand
            if desc:
                if desc in seen_descs:
                    dup_notes.append(f'description duplikat dengan {seen_descs[desc]}')
                else:
                    seen_descs[desc] = brand
            gate_info = report.get('gsc_gate') or {}
            entry.update({
                'status': 'ok',
                'path': result['paths'].get('index'),
                'keyword_score': report.get('keyword_score'),
                'gsc_failures': gate_info.get('failures') or [],
                'warnings': result.get('warnings') or [],
                'duplicate_notes': dup_notes,
            })
            ok_count += 1
        except GSCGateError as exc:
            entry.update({'status': 'gsc_blocked', 'error': str(exc)})
            blocked_count += 1
        except Exception as exc:
            entry.update({'status': 'error', 'error': str(exc)})
            error_count += 1
        items.append(entry)

    summary = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'gsc_gate': gsc_gate,
        'total': len(items),
        'ok': ok_count,
        'gsc_blocked': blocked_count,
        'errors': error_count,
        'items': items,
    }
    write_text(BATCH_REPORT_PATH, json.dumps(summary, ensure_ascii=False, indent=2))
    summary['report_path'] = str(BATCH_REPORT_PATH)
    return summary


def _strip_product_offers(html: str) -> str:
    html = re.sub(
        r',?\s*"offers"\s*:\s*\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}',
        '',
        html,
        flags=re.S,
    )
    html = re.sub(r',(\s*[\]}])', r'\1', html)
    return html


def apply_seo_fixes(html: str, cfg: Dict[str, Any]) -> str:
    brand = cfg['brand']
    title = cfg['title']
    desc = cfg['description']
    canon = cfg.get('canonical', '#LINKCANNO')
    amp = cfg.get('amp_url', '#LINKAMP')
    favicon = (cfg.get('favicon') or '').strip()
    gsc = cfg.get('gsc_token', get_global_config()['gsc_token'])
    kw = cfg.get('keyword_focus', brand)

    html = re.sub(r'<meta name="robots"[^>]*>', f'<meta name="robots" content="{ROBOTS_CONTENT}">', html, count=1)
    if 'name="robots"' not in html:
        html = html.replace('<head>', f'<head>\n<meta name="robots" content="{ROBOTS_CONTENT}">', 1)

    html = re.sub(r'<meta name="google-site-verification"[^>]*>\s*', '', html)
    gsc_val = gsc or '#KODEGSC'
    html = re.sub(
        r'(<meta name="robots")',
        f'<meta name="google-site-verification" content="{gsc_val}" />\n    \\1',
        html,
        count=1,
    )

    html = re.sub(r'hreflang="id-id"[^>]+href="[^"]*"', f'hreflang="id-id" href="{canon}"', html)
    html = re.sub(r'hreflang="id"[^>]+href="[^"]*"', f'hreflang="id" href="{canon}"', html)
    html = re.sub(r'(<link rel="canonical" href=")[^"]*(")', rf'\1{canon}\2', html, count=1)
    html = re.sub(r'(<link rel="amphtml" href=")[^"]*(")', rf'\1{amp}\2', html, count=1)
    html = re.sub(r'(<meta property="og:url" content=")[^"]*(")', rf'\1{canon}\2', html, count=1)
    html = re.sub(r'(<meta property="og:image" content=")[^"]*(")', rf'\1{cfg.get("banner", "")}\2', html)
    html = re.sub(r'(<meta name="twitter:image" content=")[^"]*(")', rf'\1{cfg.get("banner", "")}\2', html)
    html = re.sub(r'(<meta property="og:title" content=")[^"]*(")', rf'\1{title}\2', html)
    html = re.sub(r'(<meta name="twitter:title" content=")[^"]*(")', rf'\1{title}\2', html)

    if re.search(r'<meta name="keywords"', html, flags=re.I):
        html = re.sub(r'(<meta name="keywords" content=")[^"]*(")', rf'\1{kw}\2', html, count=1)
    else:
        html = re.sub(
            r'(<meta name="description"[^>]+>)',
            rf'\1\n    <meta name="keywords" content="{kw}">',
            html,
            count=1,
        )

    html = ensure_hreflang(html, canon)
    html = ensure_og_type_website(html)

    if favicon:
        html = re.sub(
            r'<link rel="(?:shortcut )?icon"[^>]+>',
            f'<link rel="icon" type="image/x-icon" href="{favicon}" />\n<link rel="shortcut icon" href="{favicon}" type="image/x-icon">',
            html,
            count=1,
        )

    html = re.sub(r'<!--\s*Cloudflare Web Analytics\s*-->.*?<!--\s*End Cloudflare Web Analytics\s*-->', '', html, flags=re.I | re.S)
    html = re.sub(r'\s*<script defer src="https://static\.cloudflareinsights\.com/beacon\.min\.js[^>]*></script>\s*', '\n', html, flags=re.I)
    cf_token = cfg.get('cf_token', get_global_config()['cf_token'])
    if cf_token:
        cf = (
            f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
            f'data-cf-beacon=\'{{"token": "{cf_token}"}}\'></script>'
        )
        if 'cloudflareinsights.com/beacon.min.js' not in html and '</body>' in html.lower():
            html = re.sub(r'</body>', f'\n{cf}\n</body>', html, count=1, flags=re.I)

    logo_url = (cfg.get('logo') or '').strip()
    org_json = build_organization_schema(brand, canon, logo_url, desc)
    org = f'<script type="application/ld+json">\n{org_json}\n</script>'
    html = re.sub(
        r'<script type="application/ld\+json">\s*\{[^<]*"@type"\s*:\s*"Organization"[\s\S]*?</script>',
        org,
        html,
        count=1,
        flags=re.I,
    )
    if '"@type": "Organization"' not in html and '"@type":"Organization"' not in html:
        html = re.sub(r'</head>', f'{org}\n</head>', html, count=1, flags=re.I)

    html = _strip_product_offers(html)

    if amp and amp != canon:
        html = re.sub(rf'href="{re.escape(amp)}"(?=[^>]*>[^<]*{re.escape(brand)})', f'href="{canon}"', html)

    html = re.sub(r'(<meta itemprop="shippingDetails"[^>]+>\s*)+', '', html)
    html = re.sub(r'(<meta itemprop="hasMerchantReturnPolicy"[^>]+>\s*)+', '', html)

    return html


def build_landing_html(cfg: Dict[str, Any]) -> str:
    c = resolve_template_html(cfg)
    if not c:
        raise ValueError('Template HTML kosong — isi template_url, template file, atau template_html.')

    template_snapshot = c
    cfg = enrich_config(cfg, c)
    brand = cfg['brand']
    title = cfg['title']
    desc = cfg['description']
    canon = cfg.get('canonical', '#LINKCANNO')
    amp = cfg.get('amp_url', '#LINKAMP')
    cta = cfg['cta']
    banner = cfg.get('banner', '')
    logo = cfg.get('logo', '')
    favicon = (cfg.get('favicon') or '').strip()
    nav_icon = cfg.get('bottom_nav_icon', favicon)

    source_brand = detect_source_brand(template_snapshot)
    cfg['source_brand'] = source_brand

    c = re.sub(r'<title>[^<]+</title>', f'<title>{title}</title>', c, count=1)
    c = re.sub(r'(<meta name="description" content=")[^"]*(")', rf'\g<1>{desc}\2', c)
    c = re.sub(r'(<meta property="og:description" content=")[^"]*(")', rf'\g<1>{desc}\2', c)
    c = re.sub(r'(<meta name="twitter:description" content=")[^"]*(")', rf'\g<1>{desc}\2', c)
    c = re.sub(r'(<meta property="og:title" content=")[^"]*(")', rf'\g<1>{title}\2', c)
    c = re.sub(r'(<meta name="twitter:title" content=")[^"]*(")', rf'\g<1>{title}\2', c)
    c = re.sub(r'(<meta property="og:image:alt" content=")[^"]*(")', rf'\g<1>{title}\2', c)
    c = re.sub(r'(<meta property="og:site_name" content=")[^"]*(")', rf'\g<1>{brand}\2', c, count=1)

    if is_marketplace_template(template_snapshot):
        cfg_for_tpl = dict(cfg)
        cfg_for_tpl['source_brand'] = source_brand
        c = apply_marketplace_template(c, cfg_for_tpl)
    elif detect_tpl_type(template_snapshot) == 'generic':
        c = apply_generic_template(c, cfg)

    c = apply_cta_links(c, cta, canon, amp)
    c = apply_template_url_swaps(c, template_snapshot, canon, amp)
    c = apply_user_assets(c, template_snapshot, banner, logo, favicon, source_brand)
    c = replace_source_brand(c, brand, source_brand)

    c = re.sub(
        r'    <link rel="preconnect" href="https://www\.googletagmanager\.com" crossorigin>\n'
        r'    <script async src="https://www\.googletagmanager\.com/gtag/js[^"]*"[^>]*></script>\n'
        r'    <script[^>]*>window\.dataLayer.*?</script>\n',
        '', c, flags=re.DOTALL,
    )

    c = re.sub(
        r'"@type":\s*"WebSite".*?"potentialAction":\s*\{[^}]+\}\s*\}',
        f'"@type": "WebSite",\n    "@id": "{canon}#website",\n    "url": "{canon}",\n    "name": "{brand}",\n    "description": "{_json_esc(desc[:120])}",\n    "inLanguage": "id-ID",\n    "potentialAction": {{\n      "@type": "SearchAction",\n      "target": "{canon}?q={{search_term_string}}",\n      "query-input": "required name=search_term_string"\n    }}\n  }}',
        c, flags=re.DOTALL, count=1,
    )

    if detect_tpl_type(template_snapshot) == 'product-detail':
        c = apply_product_detail_template(c, cfg)

    bc_schema = cfg.get('breadcrumb_schema', [])
    if bc_schema:
        items_json = ',\n      '.join([
            f'{{\n        "@type": "ListItem",\n        "position": {i + 1},\n        "name": "{x["name"]}",\n        "item": "{canon}"\n      }}'
            for i, x in enumerate(bc_schema)
        ])
        new_bc = f'"@context": "https://schema.org",\n    "@type": "BreadcrumbList",\n    "itemListElement": [\n      {items_json}\n    ]\n  }}'
        if '"@graph"' in c:
            c = _patch_schema_graph(c, brand, canon, desc, bc_schema, cfg.get('faq') or [])
        else:
            c = re.sub(
                r'"@context":\s*"https://schema\.org",\s*"@type":\s*"BreadcrumbList".*?\}\s*\][\s\n]*\}',
                new_bc, c, flags=re.DOTALL, count=1,
            )

    faqs = cfg.get('faq', [])
    if faqs:
        faq_entities = ',\n      '.join([
            f'{{\n        "@type": "Question",\n        "name": "{_json_esc(x["q"])}",\n        "acceptedAnswer": {{\n          "@type": "Answer",\n          "text": "{_json_esc(x["a"])}"\n        }}\n      }}'
            for x in faqs
        ])
        new_faq = f'"@context": "https://schema.org",\n    "@type": "FAQPage",\n    "mainEntity": [\n      {faq_entities}\n    ]\n  }}'
        if '"@graph"' in c:
            c = _patch_schema_graph(c, brand, canon, desc, bc_schema, faqs)
        else:
            c = re.sub(
                r'"@context":\s*"https://schema\.org",\s*"@type":\s*"FAQPage".*?\}\s*\][\s\n]*\}',
                new_faq, c, flags=re.DOTALL, count=1,
            )
    elif bc_schema and '"@graph"' in c:
        c = _patch_schema_graph(c, brand, canon, desc, bc_schema, [])

    c = finalize_user_rewrite(c, cfg, template_snapshot)
    c = apply_seo_fixes(c, cfg)
    h1_text = cfg.get('h1') or gen_h1_text(brand, parse_keyword_focus(cfg.get('keyword_focus', ''))['primary'])
    c = enforce_single_h1(c, h1_text)
    c = limit_article_canonical_anchors(c, canon, 1)
    c = strip_production_comments(c)
    c, sanitize_notes = sanitize_client_urls(c, cfg)
    if sanitize_notes:
        cfg.setdefault('_sanitize_notes', sanitize_notes)
    return c


def list_amp_templates() -> List[str]:
    if not AMP_TEMPLATE_DIR.is_dir():
        return [AMP_TEMPLATE_DEFAULT]
    names = sorted(
        p.name for p in AMP_TEMPLATE_DIR.glob('*.html')
        if p.is_file() and not p.name.startswith('_')
    )
    return names or [AMP_TEMPLATE_DEFAULT]


def resolve_amp_template_path(name: str = '') -> Path:
    chosen = (name or AMP_TEMPLATE_DEFAULT).strip()
    if not chosen.endswith('.html'):
        chosen = f'{chosen}.html'
    path = AMP_TEMPLATE_DIR / Path(chosen).name
    if path.is_file():
        return path
    fallback = AMP_TEMPLATE_DIR / AMP_TEMPLATE_DEFAULT
    if fallback.is_file():
        return fallback
    raise FileNotFoundError(f'AMP template tidak ditemukan: {chosen}')


def _amp_title_tail(title: str, brand: str) -> str:
    t = (title or '').strip()
    b = (brand or '').strip()
    if not t:
        return ''
    if b and t.upper().startswith(b.upper()):
        rest = t[len(b):].lstrip(' |—:-')
        return f' | {rest}' if rest else ''
    for sep in (' | ', ' — ', ' - '):
        if sep in t:
            head, tail = t.split(sep, 1)
            if b and head.strip().upper() == b.upper():
                return f' | {tail.strip()}'
            return f' | {tail.strip()}'
    return f' | {t}'


def build_amp_html(cfg: Dict[str, Any], template_html: str = '') -> str:
    cfg = enrich_config(cfg, template_html)
    tpl_path = resolve_amp_template_path(cfg.get('amp_template', AMP_TEMPLATE_DEFAULT))
    html = tpl_path.read_text(encoding='utf-8')
    favicon = (cfg.get('favicon') or '').strip()
    brand = cfg['brand']
    title = cfg['title']
    desc = cfg['description']
    canon = cfg.get('canonical', '#LINKCANNO')
    cta = cfg.get('cta', '')
    logo = cfg.get('logo', '')
    banner = cfg.get('banner', '')
    h1 = cfg.get('h1', gen_h1_text(brand, parse_keyword_focus(cfg.get('keyword_focus', ''))['primary']))
    parsed = parse_keyword_focus(cfg.get('keyword_focus', ''))

    palette = extract_css_palette(template_html) if template_html else extract_css_palette('')
    font = extract_font_family(template_html) if template_html else 'system-ui'
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        logo_fut = pool.submit(fetch_image_dimensions, logo)
        banner_fut = pool.submit(fetch_image_dimensions, banner)
        logo_w, logo_h = logo_fut.result()
        banner_w, banner_h = banner_fut.result()
    promo = gen_amp_promo(brand, parsed['primary'], cfg.get('short_info', {}).get('minimal_deposit', 'Rp10.000'))
    ticker = gen_keyword_ticker(parsed.get('all', []), brand)
    h1_tail = h1.replace(brand, '').strip(' |—:-')
    if h1_tail.lower().startswith(brand.lower()):
        h1_tail = h1_tail[len(brand):].strip(' |—:-')
    webpage_schema = build_amp_webpage_schema(brand, canon, title, desc)
    footer_tagline = f'Portal {parsed["primary"]} & layanan member'

    repl = {
        '#TITLE': title,
        '#DESCRIPTION': desc,
        '#BRAND': brand,
        '#LINKCANNO': canon,
        '#LINKREFF': cta,
        '#LOGO': logo,
        '#BANNER': banner,
        '#FAVICON': favicon,
        '#AMP_ROBOTS': amp_robots_content(),
        '#WEBPAGE_SCHEMA': webpage_schema,
        '#H1_TAIL': h1_tail or 'Portal Digital Terpercaya',
        '#TAGLINE': f'{brand} — akses member stabil & transaksi cepat',
        '#TICKER': ticker,
        '#PROMO': promo,
        '#LOGO_W': str(logo_w),
        '#LOGO_H': str(logo_h),
        '#BANNER_W': str(banner_w),
        '#BANNER_H': str(banner_h),
        '#BANNER_ALT': f'Banner promosi {brand} {parsed["primary"]}',
        '#YEAR': str(datetime.now().year),
        '#FOOTER_TAGLINE': footer_tagline,
        '#BODY_BG': palette['body_bg'],
        '#BODY_BG2': palette['body_bg2'],
        '#CARD_BG': palette['card_bg'],
        '#CARD_BG2': palette['card_bg2'],
        '#ACCENT': palette['accent'],
        '#ACCENT_DARK': palette['accent_dark'],
        '#BORDER_COLOR': palette['border'],
        '#TEXT_COLOR': palette['text'],
        '#BTN_TEXT': palette['btn_text'],
        '#FONT_FAMILY': font,
    }
    for key, val in sorted(repl.items(), key=lambda x: len(x[0]), reverse=True):
        html = html.replace(key, val or '')

    source = cfg.get('source_brand') or (detect_source_brand(template_html) if template_html else '')
    if source:
        html = replace_source_brand(html, brand, source)

    html = strip_production_comments(html, keep_amp_boilerplate=True)
    html, _ = sanitize_client_urls(html, cfg)
    return html


def generate_sitemap_xml(canonical: str, amp_url: str) -> str:
    today = datetime.now().strftime('%Y-%m-%d')
    canon = canonical if canonical.endswith('/') else canonical + '/'
    amp = amp_url.rstrip('/') if amp_url else ''
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f'  <url>\n    <loc>{canon}</loc>\n    <lastmod>{today}</lastmod>\n    <priority>1.0</priority>\n  </url>',
    ]
    if amp:
        lines.append(f'  <url>\n    <loc>{amp}</loc>\n    <lastmod>{today}</lastmod>\n    <priority>0.8</priority>\n  </url>')
    lines.append('</urlset>\n')
    return '\n'.join(lines)


def generate_robots_txt(canonical: str) -> str:
    if '://' in canonical:
        base = canonical.split('/')[0] + '//' + canonical.split('/')[2]
    else:
        base = canonical
    return f'User-agent: *\nAllow: /\n\nSitemap: {base.rstrip("/")}/sitemap.xml\n'


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def count_term(content: str, term: str) -> int:
    return len(re.findall(re.escape(term), content))


def validate_output(html: str, cfg: Dict[str, Any], template_html: str = '') -> List[str]:
    warnings: List[str] = []
    brand = cfg.get('brand', '')
    source = cfg.get('source_brand', '')
    if source and brand and source.upper() != brand.upper():
        n = count_term(html, source)
        if n:
            warnings.append(f'nama brand template "{source}" masih {n}x — cek replace')
    warnings.extend(audit_plagiarism_bleed(html, template_html, cfg))
    warnings.extend(audit_spam_signals(html, cfg))
    for junk in _TEMPLATE_JUNK_MARKERS:
        if junk.lower() in html.lower():
            warnings.append(f'konten template legacy terdeteksi: {junk}')
    if len(cfg.get('title', '')) > title_max_len() or len(cfg.get('title', '')) < title_min_len():
        warnings.append(f'title {len(cfg["title"])} char — wajib {title_min_len()}-{title_max_len()}')
    if title_has_banned_word(cfg.get('title', '')):
        warnings.append('title mengandung kata terlarang (slot/gacor/maxwin/judi/togel)')
    if len(cfg.get('description', '')) > desc_max_len() or len(cfg.get('description', '')) < desc_min_len():
        warnings.append(f'description {len(cfg["description"])} char — wajib {desc_min_len()}-{desc_max_len()}')
    warnings.extend(audit_h1(html, brand))
    warnings.extend(audit_link_policy(html, cfg.get('canonical', ''), cfg.get('cta', '')))
    warnings.extend(audit_images(html))
    warnings.extend(audit_faq_schema_sync(html, cfg.get('faq') or []))
    for note in cfg.get('_sanitize_notes') or []:
        warnings.append(note)
    for vendor in ('ik.imagekit.io/leonz', 'referral.example.com', 'example.com/testbrand'):
        if vendor.split('/')[0] in html.lower() and not any(
            vendor in (cfg.get(k) or '') for k in ('logo', 'banner', 'favicon', 'cta', 'canonical', 'amp_url')
        ):
            warnings.append(f'URL vendor terdeteksi di output: {vendor.split("/")[0]} — cek template/konfigurasi')
            break
    for phrase in audit_ai_phrases(_visible_text(html)):
        warnings.append(f'Frasa AI generik terdeteksi: "{phrase}"')
    if '<!--' in html:
        warnings.append('Masih ada komentar HTML di output produksi')
    if canon := cfg.get('canonical'):
        if count_term(html, canon) < 1:
            warnings.append('canonical URL tidak ditemukan di output')
    if brand and count_term(html, brand) < 3:
        warnings.append(f'brand {brand} jarang muncul')
    faqs = cfg.get('faq') or []
    if len(faqs) < FAQ_PICK_COUNT:
        warnings.append(f'FAQ hanya {len(faqs)} item — risiko thin content')
    kw_parsed = parse_keyword_focus(cfg.get('keyword_focus', ''))
    if kw_parsed['all'] and faqs:
        kw_hits = sum(
            1 for f in faqs
            if _text_has_user_keyword(f.get('q', '') + ' ' + f.get('a', ''), kw_parsed)
        )
        if kw_hits < min(3, len(faqs)):
            warnings.append(f'FAQ kurang selaras keyword ({kw_hits}/{len(faqs)} item menyebut fokus)')
    reviews = cfg.get('reviews') or []
    if len(reviews) < REVIEW_PICK_COUNT:
        warnings.append(f'review hanya {len(reviews)} item — risiko thin content')
    article = cfg.get('article_html') or ''
    para_count = len([p for p in article.split('\n') if p.strip()])
    if para_count < ARTICLE_MIN_PARAS:
        warnings.append(f'artikel hanya {para_count} paragraf — minimum {ARTICLE_MIN_PARAS}')
    reservations = get_content_reservations(exclude_brand=brand)
    meta = cfg.get('_content_meta') or {}
    overlap = set(meta.get('faq_ids', [])) & reservations.get('faq_ids', set())
    if overlap:
        warnings.append(f'{len(overlap)} FAQ ID bentrok dengan brand lain — perlu pool lebih besar')
    audit = audit_keyword_coverage(
        brand,
        cfg.get('keyword_focus', ''),
        title=cfg.get('title', ''),
        description=cfg.get('description', ''),
        faqs=faqs,
        reviews=reviews,
        article_html=article,
    )
    if audit['score'] < 4:
        warnings.append(
            f'Cakupan keyword rendah ({audit["score"]}/{audit["max_score"]}) — regenerasi konten sebelum deploy',
        )
    if not audit['title_ok']:
        warnings.append(f'Title belum optimal untuk keyword "{audit["primary"]}"')
    if not audit['desc_ok']:
        warnings.append(f'Deskripsi belum menyebut keyword fokus "{audit["primary"]}"')
    return warnings


def deploy(
    cfg: Dict[str, Any],
    *,
    write_amp: bool = True,
    write_seo_files: bool = True,
    fresh_content: bool = True,
    gsc_gate: str = 'warn',
) -> Dict[str, Any]:
    cfg = migrate_legacy_config(merge_brand_defaults(cfg))
    template_html = resolve_template_html(cfg)
    if not template_html:
        raise ValueError('Template tidak ditemukan.')
    cfg['source_brand'] = detect_source_brand(template_html)

    missing = [k for k in ('brand', 'cta', 'canonical', 'amp_url', 'logo', 'banner') if not cfg.get(k)]
    if missing:
        raise ValueError(f'Field wajib dari input user belum lengkap: {", ".join(missing)}')

    pre_warnings: List[str] = []
    if not cfg.get('favicon'):
        g_fav = get_global_config().get('favicon')
        if g_fav:
            cfg['favicon'] = g_fav
        else:
            pre_warnings.append('Favicon kosong — isi di Default Global atau field favicon')

    manual_title = cfg.pop('_manual_title', None)
    manual_desc = cfg.pop('_manual_description', None)
    keep_reviews = cfg.pop('_keep_reviews', False)
    keep_faq = cfg.pop('_keep_faq', False)

    if fresh_content:
        if not keep_faq:
            cfg.pop('faq', None)
        for key in ('breadcrumb_html', 'breadcrumb_schema', 'article_html'):
            cfg.pop(key, None)
        if not keep_reviews:
            cfg.pop('reviews', None)
        if not manual_title:
            cfg.pop('title', None)
        if not manual_desc:
            cfg.pop('description', None)

    cfg = enrich_config(cfg, template_html, vary=fresh_content)
    if manual_title:
        _dep_val = (cfg.get('short_info') or {}).get('minimal_deposit', 'Rp10.000')
        cfg['title'] = sanitize_title_neutral(_trim_title(manual_title), cfg.get('brand', ''), _dep_val)
    if manual_desc:
        cfg['description'] = _trim_desc(manual_desc)
    result_html = build_landing_html(cfg)
    amp_html = ''
    if write_amp:
        amp_html = build_amp_html(cfg, template_html)

    warnings = pre_warnings + validate_output(result_html, cfg, template_html)
    if amp_html and 'FAQPage' in amp_html:
        warnings.append('AMP mengandung FAQPage schema — dilarang')
    report = generate_seo_report(cfg, result_html, warnings, template_html, amp_html=amp_html)
    gate_ok, gate_failures = evaluate_gsc_gate(report, gsc_gate)
    report['gsc_gate'] = {
        'mode': gsc_gate,
        'passed': gate_ok,
        'failures': gate_failures,
    }
    if gsc_gate == 'block' and gate_failures:
        raise GSCGateError(
            f'GSC gate: build ditolak — {", ".join(gate_failures)}',
        )
    if gate_failures and gsc_gate == 'warn':
        warnings = warnings + [f'GSC checklist: {", ".join(gate_failures)}']

    out_base = resolve_output_base(cfg.get('output_folder', ''), cfg.get('slug', 'brand'))
    index_path = out_base / 'index.html'
    write_text(index_path, result_html)

    paths: Dict[str, str] = {'index': str(index_path)}

    if write_amp and amp_html:
        amp_path = out_base / 'amp' / 'index.html'
        write_text(amp_path, amp_html)
        paths['amp'] = str(amp_path)

    if write_seo_files:
        canon = cfg.get('canonical', '#LINKCANNO')
        amp_url = cfg.get('amp_url', '#LINKAMP')
        sm_path = out_base / 'sitemap.xml'
        rb_path = out_base / 'robots.txt'
        write_text(sm_path, generate_sitemap_xml(canon, amp_url))
        write_text(rb_path, generate_robots_txt(canon))
        paths['sitemap'] = str(sm_path)
        paths['robots'] = str(rb_path)

    report_path = out_base / 'seo-report.json'
    write_text(report_path, json.dumps(report, ensure_ascii=False, indent=2))
    paths['seo_report'] = str(report_path)
    record_brand_content(cfg.get('brand', ''), cfg.pop('_content_meta', {}))
    upsert_brand_links(cfg)
    stored_cfg = slim_config_for_storage(cfg, cfg.get('template_file', ''))
    return {
        'cfg': stored_cfg,
        'html': result_html,
        'paths': paths,
        'warnings': warnings,
        'seo_report_data': report,
        'size': len(result_html),
        'brand_count': count_term(result_html, cfg['brand']),
    }

gen_desc = gen_description
_count = count_term

import customtkinter as ctk
from PIL import Image
ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('dark-blue')

BG = '#0f1115'
PANEL = '#151820'
CARD = '#1a1f28'
SURFACE = '#222833'
INPUT = '#12161d'
BORDER = '#2a3140'
BORDER_SUBTLE = '#232833'
ACCENT = '#c9a24b'
ACCENT2 = '#dcb869'
ACCENT_SOFT = '#2a2418'
TEXT = '#eef1f6'
MUTED = '#9aa3b2'
LABEL = '#c5ccd8'
SUBTITLE = '#aeb7c7'
DIM = '#8a939f'
PLACEHOLDER = '#7d8794'
GREEN = '#6fbf9a'
RED = '#d4847a'
AMBER = '#d4ad5b'
BLUE = '#7eb0df'
TEAL = '#5fb3a3'
VIOLET = '#a894d4'

FT = ('Segoe UI', 12)
FT_B = ('Segoe UI', 12, 'bold')
FT_H = ('Segoe UI Semibold', 13)
FT_TITLE = ('Segoe UI Semibold', 19)
FT_I = ('Segoe UI', 12)
FT_LOG = ('Cascadia Mono', 10)
FT_MONO = ('Cascadia Mono', 10)

ENTRY_H = 36
RADIUS = 12
RADIUS_SM = 8
PAD = 14
INSET = 14
FIELD_GAP = 8
SIDEBAR_W = 640
LOG_MIN_W = 360
WIN_W = 1417
WIN_H = 837
WIN_MIN_W = 1100
WIN_MIN_H = 720
TOPBAR_H = 72
BTN_STYLE_PRIMARY = {
    'fg_color': ACCENT, 'hover_color': ACCENT2,
    'text_color': '#171a20', 'border_color': ACCENT2,
}
BTN_STYLE_SECONDARY = {
    'fg_color': '#252219', 'hover_color': '#2e2a22',
    'text_color': ACCENT2, 'border_color': '#4a4030',
}
BTN_STYLE_SLATE = {
    'fg_color': '#1c2330', 'hover_color': '#242c3c',
    'text_color': '#9ec5e8', 'border_color': '#2e3d52',
}
BTN_STYLE_TEAL = {
    'fg_color': '#1a2628', 'hover_color': '#223032',
    'text_color': '#7ec4b8', 'border_color': '#2a4540',
}
BTN_STYLE_VIOLET = {
    'fg_color': '#211e2c', 'hover_color': '#2a2638',
    'text_color': '#b8a8d8', 'border_color': '#3a3450',
}
BTN_STYLE_EMERALD = {
    'fg_color': '#1a2520', 'hover_color': '#223028',
    'text_color': '#8ec4a8', 'border_color': '#2a4035',
}
BTN_STYLE_SOFT = {
    'fg_color': SURFACE, 'hover_color': '#2a3140',
    'text_color': TEXT, 'border_color': BORDER,
}
BTN_STYLE_NEUTRAL = {
    'fg_color': '#1e232d', 'hover_color': '#262c38',
    'text_color': MUTED, 'border_color': BORDER_SUBTLE,
}
BTN_STYLE_DANGER = {
    'fg_color': '#2a2224', 'hover_color': '#342a2c',
    'text_color': '#c89890', 'border_color': '#453032',
}

BTN_VARIANTS: Dict[str, Dict[str, str]] = {
    'primary': BTN_STYLE_PRIMARY,
    'secondary': BTN_STYLE_SECONDARY,
    'slate': BTN_STYLE_SLATE,
    'teal': BTN_STYLE_TEAL,
    'violet': BTN_STYLE_VIOLET,
    'emerald': BTN_STYLE_EMERALD,
    'soft': BTN_STYLE_SOFT,
    'neutral': BTN_STYLE_NEUTRAL,
    'danger': BTN_STYLE_DANGER,
    'info': BTN_STYLE_SLATE,
    'blue': BTN_STYLE_SLATE,
    'green': BTN_STYLE_EMERALD,
    'amber': BTN_STYLE_SECONDARY,
}

BASE_DIR = AUTOLANDING_DIR
TEMPLATES_DIR = BASE_DIR / 'templates'
CACHE_DIR = TEMPLATES_DIR / 'cache'
ASSETS_DIR = BASE_DIR / 'assets'
LEONZ_LOGO_WEBP = ASSETS_DIR / 'leonz_logo.webp'
LEONZ_LOGO_PNG = ASSETS_DIR / 'leonz_logo.png'
LEONZ_LOGO = LEONZ_LOGO_WEBP
LEONZ_ICON = ASSETS_DIR / 'leonz_icon.ico'

DEFAULT_BRAND = 'BRANDMU'
DEFAULT_SLUG = 'brandmu'

for _dir in (CONFIGS_DIR, LANDING_DIR, TEMPLATES_DIR, CACHE_DIR, ASSETS_DIR, CONTENT_DIR, CONTENT_CACHE_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

ensure_brand_links_file()
ensure_build_mode_file()
ensure_serp_secrets_file()
try:
    migrate_serp_from_brand_links(load_brand_links())
except Exception:
    pass

WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040


def _asset_urls(slug: str) -> Dict[str, str]:
    favicon = get_global_config().get('favicon', '')
    return {
        'cta': '',
        'logo': '',
        'banner': '',
        'favicon': favicon,
    }


def _is_valid_url(value: str) -> bool:
    if not value:
        return False
    return bool(re.match(r'^https?://[^\s]+\.[^\s]+', value.strip(), flags=re.I))


def _truncate_middle(text: str, max_len: int = 44) -> str:
    if len(text) <= max_len:
        return text
    keep = max_len - 1
    front = keep // 2
    back = keep - front
    return f'{text[:front]}…{text[-back:]}'


def _card(parent: Any) -> ctk.CTkFrame:
    frame = ctk.CTkFrame(
        parent, fg_color=CARD, corner_radius=RADIUS,
        border_width=1, border_color=BORDER_SUBTLE,
    )
    frame.grid_columnconfigure(0, weight=1)
    return frame


def _sec_label(
    parent: Any, row: int, title: str, *,
    subtitle: str = '', accent: str = ACCENT,
) -> None:
    wrap = ctk.CTkFrame(parent, fg_color='transparent')
    wrap.grid(row=row, column=0, sticky='ew', padx=INSET, pady=(INSET, 6))
    wrap.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(wrap, text=title, font=FT_H, text_color=TEXT, anchor='w').grid(
        row=0, column=0, sticky='w',
    )
    if subtitle:
        ctk.CTkLabel(wrap, text=subtitle, font=FT, text_color=SUBTITLE, anchor='w').grid(
            row=1, column=0, sticky='w', pady=(3, 0),
        )
    line_row = 2 if subtitle else 1
    ctk.CTkFrame(wrap, height=2, fg_color=accent, corner_radius=1).grid(
        row=line_row, column=0, sticky='ew', pady=(8, 0),
    )


def _field_label(parent: Any, row: int, text: str) -> None:
    _lbl(parent, text).grid(
        row=row, column=0, sticky='ew', padx=INSET, pady=(FIELD_GAP, 4),
    )


def _field_widget(parent: Any, row: int, widget: Any, *, bottom: int = FIELD_GAP) -> None:
    widget.grid(row=row, column=0, sticky='ew', padx=INSET, pady=(0, bottom))


def _lbl(parent: Any, text: str, **kwargs: Any) -> ctk.CTkLabel:
    defaults: Dict[str, Any] = dict(font=FT, text_color=LABEL, anchor='w')
    defaults.update(kwargs)
    return ctk.CTkLabel(parent, text=text, **defaults)


def _entry(parent: Any, placeholder: str = '', **kwargs: Any) -> ctk.CTkEntry:
    defaults: Dict[str, Any] = dict(
        placeholder_text=placeholder, font=FT_I, fg_color=INPUT, border_color=BORDER,
        border_width=1, text_color=TEXT, placeholder_text_color=PLACEHOLDER, height=ENTRY_H,
        corner_radius=RADIUS,
    )
    defaults.update(kwargs)
    return ctk.CTkEntry(parent, **defaults)


def _btn(parent: Any, text: str, command: Any, variant: str = 'neutral', **kwargs: Any) -> ctk.CTkButton:
    style = BTN_VARIANTS.get(variant, BTN_VARIANTS['neutral'])
    border_w = 0 if variant == 'primary' else 1
    defaults: Dict[str, Any] = dict(
        text=text, command=command, font=FT_B, height=34, corner_radius=RADIUS_SM,
        fg_color=style['fg_color'], hover_color=style['hover_color'],
        text_color=style['text_color'], border_color=style.get('border_color', BORDER),
        border_width=border_w,
    )
    defaults.update(kwargs)
    return ctk.CTkButton(parent, **defaults)


def _path_badge(parent: Any, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent, text=text, font=FT_MONO, text_color=ACCENT2, fg_color=SURFACE,
        corner_radius=6, anchor='w', padx=8, height=26,
    )


def _status_pill(parent: Any, text: str, color: str = MUTED) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent, text=text, font=FT, text_color=color, fg_color=SURFACE,
        corner_radius=10, padx=10, height=22,
    )


def _ensure_brand_assets() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_leonz_logo_path() -> Optional[Path]:
    for candidate in (LEONZ_LOGO_WEBP, LEONZ_LOGO_PNG, AUTOLANDING_DIR / 'leonz_logo.webp'):
        if candidate.is_file():
            return candidate
    return None


def _schedule_window_icon(win: Any, is_root: bool = True) -> None:
    def _apply() -> None:
        try:
            if LEONZ_ICON.is_file():
                win.iconbitmap(str(LEONZ_ICON))
        except Exception:
            pass
        if sys.platform.startswith('win') and LEONZ_ICON.is_file():
            try:
                hwnd = win.winfo_id()
                user32 = ctypes.windll.user32
                hicon = user32.LoadImageW(
                    0, str(LEONZ_ICON), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE,
                )
                if hicon:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
            except Exception:
                pass

    for delay in (0, 80, 200, 450, 800):
        win.after(delay, _apply)


def _load_brand_pil(url: str, timeout: int = 5) -> Optional[Image.Image]:
    if not url:
        return None
    try:
        if url.startswith('http'):
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; LPBuilder/2.0)'})
            with urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            return Image.open(BytesIO(data)).convert('RGBA')
        path = Path(url)
        if path.is_file():
            return Image.open(path).convert('RGBA')
    except Exception:
        return None
    return None


def _pil_to_ctk_logo(img: Optional[Image.Image], height: int = 40) -> Optional[ctk.CTkImage]:
    if img is None:
        return None
    try:
        w, h = img.size
        if h <= 0 or w <= 0:
            return None
        ratio = height / float(h)
        size = (max(1, int(w * ratio)), height)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception:
        return None


def _sep(parent: Any, row: int) -> None:
    ctk.CTkFrame(parent, height=1, fg_color=BORDER).grid(
        row=row, column=0, sticky='ew', padx=INSET, pady=(6, 0),
    )


class LPWidget(ctk.CTk):

    def __init__(self) -> None:
        super().__init__()
        self.withdraw()

        self._ui_built = False
        self._brand_job: Optional[str] = None
        self._kw_job: Optional[str] = None
        self._building = False
        self._template_html_cache = ''
        self._template_name = ''
        self._source_brand = ''
        self._keep_reviews = False
        self._preview_reviews: List[Dict[str, Any]] = []
        self._preview_faq: List[Dict[str, str]] = []
        self._preview_article = ''
        self._keep_faq = False
        self._faq_job: Optional[str] = None
        self._seo_job: Optional[str] = None
        self._seo_regen_nonce = 0
        self._content_regen_nonce = 0
        self._header_logo_img: Optional[ctk.CTkImage] = None
        self._logo_preview_img: Optional[ctk.CTkImage] = None
        self._output_path_full = str(resolve_output_base('', DEFAULT_SLUG) / 'index.html')

        self.title('Landing Page Builder')
        self.geometry(f'{WIN_W}x{WIN_H}')
        self.minsize(WIN_MIN_W, WIN_MIN_H)
        self.configure(fg_color=BG)

        _ensure_brand_assets()
        self._header_logo_img = self._load_header_logo()
        self._build_ui()
        _schedule_window_icon(self, is_root=True)
        self.after(0, self._center_window)

        self._refresh_tpl_list()
        self.after(100, self._load_global_form_defaults)
        self.after(400, self._load_content_async)
        self.after(600, lambda: self._log('Landing Page Builder siap — fetch template, isi brand, build.', 'head'))

    def _center_window(self) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - WIN_W) // 2)
        y = max(0, (sh - WIN_H) // 2)
        self.geometry(f'{WIN_W}x{WIN_H}+{x}+{y}')
        self.deiconify()
        self.lift()
        self.focus_force()

    def _load_header_logo(self) -> Optional[ctk.CTkImage]:
        logo_path = _resolve_leonz_logo_path()
        if not logo_path:
            return None
        img = _load_brand_pil(str(logo_path))
        return _pil_to_ctk_logo(img, height=38)

    def _build_ui(self) -> None:
        if self._ui_built:
            return
        self._ui_built = True

        self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_W)
        self.grid_columnconfigure(1, weight=0, minsize=1)
        self.grid_columnconfigure(2, weight=1, minsize=LOG_MIN_W)
        self.grid_rowconfigure(1, weight=1)

        self._build_topbar()

        left = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        left.grid(row=1, column=0, sticky='nsew')
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1, minsize=240)
        left.grid_rowconfigure(1, weight=0)

        ctk.CTkFrame(self, width=1, fg_color=BORDER_SUBTLE, corner_radius=0).grid(
            row=1, column=1, sticky='ns',
        )

        right = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        right.grid(row=1, column=2, sticky='nsew')
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(
            left, fg_color=PANEL, segmented_button_fg_color=SURFACE,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT2,
            segmented_button_unselected_color=SURFACE,
            segmented_button_unselected_hover_color=BORDER,
            text_color=TEXT, corner_radius=RADIUS,
        )
        self.tabview.grid(row=0, column=0, sticky='nsew', padx=(12, 12), pady=(10, 6))
        self.tabview.add('Utama')
        self.tabview.add('Lanjutan')

        tab_utama = self.tabview.tab('Utama')
        tab_lanjutan = self.tabview.tab('Lanjutan')
        for tab in (tab_utama, tab_lanjutan):
            tab.grid_rowconfigure(0, weight=1)
            tab.grid_columnconfigure(0, weight=1)

        scroll_utama = self._make_tab_scroll(tab_utama)
        scroll_lanjutan = self._make_tab_scroll(tab_lanjutan)
        self._build_tab_utama(scroll_utama)
        self._build_tab_lanjutan(scroll_lanjutan)
        self._build_action_footer(left)
        self._build_right_panel(right)

    def _make_tab_scroll(self, tab: Any) -> ctk.CTkScrollableFrame:
        scroll = ctk.CTkScrollableFrame(
            tab, fg_color=PANEL,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=ACCENT,
            corner_radius=0,
        )
        scroll.grid(row=0, column=0, sticky='nsew')
        scroll.grid_columnconfigure(0, weight=1)
        return scroll

    def _build_action_footer(self, parent: Any) -> None:
        foot = ctk.CTkFrame(
            parent, fg_color=SURFACE, corner_radius=0,
            border_width=1, border_color=BORDER_SUBTLE,
        )
        foot.grid(row=1, column=0, sticky='ew')
        foot.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(foot, fg_color='transparent')
        inner.grid(row=0, column=0, sticky='ew', padx=INSET, pady=(10, 12))
        inner.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(
            inner, fg_color=INPUT, progress_color=ACCENT, corner_radius=RADIUS_SM, height=5,
        )
        self.progress.set(0)
        self.progress.grid(row=0, column=0, sticky='ew', pady=(0, 8))

        actions = ctk.CTkFrame(inner, fg_color='transparent')
        actions.grid(row=1, column=0, sticky='ew')
        actions.grid_columnconfigure(5, weight=0)
        for col in (1, 2, 3, 4):
            actions.grid_columnconfigure(col, weight=1, uniform='act')

        btn_h = 34

        self.lbl_build_status = _status_pill(actions, 'Siap', GREEN)
        self.lbl_build_status.grid(row=0, column=0, sticky='w', padx=(0, 8))

        _btn(actions, 'Preview', self._preview_config, variant='slate', height=btn_h).grid(
            row=0, column=1, padx=(0, 4), sticky='ew',
        )
        _btn(actions, 'Buka HTML', self._open_preview_html, variant='teal', height=btn_h).grid(
            row=0, column=2, padx=4, sticky='ew',
        )
        _btn(actions, 'Muat', self._load_config_dialog, variant='violet', height=btn_h).grid(
            row=0, column=3, padx=4, sticky='ew',
        )
        _btn(actions, 'Reset', self._reset_form, variant='danger', height=btn_h).grid(
            row=0, column=4, padx=(4, 8), sticky='ew',
        )
        _btn(
            actions, 'Build Landing Page', self._start_build,
            variant='primary', height=btn_h, width=152,
        ).grid(row=0, column=5, sticky='e')

        batch_row = ctk.CTkFrame(inner, fg_color='transparent')
        batch_row.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        batch_row.grid_columnconfigure(1, weight=1)
        _btn(
            batch_row, 'Batch Build (semua config)', self._start_batch_build,
            variant='secondary', height=30,
        ).grid(row=0, column=0, sticky='w')
        _btn(
            batch_row, 'Sync Config dari brand-links', self._sync_configs_from_brands,
            variant='neutral', height=30,
        ).grid(row=0, column=1, padx=(8, 0), sticky='w')

    def _build_topbar(self) -> None:
        top = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=TOPBAR_H)
        top.grid(row=0, column=0, columnspan=3, sticky='ew')
        top.grid_propagate(False)
        top.grid_rowconfigure(0, weight=1)
        top.grid_columnconfigure(0, weight=1)

        body = ctk.CTkFrame(top, fg_color='transparent')
        body.grid(row=0, column=0, sticky='nsew', padx=0, pady=0)
        body.grid_columnconfigure(1, weight=1)

        brand_wrap = ctk.CTkFrame(body, fg_color='transparent')
        brand_wrap.grid(row=0, column=0, sticky='w', padx=(16, 8), pady=10)

        if self._header_logo_img is not None:
            ctk.CTkLabel(brand_wrap, text='', image=self._header_logo_img).pack(side='left', padx=(0, 12))

        title_col = ctk.CTkFrame(brand_wrap, fg_color='transparent')
        title_col.pack(side='left')
        ctk.CTkLabel(title_col, text='Landing Page Builder', font=FT_TITLE, text_color=TEXT).pack(anchor='w')
        ctk.CTkLabel(
            title_col, text='Fetch template · isi brand · build otomatis ke folder landing/',
            font=FT, text_color=SUBTITLE, anchor='w', justify='left',
        ).pack(anchor='w', pady=(2, 0))

        status_wrap = ctk.CTkFrame(body, fg_color='transparent')
        status_wrap.grid(row=0, column=2, sticky='e', padx=(8, 16), pady=10)
        self.lbl_ready = _status_pill(status_wrap, '● Ready', GREEN)
        self.lbl_ready.pack(side='right', padx=(8, 0))
        mode_color = ACCENT2 if is_developer_mode() else TEAL
        self.lbl_build_mode = _status_pill(status_wrap, build_mode_label(), mode_color)
        self.lbl_build_mode.pack(side='right')

        ctk.CTkFrame(top, height=1, fg_color=BORDER_SUBTLE, corner_radius=0).place(
            relx=0, rely=1.0, relwidth=1, anchor='sw',
        )

    def _build_tab_utama(self, tab: Any) -> None:
        for i, fn in enumerate((
            self._section_template,
            self._section_brand,
            self._section_link,
            self._section_asset,
        )):
            card = _card(tab)
            card.grid(row=i, column=0, sticky='ew', padx=6, pady=(4 if i == 0 else 0, 8))
            fn(card, ACCENT if i % 2 == 0 else ACCENT2)

    def _build_tab_lanjutan(self, tab: Any) -> None:
        for i, fn in enumerate((
            self._section_keyword,
            self._section_global,
            self._section_content_pack,
            self._section_seo,
            self._section_faq,
            self._section_reviews,
            self._section_amp,
        )):
            card = _card(tab)
            card.grid(row=i, column=0, sticky='ew', padx=6, pady=(4 if i == 0 else 0, 8))
            fn(card, ACCENT if i % 2 == 0 else ACCENT2)

    def _section_template(self, p: Any, accent: str = BLUE) -> None:
        _sec_label(p, 0, 'Template', subtitle='Fetch dari URL atau pilih file HTML lokal', accent=accent)

        _field_label(p, 1, 'URL template')
        self.e_url = _entry(p, 'https://contoh.com/landing-page.html')
        _field_widget(p, 2, self.e_url)

        btn_row = ctk.CTkFrame(p, fg_color='transparent')
        btn_row.grid(row=3, column=0, sticky='ew', padx=INSET, pady=(0, FIELD_GAP))
        btn_row.grid_columnconfigure((0, 1), weight=1)
        _btn(btn_row, 'Fetch Template', self._fetch_tpl, variant='primary').grid(
            row=0, column=0, padx=(0, 5), sticky='ew',
        )
        _btn(btn_row, 'Buka File Lokal', self._pick_local_tpl, variant='violet').grid(
            row=0, column=1, padx=(5, 0), sticky='ew',
        )

        _field_label(p, 4, 'Template aktif')
        self.cmb_tpl = ctk.CTkComboBox(
            p, values=['(fetch URL atau pilih file)'], font=FT_I,
            fg_color=INPUT, border_color=BORDER, border_width=1, text_color=TEXT,
            button_color=BORDER, button_hover_color=ACCENT,
            dropdown_fg_color=SURFACE, dropdown_text_color=TEXT,
            height=ENTRY_H, corner_radius=RADIUS,
            command=lambda _choice=None: self._on_tpl_selected(),
        )
        _field_widget(p, 5, self.cmb_tpl, bottom=INSET)

        self.lbl_tpl_status = _status_pill(p, 'belum ada template', SUBTITLE)
        self.lbl_tpl_status.grid(row=6, column=0, sticky='w', padx=INSET, pady=(0, 4))
        self.lbl_source_brand = _status_pill(p, 'Brand template: —', SUBTITLE)
        self.lbl_source_brand.grid(row=7, column=0, sticky='w', padx=INSET, pady=(0, INSET))

    def _section_brand(self, p: Any, accent: str = ACCENT) -> None:
        _sec_label(p, 0, 'Brand', subtitle='Ketik nama brand — lokasi landing bisa disesuaikan', accent=accent)

        _field_label(p, 1, 'Nama brand (huruf kapital)')
        brand_row = ctk.CTkFrame(p, fg_color='transparent')
        brand_row.grid(row=2, column=0, sticky='ew', padx=INSET, pady=(0, FIELD_GAP))
        brand_row.grid_columnconfigure(0, weight=1)
        self.e_brand = _entry(brand_row, DEFAULT_BRAND)
        self.e_brand.grid(row=0, column=0, sticky='ew', padx=(0, 8))
        self.e_brand.insert(0, DEFAULT_BRAND)
        self.e_brand.bind('<KeyRelease>', self._schedule_brand_change)
        _btn(brand_row, 'Simpan Brand', self._save_brand_dialog, variant='secondary', width=112, height=ENTRY_H).grid(
            row=0, column=1, sticky='e', padx=(8, 0),
        )

        _field_label(p, 3, 'Lokasi folder landing')
        folder_row = ctk.CTkFrame(p, fg_color='transparent')
        folder_row.grid(row=4, column=0, sticky='ew', padx=INSET, pady=(0, FIELD_GAP))
        folder_row.grid_columnconfigure(0, weight=1)
        self.e_folder = _entry(folder_row, default_output_folder(DEFAULT_SLUG))
        self.e_folder.grid(row=0, column=0, sticky='ew', padx=(0, 8))
        self.e_folder.insert(0, default_output_folder(DEFAULT_SLUG))
        self.e_folder.bind('<KeyRelease>', lambda _e: self._update_path_preview())
        _btn(folder_row, 'Pilih', self._pick_output_folder, variant='violet', width=72, height=ENTRY_H).grid(
            row=0, column=1, sticky='e',
        )

        path_row = ctk.CTkFrame(p, fg_color='transparent')
        path_row.grid_columnconfigure(0, weight=1)
        self.lbl_path = _path_badge(path_row, _truncate_middle(str(resolve_output_base('', DEFAULT_SLUG) / 'index.html')))
        self.lbl_path.grid(row=0, column=0, sticky='ew')
        _btn(path_row, 'Buka', self._open_output_folder, variant='emerald', width=56, height=26).grid(
            row=0, column=1, padx=(8, 0),
        )
        _btn(path_row, 'Salin', self._copy_output_path, variant='neutral', width=56, height=26).grid(
            row=0, column=2, padx=(8, 0),
        )

    def _section_link(self, p: Any, accent: str = TEAL) -> None:
        _sec_label(
            p, 0, 'Link & URL',
            subtitle='CTA referral wajib diisi manual — dipasang ke tombol Login/Daftar saat build',
            accent=accent,
        )

        _field_label(p, 1, 'Link referral / CTA (wajib)')
        self.e_cta = _entry(p, 'https://… — URL referral untuk tombol Login & Daftar')
        _field_widget(p, 2, self.e_cta)

        _field_label(p, 3, 'Canonical (#LINKCANNO)')
        self.e_canon = _entry(p, '#LINKCANNO')
        _field_widget(p, 4, self.e_canon)

        _field_label(p, 5, 'AMP URL (#LINKAMP)')
        self.e_amp = _entry(p, '#LINKAMP')
        _field_widget(p, 6, self.e_amp, bottom=INSET)

    def _section_asset(self, p: Any, accent: str = VIOLET) -> None:
        _sec_label(
            p, 0, 'Asset Gambar',
            subtitle='URL publik HTTPS — logo untuk header, banner untuk OG/social (1200×630)',
            accent=accent,
        )

        _field_label(p, 1, 'Logo URL')
        self.e_logo = _entry(p, 'https://…/logo.png — logo brand, PNG/WebP')
        _field_widget(p, 2, self.e_logo)
        self.e_logo.bind('<FocusOut>', lambda _e: self._refresh_brand_logo_preview())

        _field_label(p, 3, 'Banner URL')
        self.e_banner = _entry(p, 'https://…/banner.png — hero & og:image')
        _field_widget(p, 4, self.e_banner, bottom=FIELD_GAP)

        preview_wrap = ctk.CTkFrame(p, fg_color=INPUT, corner_radius=RADIUS_SM, height=72)
        preview_wrap.grid(row=5, column=0, sticky='ew', padx=INSET, pady=(0, INSET))
        preview_wrap.grid_propagate(False)
        preview_wrap.grid_columnconfigure(0, weight=1)
        self.lbl_logo_preview = ctk.CTkLabel(
            preview_wrap, text='Pratinjau logo', font=FT, text_color=SUBTITLE,
        )
        self.lbl_logo_preview.grid(row=0, column=0, pady=12)

    def _section_keyword(self, p: Any, accent: str = AMBER) -> None:
        _sec_label(
            p, 0, 'Keyword & Deposit',
            subtitle='Keyword 1 = target ranking · sisanya variasi semantik · mengontrol FAQ intent & cakupan SEO',
            accent=accent,
        )

        _field_label(p, 1, 'Keyword fokus (pisah koma)')
        self.e_kw = _entry(p, 'slot gacor, link alternatif, deposit murah')
        _field_widget(p, 2, self.e_kw)
        self.e_kw.bind('<KeyRelease>', self._on_keyword_changed)

        _field_label(p, 3, 'Minimal deposit')
        self.e_dep = _entry(p, 'Rp10.000')
        _field_widget(p, 4, self.e_dep, bottom=INSET)
        self.e_dep.insert(0, 'Rp10.000')
        self.e_dep.bind('<KeyRelease>', self._on_deposit_changed)

    def _section_global(self, p: Any, accent: str = VIOLET) -> None:
        _sec_label(
            p, 0, 'Default Global',
            subtitle='Isi dari dashboard masing-masing — simpan ke brand-links.json agar dipakai ulang',
            accent=accent,
        )

        _field_label(p, 1, 'Google Search Console')
        self.e_gsc = _entry(p, 'Token meta tag dari GSC → Settings → Ownership verification', show='•')
        _field_widget(p, 2, self.e_gsc)

        _field_label(p, 3, 'Cloudflare Analytics')
        self.e_cf = _entry(p, 'Token beacon dari Cloudflare → Web Analytics', show='•')
        _field_widget(p, 4, self.e_cf)

        _field_label(p, 5, 'Favicon global')
        self.e_favicon = _entry(p, 'URL favicon client — kosongkan jika belum ada')
        _field_widget(p, 6, self.e_favicon)
        self.e_favicon.bind('<FocusOut>', lambda _e: self._refresh_favicon_preview())

        fav_preview_wrap = ctk.CTkFrame(p, fg_color=INPUT, corner_radius=RADIUS_SM, height=56)
        fav_preview_wrap.grid(row=7, column=0, sticky='ew', padx=INSET, pady=(0, FIELD_GAP))
        fav_preview_wrap.grid_propagate(False)
        self.lbl_favicon_preview = ctk.CTkLabel(
            fav_preview_wrap, text='Pratinjau favicon client', font=FT, text_color=SUBTITLE,
        )
        self.lbl_favicon_preview.grid(row=0, column=0, pady=10)

        _field_label(p, 8, 'Bottom nav icon')
        self.e_nav = _entry(p, 'Kosongkan = pakai favicon global')
        _field_widget(p, 9, self.e_nav, bottom=FIELD_GAP)

        btn_row = ctk.CTkFrame(p, fg_color='transparent')
        btn_row.grid(row=10, column=0, sticky='ew', padx=INSET, pady=(0, INSET))
        _btn(btn_row, 'Simpan Default Global', self._save_global_config, variant='secondary', height=30).pack(side='left')

    def _section_content_pack(self, p: Any, accent: str = BLUE) -> None:
        _sec_label(
            p, 0, 'Bank Konten',
            subtitle='pack.json + enrich Google otomatis — lihat content/CONTENT.md',
            accent=accent,
        )

        self.lbl_content_status = ctk.CTkLabel(
            p, text='Memuat info pack…', font=FT, text_color=SUBTITLE, anchor='w', justify='left',
        )
        self.lbl_content_status.grid(row=1, column=0, sticky='ew', padx=INSET, pady=(FIELD_GAP, 4))

        _field_label(p, 2, 'Remote pack URL (raw GitHub, kosong = lokal)')
        self.e_content_remote = _entry(
            p, 'https://raw.githubusercontent.com/leonzdigital/builder/main/content/pack.json',
        )
        _field_widget(p, 3, self.e_content_remote)

        ttl_row = ctk.CTkFrame(p, fg_color='transparent')
        ttl_row.grid(row=4, column=0, sticky='ew', padx=INSET)
        ttl_row.grid_columnconfigure(1, weight=1)
        _field_label(ttl_row, 0, 'Cache TTL (jam)')
        self.e_content_ttl = _entry(ttl_row, '24')
        self.e_content_ttl.grid(row=0, column=1, sticky='ew', padx=(8, 0))

        btn_row = ctk.CTkFrame(p, fg_color='transparent')
        btn_row.grid(row=5, column=0, sticky='ew', padx=INSET, pady=(FIELD_GAP, 6))
        btn_row.grid_columnconfigure((0, 1), weight=1)
        _btn(btn_row, 'Simpan Manifest', self._save_content_manifest, variant='secondary', height=30).grid(
            row=0, column=0, padx=(0, 5), sticky='ew',
        )
        _btn(btn_row, 'Muat Ulang Bank Konten', self._refresh_content, variant='primary', height=30).grid(
            row=0, column=1, padx=(5, 0), sticky='ew',
        )

        self._section_content_serp_status(p)
        self.after(150, self._load_content_manifest_form)

    def _section_content_serp_status(self, p: Any) -> None:
        _sep(p, 6)
        _sec_label(
            p, 7, 'Enrich Google',
            subtitle='Key dari secrets/serp-keys.json — otomatis, tanpa input di GUI',
            accent=TEAL,
        )

        self.lbl_serp_status = ctk.CTkLabel(
            p, text='Memuat status enrich…', font=FT, text_color=SUBTITLE, anchor='w', justify='left',
        )
        self.lbl_serp_status.grid(row=8, column=0, sticky='ew', padx=INSET, pady=(FIELD_GAP, 4))

        self.var_serp_enrich = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            p, text='Aktifkan enrich Google saat generate konten',
            variable=self.var_serp_enrich, font=FT, text_color=TEXT,
            fg_color=ACCENT, hover_color=ACCENT2, checkmark_color=INPUT,
            border_color=BORDER, corner_radius=4,
            command=self._on_serp_enrich_toggle,
        ).grid(row=9, column=0, sticky='w', padx=INSET, pady=(0, 4))

        serp_btn = ctk.CTkFrame(p, fg_color='transparent')
        serp_btn.grid(row=10, column=0, sticky='ew', padx=INSET, pady=(FIELD_GAP, INSET))
        serp_btn.grid_columnconfigure((0, 1), weight=1)
        _btn(serp_btn, 'Preview Enrich Keyword', self._preview_serp_enrich, variant='teal', height=30).grid(
            row=0, column=0, padx=(0, 5), sticky='ew',
        )
        _btn(serp_btn, 'Muat Ulang Enrich Cache', self._reload_serp_cache, variant='secondary', height=30).grid(
            row=0, column=1, padx=(5, 0), sticky='ew',
        )

    def _load_content_manifest_form(self) -> None:
        if not hasattr(self, 'e_content_remote'):
            return
        manifest = load_content_manifest()
        self.e_content_remote.delete(0, 'end')
        self.e_content_remote.insert(0, manifest.get('remote_url') or '')
        self.e_content_ttl.delete(0, 'end')
        self.e_content_ttl.insert(0, str(int(manifest.get('cache_ttl_hours') or 24)))
        self._load_serp_status()
        self._update_content_status_label()

    def _load_serp_status(self) -> None:
        if not hasattr(self, 'lbl_serp_status'):
            return
        summary = serp_secrets_summary()
        g = get_global_config()
        if hasattr(self, 'var_serp_enrich'):
            self.var_serp_enrich.set(bool(g.get('serp_enrich_enabled', True)))
        if summary['configured']:
            parts = [f"● Enrich siap · {summary['key_count']} SerpAPI key"]
            if summary.get('has_cse'):
                parts.append('CSE')
            parts.append('rotasi aktif')
            text = ' · '.join(parts)
            color = GREEN if summary['enabled'] else AMBER
        else:
            text = 'Enrich belum dikonfigurasi — isi secrets/serp-keys.json (lihat secrets/serp-keys.example.json)'
            color = AMBER
        self.lbl_serp_status.configure(text=text, text_color=color)

    def _on_serp_enrich_toggle(self) -> None:
        enabled = bool(self.var_serp_enrich.get()) if hasattr(self, 'var_serp_enrich') else True
        try:
            set_serp_enrich_enabled(enabled)
            clear_serp_pool_cache()
            self._load_serp_status()
            state = 'aktif' if enabled else 'nonaktif'
            self._log(f'Enrich Google {state} (disimpan ke secrets/serp-keys.json).', 'ok')
        except OSError as exc:
            self._log(f'Gagal simpan toggle enrich: {exc}', 'err')

    def _reload_serp_cache(self) -> None:
        clear_serp_pool_cache()
        self._log('Cache enrich direset — build berikutnya fetch ulang jika perlu.', 'ok')

    def _update_content_status_label(self) -> None:
        if not hasattr(self, 'lbl_content_status'):
            return
        info = content_pack_summary()
        remote = (info.get('remote_url') or '').strip()
        remote_hint = 'remote GitHub' if remote else 'content/pack.json'
        self.lbl_content_status.configure(
            text=(
                f"Pack v{info['pack_version']} · sumber: {info['source']} · "
                f"{info['faq_total']} entri FAQ · via {remote_hint}"
            ),
            text_color=GREEN if info['source'] in ('local', 'remote', 'cache') else SUBTITLE,
        )

    def _save_content_manifest(self) -> None:
        remote = self.e_content_remote.get().strip() if hasattr(self, 'e_content_remote') else ''
        try:
            ttl = max(1, int((self.e_content_ttl.get().strip() if hasattr(self, 'e_content_ttl') else '') or '24'))
        except ValueError:
            ttl = 24
            self.e_content_ttl.delete(0, 'end')
            self.e_content_ttl.insert(0, '24')
        if remote and not remote.startswith('https://'):
            self._log('Remote URL harus HTTPS (raw GitHub disarankan).', 'err')
            return
        try:
            save_content_manifest({
                'version': load_content_manifest().get('version', '2.0.0'),
                'remote_url': remote,
                'cache_ttl_hours': ttl,
            })
            self._log('Manifest konten disimpan ke content/manifest.json', 'ok')
            self._update_content_status_label()
        except OSError as exc:
            self._log(f'Gagal simpan manifest: {exc}', 'err')

    def _preview_serp_enrich(self) -> None:
        kw = self.e_kw.get().strip() if hasattr(self, 'e_kw') else ''
        if not kw:
            self._log('Isi keyword fokus dulu untuk preview enrich.', 'warn')
            return
        g = get_global_config()
        if not serp_configured(g):
            self._log('Enrich belum dikonfigurasi — isi secrets/serp-keys.json', 'warn')
            return
        if not g.get('serp_enrich_enabled', True):
            self._log('Enrich Google nonaktif — centang checkbox di atas.', 'warn')
            return
        self._log(f'Enrich Google untuk: {kw.split(",")[0].strip()}…', 'info')

        def worker() -> None:
            enrich = get_serp_enrichment(
                kw,
                serpapi_keys=g.get('serpapi_keys') or [],
                google_cse_key=g.get('google_cse_key', ''),
                google_cse_cx=g.get('google_cse_cx', ''),
                force=True,
            )
            clear_serp_pool_cache()
            msg = (
                f"Enrich OK ({enrich.get('source', '?')}): "
                f"{len(enrich.get('faq') or [])} FAQ, "
                f"{len(enrich.get('titles') or [])} title, "
                f"{len(enrich.get('descriptions') or [])} desc, "
                f"{len(enrich.get('synonyms') or [])} sinonim"
            )
            self.after(0, lambda: self._log(msg, 'ok'))
            self.after(0, self._schedule_faq_refresh)
            self.after(0, self._schedule_seo_refresh)

        threading.Thread(target=worker, daemon=True).start()

    def _section_seo(self, p: Any, accent: str = BLUE) -> None:
        _sec_label(
            p, 0, 'SEO Teks',
            subtitle='Regenerate untuk variasi unik — kunci jika sudah cocok sebelum build',
            accent=accent,
        )

        title_row = ctk.CTkFrame(p, fg_color='transparent')
        title_row.grid(row=1, column=0, sticky='ew', padx=INSET)
        title_row.grid_columnconfigure(0, weight=1)
        _field_label(title_row, 0, 'Title')
        self.lbl_title_len = ctk.CTkLabel(title_row, text='0/60', font=FT, text_color=SUBTITLE)
        self.lbl_title_len.grid(row=0, column=1, sticky='e', padx=(8, 0))

        self.e_title = _entry(p, '')
        _field_widget(p, 2, self.e_title)
        self.e_title.bind('<KeyRelease>', lambda _e: self._update_seo_counters())

        desc_row = ctk.CTkFrame(p, fg_color='transparent')
        desc_row.grid(row=3, column=0, sticky='ew', padx=INSET)
        desc_row.grid_columnconfigure(0, weight=1)
        _field_label(desc_row, 0, 'Meta description')
        self.lbl_desc_len = ctk.CTkLabel(desc_row, text='0/160', font=FT, text_color=SUBTITLE)
        self.lbl_desc_len.grid(row=0, column=1, sticky='e', padx=(8, 0))

        self.e_desc = ctk.CTkTextbox(
            p, height=72, font=FT_I, fg_color=INPUT, border_color=BORDER,
            border_width=1, text_color=TEXT, wrap='word', corner_radius=RADIUS,
        )
        _field_widget(p, 4, self.e_desc, bottom=FIELD_GAP)
        self.e_desc.bind('<KeyRelease>', lambda _e: self._update_seo_counters())

        btn_row = ctk.CTkFrame(p, fg_color='transparent')
        btn_row.grid(row=5, column=0, sticky='ew', padx=INSET, pady=(0, 4))
        _btn(btn_row, 'Regenerasi Title', self._regenerate_title, variant='primary', height=30).pack(
            side='left', padx=(0, 6),
        )
        _btn(btn_row, 'Regenerasi Deskripsi', self._regenerate_description, variant='teal', height=30).pack(
            side='left', padx=(0, 6),
        )
        _btn(btn_row, 'Regenerasi Keduanya', self._regenerate_seo_both, variant='violet', height=30).pack(
            side='left',
        )

        lock_row = ctk.CTkFrame(p, fg_color='transparent')
        lock_row.grid(row=6, column=0, sticky='ew', padx=INSET, pady=(0, 6))
        self.var_keep_title = ctk.BooleanVar(value=False)
        self.var_keep_desc = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            lock_row, text='Kunci title untuk build', variable=self.var_keep_title, font=FT,
            text_color=SUBTITLE, fg_color=ACCENT, hover_color=ACCENT2, checkmark_color=INPUT,
            border_color=BORDER, corner_radius=4, command=lambda: self._update_coverage_panel(),
        ).pack(side='left', padx=(0, 12))
        ctk.CTkCheckBox(
            lock_row, text='Kunci deskripsi untuk build', variable=self.var_keep_desc, font=FT,
            text_color=SUBTITLE, fg_color=ACCENT, hover_color=ACCENT2, checkmark_color=INPUT,
            border_color=BORDER, corner_radius=4, command=lambda: self._update_coverage_panel(),
        ).pack(side='left')

        cov_wrap = ctk.CTkFrame(p, fg_color=INPUT, corner_radius=RADIUS_SM)
        cov_wrap.grid(row=7, column=0, sticky='ew', padx=INSET, pady=(0, 6))
        cov_wrap.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        _lbl(cov_wrap, 'Cakupan keyword', font=FT_B, text_color=TEXT).grid(
            row=0, column=0, columnspan=5, sticky='w', padx=10, pady=(8, 4),
        )
        self.lbl_cov_title = ctk.CTkLabel(cov_wrap, text='Title —', font=FT, text_color=SUBTITLE)
        self.lbl_cov_title.grid(row=1, column=0, padx=6, pady=(0, 8))
        self.lbl_cov_desc = ctk.CTkLabel(cov_wrap, text='Desc —', font=FT, text_color=SUBTITLE)
        self.lbl_cov_desc.grid(row=1, column=1, padx=6, pady=(0, 8))
        self.lbl_cov_faq = ctk.CTkLabel(cov_wrap, text='FAQ —', font=FT, text_color=SUBTITLE)
        self.lbl_cov_faq.grid(row=1, column=2, padx=6, pady=(0, 8))
        self.lbl_cov_rev = ctk.CTkLabel(cov_wrap, text='Ulasan —', font=FT, text_color=SUBTITLE)
        self.lbl_cov_rev.grid(row=1, column=3, padx=6, pady=(0, 8))
        self.lbl_cov_art = ctk.CTkLabel(cov_wrap, text='Artikel —', font=FT, text_color=SUBTITLE)
        self.lbl_cov_art.grid(row=1, column=4, padx=6, pady=(0, 8))
        self.lbl_cov_score = ctk.CTkLabel(cov_wrap, text='Skor SEO: —/5', font=FT, text_color=MUTED)
        self.lbl_cov_score.grid(row=2, column=0, columnspan=5, sticky='w', padx=10, pady=(0, 8))

        all_row = ctk.CTkFrame(p, fg_color='transparent')
        all_row.grid(row=8, column=0, sticky='ew', padx=INSET, pady=(0, INSET))
        _btn(all_row, 'Regenerasi Semua Konten', self._regenerate_all_content, variant='emerald', height=30).pack(side='left')

    def _section_faq(self, p: Any, accent: str = AMBER) -> None:
        _sec_label(
            p, 0, 'FAQ Otomatis',
            subtitle='Intent login/deposit/RTP/mirror — selaras keyword, unik antar brand',
            accent=accent,
        )

        ctrl = ctk.CTkFrame(p, fg_color='transparent')
        ctrl.grid(row=1, column=0, sticky='ew', padx=INSET, pady=(FIELD_GAP, 4))
        _btn(ctrl, 'Regenerasi FAQ', self._regenerate_faq, variant='amber', height=30).pack(side='left')

        self.var_keep_faq = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            ctrl, text='Kunci FAQ untuk build', variable=self.var_keep_faq, font=FT,
            text_color=SUBTITLE, fg_color=ACCENT, hover_color=ACCENT2, checkmark_color=INPUT,
            border_color=BORDER, corner_radius=4, command=self._toggle_keep_faq,
        ).pack(side='left', padx=(12, 0))

        self.txt_faq = ctk.CTkTextbox(
            p, height=160, font=FT_LOG, fg_color=INPUT, border_color=BORDER,
            border_width=1, text_color=TEXT, wrap='word', corner_radius=RADIUS,
            state='disabled',
        )
        self.txt_faq.grid(row=2, column=0, sticky='ew', padx=INSET, pady=(0, INSET))
        self.txt_faq.tag_config('q', foreground=ACCENT2)
        self.txt_faq.tag_config('a', foreground=MUTED)

    def _section_reviews(self, p: Any, accent: str = TEAL) -> None:
        _sec_label(p, 0, 'Ulasan Otomatis', subtitle='Unik tiap build — selaras keyword fokus', accent=accent)

        ctrl = ctk.CTkFrame(p, fg_color='transparent')
        ctrl.grid(row=1, column=0, sticky='ew', padx=INSET, pady=(FIELD_GAP, 4))
        ctrl.grid_columnconfigure(1, weight=1)

        _lbl(ctrl, 'Jumlah', anchor='w').grid(row=0, column=0, sticky='w')
        self.e_rev_count = _entry(ctrl, '6', width=52)
        self.e_rev_count.grid(row=0, column=1, padx=(8, 12), sticky='w')
        self.e_rev_count.insert(0, '6')

        _btn(ctrl, 'Regenerate', self._regenerate_reviews, variant='teal', height=30).grid(
            row=0, column=2, sticky='w',
        )

        self.var_keep_reviews = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            ctrl, text='Kunci ulasan untuk build', variable=self.var_keep_reviews, font=FT,
            text_color=SUBTITLE, fg_color=ACCENT, hover_color=ACCENT2, checkmark_color=INPUT,
            border_color=BORDER, corner_radius=4, command=self._toggle_keep_reviews,
        ).grid(row=1, column=0, columnspan=3, sticky='w', pady=(8, 0))

        self.txt_reviews = ctk.CTkTextbox(
            p, height=140, font=FT_LOG, fg_color=INPUT, border_color=BORDER,
            border_width=1, text_color=TEXT, wrap='word', corner_radius=RADIUS,
            state='disabled',
        )
        self.txt_reviews.grid(row=2, column=0, sticky='ew', padx=INSET, pady=(0, INSET))
        self.txt_reviews.tag_config('name', foreground=ACCENT2)
        self.txt_reviews.tag_config('body', foreground=MUTED)

    def _section_amp(self, p: Any, accent: str = GREEN) -> None:
        _sec_label(p, 0, 'Halaman AMP', subtitle='Template dinamis — warna & font mengikuti template desktop', accent=accent)

        self.var_amp = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            p, text='Generate halaman AMP',
            variable=self.var_amp, font=FT, text_color=TEXT,
            fg_color=ACCENT, hover_color=ACCENT2, checkmark_color=INPUT,
            border_color=BORDER, corner_radius=4,
        ).grid(row=1, column=0, sticky='w', padx=INSET, pady=(FIELD_GAP, 4))

        _field_label(p, 2, 'Desain template AMP')
        amp_names = list_amp_templates()
        default_amp = AMP_TEMPLATE_DEFAULT if AMP_TEMPLATE_DEFAULT in amp_names else amp_names[0]
        self.cmb_amp_tpl = ctk.CTkComboBox(
            p, values=amp_names, font=FT_I,
            fg_color=INPUT, border_color=BORDER, border_width=1, text_color=TEXT,
            button_color=BORDER, button_hover_color=ACCENT,
            dropdown_fg_color=SURFACE, dropdown_text_color=TEXT,
            height=ENTRY_H, corner_radius=RADIUS,
        )
        self.cmb_amp_tpl.set(default_amp)
        _field_widget(p, 3, self.cmb_amp_tpl, bottom=4)

        self.var_gsc_block = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            p, text='Blokir build jika GSC checklist gagal (gate ketat)',
            variable=self.var_gsc_block, font=FT, text_color=TEXT,
            fg_color=ACCENT, hover_color=ACCENT2, checkmark_color=INPUT,
            border_color=BORDER, corner_radius=4,
        ).grid(row=4, column=0, sticky='w', padx=INSET, pady=(0, INSET))

    def _build_right_panel(self, p: Any) -> None:
        p.grid_rowconfigure(0, weight=1)
        p.grid_columnconfigure(0, weight=1)

        outer = ctk.CTkFrame(
            p, fg_color=CARD, corner_radius=RADIUS,
            border_width=1, border_color=BORDER_SUBTLE,
        )
        outer.grid(row=0, column=0, sticky='nsew', padx=(4, INSET), pady=(10, INSET))
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(outer, fg_color='transparent')
        hdr.grid(row=0, column=0, sticky='ew', padx=INSET, pady=(INSET, 8))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text='Activity Log', font=FT_H, text_color=TEXT).grid(
            row=0, column=0, sticky='w',
        )
        ctk.CTkLabel(hdr, text='Log build, fetch, dan status output', font=FT, text_color=SUBTITLE).grid(
            row=1, column=0, sticky='w', pady=(2, 0),
        )

        btn_row = ctk.CTkFrame(hdr, fg_color='transparent')
        btn_row.grid(row=0, column=1, rowspan=2, sticky='e')
        self.lbl_log_status = _status_pill(btn_row, 'idle', MUTED)
        self.lbl_log_status.pack(side='left', padx=(0, 8))
        _btn(btn_row, 'Clear', self._clear_log, variant='neutral', width=68, height=28).pack(side='left')

        ctk.CTkFrame(outer, height=1, fg_color=BORDER_SUBTLE).grid(
            row=0, column=0, sticky='s', padx=INSET,
        )

        self.log_box = ctk.CTkTextbox(
            outer, font=FT_LOG, fg_color=INPUT, text_color=TEXT, wrap='word',
            state='disabled', border_width=0, corner_radius=RADIUS_SM,
        )
        self.log_box.grid(row=1, column=0, sticky='nsew', padx=INSET, pady=(8, INSET))
        self.log_box.tag_config('ok', foreground=GREEN)
        self.log_box.tag_config('err', foreground=RED)
        self.log_box.tag_config('warn', foreground=AMBER)
        self.log_box.tag_config('info', foreground=BLUE)
        self.log_box.tag_config('head', foreground=ACCENT2)
        self.log_box.tag_config('dim', foreground=MUTED)

    def _set_app_status(self, text: str, color: str) -> None:
        if hasattr(self, 'lbl_build_status'):
            self.lbl_build_status.configure(text=text, text_color=color)
        if hasattr(self, 'lbl_ready'):
            self.lbl_ready.configure(text=f'● {text}', text_color=color)

    def _refresh_tpl_list(self) -> None:
        names: List[str] = []
        for folder in (CACHE_DIR, TEMPLATES_DIR):
            if folder.is_dir():
                names.extend(f.name for f in folder.glob('*.html') if f.is_file())
        names = sorted(set(names))
        if not names:
            names = ['(fetch URL atau pilih file)']
        self.cmb_tpl.configure(values=names)
        current = self._template_name if self._template_name in names else names[0]
        self.cmb_tpl.set(current)
        self._update_path_preview()

    def _read_tpl_file(self, name: str) -> str:
        for base in (CACHE_DIR, TEMPLATES_DIR):
            path = base / name
            if path.is_file():
                try:
                    return path.read_text(encoding='utf-8')
                except OSError:
                    pass
        return ''

    def _template_html(self) -> str:
        if self._template_html_cache:
            return self._template_html_cache
        name = self.cmb_tpl.get().strip()
        if name and not name.startswith('('):
            return self._read_tpl_file(name)
        return ''

    def _on_tpl_selected(self) -> None:
        name = self.cmb_tpl.get().strip()
        if not name or name.startswith('('):
            return
        html = self._read_tpl_file(name)
        if not html:
            return
        self._template_html_cache = html
        self._template_name = name
        self._source_brand = detect_source_brand(html)
        ttype = detect_tpl_type(html)
        self.lbl_tpl_status.configure(
            text=f'{ttype.upper()} · {len(html):,} chars', text_color=GREEN,
        )
        self._apply_extracted_assets(html)
        self._schedule_review_refresh()

    def _load_content_async(self) -> None:
        def worker() -> None:
            global _banks_cache
            _banks_cache = None
            load_content_banks()
            info = content_pack_summary()
            self.after(0, lambda i=info: self._log(
                f"Bank konten: {i['source']} · pack v{i['pack_version']} · {i['faq_total']} FAQ",
                'dim',
            ))
            self.after(0, self._update_content_status_label)

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_content(self) -> None:
        self._log('Memuat ulang bank konten…', 'info')
        if hasattr(self, 'lbl_content_status'):
            self.lbl_content_status.configure(text='Memuat ulang bank konten…', text_color=AMBER)

        def worker() -> None:
            global _banks_cache
            _banks_cache = None
            clear_serp_pool_cache()
            load_content_banks(force=True)
            info = content_pack_summary()
            self.after(0, lambda i=info: self._log(
                f"Konten diperbarui: {i['source']} · pack v{i['pack_version']} · {i['faq_total']} FAQ",
                'ok',
            ))
            self.after(0, self._update_content_status_label)
            self.after(0, self._schedule_review_refresh)

        threading.Thread(target=worker, daemon=True).start()

    def _fetch_tpl(self) -> None:
        url = self.e_url.get().strip()
        if not url:
            self._log('URL template kosong.', 'warn')
            return
        self._log(f'Fetch: {url}', 'info')
        self.lbl_tpl_status.configure(text='Mengambil template…', text_color=AMBER)
        self.progress.set(0.1)

        def worker() -> None:
            html = fetch_url(url)
            if not html:
                self.after(0, lambda: self._log('Gagal fetch template. Cek koneksi / URL.', 'err'))
                self.after(0, lambda: self.lbl_tpl_status.configure(text='gagal fetch', text_color=RED))
                self.after(0, lambda: self.progress.set(0))
                return
            slug = re.sub(r'[^\w]+', '_', url.split('//')[-1].split('?')[0])[:40] or 'fetched'
            fname = f'tpl_{slug}.html'
            (CACHE_DIR / fname).write_text(html, encoding='utf-8')
            self._template_html_cache = html
            self._template_name = fname
            self._source_brand = detect_source_brand(html)
            ttype = detect_tpl_type(html)
            src = self._source_brand or '—'
            self.after(0, lambda: self._log(f'OK fetch: {fname} [{ttype.upper()}] brand template: {src}', 'ok'))
            self.after(0, self._refresh_tpl_list)
            self.after(0, lambda: self.cmb_tpl.set(fname))
            self.after(0, lambda: self.lbl_tpl_status.configure(
                text=f'{ttype.upper()} · {len(html):,} chars', text_color=GREEN,
            ))
            self.after(0, lambda s=src: self.lbl_source_brand.configure(
                text=f'Brand template: {s}', text_color=ACCENT2 if s != '—' else SUBTITLE,
            ))
            self.after(0, lambda: self._apply_extracted_assets(html))
            self.after(0, self._schedule_review_refresh)
            self.after(0, lambda: self.progress.set(0.3))

        threading.Thread(target=worker, daemon=True).start()

    def _pick_local_tpl(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=str(CACHE_DIR), title='Pilih template HTML',
            filetypes=[('HTML', '*.html'), ('Semua file', '*.*')],
        )
        if not path:
            return
        src = Path(path)
        dst = CACHE_DIR / src.name
        if src.resolve() != dst.resolve():
            try:
                shutil.copy2(src, dst)
            except OSError as exc:
                self._log(f'Gagal menyalin template: {exc}', 'err')
                return
        html = dst.read_text(encoding='utf-8', errors='replace')
        self._template_html_cache = html
        self._template_name = dst.name
        self._source_brand = detect_source_brand(html)
        self._refresh_tpl_list()
        self.cmb_tpl.set(dst.name)
        ttype = detect_tpl_type(html)
        src = self._source_brand or '—'
        self.lbl_tpl_status.configure(
            text=f'lokal · {ttype.upper()} · {len(html):,} chars', text_color=GREEN,
        )
        self.lbl_source_brand.configure(
            text=f'Brand template: {src}', text_color=ACCENT2 if src != '—' else SUBTITLE,
        )
        self._apply_extracted_assets(html)
        self._schedule_review_refresh()
        self._log(f'Template lokal dimuat: {dst.name}', 'ok')

    def _apply_extracted_assets(self, html: str) -> None:
        if not html:
            return
        extracted = extract_assets_from_html(html)
        mapping = {
            'logo': self.e_logo,
            'banner': self.e_banner,
            'favicon': self.e_favicon,
        }
        for key, widget in mapping.items():
            value = extracted.get(key)
            if not value:
                continue
            if not widget.get().strip():
                widget.delete(0, 'end')
                widget.insert(0, value)
                self._log(f'Hint asset template ({key}) — ganti dengan URL asset brand Anda.', 'dim')
        self._refresh_brand_logo_preview()

    def _schedule_brand_change(self, _event: Any = None) -> None:
        if self._brand_job is not None:
            try:
                self.after_cancel(self._brand_job)
            except Exception:
                pass
        self._brand_job = self.after(400, self._on_brand_change)

    def _on_brand_change(self) -> None:
        self._brand_job = None
        brand = self.e_brand.get().strip().upper()
        if not brand:
            return
        slug = _slugify(brand)
        if not self.e_folder.get().strip():
            self._fill_default(self.e_folder, default_output_folder(slug))

        entry = find_brand_entry(brand)
        assets = _asset_urls(slug)
        if entry:
            self._fill_default(self.e_canon, entry.get('linkcanno', '#LINKCANNO'))
            self._fill_default(self.e_amp, entry.get('linkamp', '#LINKAMP'))
            if entry.get('linkref'):
                self._fill_default(self.e_cta, entry['linkref'])
            if entry.get('logo'):
                self._fill_default(self.e_logo, entry['logo'])
            if entry.get('banner'):
                self._fill_default(self.e_banner, entry['banner'])
        if assets['favicon']:
            self._fill_default(self.e_favicon, assets['favicon'])

        self._update_path_preview()
        self._refresh_brand_logo_preview()
        self._schedule_review_refresh()
        self._schedule_seo_refresh()
        self._schedule_faq_refresh()

    @staticmethod
    def _fill_default(widget: ctk.CTkEntry, value: str) -> None:
        if not value:
            return
        if not widget.get().strip():
            widget.delete(0, 'end')
            widget.insert(0, value)

    def _brand_entry_from_form(self) -> Optional[Dict[str, str]]:
        brand = self.e_brand.get().strip().upper()
        if not brand:
            return None
        cta = self.e_cta.get().strip()
        if not cta:
            return None
        return {
            'linkref': cta,
            'linkcanno': self.e_canon.get().strip() or '#LINKCANNO',
            'linkamp': self.e_amp.get().strip() or '#LINKAMP',
            'logo': self.e_logo.get().strip(),
            'banner': self.e_banner.get().strip(),
        }

    def _save_brand_dialog(self) -> None:
        brand = self.e_brand.get().strip().upper()
        if not brand:
            self._log('Nama brand wajib diisi.', 'err')
            return
        entry = self._brand_entry_from_form()
        if not entry:
            self._log('Link CTA wajib diisi sebelum menyimpan brand.', 'err')
            return

        slug = _slugify(brand)
        existing = find_brand_entry(brand) is not None
        if existing:
            ok = messagebox.askyesno(
                'Timpa brand?',
                f'Brand "{slug}" sudah ada di brand-links.json.\n\nTimpa dengan data form saat ini?',
                parent=self,
            )
            if not ok:
                return

        dlg = ctk.CTkToplevel(self)
        dlg.title('Simpan Brand')
        dlg.geometry('460x340')
        dlg.configure(fg_color=CARD)
        dlg.transient(self)
        dlg.grab_set()
        _schedule_window_icon(dlg, is_root=False)
        dlg.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dlg, text=f'Simpan ke brand-links.json', font=FT_H, text_color=TEXT,
        ).grid(row=0, column=0, sticky='w', padx=16, pady=(16, 4))
        ctk.CTkLabel(
            dlg, text=f'Key: {slug}  ·  Brand: {brand}',
            font=FT, text_color=MUTED,
        ).grid(row=1, column=0, sticky='w', padx=16, pady=(0, 10))

        preview = ctk.CTkTextbox(
            dlg, height=160, font=FT_MONO, fg_color=INPUT, border_color=BORDER,
            border_width=1, text_color=TEXT, wrap='word', corner_radius=RADIUS_SM,
        )
        preview.grid(row=2, column=0, sticky='ew', padx=16, pady=(0, 12))
        preview.insert('1.0', json.dumps({slug: entry}, ensure_ascii=False, indent=2))
        preview.configure(state='disabled')

        btn_row = ctk.CTkFrame(dlg, fg_color='transparent')
        btn_row.grid(row=3, column=0, sticky='ew', padx=16, pady=(0, 16))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        def do_save() -> None:
            if self._write_brand_links(slug, entry):
                self._log(f'Brand "{brand}" disimpan ke brand-links.json ({slug}).', 'ok')
            dlg.destroy()

        _btn(btn_row, 'Batal', dlg.destroy, variant='neutral').grid(row=0, column=0, padx=(0, 6), sticky='ew')
        _btn(btn_row, 'Simpan', do_save, variant='primary').grid(row=0, column=1, padx=(6, 0), sticky='ew')

    def _save_global_config(self) -> None:
        gsc = self.e_gsc.get().strip() if hasattr(self, 'e_gsc') else ''
        cf = self.e_cf.get().strip() if hasattr(self, 'e_cf') else ''
        favicon = self.e_favicon.get().strip() if hasattr(self, 'e_favicon') else ''
        if not gsc and not cf and not favicon:
            self._log('Isi minimal satu field global sebelum simpan.', 'warn')
            return
        try:
            data = load_brand_links()
            if not isinstance(data.get('global'), dict):
                data['global'] = {}
            if gsc:
                data['global']['gsc_token'] = gsc
            if cf:
                data['global']['cf_token'] = cf
            if favicon:
                data['global']['favicon'] = favicon
            if not isinstance(data.get('brands'), dict):
                data['brands'] = {}
            BRAND_LINKS_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8',
            )
            self._log('Default global disimpan ke brand-links.json', 'ok')
        except OSError as exc:
            self._log(f'Gagal simpan global: {exc}', 'err')

    def _write_brand_links(self, slug: str, entry: Dict[str, str]) -> bool:
        try:
            path = BRAND_LINKS_WRITE_PATH
            if path.is_file():
                data = json.loads(path.read_text(encoding='utf-8'))
            elif BRAND_LINKS_PATH.is_file():
                data = json.loads(BRAND_LINKS_PATH.read_text(encoding='utf-8'))
            else:
                data = {'brands': {}, 'global': get_global_config()}
            if not isinstance(data.get('brands'), dict):
                data['brands'] = {}
            data['brands'][slug] = entry
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8',
            )
            return True
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            self._log(f'Gagal menyimpan brand-links.json: {exc}', 'err')
            return False

    def _update_path_preview(self, *_args: Any) -> None:
        brand = self.e_brand.get().strip() if hasattr(self, 'e_brand') else ''
        folder = self.e_folder.get().strip() if hasattr(self, 'e_folder') else ''
        slug = _slugify(brand) if brand else DEFAULT_SLUG
        base = resolve_output_base(folder, slug)
        self._output_path_full = str(base / 'index.html')
        if hasattr(self, 'lbl_path'):
            self.lbl_path.configure(text=_truncate_middle(self._output_path_full, 52))

    def _pick_output_folder(self) -> None:
        brand = self.e_brand.get().strip() if hasattr(self, 'e_brand') else ''
        slug = _slugify(brand) if brand else DEFAULT_SLUG
        current = resolve_output_base(self.e_folder.get().strip(), slug)
        start = current if current.is_dir() else current.parent
        if not start.is_dir():
            start = LANDING_DIR if LANDING_DIR.is_dir() else AUTOLANDING_DIR
        path = filedialog.askdirectory(
            initialdir=str(start),
            title='Pilih lokasi folder landing',
            parent=self,
        )
        if not path:
            return
        self.e_folder.delete(0, 'end')
        self.e_folder.insert(0, path)
        self._update_path_preview()
        self._log(f'Lokasi landing: {path}', 'ok')

    def _copy_output_path(self) -> None:
        text = getattr(self, '_output_path_full', '') or (
            self.lbl_path.cget('text') if hasattr(self, 'lbl_path') else ''
        )
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._log(f'Path disalin ke clipboard: {text}', 'dim')

    def _open_output_folder(self) -> None:
        brand = self.e_brand.get().strip() if hasattr(self, 'e_brand') else ''
        slug = _slugify(brand) if brand else DEFAULT_SLUG
        target = resolve_output_base(self.e_folder.get().strip(), slug)
        target.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith('win'):
                os.startfile(str(target))
            else:
                webbrowser.open(target.as_uri())
        except Exception as exc:
            self._log(f'Gagal membuka folder: {exc}', 'err')
            return
        self._log(f'Folder dibuka: {target}', 'dim')

    def _load_global_form_defaults(self) -> None:
        if not hasattr(self, 'e_favicon'):
            return
        g = get_global_config()
        self._fill_default(self.e_gsc, g.get('gsc_token', ''))
        self._fill_default(self.e_cf, g.get('cf_token', ''))
        self._fill_default(self.e_favicon, g.get('favicon', ''))
        self._refresh_favicon_preview()

    def _refresh_favicon_preview(self) -> None:
        if not hasattr(self, 'lbl_favicon_preview'):
            return
        url = self.e_favicon.get().strip() if hasattr(self, 'e_favicon') else ''
        def worker() -> None:
            img = _load_brand_pil(url)
            ctk_img = _pil_to_ctk_logo(img, height=28) if img is not None else None
            self.after(0, lambda: self._apply_favicon_preview(ctk_img))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_favicon_preview(self, ctk_img: Optional[ctk.CTkImage]) -> None:
        if ctk_img is not None:
            self.lbl_favicon_preview.configure(image=ctk_img, text='')
        else:
            self.lbl_favicon_preview.configure(image=None, text='favicon')

    def _refresh_brand_logo_preview(self) -> None:
        if not hasattr(self, 'e_logo') or not hasattr(self, 'lbl_logo_preview'):
            return
        url = self.e_logo.get().strip()
        if not url:
            self.lbl_logo_preview.configure(image=None, text='logo')
            return

        def worker() -> None:
            img = _load_brand_pil(url)
            ctk_img = _pil_to_ctk_logo(img, height=48) if img is not None else None
            self.after(0, lambda: self._apply_logo_preview(ctk_img))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_logo_preview(self, ctk_img: Optional[ctk.CTkImage]) -> None:
        self._logo_preview_img = ctk_img
        if ctk_img is not None:
            self.lbl_logo_preview.configure(image=ctk_img, text='')
        else:
            self.lbl_logo_preview.configure(image=None, text='n/a')

    def _review_count(self) -> int:
        try:
            n = int(self.e_rev_count.get().strip() or '6')
        except ValueError:
            n = 6
        return max(3, min(12, n))

    def _schedule_review_refresh(self, _event: Any = None) -> None:
        if self._kw_job is not None:
            try:
                self.after_cancel(self._kw_job)
            except Exception:
                pass
        self._kw_job = self.after(400, self._refresh_reviews_preview)

    def _refresh_reviews_preview(self) -> None:
        self._kw_job = None
        if self._keep_reviews and self._preview_reviews:
            self._render_reviews(self._preview_reviews)
            return
        brand = self.e_brand.get().strip().upper() or DEFAULT_BRAND
        kw = self.e_kw.get().strip() or f'{brand.lower()} platform permainan digital'
        dep = self.e_dep.get().strip() or 'Rp10.000'
        reviews, _, _ = gen_reviews(
            brand, kw, dep, count=self._review_count(), template_html=self._template_html(), vary=False,
        )
        self._preview_reviews = reviews
        self._render_reviews(reviews)
        self._update_coverage_panel()

    def _regenerate_reviews(self) -> None:
        brand = self.e_brand.get().strip().upper() or DEFAULT_BRAND
        kw = self.e_kw.get().strip() or f'{brand.lower()} platform permainan digital'
        dep = self.e_dep.get().strip() or 'Rp10.000'
        reviews, _, _ = gen_reviews(
            brand, kw, dep, count=self._review_count(), template_html=self._template_html(), vary=True,
        )
        self._preview_reviews = reviews
        self._render_reviews(reviews)
        self._log(f'Pratinjau {len(reviews)} ulasan diperbarui.', 'ok')
        self._update_coverage_panel()

    def _toggle_keep_reviews(self) -> None:
        self._keep_reviews = bool(self.var_keep_reviews.get())
        if self._keep_reviews:
            self._log('Ulasan preview dikunci — akan dipakai saat build.', 'info')
        else:
            self._log('Ulasan preview dilepas — akan digenerate ulang saat build.', 'dim')
            self._schedule_review_refresh()

    def _render_reviews(self, reviews: List[Dict[str, Any]]) -> None:
        self.txt_reviews.configure(state='normal')
        self.txt_reviews.delete('1.0', 'end')
        if not reviews:
            self.txt_reviews.insert('end', 'Belum ada ulasan pratinjau.\n', 'body')
        else:
            for review in reviews:
                stars = '★' * int(review.get('rating', 5))
                self.txt_reviews.insert('end', f'{review["name"]}  {stars}\n', 'name')
                self.txt_reviews.insert('end', f'{review["text"]}\n\n', 'body')
        self.txt_reviews.configure(state='disabled')

    def _on_keyword_changed(self, _event: Any = None) -> None:
        self._schedule_review_refresh()
        self._schedule_seo_refresh()
        self._schedule_faq_refresh()
        self._preview_article = ''

    def _on_deposit_changed(self, _event: Any = None) -> None:
        self._schedule_review_refresh()
        self._schedule_seo_refresh()

    def _seo_form_context(self) -> Tuple[str, str, str, Dict[str, set], Dict[str, str]]:
        brand = self.e_brand.get().strip().upper() or DEFAULT_BRAND
        kw = self.e_kw.get().strip() or f'{brand.lower()} platform permainan digital'
        dep = self.e_dep.get().strip() or 'Rp10.000'
        reservations = get_content_reservations(exclude_brand=brand)
        fill_ctx = build_fill_context({
            'brand': brand,
            'keyword_focus': kw,
            'short_info': {'minimal_deposit': dep},
        })
        return brand, kw, dep, reservations, fill_ctx

    def _seo_exclude_fps(self, brand: str, *texts: str) -> set:
        fps: set = set()
        for text in texts:
            t = (text or '').strip()
            if t:
                fps.add(_text_fingerprint(t, brand))
        return fps

    def _update_seo_counters(self) -> None:
        if not hasattr(self, 'lbl_title_len'):
            return
        t_len = len(self.e_title.get().strip())
        d_len = len(self.e_desc.get('1.0', 'end').strip())
        t_color = RED if t_len > 60 else (AMBER if t_len > 52 else SUBTITLE)
        d_color = RED if d_len > 160 else (AMBER if d_len > 145 else SUBTITLE)
        self.lbl_title_len.configure(text=f'{t_len}/60', text_color=t_color)
        self.lbl_desc_len.configure(text=f'{d_len}/160', text_color=d_color)
        self._update_coverage_panel()

    def _cov_label(self, ok: bool, name: str, detail: str = '') -> Tuple[str, str]:
        mark = '✓' if ok else '✗'
        color = GREEN if ok else AMBER
        text = f'{name} {mark}'
        if detail:
            text = f'{name} {detail} {mark}'
        return text, color

    def _update_coverage_panel(self) -> None:
        if not hasattr(self, 'lbl_cov_title'):
            return
        brand, kw, dep, reservations, fill_ctx = self._seo_form_context()
        canon = self.e_canon.get().strip() or '#LINKCANNO'
        title = self.e_title.get().strip()
        desc = self.e_desc.get('1.0', 'end').strip()
        faqs = self._preview_faq if self._preview_faq else []
        reviews = self._preview_reviews if self._preview_reviews else []
        if not self._preview_article and faqs:
            try:
                art, _ = gen_article_html(
                    brand, kw, dep, canon, reservations, fill_ctx, vary=False,
                )
                self._preview_article = art
            except Exception:
                self._preview_article = ''
        audit = audit_keyword_coverage(
            brand, kw, title=title, description=desc,
            faqs=faqs, reviews=reviews, article_html=self._preview_article,
        )
        t_text, t_color = self._cov_label(audit['title_ok'], 'Title')
        d_text, d_color = self._cov_label(audit['desc_ok'], 'Desc')
        f_detail = f"{audit['faq_hits']}/{audit['faq_total']}" if audit['faq_total'] else '—'
        f_text, f_color = self._cov_label(audit['faq_ok'], 'FAQ', f_detail)
        r_detail = f"{audit['review_hits']}/{audit['review_total']}" if audit['review_total'] else '—'
        r_text, r_color = self._cov_label(audit['reviews_ok'], 'Ulasan', r_detail)
        a_text, a_color = self._cov_label(audit['article_ok'], 'Artikel')
        self.lbl_cov_title.configure(text=t_text, text_color=t_color)
        self.lbl_cov_desc.configure(text=d_text, text_color=d_color)
        self.lbl_cov_faq.configure(text=f_text, text_color=f_color)
        self.lbl_cov_rev.configure(text=r_text, text_color=r_color)
        self.lbl_cov_art.configure(text=a_text, text_color=a_color)
        score_color = GREEN if audit['score'] >= 4 else (AMBER if audit['score'] >= 3 else RED)
        self.lbl_cov_score.configure(
            text=f"Skor SEO: {audit['score']}/{audit['max_score']} · fokus: {audit['primary']}",
            text_color=score_color,
        )

    def _apply_generated_title(self, title: str) -> None:
        self.e_title.delete(0, 'end')
        self.e_title.insert(0, title)
        self._update_seo_counters()

    def _apply_generated_description(self, desc: str) -> None:
        self.e_desc.delete('1.0', 'end')
        self.e_desc.insert('1.0', desc)
        self._update_seo_counters()

    def _regenerate_title(self) -> None:
        brand, kw, dep, reservations, fill_ctx = self._seo_form_context()
        exclude = self._seo_exclude_fps(brand, self.e_title.get().strip())
        self._seo_regen_nonce += 1
        title, _ = gen_title(
            brand, kw, reservations, fill_ctx, vary=True,
            exclude_fps=exclude, regen_nonce=self._seo_regen_nonce,
        )
        self._apply_generated_title(title)
        self._log(f'Title diperbarui ({len(title)} char): {title[:72]}…', 'ok')
        self._update_coverage_panel()

    def _regenerate_description(self) -> None:
        brand, kw, dep, reservations, fill_ctx = self._seo_form_context()
        exclude = self._seo_exclude_fps(brand, self.e_desc.get('1.0', 'end').strip())
        self._seo_regen_nonce += 1
        desc, _ = gen_description(
            brand, kw, dep, reservations, fill_ctx, vary=True,
            exclude_fps=exclude, regen_nonce=self._seo_regen_nonce,
        )
        self._apply_generated_description(desc)
        self._log(f'Deskripsi diperbarui ({len(desc)} char).', 'ok')
        self._preview_article = ''
        self._update_coverage_panel()

    def _regenerate_seo_both(self) -> None:
        self._regenerate_title()
        self._regenerate_description()
        self._log('Title & deskripsi diperbarui — cek panel cakupan keyword.', 'info')

    def _schedule_faq_refresh(self) -> None:
        if self._faq_job is not None:
            try:
                self.after_cancel(self._faq_job)
            except Exception:
                pass
        self._faq_job = self.after(450, self._refresh_faq_preview)

    def _refresh_faq_preview(self) -> None:
        self._faq_job = None
        if self._keep_faq and self._preview_faq:
            self._render_faq(self._preview_faq)
            self._update_coverage_panel()
            return
        brand, kw, dep, reservations, fill_ctx = self._seo_form_context()
        canon = self.e_canon.get().strip() or '#LINKCANNO'
        faqs, _ = gen_faq(brand, kw, dep, canon, reservations, fill_ctx, vary=False)
        self._preview_faq = faqs
        self._preview_article = ''
        self._render_faq(faqs)
        self._update_coverage_panel()

    def _regenerate_faq(self) -> None:
        brand, kw, dep, reservations, fill_ctx = self._seo_form_context()
        canon = self.e_canon.get().strip() or '#LINKCANNO'
        exclude: set = set()
        for item in self._preview_faq:
            exclude.add(_text_fingerprint(item.get('q', '') + ' ' + item.get('a', ''), brand))
        self._content_regen_nonce += 1
        faqs, _ = gen_faq(
            brand, kw, dep, canon, reservations, fill_ctx, vary=True,
            exclude_fps=exclude, regen_nonce=self._content_regen_nonce,
        )
        self._preview_faq = faqs
        self._preview_article = ''
        self._render_faq(faqs)
        self._log(
            f'FAQ diperbarui ({len(faqs)} item · intent: {", ".join(_detect_faq_intents_from_kw(kw))}).',
            'ok',
        )
        self._update_coverage_panel()

    def _render_faq(self, faqs: List[Dict[str, str]]) -> None:
        self.txt_faq.configure(state='normal')
        self.txt_faq.delete('1.0', 'end')
        if not faqs:
            self.txt_faq.insert('end', 'Belum ada FAQ pratinjau.\n', 'a')
        else:
            for i, item in enumerate(faqs, 1):
                self.txt_faq.insert('end', f'Q{i}. {item["q"]}\n', 'q')
                self.txt_faq.insert('end', f'A: {item["a"]}\n\n', 'a')
        self.txt_faq.configure(state='disabled')

    def _toggle_keep_faq(self) -> None:
        self._keep_faq = bool(self.var_keep_faq.get())
        if self._keep_faq:
            self._log('FAQ preview dikunci — akan dipakai saat build.', 'info')
        else:
            self._log('FAQ preview dilepas — akan digenerate ulang saat build.', 'dim')
            self._schedule_faq_refresh()

    def _regenerate_all_content(self) -> None:
        self._regenerate_title()
        self._regenerate_description()
        self._regenerate_faq()
        self._regenerate_reviews()
        self._log('Semua konten (title, desc, FAQ, ulasan) diperbarui.', 'ok')
        self._update_coverage_panel()

    def _schedule_seo_refresh(self) -> None:
        if self._seo_job is not None:
            try:
                self.after_cancel(self._seo_job)
            except Exception:
                pass
        self._seo_job = self.after(450, self._refresh_seo_preview)

    def _refresh_seo_preview(self) -> None:
        self._seo_job = None
        if self.var_keep_title.get() and self.var_keep_desc.get():
            self._update_coverage_panel()
            return
        brand, kw, dep, reservations, fill_ctx = self._seo_form_context()
        if not self.var_keep_title.get() and not self.e_title.get().strip():
            title, _ = gen_title(brand, kw, reservations, fill_ctx, vary=False)
            self._apply_generated_title(title)
        if not self.var_keep_desc.get() and not self.e_desc.get('1.0', 'end').strip():
            desc, _ = gen_description(brand, kw, dep, reservations, fill_ctx, vary=False)
            self._apply_generated_description(desc)
        self._update_seo_counters()
        self._schedule_faq_refresh()

    def _suggest_description(self) -> None:
        self._regenerate_description()

    def _collect_cfg(self) -> Optional[Dict[str, Any]]:
        brand = self.e_brand.get().strip().upper()
        if not brand:
            self._log('Nama brand wajib diisi.', 'err')
            return None
        cta = self.e_cta.get().strip()
        if not cta:
            self._log('Link referral / CTA wajib diisi.', 'err')
            return None
        if not _is_valid_url(cta):
            self._log('Link referral / CTA sepertinya bukan URL valid — lanjut tetap dicoba.', 'warn')

        folder = self.e_folder.get().strip()
        slug = _slugify(brand)
        output_folder = folder or default_output_folder(slug)
        kw = self.e_kw.get().strip() or f'{brand.lower()} platform permainan digital'
        dep = self.e_dep.get().strip() or 'Rp10.000'
        canon = self.e_canon.get().strip() or '#LINKCANNO'
        amp_url = self.e_amp.get().strip() or '#LINKAMP'
        logo = self.e_logo.get().strip()
        banner = self.e_banner.get().strip()
        favicon = self.e_favicon.get().strip()
        nav = self.e_nav.get().strip() or favicon
        gsc = self.e_gsc.get().strip() if hasattr(self, 'e_gsc') else ''
        cf = self.e_cf.get().strip() if hasattr(self, 'e_cf') else ''
        title = self.e_title.get().strip()
        desc = self.e_desc.get('1.0', 'end').strip()
        url = self.e_url.get().strip()
        tpl_name = self.cmb_tpl.get().strip()

        cfg: Dict[str, Any] = {
            'brand': brand,
            'slug': slug,
            'output_folder': output_folder,
            'keyword_focus': kw,
            'canonical': canon,
            'amp_url': amp_url,
            'cta': cta,
            'logo': logo,
            'banner': banner,
            'favicon': favicon,
            'bottom_nav_icon': nav,
            'short_info': {'minimal_deposit': dep},
        }
        if gsc:
            cfg['gsc_token'] = gsc
        if cf:
            cfg['cf_token'] = cf

        html = self._template_html_cache
        if not html and tpl_name and not tpl_name.startswith('('):
            html = self._read_tpl_file(tpl_name)
        tpl_ref = ''
        if tpl_name and not tpl_name.startswith('('):
            tpl_ref = tpl_name
        elif self._template_name and not self._template_name.startswith('('):
            tpl_ref = self._template_name
        if tpl_ref:
            cfg['template_file'] = tpl_ref
        if html:
            cfg['_runtime_template_html'] = html
            cfg['source_brand'] = detect_source_brand(html)
        if url:
            cfg['template_url'] = url
        if self.var_keep_title.get() and title:
            cfg['_manual_title'] = title
        if self.var_keep_desc.get() and desc:
            cfg['_manual_description'] = desc
        if self._keep_reviews and self._preview_reviews:
            cfg['reviews'] = self._preview_reviews
            cfg['_keep_reviews'] = True
        if self._keep_faq and self._preview_faq:
            cfg['faq'] = self._preview_faq
            cfg['_keep_faq'] = True

        cfg['generate_amp'] = bool(self.var_amp.get())
        if hasattr(self, 'cmb_amp_tpl'):
            amp_tpl = self.cmb_amp_tpl.get().strip()
            if amp_tpl:
                cfg['amp_template'] = Path(amp_tpl).name

        if not (html or url or cfg.get('template_file')):
            self._log('Isi URL template atau pilih file lokal terlebih dahulu.', 'err')
            return None
        return cfg

    def _validate_fields(self, cfg: Dict[str, Any]) -> List[str]:
        warnings: List[str] = []
        if cfg.get('canonical') == '#LINKCANNO':
            warnings.append('Canonical masih placeholder #LINKCANNO.')
        elif not _is_valid_url(cfg.get('canonical', '')):
            warnings.append('Canonical bukan URL yang valid.')
        if cfg.get('amp_url') == '#LINKAMP':
            warnings.append('AMP URL masih placeholder #LINKAMP.')
        if not cfg.get('logo'):
            warnings.append('Logo URL belum diisi.')
        if not cfg.get('banner'):
            warnings.append('Banner URL belum diisi — wajib asset user, bukan template.')
        if not cfg.get('favicon'):
            warnings.append('Favicon URL belum diisi — akan pakai favicon global.')
        tpl_html = cfg.get('_runtime_template_html') or resolve_template_html(cfg) or ''
        if tpl_html:
            extracted = extract_assets_from_html(tpl_html)
            for key, label in (('logo', 'Logo'), ('banner', 'Banner')):
                val = cfg.get(key, '')
                old = extracted.get(key, '')
                if val and old and val.rstrip('/') == old.rstrip('/'):
                    warnings.append(f'{label} masih URL template — ganti dengan asset brand sendiri.')
        title = cfg.get('_manual_title', '')
        if title and len(title) > 60:
            warnings.append(f'Title manual terlalu panjang ({len(title)} char, maks 60).')
        elif title and not _text_has_user_keyword(title, parse_keyword_focus(cfg.get('keyword_focus', ''))):
            warnings.append('Title belum menyebut keyword fokus — regenerasi atau edit manual.')
        desc = cfg.get('_manual_description', '')
        if desc and len(desc) > 160:
            warnings.append(f'Deskripsi manual terlalu panjang ({len(desc)} char, maks 160).')
        elif desc and not _text_has_user_keyword(desc, parse_keyword_focus(cfg.get('keyword_focus', ''))):
            warnings.append('Deskripsi belum menyebut keyword fokus — regenerasi atau edit manual.')
        return warnings

    def _preview_config(self) -> None:
        cfg = self._collect_cfg()
        if not cfg:
            return
        merged = merge_brand_defaults(dict(cfg))
        html = self._template_html() or resolve_template_html(merged)
        enriched = enrich_config(dict(merged), html)
        self._log('─' * 44, 'head')
        self._log('CONFIG PREVIEW', 'head')
        self._log(f'Brand    : {enriched.get("brand")}', 'info')
        self._log(f'Title    : {enriched.get("title")}', 'info')
        self._log(f'Desc     : {str(enriched.get("description", ""))[:100]}', 'info')
        self._log(f'FAQ      : {len(enriched.get("faq", []))} item', 'dim')
        self._log(f'Reviews  : {len(enriched.get("reviews", []))} item', 'dim')
        self._log(f'Output   : {enriched.get("output_folder")}', 'dim')
        for warning in self._validate_fields(cfg):
            self._log(f'!!  {warning}', 'warn')
        self._log('─' * 44, 'head')

    def _open_preview_html(self) -> None:
        cfg = self._collect_cfg()
        if not cfg:
            return
        self._log('Membuat preview HTML…', 'info')
        try:
            merged = merge_brand_defaults(dict(cfg))
            html_tpl = resolve_template_html(merged)
            if not html_tpl:
                self._log('Template kosong — fetch atau pilih file dulu.', 'err')
                return
            merged['_runtime_template_html'] = html_tpl
            enriched = enrich_config(dict(merged), html_tpl)
            preview_html = build_landing_html(enriched)
            slug = enriched.get('slug') or _slugify(enriched['brand'])
            preview_dir = PREVIEW_DIR / slug
            preview_dir.mkdir(parents=True, exist_ok=True)
            preview_path = preview_dir / 'index.html'
            preview_path.write_text(preview_html, encoding='utf-8')
            webbrowser.open(preview_path.resolve().as_uri())
            self._log(f'Preview dibuka: {preview_path}', 'ok')
            src = enriched.get('source_brand') or detect_source_brand(html_tpl)
            if src and src.upper() != enriched['brand'].upper():
                left = _count(preview_html, src)
                if left:
                    self._log(f'!!  Brand template "{src}" masih {left}x di preview — cek output', 'warn')
        except Exception as exc:
            self._log(f'Preview gagal: {exc}', 'err')

    def _save_config_only(self) -> None:
        cfg = self._collect_cfg()
        if not cfg:
            return
        slug = cfg.get('slug') or _slugify(cfg['brand'])
        out_path = CONFIGS_DIR / f'{slug}.json'
        slim = slim_config_for_storage(cfg, self._template_name or cfg.get('template_file', ''))
        out_path.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding='utf-8')
        self._log(f'Config disimpan: configs/{slug}.json', 'ok')

    def _load_config_dialog(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=str(CONFIGS_DIR), title='Muat Config',
            filetypes=[('Config JSON', '*.json'), ('Semua file', '*.*')],
        )
        if not path:
            return
        try:
            cfg = migrate_legacy_config(json.loads(Path(path).read_text(encoding='utf-8')))
        except (json.JSONDecodeError, OSError) as exc:
            self._log(f'Gagal memuat config: {exc}', 'err')
            return
        self._apply_cfg_to_fields(cfg)
        self._log(f'Config dimuat: {Path(path).name}', 'ok')

    def _apply_cfg_to_fields(self, cfg: Dict[str, Any]) -> None:
        def set_entry(widget: ctk.CTkEntry, value: Any) -> None:
            widget.delete(0, 'end')
            if value:
                widget.insert(0, str(value))

        set_entry(self.e_brand, cfg.get('brand', DEFAULT_BRAND))
        slug = cfg.get('slug') or _slugify(cfg.get('brand', DEFAULT_BRAND))
        set_entry(self.e_folder, cfg.get('output_folder') or default_output_folder(slug))
        set_entry(self.e_kw, cfg.get('keyword_focus', ''))

        short_info = cfg.get('short_info') or {}
        set_entry(self.e_dep, short_info.get('minimal_deposit', 'Rp10.000'))

        set_entry(self.e_cta, cfg.get('cta', ''))
        set_entry(self.e_canon, cfg.get('canonical', '#LINKCANNO'))
        set_entry(self.e_amp, cfg.get('amp_url', '#LINKAMP'))
        set_entry(self.e_logo, cfg.get('logo', ''))
        set_entry(self.e_banner, cfg.get('banner', ''))
        set_entry(self.e_favicon, cfg.get('favicon', ''))
        set_entry(self.e_nav, cfg.get('bottom_nav_icon', ''))
        set_entry(self.e_gsc, cfg.get('gsc_token', ''))
        set_entry(self.e_cf, cfg.get('cf_token', ''))
        set_entry(self.e_title, cfg.get('title', ''))
        if cfg.get('title'):
            self.var_keep_title.set(True)
        set_entry(self.e_url, cfg.get('template_url', ''))

        self.e_desc.delete('1.0', 'end')
        if cfg.get('description'):
            self.e_desc.insert('1.0', cfg['description'])
            self.var_keep_desc.set(True)
        self._update_seo_counters()

        if cfg.get('template_file'):
            self._template_name = Path(cfg['template_file']).name
            self._template_html_cache = self._read_tpl_file(self._template_name) or cfg.get('template_html', '')
            self.cmb_tpl.set(self._template_name)
            self.lbl_tpl_status.configure(
                text=f'{detect_tpl_type(self._template_html_cache).upper()} · {len(self._template_html_cache):,} chars',
                text_color=GREEN if self._template_html_cache else SUBTITLE,
            )
        elif cfg.get('template_html'):
            self._template_html_cache = cfg['template_html']
            self._template_name = '(dari config)'

        reviews = cfg.get('reviews')
        if isinstance(reviews, list) and reviews:
            self._preview_reviews = reviews
            self.var_keep_reviews.set(True)
            self._keep_reviews = True
            self._render_reviews(reviews)

        faqs = cfg.get('faq')
        if isinstance(faqs, list) and faqs:
            self._preview_faq = faqs
            self.var_keep_faq.set(True)
            self._keep_faq = True
            self._render_faq(faqs)

        self.var_amp.set(bool(cfg.get('generate_amp', True)))
        if hasattr(self, 'cmb_amp_tpl'):
            names = list_amp_templates()
            self.cmb_amp_tpl.configure(values=names)
            amp_tpl = cfg.get('amp_template') or AMP_TEMPLATE_DEFAULT
            self.cmb_amp_tpl.set(amp_tpl if amp_tpl in names else names[0])
        self._update_path_preview()
        self._refresh_brand_logo_preview()
        if not self._keep_reviews:
            self._schedule_review_refresh()
        self._schedule_seo_refresh()
        if not self._keep_faq:
            self._schedule_faq_refresh()
        else:
            self._update_coverage_panel()

    def _reset_form(self) -> None:
        for widget in (
            self.e_url, self.e_cta, self.e_logo, self.e_banner, self.e_title,
            self.e_nav, self.e_kw, self.e_favicon, self.e_gsc, self.e_cf,
        ):
            widget.delete(0, 'end')

        self.e_brand.delete(0, 'end')
        self.e_brand.insert(0, DEFAULT_BRAND)
        self.e_folder.delete(0, 'end')
        self.e_folder.insert(0, default_output_folder(DEFAULT_SLUG))
        self.e_dep.delete(0, 'end')
        self.e_dep.insert(0, 'Rp10.000')
        self.e_canon.delete(0, 'end')
        self.e_amp.delete(0, 'end')
        self.e_desc.delete('1.0', 'end')

        self._template_html_cache = ''
        self._template_name = ''
        self._source_brand = ''
        self._preview_reviews = []
        self._preview_faq = []
        self._preview_article = ''
        self.var_keep_reviews.set(False)
        self._keep_reviews = False
        if hasattr(self, 'var_keep_faq'):
            self.var_keep_faq.set(False)
            self._keep_faq = False
        if hasattr(self, 'var_keep_title'):
            self.var_keep_title.set(False)
            self.var_keep_desc.set(False)
        if hasattr(self, 'cmb_amp_tpl'):
            names = list_amp_templates()
            self.cmb_amp_tpl.configure(values=names)
            self.cmb_amp_tpl.set(AMP_TEMPLATE_DEFAULT if AMP_TEMPLATE_DEFAULT in names else names[0])
        self.lbl_tpl_status.configure(text='belum ada template', text_color=SUBTITLE)
        self._render_reviews([])
        self._render_faq([])
        self._update_path_preview()
        self._refresh_brand_logo_preview()
        self._update_seo_counters()
        self._schedule_faq_refresh()
        self._log('Form direset ke default.', 'dim')

    def _gsc_gate_mode(self) -> str:
        if getattr(self, 'var_gsc_block', None) and self.var_gsc_block.get():
            return 'block'
        return 'warn'

    def _sync_configs_from_brands(self) -> None:
        tpl = self._template_name if self._template_name and not self._template_name.startswith('(') else ''
        paths = sync_configs_from_brand_links(template_file=tpl, force=False)
        if paths:
            self._log(f'Sync config: {len(paths)} file di configs/', 'ok')
        else:
            self._log('brand-links.json kosong — tidak ada config dibuat.', 'warn')

    def _start_batch_build(self) -> None:
        if self._building:
            self._log('Build sedang berjalan, tunggu sebentar.', 'warn')
            return
        configs = sorted(CONFIGS_DIR.glob('*.json'))
        if not configs:
            brands = load_brand_links().get('brands') or {}
            if brands and messagebox.askyesno(
                'Batch Build',
                f'Tidak ada config di configs/.\n\nBuat {len(brands)} config dari brand-links.json?',
            ):
                tpl = self._template_name if self._template_name and not self._template_name.startswith('(') else ''
                configs = sync_configs_from_brand_links(template_file=tpl)
            if not configs:
                self._log('Batch build dibatalkan — tidak ada config.', 'err')
                return

        self._building = True
        self.progress.set(0.05)
        self._set_app_status('Batch…', AMBER)
        self.lbl_log_status.configure(text='batch', text_color=AMBER)
        write_amp = bool(self.var_amp.get())
        gsc_gate = self._gsc_gate_mode()
        self._log('', 'dim')
        self._log('=' * 44, 'head')
        self._log(f'BATCH BUILD: {len(configs)} config  [gate: {gsc_gate}]', 'head')
        self._log('=' * 44, 'head')

        def worker() -> None:
            try:
                summary = batch_deploy(
                    write_amp=write_amp,
                    gsc_gate=gsc_gate,
                )
            except Exception as exc:
                self.after(0, lambda: self._log(f'Batch error: {exc}', 'err'))
                self.after(0, lambda: self.progress.set(0))
                self.after(0, lambda: self._set_app_status('Gagal', RED))
                self.after(0, self._build_done)
                return
            self.after(0, lambda: self._on_batch_success(summary))

        threading.Thread(target=worker, daemon=True).start()

    def _on_batch_success(self, summary: Dict[str, Any]) -> None:
        self.progress.set(1.0)
        total = summary.get('total', 0)
        ok = summary.get('ok', 0)
        blocked = summary.get('gsc_blocked', 0)
        errors = summary.get('errors', 0)
        self._log(f'OK  Selesai  : {ok}/{total} sukses', 'ok' if ok == total else 'warn')
        if blocked:
            self._log(f'!!  GSC blocked: {blocked}', 'warn')
        if errors:
            self._log(f'!!  Error: {errors}', 'err')
        for item in summary.get('items') or []:
            brand = item.get('brand', '?')
            status = item.get('status', '')
            if status == 'ok':
                score = item.get('keyword_score', '—')
                self._log(f'    ✓ {brand}  [{score}]', 'dim')
                for note in item.get('duplicate_notes') or []:
                    self._log(f'      !! {note}', 'warn')
                for fail in item.get('gsc_failures') or []:
                    self._log(f'      !! GSC: {fail}', 'warn')
            elif status == 'gsc_blocked':
                self._log(f'    ✗ {brand}  (GSC gate)', 'warn')
            else:
                self._log(f'    ✗ {brand}  {item.get("error", "")}', 'err')
        report_path = summary.get('report_path')
        if report_path:
            self._log(f'OK  Laporan : {report_path}', 'ok')
        self._log('BATCH SELESAI', 'ok')
        self._log('=' * 44, 'head')
        self._set_app_status('Batch selesai', GREEN if errors == 0 and blocked == 0 else AMBER)
        self.lbl_log_status.configure(text='batch ok', text_color=GREEN)
        self.after(600, lambda: self.progress.set(0))
        self.after(1200, lambda: self._set_app_status('Ready', GREEN))
        self._build_done()

    def _start_build(self) -> None:
        if self._building:
            self._log('Build sedang berjalan, tunggu sebentar.', 'warn')
            return
        cfg = self._collect_cfg()
        if not cfg:
            return

        self._building = True
        self.progress.set(0.08)
        self._set_app_status('Building…', AMBER)
        self.lbl_log_status.configure(text='building', text_color=AMBER)

        timestamp = datetime.now().strftime('%H:%M:%S')
        self._log('', 'dim')
        self._log('=' * 44, 'head')
        self._log(f'BUILD: {cfg["brand"]}  [{timestamp}]', 'head')
        self._log('=' * 44, 'head')
        for warning in self._validate_fields(cfg):
            self._log(f'!!  {warning}', 'warn')

        write_amp = bool(self.var_amp.get())
        slug = cfg.get('slug') or _slugify(cfg['brand'])
        slim = slim_config_for_storage(cfg, self._template_name or cfg.get('template_file', ''))
        (CONFIGS_DIR / f'{slug}.json').write_text(
            json.dumps(slim, ensure_ascii=False, indent=2), encoding='utf-8',
        )

        def worker() -> None:
            try:
                result = deploy(cfg, write_amp=write_amp, gsc_gate=self._gsc_gate_mode())
            except GSCGateError as exc:
                self.after(0, lambda: self._log(f'GSC gate: {exc}', 'err'))
                self.after(0, lambda: self.progress.set(0))
                self.after(0, lambda: self._set_app_status('GSC ditolak', RED))
                self.after(0, self._build_done)
                return
            except Exception as exc:
                self.after(0, lambda: self._log(f'Build error: {exc}', 'err'))
                self.after(0, lambda: self.progress.set(0))
                self.after(0, lambda: self._set_app_status('Gagal', RED))
                self.after(0, self._build_done)
                return
            self.after(0, lambda: self._on_build_success(result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_build_success(self, result: Dict[str, Any]) -> None:
        self.progress.set(0.85)
        html_out = result.get('html', '')
        self._log(f'OK  Output   : {result["paths"].get("index")}', 'ok')
        if 'amp' in result['paths']:
            self._log(f'OK  AMP      : {result["paths"]["amp"]}', 'ok')
        if 'sitemap' in result['paths']:
            self._log(f'OK  Sitemap  : {result["paths"]["sitemap"]}', 'ok')
        if 'robots' in result['paths']:
            self._log(f'OK  Robots   : {result["paths"]["robots"]}', 'ok')
        if 'seo_report' in result['paths']:
            self._log(f'OK  SEO report: {result["paths"]["seo_report"]}', 'ok')
            report = result.get('seo_report_data') or {}
            score = report.get('keyword_score', '—')
            self._log(f'    Skor keyword: {score}', 'dim')
            checklist = report.get('gsc_checklist') or {}
            failed = [k for k, v in checklist.items() if not v]
            if failed:
                self._log(f'    GSC checklist belum lengkap: {", ".join(failed)}', 'warn')
            gate = report.get('gsc_gate') or {}
            if gate.get('passed') is False and gate.get('mode') == 'warn':
                self._log(f'    GSC gate (warn): {", ".join(gate.get("failures") or [])}', 'warn')
        self._log(f'OK  Size     : {result["size"]:,} chars', 'ok')
        self._log(f'OK  Brand    : {result["brand_count"]}x muncul', 'ok')
        self._log(f'OK  #LINKCANNO sisa: {_count(html_out, "#LINKCANNO")}x', 'dim')
        self._log(f'OK  #LINKAMP sisa  : {_count(html_out, "#LINKAMP")}x', 'dim')
        for warning in result.get('warnings', []):
            self._log(f'!!  {warning}', 'warn')

        self.progress.set(1.0)
        self._log('BUILD SELESAI', 'ok')
        self._log('=' * 44, 'head')
        index_path = result.get('paths', {}).get('index')
        if index_path and Path(index_path).is_file():
            webbrowser.open(Path(index_path).resolve().as_uri())
            self._log('Browser dibuka untuk preview output.', 'info')
        self._set_app_status('Selesai', GREEN)
        self.lbl_log_status.configure(text='ok', text_color=GREEN)
        self.after(600, lambda: self.progress.set(0))
        self.after(1200, lambda: self._set_app_status('Ready', GREEN))
        self._build_done()

    def _build_done(self) -> None:
        self._building = False

    def _log(self, message: str, level: str = 'info') -> None:
        timestamp = datetime.now().strftime('%H:%M:%S')
        line = f'[{timestamp}] {message}\n' if message else '\n'
        self.log_box.configure(state='normal')
        self.log_box.insert('end', line, level)
        self.log_box.see('end')
        self.log_box.configure(state='disabled')
        if hasattr(self, 'lbl_log_status') and level in ('ok', 'err', 'warn'):
            colors = {'ok': GREEN, 'err': RED, 'warn': AMBER}
            self.lbl_log_status.configure(text=level, text_color=colors[level])

    def _clear_log(self) -> None:
        self.log_box.configure(state='normal')
        self.log_box.delete('1.0', 'end')
        self.log_box.configure(state='disabled')


def _ask(prompt: str, default: str = '') -> str:
    hint = f' [{default}]' if default else ''
    try:
        val = input(f'  > {prompt}{hint}: ').strip()
        return val if val else default
    except (KeyboardInterrupt, EOFError):
        print()
        return default


def _form_simple() -> dict | None:
    print('\n=== LP Builder (mode simpel) ===')
    print('Isi field wajib saja — sisanya auto-generate unik.\n')

    brand = _ask('Nama brand', 'BRANDMU').upper()
    if not brand:
        print('Brand wajib diisi.')
        return None

    entry = find_brand_entry(brand) or {}
    g = get_global_config()

    default_canon = entry.get('linkcanno', '#LINKCANNO')
    default_amp = entry.get('linkamp', '#LINKAMP')
    default_cta = entry.get('linkref', '')
    default_logo = entry.get('logo', '')
    default_banner = entry.get('banner', '')

    if entry:
        print(f'  (auto dari brand-links.json: {brand})')

    canonical = _ask('Canonical (#linkcanno)', default_canon)
    amp_url = _ask('AMP URL (#linkamp)', default_amp)
    cta = _ask('Link referral / CTA', default_cta)
    logo = _ask('Logo URL', default_logo)
    banner = _ask('Banner URL', default_banner)

    tpl_url = _ask('URL template HTML (kosong = lptemplate.html)', '')
    slug = _slugify(brand)
    folder = _ask('Lokasi folder landing (kosong = landing/slug)', default_output_folder(slug))

    cfg = {
        'brand': brand,
        'slug': slug,
        'output_folder': folder.strip() or default_output_folder(slug),
        'canonical': canonical,
        'amp_url': amp_url,
        'cta': cta,
        'logo': logo,
        'banner': banner,
        'favicon': g.get('favicon', ''),
        'template_url': tpl_url,
        'generate_amp': True,
    }

    cfg = merge_brand_defaults(cfg)
    html = resolve_template_html(cfg)
    if html:
        cfg['template_html'] = html
    cfg = enrich_config(cfg, html)

    print('\n--- Preview ---')
    print(f'  Title : {cfg["title"]}')
    print(f'  Desc  : {cfg["description"][:80]}...')
    print(f'  FAQ   : {len(cfg.get("faq", []))} item')
    print(f'  Review: {len(cfg.get("reviews", []))} item')

    if _ask('Build sekarang? (y/n)', 'y').lower() != 'y':
        return None
    return cfg


def _save_config(cfg: dict) -> Path:
    slug = cfg.get('slug') or _slugify(cfg['brand'])
    path = CONFIGS_DIR / f'{slug}.json'
    slim = slim_config_for_storage(cfg, cfg.get('template_file', ''))
    path.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def run_cli() -> None:
    while True:
        print('\n[1] Buat LP baru (simpel)  [2] Build dari config  [3] Build semua  [0] Keluar')
        choice = _ask('Pilih', '1')
        if choice == '0':
            break
        if choice == '1':
            cfg = _form_simple()
            if not cfg:
                continue
            try:
                result = deploy(cfg)
                _save_config(result['cfg'])
                print(f'\nOK  {result["paths"].get("index")}')
                for w in result['warnings']:
                    print(f'!!  {w}')
            except Exception as e:
                print(f'!!  {e}')
        elif choice == '2':
            configs = sorted(CONFIGS_DIR.glob('*.json'))
            if not configs:
                print('Belum ada config.')
                continue
            for i, p in enumerate(configs, 1):
                print(f'  {i}. {p.name}')
            raw = _ask('Pilih nomor', '1')
            try:
                idx = int(raw) - 1
                path = configs[max(0, min(idx, len(configs) - 1))]
            except ValueError:
                path = configs[0]
            with open(path, encoding='utf-8') as f:
                cfg = migrate_legacy_config(json.load(f))
            try:
                result = deploy(cfg)
                print(f'OK  {result["paths"].get("index")}')
            except Exception as e:
                print(f'!!  {e}')
        elif choice == '3':
            summary = batch_deploy(gsc_gate='warn')
            print(f'\nBatch: {summary["ok"]}/{summary["total"]} OK')
            print(f'Laporan: {summary.get("report_path")}')
            for item in summary.get('items') or []:
                if item.get('status') != 'ok':
                    print(f'  !! {item.get("brand")}: {item.get("error", item.get("status"))}')


def build_from_config(config_path: str, gsc_gate: str = 'warn') -> None:
    print(f'\n>> Building: {config_path}')
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = migrate_legacy_config(json.load(f))

    cfg = merge_brand_defaults(cfg)
    try:
        result = deploy(
            cfg,
            write_amp=cfg.get('generate_amp', True),
            write_seo_files=True,
            gsc_gate=gsc_gate,
        )
    except GSCGateError as e:
        print(f'  X GSC gate: {e}')
        return
    except Exception as e:
        print(f'  X Error: {e}')
        return

    print(f'  OK Output   : {result["paths"].get("index")}')
    if 'amp' in result['paths']:
        print(f'  OK AMP      : {result["paths"]["amp"]}')
    if 'sitemap' in result['paths']:
        print(f'  OK Sitemap  : {result["paths"]["sitemap"]}')
    if 'robots' in result['paths']:
        print(f'  OK Robots   : {result["paths"]["robots"]}')
    if 'seo_report' in result['paths']:
        print(f'  OK SEO report: {result["paths"]["seo_report"]}')
    print(f'  OK Size     : {result["size"]:,} chars')
    print(f'  OK Brand    : {result["brand_count"]}x')
    report = result.get('seo_report_data') or {}
    gate = report.get('gsc_gate') or {}
    if gate.get('failures'):
        print(f'  !! GSC gate ({gate.get("mode")}): {", ".join(gate["failures"])}')
    for w in result['warnings']:
        print(f'  !! {w}')
    print('  OK Done')


def run_build(config_path: str | None = None, gsc_gate: str = 'warn') -> None:
    if config_path:
        build_from_config(config_path, gsc_gate=gsc_gate)
        print('\n=== Build selesai ===')
        return
    summary = batch_deploy(gsc_gate=gsc_gate)
    print(f'\nBatch: {summary["ok"]}/{summary["total"]} sukses')
    if summary.get('gsc_blocked'):
        print(f'GSC blocked: {summary["gsc_blocked"]}')
    if summary.get('errors'):
        print(f'Error: {summary["errors"]}')
    print(f'Laporan: {summary.get("report_path")}')
    for item in summary.get('items') or []:
        if item.get('status') != 'ok':
            print(f'  !! {item.get("brand")}: {item.get("error", item.get("status"))}')
    print('\n=== Build selesai ===')


def run_gui() -> None:
    try:
        import customtkinter
    except ImportError:
        print('GUI membutuhkan customtkinter dan pillow.')
        print('Install: pip install customtkinter pillow')
        sys.exit(1)
    try:
        app = LPWidget()
        app.mainloop()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main() -> None:
    try:
        if len(sys.argv) == 1:
            run_gui()
            return

        parser = argparse.ArgumentParser(
            description='Landing Page Builder — fetch template, isi brand, build otomatis.',
        )
        parser.add_argument(
            '--cli', '-c', action='store_true',
            help='Mode terminal (menu interaktif)',
        )
        parser.add_argument(
            'command', nargs='?', default='gui',
            choices=('gui', 'build', 'cli'),
            help='gui (default), build, atau cli',
        )
        parser.add_argument(
            'config', nargs='?', default='',
            help='Path config JSON (hanya untuk: build path/to/config.json)',
        )
        parser.add_argument(
            '--gsc-block', action='store_true',
            help='Tolak build jika GSC checklist gagal (mode block)',
        )
        args, rest = parser.parse_known_args()

        if args.cli or args.command == 'cli':
            run_cli()
            return

        if args.command == 'build':
            cfg_path = args.config or (rest[0] if rest else '')
            gate = 'block' if args.gsc_block else 'warn'
            run_build(cfg_path or None, gsc_gate=gate)
            return

        run_gui()
    except KeyboardInterrupt:
        print()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
