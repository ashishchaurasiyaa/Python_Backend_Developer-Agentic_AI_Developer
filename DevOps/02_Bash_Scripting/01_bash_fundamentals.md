# Bash Scripting Fundamentals

**DevOps Track · Phase 2: Bash Scripting**

## Quick Concepts

- **Shebang** = `#!/usr/bin/env bash` — first line, tells the OS which interpreter runs the script
- **Variable** = no `$` when assigning, `$` when reading (`x=1` then `echo $x`)
- **Exit status** = `$?` — 0 means success, non-zero means failure, every command sets it
- **Positional parameter** = `$1`, `$2`... script/function arguments; `$@` all args, `$#` arg count
- **Quoting** = `"$var"` preserves spaces/word-splitting safety; unquoted `$var` does NOT
- **Array** = ordered list (`arr=(a b c)`); **associative array** = key-value map (`declare -A`)
- **Test** = `[ ]` (POSIX) vs `[[ ]]` (bash-only, safer — supports `&&`, `||`, regex `=~` without escaping)
- **Parameter expansion** = the `${var...}` family beyond simple substitution — trimming, replacing, measuring length, case conversion, all without calling out to `sed`/`awk`
- **Heredoc** = `<<EOF ... EOF` — a multi-line string literal fed to a command's stdin
- **ShellCheck** = the standard static analyzer for shell scripts — catches quoting bugs, unset-variable typos, and portability issues before runtime
- **getopts** = bash's built-in flag parser (`-e prod -v 1.2.3`), the standard alternative to relying on raw positional arguments

---

## Why This Matters for Backend/DevOps Work

```
Bash is the glue language of infra:
   - Deploy scripts, entrypoint scripts for Docker containers
   - CI/CD pipeline steps (GitHub Actions "run:" blocks ARE bash)
   - Cron jobs and log rotation/cleanup automation
   - Health check loops, backup scripts, quick data-munging one-offs

Past ~100 lines or real data structures, switch to Python — but every
backend engineer needs to read and write bash fluently for the glue layer.
```

---

## Variables

```bash
#!/usr/bin/env bash
set -euo pipefail

name="alice"
age=30
echo "hello, $name, age $age"
echo "hello, ${name}_suffix"      # braces avoid ambiguity when concatenating

readonly PI=3.14                    # constant — reassigning raises an error
unset name                            # delete a variable

# Default values / fallbacks
echo "${USER:-anonymous}"               # use 'anonymous' if USER is unset or empty
echo "${PORT:=8000}"                      # use 8000 AND assign it to PORT if unset
: "${DATABASE_URL:?must be set}"            # exit with error message if unset

# Command substitution — capture output of a command into a variable
today=$(date +%Y-%m-%d)
file_count=$(ls | wc -l)
```

---

## Parameter Expansion — String Manipulation Without `sed`/`awk`

The `${var:-default}` family from above handles missing values. A separate, equally common family of `${var...}` expansions trims, replaces, measures, and case-converts strings — entirely in bash, no subprocess spawned.

```bash
path="/opt/myapp/releases/v1.2.3.tar.gz"

# Remove from the FRONT — # shortest match, ## longest match
echo "${path#*/}"          # opt/myapp/releases/v1.2.3.tar.gz  (strip up to first /)
echo "${path##*/}"           # v1.2.3.tar.gz                     (strip up to LAST / — basename)

# Remove from the BACK — % shortest match, %% longest match
echo "${path%.*}"           # /opt/myapp/releases/v1.2.3.tar    (strip shortest .ext)
echo "${path%%.*}"            # /opt/myapp/releases/v1            (strip everything from FIRST .)
echo "${path%/*}"               # /opt/myapp/releases              (strip filename — dirname)

# Length
echo "${#path}"                    # character count

# Search and replace
name="hello-world-test"
echo "${name/-/_}"                    # hello_world-test   (replace FIRST match)
echo "${name//-/_}"                     # hello_world_test    (replace ALL matches — // )
echo "${name/#hello/HI}"                  # HI-world-test        (replace only if match is at the START)
echo "${name/%test/DONE}"                   # hello-world-DONE       (replace only if match is at the END)

# Substring extraction — ${var:offset:length}
version="v1.2.3"
echo "${version:1}"        # 1.2.3     (from index 1 to end)
echo "${version:1:1}"       # 1          (1 char starting at index 1)

# Case conversion (bash 4+)
env="PRODUCTION"
echo "${env,,}"          # production   (lowercase, all chars — , = one char, ,, = all)
echo "${env,}"             # pRODUCTION    (lowercase just the first char)
lower="staging"
echo "${lower^^}"            # STAGING       (uppercase all — ^ = first char, ^^ = all)
```

```
The #/##/%/%% family is genuinely the one most people never learn and
then reach for `basename`/`dirname`/`sed` for something bash already
does natively:

  #  strip from front, shortest match     ##  strip from front, longest match
  %  strip from back,  shortest match     %%  strip from back,  longest match

Mnemonic: # is to the LEFT of a US keyboard's %, and strips from the
LEFT; % strips from the RIGHT. `##*/` for "everything up to the last
slash" (basename) and `%/*` for "everything except the last segment"
(dirname) are worth memorizing outright — they show up constantly in
real deploy scripts.
```

---

## Input / Output

### echo, printf, read

```bash
echo "hello"                        # simple print, adds newline
echo -n "no newline"                  # suppress trailing newline
echo -e "tab\tnewline\n"                # interpret escape sequences

printf "%s is %d years old\n" "alice" 30   # C-style formatted output — preferred for precision
printf "%-10s%5d\n" "name" 42                # left-pad string, right-pad number

read -p "Enter name: " name                    # prompt + capture into $name
read -s -p "Password: " pass                     # -s = silent (no echo to terminal)
read -r line                                       # -r = don't interpret backslashes (ALWAYS use with read)
read -a arr                                          # read into an array
IFS=',' read -ra fields <<< "a,b,c"                    # custom delimiter split
```

### Redirection

```bash
cmd > file           # stdout → file (overwrite)
cmd >> file            # stdout → file (append)
cmd < file               # stdin ← file
cmd 2> err.log             # stderr → file
cmd > out 2>&1               # both stdout AND stderr → out (order matters: 2>&1 AFTER >out)
cmd &> out                     # shorthand for the line above
cmd < in.txt > out.txt 2> err.txt

cmd1 | cmd2                       # pipe stdout of cmd1 into stdin of cmd2
cmd | tee log.txt | grep ERROR      # tee = save to file AND continue piping
```

### Heredocs — Multi-Line Input Without a Separate File

A heredoc (`<<`) feeds a multi-line block of text to a command's stdin, or writes it to a file via redirection — the standard way to generate config files, SQL, or templated text from inside a script instead of building a string with dozens of `echo` calls.

```bash
# Write a multi-line file
cat > /etc/nginx/conf.d/app.conf <<EOF
server {
    listen 80;
    server_name ${DOMAIN};
    location / {
        proxy_pass http://127.0.0.1:${PORT};
    }
}
EOF

# Pipe a heredoc directly into a command's stdin (e.g. psql)
psql -U app -d mydb <<SQL
SELECT count(*) FROM orders WHERE status = 'pending';
SQL
```

```
<<EOF   → variables and command substitutions INSIDE the block ARE
          expanded ($DOMAIN, $PORT above become their real values)
<<'EOF' → quoting the delimiter disables ALL expansion — the block is
          treated as fully literal text, useful when writing a script
          or config that itself contains $ signs you don't want bash
          to touch (e.g. generating a shell script or a Makefile)
<<-EOF  → the "-" variant strips LEADING TABS (not spaces) from each
          line, letting you indent the heredoc body to match the
          surrounding script's indentation without that indentation
          ending up in the output
```

Related but rarer — **process substitution** (`<(...)`) treats a command's output as if it were a temporary file, useful for tools that expect a file path rather than stdin:

```bash
diff <(sort file1.txt) <(sort file2.txt)     # compare two commands' output without temp files
```

---

## Conditionals

### if / elif / else

```bash
if [ "$x" -gt 10 ]; then
    echo "big"
elif [ "$x" -eq 10 ]; then
    echo "exact"
else
    echo "small"
fi
```

### `test` / `[ ]` vs `[[ ]]`

```bash
# [ ] is the classic 'test' command — POSIX, works in /bin/sh too
[ "$env" = "prod" ]              # string equality — MUST quote, MUST space around =
[ "$x" -eq 10 ]                    # numeric equality (-eq -ne -gt -lt -ge -le)

# [[ ]] is bash-only — safer, more features, prefer it in bash scripts
[[ "$env" == "prod" ]]              # == works, no word-splitting surprises even unquoted
[[ "$x" =~ ^[0-9]+$ ]]                # regex match (only in [[ ]])
[[ "$a" == "x" && "$b" == "y" ]]        # &&/|| work directly inside [[ ]]
```

### File Tests

```bash
[ -f /etc/passwd ]        # is a regular file
[ -d /var/log ]             # is a directory
[ -x ./run.sh ]               # is executable
[ -e file ]                     # exists (any type)
[ ! -e file ]                     # does NOT exist
[ -s file ]                         # exists and is non-empty
[ -r file ] && [ -w file ]            # readable and writable
```

### Case Statements

```bash
case "$1" in
    start)
        echo "starting..."
        ;;
    stop)
        echo "stopping..."
        ;;
    restart|reload)
        echo "restarting..."
        ;;
    *)
        echo "usage: $0 {start|stop|restart}"
        exit 1
        ;;
esac
```

---

## Loops

### for

```bash
for f in *.log; do              # glob expansion
    gzip "$f"
done

for i in {1..10}; do              # brace range
    echo "$i"
done

for i in {0..20..5}; do             # range with step
    echo "$i"
done

for ((i = 0; i < 10; i++)); do        # C-style
    echo "$i"
done

for arg in "$@"; do                    # iterate script arguments, safely quoted
    echo "$arg"
done
```

### while / until

```bash
count=0
while [ "$count" -lt 5 ]; do
    echo "$count"
    count=$((count + 1))
done

# Read a file line by line — the correct, safe idiom
while IFS= read -r line; do
    echo "$line"
done < input.txt

until curl -sf http://localhost:8000/health > /dev/null; do
    echo "waiting..."
    sleep 2
done
echo "service is up"
```

### break / continue

```bash
for f in *.log; do
    [ -s "$f" ] || continue     # skip empty files
    [ "$f" = "stop.log" ] && break
    process "$f"
done
```

---

## Functions

```bash
deploy() {
    local env=$1                 # 'local' scopes the variable to the function — always use it
    local version=$2
    echo "deploying $version to $env"
    return 0                       # exit status of the function (0 = success)
}

deploy "prod" "v1.2.3"

# Capture function OUTPUT (not return code) via command substitution
get_version() {
    echo "1.2.3"
}
v=$(get_version)

# Check argument count inside a function
require_args() {
    if [ "$#" -lt 2 ]; then
        echo "need 2 args, got $#" >&2
        return 1
    fi
}
```

### Sourcing Shared Functions Across Scripts

Once you have more than one script (deploy.sh, backup.sh, healthcheck.sh) repeating the same `log()`/`require_args()`-style helpers, pull them into a shared file and `source` it instead of copy-pasting.

```bash
# lib/common.sh
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

require_env() {
    local var_name=$1
    [ -n "${!var_name:-}" ] || { echo "ERROR: $var_name must be set" >&2; exit 1; }
}
```

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"    # or: . lib/common.sh — identical, '.' is the POSIX form

require_env DATABASE_URL
log "starting deploy"
```

```
"$(dirname "${BASH_SOURCE[0]}")"  → resolves the SCRIPT's own directory
regardless of where it's CALLED from — using a relative path like
"./lib/common.sh" breaks the moment someone runs the script from a
different working directory. This is the standard fix for "works
when I run it, breaks in cron/CI" caused by relative sourcing.
```

---

## Arrays

### Indexed Arrays

```bash
fruits=("apple" "banana" "cherry")
echo "${fruits[0]}"              # apple
echo "${fruits[@]}"                # all elements
echo "${#fruits[@]}"                 # count = 3

fruits+=("date")                       # append
unset 'fruits[1]'                        # remove banana (leaves a gap in indices)

for f in "${fruits[@]}"; do               # ALWAYS quote "${arr[@]}" to preserve elements with spaces
    echo "$f"
done
```

### Associative Arrays (bash 4+)

```bash
declare -A config
config[env]="prod"
config[region]="ap-south-1"
config["db_host"]="db.internal"

echo "${config[env]}"                    # prod
echo "${!config[@]}"                       # all KEYS
echo "${config[@]}"                          # all VALUES

for key in "${!config[@]}"; do
    echo "$key = ${config[$key]}"
done
```

---

## Real-World Script Example

```bash
#!/usr/bin/env bash
set -euo pipefail

# usage: ./deploy.sh <env> <version>

ENV="${1:?usage: deploy.sh <env> <version>}"
VERSION="${2:?usage: deploy.sh <env> <version>}"

declare -A HOSTS=(
    [staging]="staging.example.com"
    [prod]="prod.example.com"
)

HOST="${HOSTS[$ENV]:-}"
if [ -z "$HOST" ]; then
    echo "ERROR: unknown environment '$ENV'" >&2
    exit 1
fi

echo "Deploying $VERSION to $ENV ($HOST)..."

if ! ssh "deploy@$HOST" "test -d /opt/myapp"; then
    echo "ERROR: /opt/myapp not found on $HOST" >&2
    exit 1
fi

ssh "deploy@$HOST" "cd /opt/myapp && git fetch && git checkout $VERSION"
ssh "deploy@$HOST" "sudo systemctl restart myapp"

for i in {1..10}; do
    if ssh "deploy@$HOST" "curl -sf http://localhost:8000/health > /dev/null"; then
        echo "Deploy successful."
        exit 0
    fi
    sleep 3
done

echo "ERROR: health check failed after deploy" >&2
exit 1
```

---

## Parsing Command-Line Flags — `getopts`

The example above relies on positional arguments (`$1`, `$2`) in a fixed order — fine for a 2-argument script, fragile the moment a script grows optional flags. Real production scripts almost always parse named flags instead: `./deploy.sh -e prod -v 1.2.3 --dry-run`.

```bash
#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 -e <env> -v <version> [-d]" >&2
    exit 1
}

DRY_RUN=false

while getopts "e:v:dh" opt; do
    case "$opt" in
        e) ENV="$OPTARG" ;;
        v) VERSION="$OPTARG" ;;
        d) DRY_RUN=true ;;
        h) usage ;;
        \?) usage ;;      # unknown flag
    esac
done

: "${ENV:?-e <env> is required}"
: "${VERSION:?-v <version> is required}"

echo "Deploying $VERSION to $ENV (dry_run=$DRY_RUN)"
```

```
getopts "e:v:dh"
  e:  → -e REQUIRES an argument, captured into $OPTARG
  v:  → same, another required-argument flag
  d   → -d is a boolean FLAG, no argument (no colon after it)
  h   → -h likewise, triggers usage/help

$OPTIND tracks how many arguments getopts has consumed so far — after
the while loop, `shift $((OPTIND - 1))` removes all parsed flags from
"$@", leaving any remaining POSITIONAL arguments (if the script mixes
flags and positional args) accessible as $1, $2, ... as normal.
```

```
getopts is bash's BUILT-IN parser — POSIX-portable, but limited to
single-character flags and no long-option (--environment) support out
of the box. For scripts wanting `--environment prod` style long flags,
teams either hand-roll a manual `while [[ "$1" == --* ]]; do case
"$1" in --environment) ENV="$2"; shift ;; esac; shift; done` loop, or
just accept that a bash script needing rich long-flag parsing is
itself a signal it's grown complex enough to be rewritten in Python.
```

---

## Linting — ShellCheck

Every other phase in this track has a static-analysis story (ruff for Python, tfsec/Checkov for Terraform, Trivy for images). Bash's is **ShellCheck** — and given how easy bash is to get subtly wrong (unquoted variables, wrong test operators, `$?` checked after the wrong command), it's arguably more load-bearing here than in most languages.

```bash
# Local
shellcheck deploy.sh
shellcheck backup.sh lib/*.sh

# Example finding — this is EXACTLY the #1 bash bug class
# SC2086: Double quote to prevent globbing and word splitting
cp $SOURCE_FILE $DEST_DIR      # ShellCheck flags both $SOURCE_FILE and $DEST_DIR
cp "$SOURCE_FILE" "$DEST_DIR"    # fixed
```

```yaml
# .github/workflows/lint.yml
      - name: ShellCheck
        uses: ludeeus/action-shellcheck@master
        with:
          scandir: './scripts'
```

```
ShellCheck catches, automatically, essentially every bug class this
file has told you to avoid by habit: unquoted variables, using [ ]
where behavior differs from [[ ]], comparing strings with -eq instead
of =, a $? checked after the WRONG command (e.g. checked after `echo`
instead of the command before it), and useless use of cat. Running it
in CI on every script change is strictly better than relying on every
contributor remembering the Senior Tip rules below by memory.
```

---

## Senior Tip

```
1. Always quote variables: "$var" not $var. Unquoted variables undergo
   word-splitting and glob expansion — the #1 source of bash bugs.
2. Use [[ ]] over [ ] in bash-specific scripts — fewer footguns.
3. `local` every function variable — without it, everything is global
   and functions silently clobber each other's state.
4. set -euo pipefail at the top of every script (see 02_automation_cron_scripting.md
   for the full breakdown of what each flag does).
5. Prefer $(...) over legacy backticks `...` — nests cleanly, more readable.
```

## Interview Angle

**Q: Difference between `[ ]` and `[[ ]]`?**
`[ ]` is the POSIX `test` command — portable to `/bin/sh`, but requires careful quoting and doesn't support `&&`/`||`/regex directly inside it. `[[ ]]` is a bash keyword — safer (no word-splitting on unquoted variables inside it), supports `=~` regex matching and logical operators natively. Use `[[ ]]` unless you specifically need POSIX `sh` portability.

**Q: What does `local` do inside a function and why does it matter?**
It scopes a variable to the function instead of leaking it into global scope. Without it, two functions using the same variable name silently overwrite each other's state — a hard-to-trace bug in longer scripts.

**Q: `$@` vs `$*` — what's the difference?**
Both expand to all positional parameters, but `"$@"` (quoted) expands to each argument as a SEPARATE quoted word — preserving arguments with spaces. `"$*"` expands to ONE single string joined by the first char of `$IFS`. Always use `"$@"` when forwarding arguments.

**Q: Get just the filename (no path, no extension) from `/opt/app/releases/v1.2.3.tar.gz` using only bash, no `basename`/`sed`.**
`${path##*/}` strips everything up to and including the last `/` (basename: `v1.2.3.tar.gz`), then `${name%%.*}` strips from the first `.` onward (`v1`) — or `${name%.tar.gz}` if you only want to strip that specific known extension rather than everything after the first dot.

**Q: Why prefer `getopts` over reading `$1`/`$2` positionally once a script has more than one or two arguments?**
Positional args are order-dependent and undocumented at the call site — the caller has to know `$1` is env and `$2` is version. `getopts` makes flags self-describing (`-e prod -v 1.2.3`), order-independent, and supports optional boolean flags (`-d` for dry-run) without needing placeholder positional args for skipped options.
