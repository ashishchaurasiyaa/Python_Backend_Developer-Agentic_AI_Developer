# py-spy & scalene — Production Profiling

> **Interview angle:** "Production mein app slow ho gayi — code change kiye bina kaise debug?"

`cProfile` development me thik hai but production me dangerous hai (overhead, instrumentation cost). `py-spy` aur `scalene` next-gen profilers hain.

---

## 1. Profiling Tools Landscape

| Tool | Type | Overhead | Production-safe | Best For |
|---|---|---|---|---|
| `cProfile` | Deterministic | High (20-50%) | ❌ | Dev, small scripts |
| `line_profiler` | Deterministic | Very High | ❌ | Line-by-line in dev |
| `memory_profiler` | Deterministic | High | ❌ | Memory usage in dev |
| **`py-spy`** | **Sampling** | **<5%** | ✅ | **Live prod debugging** |
| **`scalene`** | Sampling | ~5% | ✅ | CPU + memory + GPU |
| `austin` | Sampling | Low | ✅ | Alternative to py-spy |
| `palanteer` | Tracing + sampling | Low | ✅ | Multi-thread visualization |

---

## 2. `py-spy` — Sampling Profiler

### Kya hai?
- Written in **Rust**
- Attaches to running Python process (like gdb)
- Reads stack frames via **process memory** — no code change!
- Sample-based: takes stack snapshot every ~10ms

### Install
```bash
pip install py-spy
# OR system-wide:
brew install py-spy   # Mac
```

### Main commands

#### a) `record` — Generate flame graph
```bash
py-spy record -o profile.svg --pid 12345
# Open profile.svg in browser
# Stop with Ctrl+C — generates flame graph

# OR profile a new process
py-spy record -o profile.svg -- python myscript.py
```

#### b) `top` — Live top-style view (like Unix `top`)
```bash
py-spy top --pid 12345
```

#### c) `dump` — Snapshot all thread stacks NOW
```bash
py-spy dump --pid 12345
```

**Output:**
```
Thread 0x7f8b4c (idle): 1 active threads
  Active threads:
    Thread 12345 (active+gil): "MainThread"
        process_request (app/main.py:42)
        handle (uvicorn/protocols.py:101)
```

### Production setup

```bash
# Allow ptrace (Linux)
sudo sysctl kernel.yama.ptrace_scope=0

# Or run with capabilities
sudo setcap cap_sys_ptrace=eip /usr/bin/py-spy

# Profile production container
docker exec -it my-app py-spy record -o /tmp/prof.svg --pid 1
```

### Flame Graph Reading
- **X-axis** = sample count (wider = more time spent)
- **Y-axis** = call stack depth
- Look for **wide rectangles** at top — that's where time goes
- Color is arbitrary (visual grouping)

---

## 3. `scalene` — CPU + Memory + GPU Profiler

### Kya hai?
- Sampling profiler with **memory tracking**
- Differentiates **Python time vs Native (C) time**
- **Per-line** memory allocations
- Web UI with AI suggestions (`--ai`)

### Install
```bash
pip install scalene
```

### Usage
```bash
# Profile script
scalene myscript.py

# Profile with HTML report
scalene --html --outfile profile.html myscript.py

# Profile specific time window
scalene --profile-interval 5 myscript.py

# Reduced overhead mode
scalene --cpu-only myscript.py

# Memory only
scalene --memory-only myscript.py
```

### Output Sample
```
Line │ CPU% Py │ CPU% Native │ Mem MB │ Code
─────┼─────────┼─────────────┼────────┼─────────────────
  42 │   2.1%  │    15.3%    │  120   │ data = np.array(...)
  43 │  45.2%  │     0.0%    │   10   │ for x in data: ...
  55 │   0.0%  │    32.4%    │    0   │ json.dumps(data)
```

**Key insight:** Line 42 spends time in **NumPy C code**, line 43 in **Python loop** — fix the Python loop first.

### Reduced-noise profiling (annotations)
```python
from scalene import scalene_profiler

scalene_profiler.start()
# ... code to profile ...
scalene_profiler.stop()
```

---

## 4. Comparison Workflow

### Scenario 1: "API endpoint slow"
1. `py-spy top --pid <pid>` → see what's hot RIGHT NOW
2. `py-spy record -o flame.svg --pid <pid>` for 60s → flame graph
3. Identify hot function → re-profile with `scalene` locally with realistic data
4. Apply fix → benchmark again

### Scenario 2: "Memory grows over time"
1. `py-spy dump --pid <pid>` to confirm no thread is hung
2. `scalene --memory-only --profile-all my_repro_script.py`
3. Identify line with growing allocations
4. Use `tracemalloc.snapshot()` for diff snapshots

### Scenario 3: "Investigate CPU vs I/O time"
```bash
py-spy record -o flame.svg --idle  --pid <pid>
# --idle shows time waiting on I/O too
```

---

## 5. Production Best Practices

### 1. Always have py-spy in your container
```dockerfile
RUN pip install py-spy
```

### 2. Enable ptrace selectively
```yaml
# Kubernetes
securityContext:
  capabilities:
    add: ["SYS_PTRACE"]
```

### 3. Sample at right rate
- Default 100 Hz (every 10ms) — fine
- For long traces: `--rate 10` (every 100ms) — less data, lower overhead

### 4. Save flame graphs to artifact storage
```bash
py-spy record -o "profile_$(date +%s).svg" --pid 1
aws s3 cp profile_*.svg s3://my-bucket/profiles/
```

### 5. Trigger profiling on alert
Wire up Prometheus alert → webhook → start py-spy → upload SVG.

### 6. Profile in staging with prod traffic
Use traffic mirroring (e.g., AWS Mirror Target, GoReplay).

---

## 6. Reading Flame Graphs — Common Patterns

### Pattern: Wide rectangle at top
**Function spent a lot of time** — optimize this.

### Pattern: Tall stack
**Deep call hierarchy** — possibly recursion or excessive abstraction.

### Pattern: Many small spikes
**Lots of short-lived calls** — consider batching.

### Pattern: Wide GIL block
Multi-threaded but only 1 CPU used — GIL-bound. Use multiprocessing or release GIL in C extension.

### Pattern: Wide socket/select
I/O bound — async or larger thread pool may help.

---

## 7. Advanced: Continuous Profiling

For long-term production observability:

### Pyroscope
```python
import pyroscope
pyroscope.configure(
    application_name="my-app",
    server_address="http://pyroscope:4040",
)
```
- Always-on profiling
- Diff between deploys
- Production-safe overhead

### Datadog Continuous Profiler
- Built-in to Datadog APM
- Auto-correlates traces with profiles

---

## 8. Mini Cheat Sheet

```bash
# Live top-style
py-spy top --pid 12345

# Stack snapshot now
py-spy dump --pid 12345

# 60s flame graph
py-spy record -o prof.svg --pid 12345 --duration 60

# With I/O time
py-spy record -o prof.svg --pid 12345 --idle

# Profile new script
py-spy record -o prof.svg -- python script.py

# Scalene local script
scalene myscript.py
scalene --html --outfile r.html myscript.py
scalene --cpu-only myscript.py     # less overhead
```

---

## 9. Interview Questions

**Q1: cProfile vs py-spy difference?**
- cProfile: deterministic, instruments every call, high overhead, dev-only
- py-spy: sampling (10ms intervals), <5% overhead, production-safe, no code change

**Q2: Production app slow — debug kaise?**
1. `py-spy top --pid` for live view
2. `py-spy record` for flame graph
3. Identify hot path
4. Local repro + scalene for detailed line info
5. Fix + benchmark

**Q3: scalene ka unique feature?**
Separates Python time vs C/native time per-line + memory tracking. Helps identify if NumPy/Pandas is the bottleneck vs Python loops.

**Q4: Flame graph kaise read karte?**
X-axis = time spent (wider = slower). Y-axis = stack depth. Look for wide bars at the top.

**Q5: Multi-threaded profiling?**
py-spy supports `--threads` flag to profile all threads. scalene shows thread info too.

**Q6: Continuous profiling kya hai?**
Always-on, low-overhead profiling stored centrally. Pyroscope, Datadog. Compare across versions.

---

## 10. Best Practices Summary

1. **Ship py-spy in containers** — zero-cost insurance
2. **Profile in staging with realistic load** before prod
3. **Save flame graphs as artifacts** — useful for postmortems
4. **Use scalene locally** for detailed per-line analysis
5. **Use Pyroscope/Datadog** for continuous profiling
6. **Don't optimize without profiling** — guesses are wrong 80% of time

---

## Related
- [[07_performance_profiling]] — cProfile + general profiling
- [[12_deadlock_debugging]] — py-spy dump for stuck threads
- [[03_memory_gil]] — GIL impact visible in flame graphs
