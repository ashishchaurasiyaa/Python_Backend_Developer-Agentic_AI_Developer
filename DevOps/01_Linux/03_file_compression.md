# File Compression & Archiving

**DevOps Track · Phase 1: Linux**

## Quick Concepts

| Concept | One-line definition |
|---------|---------------------|
| **Archive** | Bundle multiple files into ONE file, preserving structure — that is `tar`'s job (no compression by itself) |
| **Compression** | Shrink data size using an algorithm (gzip, bzip2, xz, zstd) |
| **Tarball** | A `.tar` archive further compressed to `.tar.gz` / `.tgz` |
| **Lossless** | Compression that reconstructs exact original bytes — all tools here are lossless |

---

## Quick Concepts — In Depth

### Archive vs Compression — They Are Separate Things

```
Archive = combine many files into ONE file, preserving:
            - directory structure
            - file permissions (rwx)
            - ownership (UID/GID)
            - timestamps
            - symlinks
          tar does this. It does NOT shrink the data.

Compression = apply an algorithm to make the bytes smaller.
               gzip, bzip2, xz, zstd do this.
               They work on ONE file — not a directory tree.

Tarball = tar archive THEN compressed:
           myapp/           → tar → myapp.tar → gzip → myapp.tar.gz
           (directory tree)   (single file)    (smaller single file)
```

### Lossless vs Lossy

```
Lossless: decompress → byte-for-byte identical original
          ALL tools here (gzip, bzip2, xz, zip) are lossless
          Required for code, binaries, configs, databases

Lossy: decompress → approximation (some data permanently discarded)
       JPEG, MP3, MP4 use lossy compression
       NEVER use lossy for anything you need to restore exactly
```

---

## Why This Matters for Backend/DevOps Work

```
- Shipping build artifacts / release bundles between CI and servers
- Rotating and compressing old logs to save disk (logrotate uses gzip)
- Downloading and unpacking third-party binaries/SDKs
- Backing up databases and app directories before a deploy
- Docker build context and layer caching indirectly relate to tar format
```

---

## tar — Tape Archive

`tar` bundles files together. It does NOT compress by itself — you pair it with gzip/bzip2/xz via a flag.

### How tar Actually Works

```bash
# tar takes a directory tree and streams it as a sequential format:
# [file1 header][file1 data][file2 header][file2 data]...

# The header contains:
# - filename and path
# - permissions (mode)
# - UID/GID
# - size
# - modification timestamp
# - file type (regular, symlink, directory)

# This is why tar preserves everything — permissions, symlinks, timestamps.
# zip doesn't reliably preserve Unix permissions.
```

### Core Flags

```
Operations (pick ONE):
  c   Create  — make a new archive
  x   eXtract — unpack an archive
  t   Test/lisT — list contents without extracting
  r   append  — add files to existing uncompressed archive
  u   Update  — add files newer than archive copy

Compression (pick ONE or none):
  z   gzip   — fast, universal, .tar.gz / .tgz
  j   bzip2  — smaller than gzip, slower, .tar.bz2
  J   xz     — smallest, slowest, .tar.xz
  (none)     — no compression, just archive, .tar

Other flags:
  v   verbose — print each filename as processed
  f   file    — MUST be followed immediately by the archive name
  C   Change to directory before extracting (or creating)
  p   preserve permissions exactly (default when run as root)
  --exclude='pattern'    exclude matching files/dirs
  --strip-components=N   strip N leading path components on extract
```

### Common Combos

```bash
tar -czvf archive.tar.gz dir/          # Create, gZip, Verbose, File — most common
tar -xzvf archive.tar.gz               # eXtract, gZip, Verbose, File
tar -xzvf archive.tar.gz -C /opt/      # extract into a specific directory
tar -tzvf archive.tar.gz               # list contents (sanity check BEFORE extracting)

tar -cJvf archive.tar.xz dir/          # xz compression — smaller, slower
tar -xJvf archive.tar.xz

tar -cjvf archive.tar.bz2 dir/         # bzip2 — less common now
tar -cvf archive.tar dir/              # no compression, just bundling

tar --exclude='*.log' --exclude='.git' --exclude='node_modules' \
    -czvf app.tar.gz myapp/            # exclude patterns

tar -czvf - dir/ | ssh user@host 'tar -xzvf - -C /opt/'  # stream over SSH
```

### Flag Order Mnemonic

```
"czvf" = Create, Ze compress, Verbose, to File <name>
"xzvf" = eXtract, Ze decompress, Verbose, from File <name>

Whatever you did to make it (c+z), you undo to open it (x+z).
```

### The `-C` Flag — Always Use It on Extract

```bash
# WITHOUT -C — dangerous on messy archives
tar -xzvf archive.tar.gz
# If archive contains "etc/passwd" at root level — it overwrites ./etc/passwd
# If archive has absolute paths — it could write ANYWHERE

# WITH -C — controlled, explicit
mkdir -p /opt/myapp
tar -xzvf archive.tar.gz -C /opt/myapp/
# All files land inside /opt/myapp/ — no surprises

# ALWAYS list first on archives from the internet:
tar -tzvf downloaded.tar.gz | head -20
# Check: does it have a top-level dir (safe) or dump files at root (messy)?

# Strip leading directory (common with downloaded tarballs from GitHub):
tar -xzvf redis-7.2.tar.gz --strip-components=1 -C /opt/redis/
# Without: extracts to /opt/redis/redis-7.2/bin/...
# With:    extracts to /opt/redis/bin/...
```

### Extract a Single File from an Archive

```bash
# List contents to find the exact path
tar -tzvf archive.tar.gz | grep "config"
# myapp/config/settings.py

# Extract just that file
tar -xzvf archive.tar.gz myapp/config/settings.py

# Extract to stdout (view without saving)
tar -xzvf archive.tar.gz -O myapp/config/settings.py
```

### Backup and Restore Patterns

```bash
# Full app backup before a deploy
tar --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='venv' \
    -czvf /backup/myapp-$(date +%Y%m%d-%H%M%S).tar.gz \
    /opt/myapp/

# Restore from backup
tar -xzvf /backup/myapp-20260811-142300.tar.gz -C /opt/

# Database dump + compress in one step (no temp file)
pg_dump mydb | gzip > /backup/mydb-$(date +%Y%m%d).sql.gz

# Restore database from compressed dump
gunzip -c /backup/mydb-20260811.sql.gz | psql mydb
```

---

## gzip / gunzip

### How gzip Works (Enough to Matter)

```
gzip uses the DEFLATE algorithm:
  1. LZ77: finds repeated byte sequences, replaces with back-references
  2. Huffman coding: assigns shorter bit patterns to more frequent symbols

Result: text/logs → typically 10-30% of original size
        already-compressed files (JPEG, zip) → shrinks very little
```

### Full Command Reference

```bash
gzip file.txt              # compress → file.txt.gz, original DELETED
gzip -k file.txt            # keep original, also produce file.txt.gz
gzip -d file.txt.gz          # decompress (identical to gunzip)
gzip -9 file.txt              # max compression (slower, ~5-10% smaller than default)
gzip -1 file.txt               # fastest compression (less shrinkage)
gzip -l file.txt.gz             # show compression ratio without decompressing
gzip -t file.txt.gz              # test integrity (verify not corrupted)
gzip -v file.txt                  # verbose — show compression ratio

gunzip file.txt.gz            # decompress → file.txt, .gz deleted
gunzip -k file.txt.gz          # keep .gz, also produce file.txt
gunzip -c file.txt.gz           # decompress to stdout, original untouched
```

### The z-Family Tools — Work WITHOUT Decompressing

```bash
zcat file.txt.gz               # view content (like cat but for .gz)
zless file.txt.gz               # page through content (like less)
zgrep "ERROR" app.log.gz         # grep inside .gz without extracting
zgrep -E "ERROR|WARN" *.log.gz    # grep multiple .gz files
zdiff file1.gz file2.gz            # diff two compressed files

# These are crucial for searching rotated logs:
# Log rotation creates: app.log, app.log.1, app.log.2.gz, app.log.3.gz...
# Search all of them:
grep "ERROR" /var/log/nginx/access.log          # current (uncompressed)
zgrep "ERROR" /var/log/nginx/access.log.*.gz    # rotated (compressed)
```

### Compression Levels — When Each Makes Sense

```
-1  (fastest):  use in pipelines where CPU is bottleneck (live pg_dump | gzip)
-6  (default):  good balance — use for log rotation, everyday backups
-9  (best):     cold archives you compress once and rarely read
                only ~5-10% smaller than -6 but ~2x slower
```

---

## zip / unzip

```bash
# Create
zip archive.zip file1 file2               # specific files
zip -r archive.zip dir/                    # directory recursively
zip -r archive.zip dir/ -x "*.log"         # exclude patterns
zip -9 archive.zip file                     # max compression
zip -e archive.zip secret.txt               # password-protect (weak encryption!)
zip -u archive.zip newfile.txt              # update — add/replace if newer

# Inspect
unzip -l archive.zip                        # list contents
unzip -p archive.zip path/in/zip/file.txt   # print file to stdout (no extract)
unzip -t archive.zip                        # test integrity

# Extract
unzip archive.zip                           # extract to current dir
unzip archive.zip -d /opt/target/           # extract to specific dir
unzip -o archive.zip                        # overwrite without prompting
unzip -n archive.zip                        # never overwrite existing files
unzip archive.zip "*.py"                    # extract only Python files
```

### AWS Lambda Deployment Packages

```bash
# Lambda REQUIRES zip — not tar.gz
# Function code + dependencies must be at the root of the zip

# Python Lambda:
pip install -r requirements.txt -t package/
cp lambda_function.py package/
cd package
zip -r ../deployment.zip .
cd ..

# Verify contents
unzip -l deployment.zip | head -20

# Upload to Lambda
aws lambda update-function-code \
    --function-name my-function \
    --zip-file fileb://deployment.zip
```

---

## Compression Algorithm Comparison

| Algorithm | Flag | Extension | Speed | Ratio | Use Case |
|-----------|------|-----------|-------|-------|----------|
| gzip | `z` | `.tar.gz` | Fast | Good | Default for everything |
| bzip2 | `j` | `.tar.bz2` | Medium | Better | Legacy — use xz instead |
| xz | `J` | `.tar.xz` | Slow | Best | Cold storage, release tarballs |
| zstd | `--zstd` | `.tar.zst` | Very Fast | Good | Modern pipelines (Facebook) |
| zip | n/a | `.zip` | Fast | Good | Lambda, Windows, cross-platform |

**Concrete numbers on a 100MB text log:**

```
No compression:     100MB    0.0s
gzip -1:             12MB    0.8s
gzip -6 (default):   10MB    1.5s
gzip -9:              9.5MB  3.0s
bzip2:                8MB    4.0s
xz:                   7MB   12.0s
zstd (default):      11MB    0.4s   ← fastest + decent ratio
```

### When to Use Which

```
gzip:   Default. Always installed. tar knows it. zgrep/zcat work with it.
        → logs, backups, deploy artifacts, everything day-to-day

xz:     Compress once, many people download.
        → cold archives, public downloads, GitHub releases, Linux packages

bzip2:  Legacy. xz replaced it. Only use for compatibility with old systems.

zstd:   Modern, fastest. Not universally installed — check before using in scripts.
        → high-throughput pipelines, real-time compression, Dockerfile layers

zip:    Consumer is Windows, or target is AWS Lambda.
        Does NOT reliably preserve Unix permissions/symlinks.
        → Lambda packages, sharing with Windows users, cross-platform
```

---

## tar.gz vs zip — Which to Use

| | tar.gz | zip |
|-|--------|-----|
| **Preserves Unix permissions/symlinks** | Yes | Not reliably |
| **Cross-platform (Windows-friendly)** | Awkward without extra tools | Native everywhere |
| **Compression ratio** | Slightly better (gzip/xz) | Good, DEFLATE |
| **Streaming (pipe to/from network)** | Natural — tar streams well | Less natural |
| **Typical DevOps use** | Linux server backups, Docker layers, deploy artifacts | Lambda packages, cross-platform sharing, Windows |

### Senior Tip

```
Default to tar.gz on Linux/Unix infrastructure — it preserves permissions
and symlinks correctly, which matters for backups you intend to restore.

Use zip specifically when:
  - The consumer is Windows
  - The target is AWS Lambda (Lambda requires zip)
  - You need to share with someone on macOS/Windows who doesn't have tar
```

---

## Real-World Patterns

### Pattern 1: Deploy Artifact Pipeline

```bash
# CI: build versioned artifact
VERSION=$(cat VERSION)
tar --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='tests/' \
    --exclude='venv/' \
    -czvf "myapp-${VERSION}.tar.gz" \
    myapp/

# Upload to S3
aws s3 cp "myapp-${VERSION}.tar.gz" "s3://my-artifacts/releases/"

# Server: download and deploy
aws s3 cp "s3://my-artifacts/releases/myapp-${VERSION}.tar.gz" /tmp/
mkdir -p "/opt/myapp/releases/${VERSION}"
tar -xzvf "/tmp/myapp-${VERSION}.tar.gz" \
    --strip-components=1 \
    -C "/opt/myapp/releases/${VERSION}/"

# Atomic symlink swap (zero downtime)
ln -sfn "/opt/myapp/releases/${VERSION}" /opt/myapp/current
sudo systemctl restart myapp
```

### Pattern 2: Database Backup with Compression

```bash
# Compressed dump — no uncompressed temp file on disk
pg_dump -U postgres mydb | gzip -9 > "/backup/mydb-$(date +%Y%m%d-%H%M%S).sql.gz"

# Verify backup is readable BEFORE you trust it
gunzip -c /backup/mydb-20260811-140000.sql.gz | head -20

# Restore
gunzip -c /backup/mydb-20260811-140000.sql.gz | psql -U postgres mydb

# Keep last 7 days, delete older
find /backup -name "mydb-*.sql.gz" -mtime +7 -delete
```

### Pattern 3: Stream to S3 Without Local Disk Space

```bash
# Disk is full — can't save locally — stream directly to S3
tar -czf - /var/log/myapp/ | aws s3 cp - s3://my-backups/logs-$(date +%Y%m%d).tar.gz

# Stream from S3 directly into extract (no local file needed)
aws s3 cp s3://my-backups/restore.tar.gz - | tar -xzvf - -C /opt/myapp/
```

### Pattern 4: Verify Backup Integrity

```bash
# ALWAYS verify before you need to restore
# (backups that fail silently are worse than no backups)

gzip -t /backup/myapp-20260811.tar.gz && echo "OK" || echo "CORRUPT"
tar -tzvf /backup/myapp-20260811.tar.gz > /dev/null && echo "OK" || echo "CORRUPT"

# Add to cron — verify last 24h of backups every morning at 3am:
# 0 3 * * * find /backup -name "*.tar.gz" -mtime -1 \
#   -exec gzip -t {} \; >> /var/log/backup-verify.log 2>&1
```

---

## Interview Angle

**Q: Why does `tar` need a separate `z`/`j`/`J` flag instead of always compressing?**

Because `tar`'s job is purely archiving — bundling files and preserving metadata. Compression is a separate, composable concern. Unix philosophy: each tool does one thing well, tools are composed via pipes.

```bash
# These are equivalent:
tar -czvf archive.tar.gz dir/
tar -cvf - dir/ | gzip > archive.tar.gz

# The -z flag is just a shortcut for the pipe.
# You can swap gzip for anything:
tar -cvf - dir/ | zstd  > archive.tar.zst
tar -cvf - dir/ | xz    > archive.tar.xz
```

**Q: How do you inspect a `.tar.gz` without extracting it?**

```bash
tar -tzvf archive.tar.gz              # list all files
tar -tzvf archive.tar.gz | grep conf  # filter the listing
tar -xzvf archive.tar.gz -O myapp/config.yml  # extract ONE file to stdout
```

**Q: Why choose `.tar.xz` over `.tar.gz`?**

```
xz compresses 20-30% smaller than gzip at the cost of 5-10x more CPU.

Worth it when:
  - You compress ONCE, many people download it (Linux packages, GitHub releases)
  - Cold storage where transfer cost > CPU cost

Not worth it when:
  - Real-time compression (use gzip -1 or zstd)
  - Systems where xz isn't installed (Alpine minimal images)
  - Frequently accessed archives
```

**Q: What's wrong with `zip -e` for protecting secrets?**

```
zip -e uses ZipCrypto — a weak algorithm from the 1990s.
Crackable with known-plaintext attacks:
  - You often know what some files inside the zip contain (LICENSE, README)
  - The encryption key can be recovered from those known bytes
  - Tools like pkcrack crack it in seconds

For real secrets: use GPG, age, or openssl enc with AES-256.
zip -e = "don't want casual viewers", not actual security.
```

**Q: `tar -czvf` with and without `-C` — what's the difference?**

```bash
# Without -C: archive contains relative path from current directory
cd /opt
tar -czvf app.tar.gz myapp/
# Archive root: myapp/config.yml, myapp/bin/run.sh

# With -C: tar changes into the directory first
tar -czvf app.tar.gz -C /opt myapp/
# Same result here

# Why it matters on extract:
# Archive with leading dir: extracts to /dest/myapp/config.yml  (safe)
# Archive without:          extracts to /dest/config.yml         (messy)
# ALWAYS check with tar -tzvf before extracting unknown archives
```