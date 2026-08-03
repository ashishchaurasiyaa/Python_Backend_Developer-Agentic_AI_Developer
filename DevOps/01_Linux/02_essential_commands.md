# Essential Linux Commands

**DevOps Track · Phase 1: Linux**

## Quick Concepts

- **Argument vs flag** — `command arg -f flagvalue` — flags modify behavior, args are the targets
- **Glob** — shell-expanded wildcard pattern (`*.log`) resolved BEFORE the command runs
- **Pipe (`|`)** — stdout of one command becomes stdin of the next — the core Unix composition tool
- **stdin/stdout/stderr** — file descriptors 0/1/2 every process gets by default
- **In-place edit** — modifying a file directly instead of printing to stdout (`sed -i`, `sort -o`)

---

## Why This Matters for Backend/DevOps Work

```
This is the toolkit you reach for BEFORE you write a script:
   - Grepping a production log for an error pattern during an incident
   - Renaming 500 uploaded files in one line instead of a Python loop
   - Finding every file over 1GB filling up a disk
   - Building a one-liner in CI to extract a version number from a file
   - Piping curl output through jq/grep to check a health endpoint

Speed here is a direct multiplier on how fast you debug production.
```

---

## Navigation: `ls`, `pwd`, `cd`

```bash
pwd                        # print current directory
ls                         # list files
ls -la                     # long format, include hidden (dotfiles)
ls -lh                     # long format, human-readable sizes (K/M/G)
ls -lt                     # sort by modified time, newest first
ls -lS                     # sort by size, largest first
ls -R                      # recursive listing

cd /var/log                # absolute path
cd ..                      # up one level
cd ~                       # home directory
cd -                       # previous directory (toggle back and forth)
```

```bash
# Practical: find the 5 most recently modified files in a deploy dir
ls -lt /opt/myapp | head -6

# Practical: total size of everything, human readable, largest first
ls -lhS /var/log | head -10
```

---

## Creating & Removing: `mkdir`, `rm`, `touch`

```bash
mkdir logs                  # create one dir
mkdir -p a/b/c               # create nested path, no error if exists
mkdir -m 700 secrets          # create with specific permissions

touch app.log                # create empty file OR update its mtime if it exists
touch -t 202601010000 file    # set a specific timestamp

rm file.txt                  # remove a file
rm -i file.txt                # prompt before removing (safer default to alias)
rm -rf build/                 # remove dir + contents, no prompt — DANGEROUS, always double-check the path
rmdir empty_dir/               # remove ONLY if empty (safety net vs rm -rf)
```

```bash
# Practical: nuke all __pycache__ dirs in a Python repo
find . -type d -name "__pycache__" -exec rm -rf {} +

# Practical: clean build artifacts safely with a dry-run first
find . -name "*.pyc"          # LOOK before you leap
find . -name "*.pyc" -delete  # then delete
```

---

## Copying & Moving: `cp`, `mv`

```bash
cp file.txt backup.txt         # copy file
cp -r src/ dst/                 # copy directory recursively
cp -a src/ dst/                  # archive mode — preserves perms/timestamps/symlinks
cp -v file.txt backup.txt         # verbose — show what's happening
cp -n file.txt backup.txt          # no-clobber — don't overwrite existing

mv old.txt new.txt              # rename (same fs = instant, no actual copy)
mv file.txt /opt/archive/        # move into a directory
mv -i file.txt existing.txt       # prompt before overwrite
```

```bash
# Practical: batch-rename all .txt to .bak
for f in *.txt; do mv "$f" "${f%.txt}.bak"; done

# Practical: timestamped backup before editing a config
cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.$(date +%Y%m%d-%H%M%S).bak
```

---

## Finding Files: `find`, `locate`

```bash
find . -name "*.py"                    # by exact glob pattern (case-sensitive)
find . -iname "*.PY"                    # case-insensitive
find . -type f -name "*.log"             # files only
find . -type d -name "node_modules"       # directories only
find . -mtime -1                          # modified in last 24h
find . -mtime +30                          # modified more than 30 days ago
find . -size +100M                          # bigger than 100MB
find . -size -1k                             # smaller than 1KB
find . -empty                                 # empty files/dirs
find / -perm -4000 2>/dev/null                # SUID binaries (security audit)
find . -name "*.pyc" -delete                   # find AND delete
find . -name "*.log" -exec gzip {} \;           # run a command per result
find . -name "*.log" -exec gzip {} +             # same, but batches args (faster)

locate nginx.conf                                # instant — searches a prebuilt index
sudo updatedb                                     # rebuild the locate index (locate is stale until this runs)
```

```
find vs locate:
  find    — walks the filesystem live, always accurate, slower on huge trees
  locate  — queries a cached index (updatedb, often cron'd nightly), instant
            but can miss files created since the last index update
```

---

## Searching Inside Files: `grep`

```bash
grep "ERROR" app.log                    # matching lines
grep -i "error" app.log                  # case-insensitive
grep -r "TODO" .                          # recursive through a directory
grep -rn "TODO" . --include="*.py"         # recursive + line numbers + filter by extension
grep -v "DEBUG" app.log                     # invert match (exclude lines)
grep -c "ERROR" app.log                      # count matching lines
grep -l "ERROR" *.log                         # just filenames that contain a match
grep -E "(ERROR|FATAL|CRITICAL)" app.log       # extended regex, alternation
grep -A3 -B3 "Traceback" app.log                # 3 lines After + Before context
grep -w "cat" file                                # whole word only (not "concatenate")
```

```bash
# Practical: find every 500 error in today's nginx access log
grep " 500 " /var/log/nginx/access.log | wc -l

# Practical: search all Python files for a deprecated function call
grep -rn "old_function(" --include="*.py" .
```

---

## Stream Editing: `sed`

```bash
sed 's/foo/bar/' file           # replace FIRST occurrence per line
sed 's/foo/bar/g' file            # replace ALL occurrences per line (global)
sed -n '10,20p' file               # print only lines 10-20
sed '5d' file                       # delete line 5
sed '/DEBUG/d' file                  # delete lines matching pattern
sed -i 's/foo/bar/g' file             # in-place edit (Linux)
sed -i '' 's/foo/bar/g' file           # in-place edit (macOS — needs empty '' backup arg)
sed -i.bak 's/foo/bar/g' file           # in-place, keep a .bak backup
```

```bash
# Practical: bump a version string across a config file
sed -i 's/version: 1.2.3/version: 1.2.4/' config.yml

# Practical: strip Windows carriage returns from a file
sed -i 's/\r$//' file.txt
```

---

## Column Processing: `awk`

```bash
awk '{print $1}' file             # print column 1 (whitespace-delimited)
awk -F',' '{print $2}' file.csv    # custom delimiter (CSV)
awk '{print $1, $NF}' file          # first + last column
awk '$3 > 100 {print $0}' file       # conditional — print full line if col 3 > 100
awk '{sum+=$2} END{print sum}' file   # sum a column
awk 'NR==5' file                       # print only line 5
awk '{print NR, $0}' file               # prepend line numbers
```

```bash
# Practical: top IPs hitting an API from an access log
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -5

# Practical: total bytes transferred (nginx log, bytes usually col 10)
awk '{sum+=$10} END{print sum/1024/1024 " MB"}' access.log
```

---

## `cut`, `sort`, `uniq`, `head`, `tail`

```bash
cut -d',' -f1,3 file.csv       # extract fields 1 and 3 (comma-delimited)
cut -c1-10 file                 # first 10 characters of each line
cut -d':' -f1 /etc/passwd        # just usernames from passwd

sort file                        # alphabetical
sort -n file                      # numeric sort
sort -r file                       # reverse
sort -k2 file                       # sort by 2nd field
sort -u file                         # sort + dedupe in one step
sort -t',' -k2 -n file.csv            # CSV sort by 2nd column, numeric

uniq file                              # remove ADJACENT duplicate lines (must sort first!)
uniq -c file                            # count occurrences of each adjacent line
sort file | uniq -c | sort -rn           # classic "top N frequency" pattern

head -n 20 file                           # first 20 lines
head -c 100 file                            # first 100 bytes
tail -n 50 file                              # last 50 lines
tail -f app.log                               # follow live (stops if file is rotated/deleted)
tail -F app.log                                # follow, survives log rotation — prefer this in prod
```

```bash
# Practical: most frequent status codes in a log
awk '{print $9}' access.log | sort | uniq -c | sort -rn

# Practical: unique visitor IPs
awk '{print $1}' access.log | sort -u | wc -l
```

---

## Output Duplication: `tee`

```bash
cmd | tee output.log                  # write to file AND pass through to stdout
cmd | tee -a output.log                # append instead of overwrite
cmd | tee output.log | grep ERROR       # save full output, filter in the same pipeline

# common in deploy scripts — see full output live AND keep a log
./deploy.sh 2>&1 | tee -a deploy.log
```

---

## Building Command Lines: `xargs`

```bash
find . -name "*.log" | xargs rm                      # feed find results as ARGS, not stdin
find . -name "*.log" | xargs -I{} mv {} /tmp/         # {} placeholder for each item
cat urls.txt | xargs -n1 curl -O                       # one curl call per line
find . -name "*.jpg" | xargs -P4 -I{} convert {} {}.png # -P4 = run 4 in parallel

echo "a b c" | xargs -n1 echo                            # one arg per invocation
```

```
Why xargs instead of piping directly?
  Most commands (rm, cp, mv) don't read stdin as their operand list —
  they take arguments. xargs converts a stream of lines into arguments.

  find . -name "*.tmp" | rm          ✗ rm doesn't read stdin, does nothing useful
  find . -name "*.tmp" | xargs rm     ✓ works
  find . -name "*.tmp" -delete         ✓ also works, no xargs needed for find specifically
```

---

## Senior Tip

```
1. Prefer `find ... -delete` or `-exec ... +` over piping to xargs for
   filenames — filenames with spaces/newlines break naive pipes.
2. `uniq -c` only counts ADJACENT duplicates — always `sort` first.
3. `sed -i` differs between GNU (Linux) and BSD (macOS) — the macOS
   version requires an explicit (even empty) backup suffix argument.
   This breaks scripts written on a Mac when they hit a Linux CI runner.
4. Chain tools instead of reaching for Python for quick log analysis —
   `awk | sort | uniq -c | sort -rn` is faster to write and run than a
   script for one-off investigation.
```

## Interview Angle

**Q: `grep -r` vs `find -exec grep`?**
`grep -r` is simpler and usually faster for "search everything under a directory." `find ... -exec grep` is for when you need to filter WHICH files first (by name, size, mtime) before searching their content.

**Q: Why does `uniq -c` sometimes give wrong-looking counts?**
Because it only collapses consecutive duplicate lines. If duplicates aren't adjacent, sort first: `sort file | uniq -c`.

**Q: `xargs` vs a direct pipe — when do you need it?**
When the downstream command takes its operands as command-line arguments rather than reading stdin (e.g. `rm`, `cp`, `mv`, `curl`). `xargs` bridges stream output into argument lists.
