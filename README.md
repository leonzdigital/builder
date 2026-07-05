# Landing Page Builder

Tool portable untuk generate landing page + AMP dengan compliance SEO/GSC. Multi-brand — setiap user isi brand, URL, dan asset sendiri.

## Fitur

- Build HTML desktop + AMP dari template
- Bank konten dinamis (`content/pack.json`) — FAQ, title, review, artikel
- Update konten via GitHub (`remote_url` di manifest)
- GSC checklist gate sebelum deploy
- Portable: tidak ada hardcode brand/link/asset vendor di output

## Quick start

```powershell
cd "LP Builder"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python lp_builder.py
```

### Setup pertama

1. Copy config brand:
   ```powershell
   copy brand-links.example.json brand-links.json
   ```
   *(Tool otomatis copy jika `brand-links.json` belum ada.)*

2. Tab **Utama**: isi brand, canonical, AMP, CTA, logo, banner
3. Tab **Lanjutan**: keyword, GSC token (opsional), build
4. Output: `landing/{slug}/index.html` + `amp.html`

## Struktur repo

```
LP Builder/
├── lp_builder.py          # Engine + GUI
├── lp_compliance.py       # SEO/compliance helpers
├── content/
│   ├── pack.json          # Bank teks (commit ke GitHub)
│   ├── manifest.json      # Remote pack URL + cache TTL
│   ├── CONTENT.md         # Panduan kontribusi pack
│   └── CHANGELOG.md
├── templates/
│   ├── generic-template.html
│   └── amp/index.html
├── brand-links.example.json
├── build-requirements.json
└── assets/                # Logo GUI tool saja
```

## Content pack dan GitHub

| File | Commit? |
|---|---|
| `content/pack.json` | Ya |
| `content/manifest.json` | Ya |
| `brand-links.json` | Tidak (token/URL client) |
| `landing/` | Tidak (hasil build) |

Update pack dari repo terpisah — set `remote_url` ke raw GitHub:

```
https://raw.githubusercontent.com/USERNAME/lp-builder-content/main/pack.json
```

Atur di tab **Lanjutan → Bank Konten**, lalu **Muat Ulang Bank Konten**.

### Enrich kosa kata dari Google

Isi **SerpAPI key** (PAA + related search) atau **Google CSE key + cx** di tab Bank Konten. Konten FAQ/title/deskripsi diperkaya otomatis saat generate — dipilih acak sesuai keyword. API key disimpan lokal di `brand-links.json` (tidak di-push ke GitHub).

Detail: [content/CONTENT.md](content/CONTENT.md)

## Deploy ke GitHub

Repo: **[github.com/leonzdigital/builder](https://github.com/leonzdigital/builder)**

Clone:

```powershell
git clone https://github.com/leonzdigital/builder.git
cd builder
pip install -r requirements.txt
python lp_builder.py
```

Push update:

```powershell
git add .
git commit -m "Deskripsi perubahan"
git push
```
