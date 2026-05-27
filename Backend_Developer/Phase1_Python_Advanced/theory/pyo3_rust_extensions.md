# Python Advanced — PyO3 Rust Extensions for Performance
**Phase 1 Python Advanced | Senior Backend + Agentic AI**

## Quick Concepts
- **PyO3** = Rust ↔ Python bindings — write Python modules in Rust
- **Why** = 10-100x faster than Python for CPU-bound work; safer than C
- **Maturin** = build tool — Rust crate → Python wheel (one command)
- **GIL handling** = Rust can release GIL → true parallelism
- **Zero-copy** = pass NumPy/bytes without copying memory
- **PyPy vs PyO3** = PyPy = JIT, less effort; PyO3 = max control, integrates with C/system libs
- **Use cases** = parsers, crypto, data transforms, image/audio processing, ML preprocessing

---

## Why Rust Over Cython/C?

| Aspect | C extension | Cython | PyO3 (Rust) |
|---|---|---|---|
| Memory safety | ❌ Manual | 🟡 Some safety | ✅ Compiler-enforced |
| Async support | ❌ Hard | 🟡 Limited | ✅ Native (Tokio) |
| Ecosystem | Old | Python-focused | Rust crates.io (200K+) |
| Build complexity | Hard | Medium | Easy (`maturin`) |
| Tooling | Old | Decent | Modern (cargo, clippy) |
| Learning curve | High + footguns | Medium | Medium |
| Performance | 1.0x baseline | 0.8-1.0x | 1.0-1.2x |

**2026 reality**: Pydantic v2, polars, ruff, uv — all migrated from Python/C to Rust. PyO3 is the modern choice.

---

## Real-World PyO3 Users

- **Pydantic v2 core** — JSON parsing, validation (10x faster)
- **Polars** — DataFrame library (faster than pandas)
- **Ruff** — Linter (100x faster than flake8)
- **uv** — Python package manager (10-100x faster than pip)
- **Cryptography** — primitives library
- **Tokenizers** (Hugging Face) — fast BPE
- **Watchfiles** — file watcher

---

## Interview Questions & Answers

### Q1: Apna first PyO3 module — setup + hello world?

**Answer:**
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install maturin
pip install maturin

# Bootstrap project
mkdir mymodule && cd mymodule
maturin init --bindings pyo3
```

**`Cargo.toml`:**
```toml
[package]
name = "mymodule"
version = "0.1.0"
edition = "2021"

[lib]
name = "mymodule"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.22", features = ["extension-module"] }
```

**`src/lib.rs`:**
```rust
use pyo3::prelude::*;

#[pyfunction]
fn hello(name: &str) -> PyResult<String> {
    Ok(format!("Hello, {}!", name))
}

#[pyfunction]
fn sum_squares(numbers: Vec<i64>) -> i64 {
    numbers.iter().map(|x| x * x).sum()
}

#[pymodule]
fn mymodule(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(hello, m)?)?;
    m.add_function(wrap_pyfunction!(sum_squares, m)?)?;
    Ok(())
}
```

**Build + use:**
```bash
maturin develop --release    # builds + installs in current venv
```

```python
import mymodule
print(mymodule.hello("World"))               # "Hello, World!"
print(mymodule.sum_squares([1, 2, 3, 4, 5])) # 55

# Benchmark
import time
nums = list(range(1_000_000))

# Pure Python
start = time.perf_counter()
result = sum(x * x for x in nums)
py_time = time.perf_counter() - start

# Rust
start = time.perf_counter()
result = mymodule.sum_squares(nums)
rust_time = time.perf_counter() - start

print(f"Python: {py_time:.3f}s")
print(f"Rust:   {rust_time:.3f}s ({py_time/rust_time:.1f}x faster)")
# Python: 0.085s
# Rust:   0.003s (28.3x faster)
```

---

### Q2: Pydantic-like validation in Rust — real example?

**Answer:** Build a fast JSON validator.

```rust
// src/lib.rs
use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize)]
struct User {
    id: i64,
    email: String,
    name: String,
    age: u8,
}

#[pyfunction]
fn validate_user(json_str: &str) -> PyResult<PyObject> {
    let user: User = serde_json::from_str(json_str)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    // Custom validation
    if user.age < 18 {
        return Err(pyo3::exceptions::PyValueError::new_err("User must be 18+"));
    }
    if !user.email.contains('@') {
        return Err(pyo3::exceptions::PyValueError::new_err("Invalid email"));
    }

    Python::with_gil(|py| {
        let dict = PyDict::new_bound(py);
        dict.set_item("id", user.id)?;
        dict.set_item("email", user.email)?;
        dict.set_item("name", user.name)?;
        dict.set_item("age", user.age)?;
        Ok(dict.into())
    })
}

#[pyfunction]
fn validate_users_batch(json_arr: &str) -> PyResult<Vec<PyObject>> {
    let users: Vec<User> = serde_json::from_str(json_arr)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    Python::with_gil(|py| {
        users.into_iter().map(|u| {
            let dict = PyDict::new_bound(py);
            dict.set_item("id", u.id)?;
            dict.set_item("email", u.email)?;
            dict.set_item("name", u.name)?;
            dict.set_item("age", u.age)?;
            Ok(dict.into())
        }).collect()
    })
}

#[pymodule]
fn fast_validation(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validate_user, m)?)?;
    m.add_function(wrap_pyfunction!(validate_users_batch, m)?)?;
    Ok(())
}
```

**Benchmark vs Pydantic:**
```python
import fast_validation
from pydantic import BaseModel
import time

class UserPydantic(BaseModel):
    id: int
    email: str
    name: str
    age: int

users_json = '[{"id":1,"email":"a@b.c","name":"Alice","age":25}]' * 10000  # 10K users

# Pydantic v2 (already fast)
start = time.perf_counter()
for _ in range(100):
    UserPydantic.model_validate_json(users_json)
print(f"Pydantic: {time.perf_counter() - start:.2f}s")

# Our Rust
start = time.perf_counter()
for _ in range(100):
    fast_validation.validate_users_batch(users_json)
print(f"Rust:     {time.perf_counter() - start:.2f}s")
```

---

### Q3: GIL release for true parallelism?

**Answer:** Release GIL for pure-Rust work → other Python threads can run.

```rust
use pyo3::prelude::*;
use rayon::prelude::*;

#[pyfunction]
fn parallel_hash(data: Vec<Vec<u8>>) -> Vec<Vec<u8>> {
    // Release GIL — true parallelism via rayon
    Python::with_gil(|py| {
        py.allow_threads(|| {
            data.par_iter().map(|chunk| {
                use sha2::{Sha256, Digest};
                let mut hasher = Sha256::new();
                hasher.update(chunk);
                hasher.finalize().to_vec()
            }).collect()
        })
    })
}
```

**Python side (true CPU parallelism!):**
```python
import fast_module
import threading

def compute(data):
    return fast_module.parallel_hash(data)

# Without GIL release: only 1 thread runs at a time (Python's GIL)
# With GIL release: all threads run in parallel (Rust holds no GIL)

threads = [threading.Thread(target=compute, args=(big_data,)) for _ in range(8)]
for t in threads: t.start()
for t in threads: t.join()
# Uses all 8 CPU cores!
```

---

### Q4: Working with NumPy arrays (zero-copy)?

**Answer:** Use `numpy` crate for shared memory access.

```toml
# Cargo.toml
[dependencies]
pyo3 = { version = "0.22", features = ["extension-module"] }
numpy = "0.22"
ndarray = "0.16"
```

```rust
use ndarray::{Array1, Array2};
use numpy::{PyArray1, PyArray2, IntoPyArray, PyReadonlyArray2};
use pyo3::prelude::*;

#[pyfunction]
fn matrix_multiply<'py>(
    py: Python<'py>,
    a: PyReadonlyArray2<'py, f64>,
    b: PyReadonlyArray2<'py, f64>,
) -> Bound<'py, PyArray2<f64>> {
    // Borrow NumPy arrays without copying
    let a = a.as_array();
    let b = b.as_array();

    // Compute (release GIL since it's pure Rust)
    let result = py.allow_threads(|| a.dot(&b));

    // Return as NumPy array (zero-copy back)
    result.into_pyarray_bound(py)
}

#[pyfunction]
fn fast_normalize<'py>(
    py: Python<'py>,
    arr: PyReadonlyArray1<'py, f64>,
) -> Bound<'py, PyArray1<f64>> {
    let arr = arr.as_array();
    let max = arr.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let min = arr.iter().cloned().fold(f64::INFINITY, f64::min);
    let range = max - min;

    let normalized: Array1<f64> = arr.mapv(|x| (x - min) / range);
    normalized.into_pyarray_bound(py)
}
```

**Python:**
```python
import numpy as np
import fast_math

a = np.random.rand(1000, 1000)
b = np.random.rand(1000, 1000)

# Zero-copy access — uses same memory
result = fast_math.matrix_multiply(a, b)
```

---

### Q5: Async Rust ↔ async Python (Tokio + pyo3-async)?

**Answer:** Use `pyo3-async-runtimes` for true async interop.

```toml
[dependencies]
pyo3 = { version = "0.22", features = ["extension-module"] }
pyo3-async-runtimes = { version = "0.22", features = ["tokio-runtime"] }
tokio = { version = "1", features = ["full"] }
reqwest = "0.12"
```

```rust
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;

#[pyfunction]
fn fetch_url<'py>(py: Python<'py>, url: String) -> PyResult<Bound<'py, PyAny>> {
    // Wrap Rust async future as Python awaitable
    future_into_py(py, async move {
        let response = reqwest::get(&url).await
            .map_err(|e| pyo3::exceptions::PyConnectionError::new_err(e.to_string()))?;
        let text = response.text().await
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        Ok(text)
    })
}

#[pyfunction]
fn parallel_fetch<'py>(py: Python<'py>, urls: Vec<String>) -> PyResult<Bound<'py, PyAny>> {
    future_into_py(py, async move {
        let futures = urls.into_iter().map(|url| async move {
            reqwest::get(&url).await.ok()?.text().await.ok()
        });
        let results = futures::future::join_all(futures).await;
        Ok(results)
    })
}
```

**Python (async):**
```python
import asyncio
import fast_http

async def main():
    # Single fetch
    text = await fast_http.fetch_url("https://example.com")

    # Parallel — uses Rust's Tokio runtime
    results = await fast_http.parallel_fetch([
        "https://api1.com",
        "https://api2.com",
        "https://api3.com",
    ])

asyncio.run(main())
```

---

### Q6: Class definitions (Rust struct → Python class)?

**Answer:**
```rust
use pyo3::prelude::*;

#[pyclass]
struct RateLimiter {
    capacity: u32,
    tokens: f64,
    rate: f64,
    last_refill: std::time::Instant,
}

#[pymethods]
impl RateLimiter {
    #[new]
    fn new(capacity: u32, rate_per_second: f64) -> Self {
        RateLimiter {
            capacity,
            tokens: capacity as f64,
            rate: rate_per_second,
            last_refill: std::time::Instant::now(),
        }
    }

    fn try_acquire(&mut self, tokens: u32) -> bool {
        // Refill based on elapsed time
        let now = std::time::Instant::now();
        let elapsed = now.duration_since(self.last_refill).as_secs_f64();
        self.tokens = (self.tokens + elapsed * self.rate).min(self.capacity as f64);
        self.last_refill = now;

        if self.tokens >= tokens as f64 {
            self.tokens -= tokens as f64;
            true
        } else {
            false
        }
    }

    #[getter]
    fn available_tokens(&self) -> f64 {
        self.tokens
    }

    fn __repr__(&self) -> String {
        format!("RateLimiter(capacity={}, available={:.1})", self.capacity, self.tokens)
    }
}
```

**Python:**
```python
import fast_module

limiter = fast_module.RateLimiter(capacity=10, rate_per_second=1.0)
for _ in range(15):
    if limiter.try_acquire(1):
        print(f"Allowed. Tokens left: {limiter.available_tokens}")
    else:
        print("Rate limited")
        time.sleep(0.5)
```

---

### Q7: Error handling between Rust and Python?

**Answer:** Map Rust `Result` to Python exceptions.

```rust
use pyo3::prelude::*;
use pyo3::exceptions::{PyValueError, PyTypeError, PyKeyError};

#[derive(Debug, thiserror::Error)]
enum MyError {
    #[error("Invalid input: {0}")]
    InvalidInput(String),

    #[error("Not found: {0}")]
    NotFound(String),

    #[error("Network error: {0}")]
    Network(String),
}

// Auto-convert Rust errors to Python exceptions
impl From<MyError> for PyErr {
    fn from(err: MyError) -> PyErr {
        match err {
            MyError::InvalidInput(msg) => PyValueError::new_err(msg),
            MyError::NotFound(msg) => PyKeyError::new_err(msg),
            MyError::Network(msg) => PyValueError::new_err(format!("Network: {}", msg)),
        }
    }
}

#[pyfunction]
fn parse_input(input: &str) -> Result<i64, MyError> {
    input.parse().map_err(|_| MyError::InvalidInput(input.to_string()))
}
```

**Python:**
```python
try:
    result = mymodule.parse_input("abc")
except ValueError as e:
    print(f"Got expected error: {e}")
```

---

### Q8: Building wheels for distribution (manylinux)?

**Answer:** Use `maturin` + Docker for cross-platform builds.

```bash
# Build wheel for local platform
maturin build --release

# Build for manylinux (PyPI-compatible)
maturin build --release --target x86_64-unknown-linux-gnu --manylinux 2_28

# Build for all major platforms via GitHub Actions
```

**`.github/workflows/release.yml`:**
```yaml
name: Build Wheels
on:
  push:
    tags: ['v*']

jobs:
  linux:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        target: [x86_64, aarch64]
    steps:
      - uses: actions/checkout@v4
      - uses: PyO3/maturin-action@v1
        with:
          target: ${{ matrix.target }}
          args: --release --out dist --interpreter '3.10 3.11 3.12 3.13'
          manylinux: 2_28
      - uses: actions/upload-artifact@v4
        with: { name: wheels, path: dist }

  windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: PyO3/maturin-action@v1
        with:
          args: --release --out dist
      - uses: actions/upload-artifact@v4
        with: { name: wheels, path: dist }

  macos:
    runs-on: macos-latest
    strategy:
      matrix:
        target: [x86_64, aarch64]
    steps:
      - uses: actions/checkout@v4
      - uses: PyO3/maturin-action@v1
        with:
          target: ${{ matrix.target }}
          args: --release --out dist

  publish:
    needs: [linux, windows, macos]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with: { name: wheels }
      - uses: PyO3/maturin-action@v1
        with:
          command: upload
          args: --skip-existing *
        env:
          MATURIN_PYPI_TOKEN: ${{ secrets.PYPI_TOKEN }}
```

**Result:** `pip install yourmodule` works on Linux/Mac/Windows × Python 3.10-3.13.

---

## When to Use PyO3

| Use PyO3 when... | Stay in Python when... |
|---|---|
| CPU-bound (parsing, crypto, math) | I/O-bound (most web work) |
| Need to release GIL | Already async-bound |
| Existing Rust crate fits perfectly | Existing Python lib is fast enough |
| Building popular library (polars-style) | Internal one-off script |
| Memory safety critical | Quick prototype |
| Want zero-copy NumPy interop | Pure pandas/NumPy |

**Rule of thumb:** If profiling shows > 30% time in pure-Python CPU work → PyO3 candidate.

---

## Performance Benchmarks (typical)

| Workload | Pure Python | NumPy | Cython | PyO3 |
|---|---|---|---|---|
| Sum 1M ints | 100ms | 5ms | 8ms | **3ms** |
| Parse JSON 100MB | 2000ms | N/A | 800ms | **300ms** |
| SHA256 1GB | 8000ms | N/A | 3000ms | **600ms** |
| Sort 10M items | 5000ms | 600ms | 1500ms | **400ms** |
| Regex match 1GB | 1500ms | N/A | 800ms | **200ms** |

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| `panic!` crashes Python interpreter | Always use `Result`, never panic in public API |
| GIL not released → no parallelism | Wrap pure-Rust work in `py.allow_threads(...)` |
| Holding Python objects across `await` | Use `Python::with_gil` inside async blocks |
| String allocation overhead | Use `&str` for inputs when possible |
| Cargo profile not release | Always `--release` for production |
| Cross-platform build fails | Use `maturin-action` GitHub Action |
| Debug symbols bloat wheel | Strip symbols in release profile |
| ABI3 vs version-specific | Use `pyo3 = { features = ["abi3-py310"] }` for portable wheels |

---

## Senior-level Checklist

- [ ] Profile shows hot path is CPU-bound (not I/O)
- [ ] Rust toolchain installed in dev + CI
- [ ] `maturin` for build automation
- [ ] GIL released in pure-Rust sections (`py.allow_threads`)
- [ ] NumPy interop where applicable (zero-copy)
- [ ] Errors mapped to Python exceptions (no panics)
- [ ] ABI3 wheels for forward compat
- [ ] manylinux wheels for portability
- [ ] CI builds wheels for Linux/Mac/Windows × Py3.10-3.13
- [ ] Benchmark vs pure Python documented
- [ ] Async support via pyo3-async-runtimes (if needed)
- [ ] Tests in both Rust (`cargo test`) and Python (`pytest`)
- [ ] Type stubs (.pyi) for IDE autocomplete

---

## Common Pitfalls

```rust
// ❌ BAD: panics crash interpreter
#[pyfunction]
fn divide(a: i64, b: i64) -> i64 {
    a / b  // Panics if b == 0
}

// ✅ GOOD: return Result
#[pyfunction]
fn divide(a: i64, b: i64) -> PyResult<i64> {
    if b == 0 {
        Err(PyZeroDivisionError::new_err("division by zero"))
    } else {
        Ok(a / b)
    }
}
```

```rust
// ❌ BAD: holds GIL during slow work — blocks other threads
#[pyfunction]
fn slow_compute(data: Vec<i64>) -> i64 {
    expensive_computation(&data)
}

// ✅ GOOD: release GIL
#[pyfunction]
fn slow_compute(py: Python<'_>, data: Vec<i64>) -> i64 {
    py.allow_threads(|| expensive_computation(&data))
}
```

---

## Related Docs
- `03_memory_gil.md` — GIL deep dive
- `05_async_concurrency_deep_dive.md` — async fundamentals
- `07_performance_profiling.md` — find Rust candidates
- `08_cpython_vs_pypy.md` — alternative perf option
- `Phase2_FastAPI/04_testing_sqlalchemy.md` — testing integration

## External References
- PyO3 user guide: https://pyo3.rs
- Maturin: https://www.maturin.rs
- pyo3-async-runtimes: https://github.com/PyO3/pyo3-async-runtimes
- "Speed Up Python with Rust" book: https://maturin.rs
- Real-world examples: polars, pydantic-core, ruff source code
