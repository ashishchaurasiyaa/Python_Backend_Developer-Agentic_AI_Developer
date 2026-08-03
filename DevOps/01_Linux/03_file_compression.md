# File Compression & Archiving

**DevOps Track · Phase 1: Linux**

## Quick Concepts

- **Archive** = bundling multiple files into ONE file, preserving structure (no compression by itself — that's `tar`'s job)
- **Compression** = shrinking data size using an algorithm (gzip, bzip2, xz, zip's DEFLATE)
- **tarball** = a `.tar` archive, usually further compressed to `.tar.gz` / `.tgz`
- **Lossless** = compression that reconstructs the exact original bytes (all these tools are lossless)

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

### Core Flags

```
c   create archive
x   extract archive
t   list contents (test) without extracting
v   verbose — show files as processed
f   file — MUST be followed by the archive filename (always last flag before name)
z   filter through gzip (.tar.gz / .tgz)
j   filter through bzip2 (.tar.bz2)
J   filter through xz (.tar.xz)
```

### Common Combos

```bash
tar -czvf archive.tar.gz dir/       # Create, gZip, Verbose, File — most common
tar -xzvf archive.tar.gz             # eXtract, gZip, Verbose, File
tar -xzvf archive.tar.gz -C /opt/     # extract into a specific directory
tar -tzvf archive.tar.gz               # list contents without extracting (sanity check first!)

tar -cJvf archive.tar.xz dir/            # xz compression — smaller, slower to compress
tar -xJvf archive.tar.xz

tar -cjvf archive.tar.bz2 dir/             # bzip2 — middle ground, less common now

tar -cvf archive.tar dir/                    # no compression, just bundling
tar --exclude='*.log' -czvf app.tar.gz app/   # exclude patterns
tar -czvf - dir/ | ssh user@host 'cat > archive.tar.gz'   # stream over SSH without a local temp file
```

### Reading the flag order mnemonic

```
"czvf" = Create, Ze compress, Verbose, to File <name>
"xzvf" = eXtract, Ze decompress, Verbose, from File <name>

Easy to remember: whatever you did to make it (c+z), you undo to open it (x+z).
```

---

## gzip / gunzip

```bash
gzip file.txt              # compress IN PLACE → file.txt.gz (original deleted)
gzip -k file.txt             # keep original, also produce file.txt.gz
gzip -9 file.txt               # max compression (slower)
gzip -d file.txt.gz              # decompress (same as gunzip)

gunzip file.txt.gz            # decompress → file.txt (deletes .gz)
zcat file.txt.gz               # view compressed file contents WITHOUT decompressing
zgrep "ERROR" app.log.gz         # grep directly inside a gzipped file
```

```bash
# Practical: compress yesterday's rotated logs
gzip /var/log/app/app.log.1

# Practical: search inside rotated compressed logs without unpacking
zgrep "OutOfMemory" /var/log/app/*.gz
```

---

## zip / unzip

```bash
zip archive.zip file1 file2          # zip specific files
zip -r archive.zip dir/                # zip a directory recursively
zip -e archive.zip secret.txt            # password-protect (weak encryption, don't rely on it for real secrets)

unzip archive.zip                         # extract to current dir
unzip archive.zip -d /opt/target/           # extract to specific dir
unzip -l archive.zip                          # list contents without extracting
unzip -o archive.zip                            # overwrite without prompting
```

---

## tar.gz vs zip — Which to Use

| | tar.gz | zip |
|---|---|---|
| **Preserves Unix permissions/symlinks** | Yes | Not reliably |
| **Cross-platform (Windows-friendly)** | Awkward without extra tools | Native everywhere |
| **Compression ratio** | Slightly better (gzip/xz) | Good, DEFLATE |
| **Streaming (pipe to/from network)** | Natural — tar streams well | Less natural, needs full file usually |
| **Typical DevOps use** | Linux server backups, Docker layers, deploy artifacts | Lambda deployment packages, cross-platform sharing, Windows-consumed exports |

### Senior Tip

```
Default to tar.gz on Linux/Unix infrastructure — it preserves
permissions and symlinks correctly, which matters for backups you
intend to restore. Use zip specifically when the consumer is Windows,
or the target is an AWS Lambda deployment package (Lambda requires zip).
```

---

## Interview Angle

**Q: Why does `tar` need a separate `z`/`j`/`J` flag instead of always compressing?**
Because `tar`'s job is purely archiving (bundling + preserving metadata). Compression is a separate, composable concern — you can tar without compressing, or pipe a tarball through any compressor you want. Separation of concerns, Unix-philosophy style.

**Q: How do you inspect a `.tar.gz` without extracting it?**
`tar -tzvf archive.tar.gz` lists contents; `zcat` (for plain gz) or `tar -xzvf archive.tar.gz -O file` streams a single file's contents to stdout.

**Q: Why might you choose `.tar.xz` over `.tar.gz`?**
xz compresses noticeably smaller than gzip at the cost of more CPU time — worth it for archival/cold storage where you compress once and rarely decompress, not worth it for hot paths where compression speed matters.
