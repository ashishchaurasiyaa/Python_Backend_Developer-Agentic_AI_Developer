# 05 — Pandas for Tabular Data (Backend, Not Data Science)

> File 04 covered **writing** Excel/CSV. This file covers **reading** them: a user
> uploads a messy spreadsheet and you must turn it into validated rows in your DB
> without OOM-ing the box or silently corrupting data.

---

## The Backend Job vs the Data Science Job

| | Data science | Backend (this file) |
|---|---|---|
| Input | Clean, known schema | User upload, schema is a guess |
| Bad rows | Drop them, move on | Must report back to the user, row by row |
| Correctness | "Close enough" | `"007"` must not become `7` |
| Memory | Laptop with 32 GB | 512 MB container, 20 concurrent requests |
| Output | Chart / model | ORM bulk insert inside a transaction |
| Failure mode | Notebook cell errors | HTTP 500 at 3 a.m. |

You use *maybe 10%* of pandas. You use it for: parse, coerce, validate, hand off.
Everything else (groupby pipelines, merges, plotting) belongs elsewhere.

---

## Decision Table: pandas vs openpyxl vs csv vs polars

| Tool | Reach for it when | Avoid when |
|---|---|---|
| **`csv` (stdlib)** | Pure CSV, streaming row-by-row, constant memory, zero deps | You need Excel, type inference, or column ops |
| **`openpyxl`** (read_only) | `.xlsx`, need per-cell control (merged cells, formulas, styles, multiple oddly-shaped sheets) | Big files without `read_only=True`; it is slow |
| **`pandas`** | Mixed CSV/Excel, need dtype coercion, vectorised validation, chunking, dedupe | Tiny files (import cost ~0.5 s), or truly huge files with tight RAM |
| **`polars`** | Big files, strict schemas, speed/memory matter, greenfield code | Team doesn't know it; ecosystem glue expects a DataFrame |
| **`pyarrow.csv`** | Multi-GB CSV → Parquet/Arrow, zero-copy handoff | Excel; fiddly per-row error reporting |

Rule of thumb: **CSV-only + streaming → stdlib `csv`. Anything Excel-shaped or needing
coercion → pandas. > ~1 GB or hot path → polars/pyarrow.**

```bash
pip install "pandas>=2.2" openpyxl        # xlsx reading needs openpyxl
pip install "pandas>=2.2" python-calamine        # much faster xlsx reader, see below
pip install "polars>=1.0"                 # optional alternative
```

---

## Reading a CSV Safely — the Only Signature You Need

The default `pd.read_csv(path)` is a **loaded gun** in a backend. This is the safe form:

```python
import pandas as pd

df = pd.read_csv(
    file_obj,
    dtype=str,                 # 1. read EVERYTHING as string, coerce later
    keep_default_na=False,     # 2. don't turn "NA", "None", "null" into NaN
    na_values=[""],            # 3. only truly empty cells are missing
    encoding="utf-8-sig",      # 4. eat the Excel BOM
    engine="python",           # 5. tolerant of ragged/odd delimiters (slower)
    on_bad_lines="warn",       # 6. never silently drop malformed rows
    usecols=EXPECTED_COLUMNS,  # 7. read only what you need
    skipinitialspace=True,
)
```

Why each one matters:

### 1. `dtype=str` — the single most important argument

Pandas type inference is *per column, based on a sample*, and it is destructive:

| Source cell | Inferred as | You get | Damage |
|---|---|---|---|
| `007` | int64 | `7` | Leading zeros gone — SKUs, PIN codes, phone numbers |
| `1e5` | float64 | `100000.0` | Product code became a number |
| `+91 98765 43210` | object | fine | (mixed column → object, saved by luck) |
| `TRUE` / `FALSE` | bool | `True` | Fine until row 5000 has `"maybe"` → whole column object |
| `2024-01-02` | object (pandas 2.x) | string | Needs explicit parse |
| `00012345678901234567` | float64 | `1.2345678901234568e+19` | **Silent precision loss** |

That last row is the classic: a 20-digit account number read as float64 loses digits
and no exception is raised. `dtype=str` then explicit coercion is the only safe order.

### 2/3. NA handling

By default pandas treats these as missing: `""`, `#N/A`, `N/A`, `NA`, `NULL`, `NaN`,
`None`, `nan`, `null`, `-1.#IND`, and more. If your data has a country **NA** (Namibia)
or a status literally called `NULL`, defaults corrupt it. `keep_default_na=False` +
explicit `na_values` puts you in control.

### 4. Encodings

The three you will actually meet:

| Encoding | Where from | Symptom if wrong |
|---|---|---|
| `utf-8-sig` | Excel "Save as CSV UTF-8" | Leading `ï»¿` on the first header name |
| `cp1252` / `latin-1` | Windows Excel, older exports | `UnicodeDecodeError: 0x92` (smart quote) |
| `utf-16` | Excel "Unicode Text (*.txt)" | Nulls between every character |

Detect, then fall back:

```python
def read_with_encoding_fallback(raw: bytes) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc, dtype=str)
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode file; please re-save as UTF-8 CSV")
```

`latin-1` never raises (every byte is a valid codepoint) so it makes a good last
resort — it may mojibake, but you get *something* to show the user.
For a smarter guess: `pip install charset-normalizer` and sniff the first 64 KB.

### 5. `engine=`

| Engine | Speed | Tolerance | Notes |
|---|---|---|---|
| `c` (default) | fast | strict | no `sep=None` sniffing, no regex separators |
| `python` | ~3-5x slower | tolerant | supports `sep=None` (auto-sniff), regex seps |
| `pyarrow` | fastest, multithreaded | strict | fewer options, great for clean big files |

For user uploads: `engine="python", sep=None` to auto-detect `,` vs `;` vs tab
(European Excel exports use `;`), then re-read with the C engine if you need speed.

### 6. `on_bad_lines`

`"error"` (default) raises on the first ragged row — one broken row kills a
100 k-row import. `"skip"` silently discards. `"warn"` skips but logs. Best is a
callable (C/python engine, pandas ≥ 2.2), which lets you *collect* bad rows and
report them:

```python
bad_rows: list[list[str]] = []

df = pd.read_csv(
    path, dtype=str,
    engine="python",
    on_bad_lines=lambda row: bad_rows.append(row) or None,  # returning None skips it
)
```

---

## Messy-Value Pitfalls and Their Fixes

### Thousands separators and currency

```python
# "1,234.56"  "₹1,23,456"  "$1 234,56"  "(500)" = negative in accounting
raw = df["amount"]
cleaned = (
    raw.str.replace(r"[₹$€£,\s]", "", regex=True)
       .str.replace(r"^\((.*)\)$", r"-\1", regex=True)   # (500) → -500
)
df["amount"] = pd.to_numeric(cleaned, errors="coerce")   # unparseable → NaN
```

`pd.read_csv(thousands=",")` exists, but it only works when the column is *already*
being inferred as numeric — which you disabled with `dtype=str`. Do it explicitly.

**Never use `float` for money.** Convert to `Decimal` or integer minor units
(paise/cents) before it reaches the DB:

```python
from decimal import Decimal, InvalidOperation

def to_paise(s: str) -> int | None:
    try:
        return int(Decimal(s).quantize(Decimal("0.01")) * 100)
    except (InvalidOperation, TypeError):
        return None
```

### Dates — the ambiguity trap

`03/04/2024` is 3 April in India/UK and 4 March in the US. Pandas guesses per-column
from the first non-null values, so a file can be parsed *one way for the first 5000
rows and another way for the rest*. Since pandas 2.0 mixed formats raise instead of
silently switching — good — but you should still pin the format:

```python
# Best: you know the format (state it in the upload template)
df["invoice_date"] = pd.to_datetime(
    df["invoice_date"], format="%d/%m/%Y", errors="coerce"
)

# Acceptable: ISO-ish input
df["invoice_date"] = pd.to_datetime(df["invoice_date"], format="ISO8601", errors="coerce")

# Last resort: let it guess, but demand consistency across the column
df["invoice_date"] = pd.to_datetime(df["invoice_date"], dayfirst=True, errors="coerce")
```

Excel serial dates: if a cell was a real Excel date, `openpyxl` gives you a
`datetime` already. If someone exported to CSV first you may get `45301` — the days
since 1899-12-30:

```python
EXCEL_EPOCH = pd.Timestamp("1899-12-30")
df["d"] = EXCEL_EPOCH + pd.to_timedelta(pd.to_numeric(df["d"], errors="coerce"), unit="D")
```

Timezones: `pd.to_datetime(..., utc=True)` normalises mixed offsets. A naive
datetime going into a `timestamptz` column will be interpreted in the DB session's
timezone — decide the rule once and apply it at the boundary.

### Whitespace, casing, invisible characters

```python
str_cols = df.select_dtypes("object").columns
df[str_cols] = df[str_cols].apply(
    lambda s: s.str.replace(" ", " ", regex=False)   # non-breaking space
                .str.strip()
)
df.columns = (
    df.columns.str.strip()
              .str.replace("﻿", "", regex=False)     # stray BOM
              .str.lower()
              .str.replace(r"\s+", "_", regex=True)
)
```

Trailing spaces in headers are extremely common (`"Email "` vs `"Email"`) and
produce a baffling `KeyError`. Normalise headers before anything else.

### Duplicate column names

Excel exports happily contain two `Amount` columns. Pandas renames them
`Amount`, `Amount.1`. Detect and reject rather than guess.

### Formula cells and errors

`=A1*B1` cells: `openpyxl` with `data_only=True` returns the **cached** value, which
is `None` if the file was never opened in Excel. `#REF!`, `#DIV/0!` arrive as
strings — they must fail validation, not become `NaN` silently.

---

## Reading Excel

```python
df = pd.read_excel(
    file_obj,
    sheet_name=0,          # int, name, list, or None for ALL sheets (dict)
    dtype=str,
    engine="calamine",     # or "openpyxl"
    header=0,
    usecols="A:F",         # or list of names
    na_values=[""],
    keep_default_na=False,
)
```

| Engine | Format | Notes |
|---|---|---|
| `openpyxl` | `.xlsx`, `.xlsm` | default; pure Python, memory-hungry |
| `calamine` (`python-calamine`) | `.xlsx`, `.xls`, `.ods` | Rust-backed, **5-20x faster**, far less RAM — the 2026 default |
| `xlrd` | `.xls` only | legacy, xlsx support removed in 2.0 |
| `odf` | `.ods` | LibreOffice |

**There is no chunked reader for Excel.** `read_excel` has no `chunksize`. The xlsx
format is a zipped XML tree — you cannot seek to row 500 000. Options:

1. `openpyxl.load_workbook(path, read_only=True, data_only=True)` → `ws.iter_rows()`
   streams row by row at roughly constant memory. Build your own batches.
2. Convert to CSV/Parquet once, then chunk normally.
3. Reject Excel over N MB at the API boundary and ask for CSV.

Sanity checks worth doing before trusting an Excel upload: real header row (people
put a title in row 1 → use `skiprows`), merged cells (they yield `NaN` in all but the
top-left), hidden sheets, and trailing "Total" rows that are not data.

---

## Validation and Row-Level Error Reporting

This is the part that separates a backend engineer from a notebook user. A user who
uploads 5000 rows and gets `{"error": "invalid data"}` will hate you. They need:
**row number, column, bad value, why**.

### Pattern: accumulate errors, never raise on first

```python
from dataclasses import dataclass

@dataclass
class RowError:
    row: int          # 1-based line number IN THE USER'S FILE
    column: str
    value: str
    message: str

    def as_dict(self): return {"row": self.row, "column": self.column,
                               "value": self.value, "message": self.message}
```

**Row-number bookkeeping is the classic bug.** DataFrame index 0 is the user's line 2
(line 1 is the header). Pin it immediately after reading and never rely on positional
index again:

```python
df["_row"] = df.index + 2      # +1 for 0-based index, +1 for header row
```

If you `dropna()`, `drop_duplicates()`, or filter, the index survives but positions
shift — `_row` keeps the user-facing number correct.

### Vectorised validation (fast) with per-row reporting

```python
errors: list[RowError] = []

def collect(mask: pd.Series, column: str, message: str) -> None:
    """mask=True means INVALID. Records one RowError per offending row."""
    for row_no, value in zip(df.loc[mask, "_row"], df.loc[mask, column]):
        errors.append(RowError(int(row_no), column, str(value), message))

# required
collect(df["email"].isna() | (df["email"].str.strip() == ""), "email", "required")
# format
collect(df["email"].notna() & ~df["email"].str.match(EMAIL_RE, na=False),
        "email", "not a valid email")
# range
qty = pd.to_numeric(df["quantity"], errors="coerce")
collect(qty.isna(), "quantity", "must be a whole number")
collect(qty.notna() & (qty <= 0), "quantity", "must be greater than zero")
# in-file duplicates
collect(df["email"].str.lower().duplicated(keep="first"), "email", "duplicate in file")
```

Vectorised masks are 10-100x faster than `df.iterrows()` over 100 k rows.
`iterrows()` on a large frame is a genuine performance bug, not a style nit —
it boxes every row into a new Series.

### Cross-row / DB validation in one query, not N

```python
# Bad: SELECT per row → 5000 queries
# Good: one IN query, then a set membership check
existing = set(
    session.scalars(select(User.email).where(User.email.in_(df["email"].tolist())))
)
collect(df["email"].isin(existing), "email", "already registered")
```

### Response shape

```json
{
  "status": "rejected",
  "total_rows": 5000,
  "valid_rows": 4987,
  "error_count": 13,
  "errors": [
    {"row": 42,  "column": "email",    "value": "bob@",  "message": "not a valid email"},
    {"row": 108, "column": "quantity", "value": "-3",    "message": "must be greater than zero"}
  ],
  "errors_truncated": false,
  "error_report_url": "/imports/8f3a.../errors.csv"
}
```

Cap the inline `errors` array (100 is a good limit) and offer the full list as a
downloadable CSV — otherwise a wrong-file upload produces a 50 MB JSON response.

### All-or-nothing vs partial import

Decide and **document** it:

| Mode | Behaviour | Fits |
|---|---|---|
| Strict | Any error → import nothing | Financial data, ledgers |
| Partial | Insert valid rows, return an error CSV for the rest | Contact/product lists |
| Dry-run first | `?validate_only=true` returns the error report; second call commits | Best UX; two-phase |

Strict mode is just partial mode wrapped in a transaction that rolls back if
`errors` is non-empty — implement partial, gate it on a flag.

---

## Chunked Processing for Big Files

`chunksize` turns `read_csv` into an iterator of DataFrames. Peak memory is one
chunk, not one file.

```python
BATCH = 50_000
total = valid = 0
errors: list[RowError] = []

reader = pd.read_csv(path, dtype=str, chunksize=BATCH,
                     keep_default_na=False, na_values=[""])

for chunk_no, chunk in enumerate(reader):
    chunk["_row"] = chunk.index + 2        # index is GLOBAL across chunks — correct
    clean, chunk_errors = validate(chunk)
    errors.extend(chunk_errors[: max(0, 100 - len(errors))])
    bulk_insert(clean)                     # commit per chunk, or accumulate
    total += len(chunk)
    valid += len(clean)
    update_progress(job_id, processed=total)
```

Notes:
- The index **is** global across chunks by default, so `index + 2` stays correct.
- Cross-chunk duplicate detection needs state you carry yourself (a `set` of seen
  keys, or a UNIQUE constraint in the DB doing the work).
- Committing per chunk means a crash leaves a partial import — record
  `last_committed_chunk` in the job row so you can resume or clean up.
- Chunk size is a memory/round-trip trade: 10 k-50 k rows is the usual sweet spot.

### Memory rule of thumb

A DataFrame is roughly **5-10x the CSV file size** in RAM for string-heavy data
(every Python string object carries ~49 bytes of overhead plus pointer indirection).
A 200 MB CSV can easily be 1.5 GB as a DataFrame. Measure, don't guess:

```python
df.memory_usage(deep=True).sum() / 1024**2     # deep=True counts the actual strings
```

### Memory traps and levers

| Lever | Effect |
|---|---|
| `usecols=[...]` | Do not materialise columns you will not use. Biggest single win. |
| `dtype={"status": "category"}` | Low-cardinality strings: 8 bytes/row instead of ~60. 10-50x on such columns. |
| `chunksize=` | Bounded peak memory. |
| `dtype_backend="pyarrow"` | Arrow-backed strings: far less overhead than object dtype. |
| `del df; gc.collect()` | Chained assignments leave old frames alive in long-running workers. |
| Avoid `df.copy()` in loops | Each copy is a full duplicate; that is how workers OOM. |

`category` is a trap in the other direction too: applying it to a *high*-cardinality
column (emails, UUIDs) stores both the codes **and** the full categories index — more
memory than plain strings. Use it only when uniques ≪ rows.

Also: `df.append()` was removed in pandas 2.0, and `pd.concat` inside a loop is
O(n²) copying. Build a `list` and concat once.

---

## Handing Off to the ORM: `to_dict("records")` → bulk insert

```python
records = clean_df.to_dict("records")   # list[dict], one per row
```

Two gotchas before this crosses into the ORM:

1. **`NaN` is a float, not `None`.** `NaN` inserted into a nullable text column
   becomes the string `"nan"` or raises. Convert first:
   ```python
   clean_df = clean_df.astype(object).where(clean_df.notna(), None)
   ```
   (pandas ≥ 2.2: `clean_df.replace({np.nan: None})` is deprecated for this;
   the `where` form above is the reliable one.)
2. **NumPy scalars are not Python scalars.** `np.int64` / `np.float64` /
   `pd.Timestamp` confuse some drivers. `.astype(object)` plus
   `.to_pydatetime()` for datetimes, or let SQLAlchemy 2.x coerce — but test it.

### SQLAlchemy 2.x

```python
from sqlalchemy import insert

BATCH = 1000
for i in range(0, len(records), BATCH):
    session.execute(insert(Product), records[i : i + BATCH])
session.commit()
```

`session.execute(insert(Model), list_of_dicts)` uses **executemany** — one round trip
per batch instead of per row. `session.add_all()` with 50 k objects builds 50 k
Python objects and a giant flush; avoid it for imports.

Upsert (Postgres):

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = pg_insert(Product).values(batch)
stmt = stmt.on_conflict_do_update(
    index_elements=["sku"],
    set_={"name": stmt.excluded.name, "price": stmt.excluded.price},
)
session.execute(stmt)
```

### Django

```python
objs = [Product(**r) for r in records]
Product.objects.bulk_create(objs, batch_size=1000, ignore_conflicts=False)
# Django 4.1+: real upsert
Product.objects.bulk_create(
    objs, batch_size=1000,
    update_conflicts=True, update_fields=["name", "price"], unique_fields=["sku"],
)
```

`bulk_create` skips `save()`, signals, and `auto_now` — if your model relies on
those, do it in the data prep step.

### When even bulk insert is too slow: COPY

For 1 M+ rows into Postgres, `COPY FROM STDIN` is 5-10x faster than executemany:

```python
buf = io.StringIO()
clean_df.to_csv(buf, index=False, header=False, sep="\t", na_rep="\\N")
buf.seek(0)
with raw_conn.cursor() as cur:
    cur.copy_expert("COPY products (sku, name, price) FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t')", buf)
```

Note that `df.to_sql(..., method="multi")` exists but is generally slower than a
plain executemany and much slower than COPY.

### Batch size

Too small → round-trip overhead. Too large → one giant statement, parameter limits
(Postgres caps at 65 535 bind parameters per statement, so
`rows × columns < 65 535`), and lock duration. **500-2000 rows** is the usual answer.

---

## Polars — the 2026 Alternative

Rust-backed, Arrow memory, multithreaded, lazy query optimiser. For backend import
work it wins on three axes that matter: memory, speed, and *strictness*.

```python
import polars as pl

df = pl.read_csv(
    path,
    infer_schema_length=0,            # everything as Utf8 — equivalent of dtype=str
    schema_overrides={"sku": pl.Utf8},
    null_values=[""],
    encoding="utf8-lossy",
)

# Lazy + streaming: never loads the whole file
lf = (
    pl.scan_csv(path, infer_schema_length=0)
      .filter(pl.col("quantity").cast(pl.Int64, strict=False) > 0)
      .select(["sku", "name", "quantity"])
)
for batch in lf.collect(streaming=True).iter_slices(50_000):
    bulk_insert(batch.to_dicts())
```

| | pandas | polars |
|---|---|---|
| Big CSV read | baseline | 3-10x faster, ~2-5x less RAM |
| Excel | native | via calamine/openpyxl (`read_excel`) |
| Strictness | coerces silently | raises on schema mismatch by default |
| Lazy/streaming | no | yes (`scan_csv` + `collect(streaming=True)`) |
| Ecosystem | enormous | growing; interop via `.to_pandas()` / Arrow |
| Team familiarity | universal | still a learning curve |

**When to actually switch:** files consistently > 500 MB, or the import worker is
memory-constrained, or you want schema violations to *fail loudly*. For a
5 MB contacts CSV, pandas is fine and the team already knows it. And note pandas 2.x
with `dtype_backend="pyarrow"` closes a good part of the memory gap without a rewrite.

---

## Endpoint Shape for Uploads

```python
@app.post("/imports")
async def create_import(file: UploadFile = File(...), user=Depends(get_user)):
    # 1. Cheap rejections BEFORE reading a single row
    if not file.filename.lower().endswith((".csv", ".xlsx")):
        raise HTTPException(415, "Upload a .csv or .xlsx file")

    # 2. Stream to disk/S3 with a size cap (see file 01)
    key, size = await stream_to_storage(file, max_bytes=200 * 1024 * 1024)

    # 3. Create a job row, return immediately — never parse in the request
    job = await db.create_import_job(user.id, key, size, status="queued")
    process_import.delay(str(job.id))
    return {"job_id": job.id, "status": "queued"}

@app.get("/imports/{job_id}")
async def import_status(job_id: UUID, user=Depends(get_user)):
    return await db.get_import_job(job_id, user.id)
    # → {status, processed_rows, total_rows, valid_rows, error_count, error_report_url}
```

Parsing must not happen in the request handler: it is CPU-bound (blocks the async
event loop) and unbounded in time. Queue it; poll or push via websocket/SSE.

---

## Security Notes

| Risk | Mitigation |
|---|---|
| **CSV injection** on re-export | A cell starting with `=`, `+`, `-`, `@`, tab or CR executes in Excel. Prefix with `'` when writing user data back out. |
| **Zip bomb** (xlsx is a zip) | Check the uncompressed size from the zip directory before extracting; cap the ratio (e.g. reject > 100:1). |
| **XXE in xlsx XML** | Use maintained parsers (openpyxl/calamine disable external entities); never hand the XML to a raw `lxml` parse with entity resolution on. |
| **Formula/external links** | Read with `data_only=True`; never evaluate. |
| **Memory DoS** | Size cap at the LB *and* row-count cap after parse. |
| **Column-count DoS** | A file with 100 k columns explodes any DataFrame. Cap columns too. |
| **Path from filename** | Never use the client filename as a storage path. |

---

## Common Pitfalls

### 1. `pd.read_csv(f)` with no arguments
Type inference silently mangles IDs, zips, and phone numbers. Always `dtype=str`.

### 2. `df.iterrows()` for validation
Boxes every row into a Series. 100 k rows: seconds vs milliseconds. Use masks.

### 3. Reporting the DataFrame index as the row number
Off by one (or by however many rows you dropped). Pin `_row` right after reading.

### 4. Parsing inside the HTTP request
CPU-bound work on the event loop; request times out at 30 s, user retries, now two
imports are running.

### 5. `float` for money
`0.1 + 0.2 != 0.3`. Use `Decimal` or integer minor units.

### 6. Committing per row
50 k transactions instead of 50. Batch it.

### 7. Trusting `NaN` to become `NULL`
It becomes the float NaN or the string `"nan"`. Convert to `None` explicitly.

### 8. Full error list in the JSON response
A wrong file yields 500 k errors → multi-MB response. Truncate + CSV download.

### 9. No idempotency
User double-clicks Upload → duplicate rows. Hash the file content and reject or
return the existing job for a repeat hash within a window.

### 10. Forgetting the second sheet
`sheet_name=0` reads only the first. If users put data on "Sheet2", say so
explicitly in the error rather than importing 0 rows and claiming success.

---

## TL;DR

- Read with `dtype=str` + explicit `na_values`; coerce yourself afterwards.
- `utf-8-sig` first, then `cp1252`, then `latin-1` as a fallback.
- Pin the user-facing row number (`index + 2`) immediately after reading.
- Validate with vectorised masks, accumulate `RowError`s, never raise on the first.
- Return row/column/value/message; truncate inline, offer a CSV error report.
- Excel has no `chunksize` — use `openpyxl read_only` streaming or convert to CSV.
- `chunksize` for CSV; `usecols` and `category` for memory; measure with
  `memory_usage(deep=True)`.
- `to_dict("records")` → NaN→None → SQLAlchemy `insert()` executemany or Django
  `bulk_create(batch_size=1000)`; COPY for 1 M+ rows.
- Parse in a background job, not the request. Return a job id, poll for status.
- polars/calamine when files get big or memory gets tight.

---

## Interview Q&A

**Q: A user uploads a 500 MB Excel file to your endpoint. Walk me through it.**

A: In order:

1. **Reject early, at the edge.** Extension and content-type check, and a size cap
   enforced by NGINX (`client_max_body_size`) plus a byte counter while streaming.
   500 MB of xlsx is roughly 5-10 M rows — I'd want a product decision on whether
   that is even allowed, and if it is, I'd ask for CSV instead, because xlsx cannot
   be read incrementally with pandas.
2. **Never parse in the request.** Stream the upload to S3 in chunks (constant
   memory), insert an `import_jobs` row with status `queued`, enqueue a Celery task,
   return `202 {job_id}`. The HTTP request is over in a couple of seconds.
3. **In the worker, stream — don't `read_excel`.** `read_excel` materialises the
   whole sheet; a 500 MB xlsx would need many GB. I'd use
   `openpyxl.load_workbook(read_only=True, data_only=True)` and `ws.iter_rows()`,
   batching 50 k rows into a DataFrame at a time — or, better, convert the sheet to
   CSV/Parquet once and then use `pd.read_csv(chunksize=...)` or
   `pl.scan_csv(...).collect(streaming=True)`, which keeps peak memory flat.
4. **Per batch: coerce and validate.** Everything read as string, then explicit
   coercion (`to_numeric`, `to_datetime` with a pinned format, `Decimal` for money).
   Validation is vectorised masks producing `RowError(row, column, value, message)`
   objects. Row numbers come from a `_row` column pinned at read time, so they match
   what the user sees in Excel.
5. **Per batch: bulk insert.** `to_dict("records")`, NaN→None, then SQLAlchemy
   `session.execute(insert(Model), batch)` in chunks of ~1000 (staying under
   Postgres' 65 535 bind-parameter limit), or `COPY FROM STDIN` if throughput
   matters. Update `processed_rows` on the job row so the UI can show progress.
6. **Error handling policy.** Cap collected errors (say 1000), write the full set to
   a CSV in S3, and expose a presigned download link. Strict mode wraps everything
   in one transaction and rolls back if any error exists; partial mode commits good
   batches and reports the rest.
7. **Operational bits.** Idempotency key = SHA-256 of the file, so a double-click
   doesn't import twice. Worker memory limit + `--max-tasks-per-child` so a leak
   can't take the pool down. Timeout and retry with the job resuming from
   `last_committed_batch`. Metrics on rows/sec and peak RSS.

The headline is: constant memory, background execution, row-level error reporting.

**Q: Why is `dtype=str` on every read the default advice?**

A: Because pandas infers types from a sample and the inference is lossy and
irreversible. `007` becomes `7`, a 20-digit account number becomes a float64 and
loses its last digits, `1e5` becomes `100000.0` — all silently, no exception. Reading
as string and coercing explicitly means every conversion failure is something I chose
how to handle, and I can report it to the user instead of shipping corrupted data.

**Q: How do you tell the user which row failed?**

A: Add `df["_row"] = df.index + 2` right after reading — +1 for the zero-based index,
+1 for the header line — so it matches the line number in their spreadsheet. That
column survives filtering and dropping, so after validation I can zip
`df.loc[mask, "_row"]` with the offending values and emit
`{row, column, value, message}`. Never report the positional index, and never report
the post-filter index.

**Q: pandas or the csv module?**

A: If it's plain CSV and I'm processing row by row into the DB with no column-level
operations, the stdlib `csv` module is better — zero dependencies, genuinely constant
memory, no type-inference surprises. I reach for pandas when I need dtype coercion,
vectorised validation across a whole column, dedupe, or when the input might be
Excel. For very large files or a memory-constrained worker, polars with
`scan_csv` + streaming.

**Q: What's the memory cost of a DataFrame relative to the file?**

A: For string-heavy data, roughly 5-10x the CSV size — each Python string object
carries ~49 bytes of overhead plus a pointer in the object array. `usecols` is the
biggest lever (don't materialise columns you don't need), `category` dtype helps a
lot on low-cardinality columns and *hurts* on high-cardinality ones, and
`dtype_backend="pyarrow"` cuts string overhead substantially. I'd verify with
`df.memory_usage(deep=True).sum()` rather than guess.

**Q: How do you handle a column of dates like `03/04/2024`?**

A: I don't guess. The upload template states the expected format and I pass
`format="%d/%m/%Y"` with `errors="coerce"`, then report every NaT as a row-level
error. If the format genuinely varies I use `format="ISO8601"` or `dayfirst=True`,
but I treat an ambiguous date column as a data-contract problem to fix upstream —
silently parsing 3 April as 4 March is the kind of bug that surfaces months later in
a financial report.

**Q: Why not `bulk_create` with 500 000 objects in one call?**

A: Two reasons. Memory — 500 k model instances is a lot of Python objects — and the
database: one enormous INSERT holds locks longer, blows past Postgres' 65 535
bind-parameter cap, and gives no progress granularity. `batch_size=1000` gives
round-trip efficiency without those problems, and lets me update a progress counter
between batches.

**Q: Any security concerns with spreadsheet uploads?**

A: Yes — an xlsx is a zip file, so zip bombs are real; I check the uncompressed size
from the zip directory before extracting. XML parsing needs external entities
disabled (maintained parsers do this). Formulas must never be evaluated —
`data_only=True`. And on the way *out*, CSV injection: a cell starting with `=`, `+`,
`-`, or `@` executes as a formula when the export is opened in Excel, so user-supplied
text gets a `'` prefix when I write it back.

---

Related: [01_file_uploads_streaming.md](01_file_uploads_streaming.md) (streaming the
upload itself), [04_pdf_excel_generation.md](04_pdf_excel_generation.md) (writing
Excel/CSV back out).
