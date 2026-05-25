# Git Workflow Documentation

## Overview

Sistem git workflow baru dirancang untuk mengotomatisasi proses release dan publikasi ke PyPI. Workflow ini mengikuti pola semantic versioning dan memastikan sinkronisasi antara branch master dan tag release.

## Workflow Architecture

### 1. Sync Master to Latest Tag (`sync-master-to-latest-tag.yml`)

**Trigger:** Push ke branch `master` dengan perubahan di:
- `pyproject.toml`
- `psdfy/**`
- `.github/workflows/sync-master-to-latest-tag.yml`

**Fungsi:**
- Mengambil tag terbaru dari repository
- Memperbarui tag tersebut untuk menunjuk ke commit terbaru di master
- Memastikan latest tag selalu mencerminkan state terbaru di master

**Contoh:**
```bash
# Setelah push ke master
git push origin master
# Workflow akan otomatis update tag v1.0.5 ke commit terbaru
```

### 2. Sync New Tag to Master and Publish (`sync-tag-to-master-and-publish.yml`)

**Trigger:** Push tag baru dengan format `v*` (contoh: `v1.0.6`)

**Fungsi:**
- Ekstrak versi dari tag
- Update `pyproject.toml` dengan versi baru
- Update `psdfy/__init__.py` dengan versi baru
- Commit dan push perubahan ke master
- Build distribusi Python
- Publish ke PyPI menggunakan `PYPI_API_TOKEN`
- Buat GitHub Release

**Contoh:**
```bash
# Buat tag baru
git tag -a v1.0.6 -m "Release version 1.0.6"

# Push tag ke remote
git push origin v1.0.6

# Workflow akan otomatis:
# 1. Update version di master
# 2. Publish ke PyPI
# 3. Buat GitHub Release
```

## Workflow Sequence

### Scenario 1: Push Changes ke Master

```
1. Developer push changes ke master
   ↓
2. sync-master-to-latest-tag.yml triggered
   ↓
3. Latest tag (v1.0.5) updated ke current master commit
   ↓
4. Done - latest tag always points to master
```

### Scenario 2: Release New Version

```
1. Developer create new tag: git tag -a v1.0.6 -m "..."
   ↓
2. Developer push tag: git push origin v1.0.6
   ↓
3. sync-tag-to-master-and-publish.yml triggered
   ↓
4. Extract version from tag (1.0.6)
   ↓
5. Update pyproject.toml and psdfy/__init__.py
   ↓
6. Commit and push to master with [skip ci] flag
   ↓
7. Build distribution package
   ↓
8. Publish to PyPI using PYPI_API_TOKEN
   ↓
9. Create GitHub Release
   ↓
10. Done - new version available on PyPI
```

## Usage Instructions

### Prerequisites

Pastikan repository sudah memiliki:
- `PYPI_API_TOKEN` di GitHub Secrets
- Branch `master` sebagai default branch
- Python 3.11+ untuk build process

### Step 1: Setup Initial Tag

Jika belum ada tag, buat tag awal:

```bash
git tag -a v1.0.5 -m "Initial release"
git push origin v1.0.5
```

### Step 2: Daily Development

Push changes ke master seperti biasa:

```bash
git add .
git commit -m "feat: add new feature"
git push origin master
```

Workflow `sync-master-to-latest-tag` akan otomatis update tag v1.0.5.

### Step 3: Release New Version

Ketika siap release:

```bash
# Buat tag baru dengan semantic versioning
git tag -a v1.0.6 -m "Release version 1.0.6"

# Push tag ke remote
git push origin v1.0.6
```

Workflow `sync-tag-to-master-and-publish` akan:
- Update version di master
- Publish ke PyPI
- Buat GitHub Release

### Step 4: Verify Release

Cek di:
- PyPI: https://pypi.org/project/psdfy/
- GitHub Releases: https://github.com/[owner]/layer-psd-converter/releases
- Master branch: Version files updated

## Important Notes

### Circular Trigger Prevention

Workflow menggunakan `[skip ci]` flag saat commit ke master dari tag push untuk mencegah circular triggers.

### Version Comparison

Workflow menggunakan semantic versioning comparison untuk memastikan hanya tag yang lebih baru yang diproses.

### Error Handling

- Jika publish ke PyPI gagal, workflow akan fail dan tidak membuat release
- Jika version update gagal, workflow akan fail sebelum publish
- Semua steps memiliki proper error handling

## Deprecated Workflows

Workflow lama sudah di-deprecate:
- `publish-on-push.yml` - Replaced by sync-master-to-latest-tag.yml
- `release.yml` - Replaced by sync-tag-to-master-and-publish.yml
- `publish.yml` - Replaced by sync-tag-to-master-and-publish.yml

Workflow `ci.yml` tetap aktif untuk testing dan linting.

## Troubleshooting

### Tag tidak ter-update

Pastikan:
- Push ke master dengan perubahan di file yang di-monitor
- Workflow memiliki permission `contents: write`

### Publish ke PyPI gagal

Pastikan:
- `PYPI_API_TOKEN` sudah di-set di GitHub Secrets
- Token masih valid dan tidak expired
- Package name unik di PyPI

### Version mismatch

Pastikan:
- Tag format: `v1.0.6` (dengan prefix `v`)
- Version di pyproject.toml dan __init__.py konsisten setelah update

## Support

Untuk pertanyaan atau issue, buat issue di repository dengan label `workflow`.
