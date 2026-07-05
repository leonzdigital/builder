# Panduan Content Pack (`pack.json`)

Bank teks untuk FAQ, title, description, review, artikel, dan meta variasi. File ini **aman di-commit ke GitHub** — tidak berisi token atau URL client.

## Struktur

| Section | Isi |
|---|---|
| `version` | SemVer pack — naikkan tiap update konten |
| `faq` | FAQ per niche: `mahjong`, `zeus`, `slot`, `togel`, `casino` |
| `faq_intents` | Intent: `login`, `deposit`, `rtp`, `mirror`, `withdraw`, `bonus` |
| `titles` | Template judul (netral, tanpa kata terlarang di title) |
| `descriptions` | Meta description |
| `breadcrumbs` | Label breadcrumb |
| `reviews` | `open`, `middle`, `close` |
| `articles` | `open`, `mid`, `close` |
| `meta` | `cities`, `devices`, `payments`, `reviewer_names`, `usp_lines`, dll. |

## Placeholder

Tool mengisi otomatis saat build:

- `{brand}`, `{deposit}`, `{canon}`
- `{kw_primary}`, `{kw_secondary}`, `{kw_list}`
- `{support}`, `{withdraw}`, `{year}`, dll.

## Menambah entri dari riset Google

1. Riset manual: People Also Ask, related search, GSC queries, SERP competitor
2. **Tulis ulang** — jangan copy-paste mentah dari SERP
3. Tambahkan ke section yang sesuai intent/niche
4. Naikkan `"version"` di `pack.json`
5. Catat di `CHANGELOG.md`
6. Push ke GitHub → user klik **Muat Ulang Bank Konten** di GUI

## Distribusi via GitHub

### Opsi A — Satu repo (default)

`content/pack.json` ikut repo tool. `manifest.json` dengan `remote_url` kosong → baca lokal.

### Opsi B — Repo konten terpisah

1. Buat repo mis. `lp-builder-content` dengan `pack.json`
2. Set `content/manifest.json`:

```json
{
  "version": "2.0.0",
  "remote_url": "https://raw.githubusercontent.com/USERNAME/lp-builder-content/main/pack.json",
  "cache_ttl_hours": 24
}
```

3. Simpan dari tab **Lanjutan → Bank Konten** atau edit file langsung
4. Tool fetch otomatis, cache di `content/cache/` (di-gitignore)

## Contoh entri FAQ

```json
{
  "q": "Bagaimana cara login {brand} jika link utama diblokir?",
  "a": "Gunakan mirror alternatif {brand} yang diperbarui harian. Proses login sama — akun terdaftar tetap valid."
}
```

## Aturan kualitas

- Title: netral, 45–60 karakter, tanpa kata terlarang (slot, gacor, judi, dll.)
- FAQ build: minimal 8 item, 6 topik wajib brand (situs, login, link alternatif, rtp, website, daftar)
- Hindari duplikat antar entri dalam kategori yang sama
- Variasi natural — hindari frasa AI generik berulang
