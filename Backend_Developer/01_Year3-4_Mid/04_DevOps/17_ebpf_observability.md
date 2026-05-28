# DevOps — eBPF Observability for Python Backends
**DevOps · Year 3-4 | Senior Backend + Agentic AI**

## Quick Concepts
- **eBPF** = extended Berkeley Packet Filter — run sandboxed programs in Linux kernel
- **Why** = observability without code changes / instrumentation
- **Use cases** = profiling, networking, security, tracing
- **Kernel-level** = sees everything: syscalls, network, filesystem, processes
- **No overhead claim** = misleading; well-written eBPF = < 1% overhead
- **Tools**: Pixie (managed), Pyroscope (profiling), bpftrace (scripts), Cilium (networking), Falco (security), Parca (profiling), Tetragon (security)

---

## Why eBPF in 2026

```
TRADITIONAL OBSERVABILITY:                    eBPF OBSERVABILITY:
─────────────────────                         ─────────────────
• Add OpenTelemetry SDK to code               • Zero code changes
• Re-deploy every service                     • Already running
• Per-request overhead                        • Near-zero overhead
• Sample to reduce cost                       • Capture everything
• Logs/metrics/traces siloed                  • Kernel sees all signals
• Can't see what's not instrumented           • Sees kernel + userspace
```

**Best fit:** Auto-discovery of services, low-level networking debug, continuous profiling, security forensics.

---

## eBPF Tool Landscape

| Tool | Purpose | Maturity |
|---|---|---|
| **Pixie** | Auto-instrumented APM (HTTP, DB, Redis tracing) | Production |
| **Pyroscope** | Continuous CPU profiling | Production |
| **Parca** | Continuous profiling (alternative to Pyroscope) | Production |
| **Cilium** | K8s networking + service mesh | Production |
| **Hubble** | Cilium network observability | Production |
| **Falco** | Security threat detection | Production |
| **Tetragon** | Security observability (Cilium-related) | Production |
| **bpftrace** | Ad-hoc kernel tracing scripts | Production |
| **bcc** | eBPF tools library | Mature |
| **bpftool** | eBPF program management | Mature |
| **eBPF Manager (Tracee)** | Runtime security | Production |

---

## Interview Questions & Answers

### Q1: Pixie — auto-instrument Python services in K8s?

**Answer:** Install once, get HTTP/MySQL/Postgres/Redis traces automatically.

```bash
# Install Pixie via Helm
helm repo add pixie https://pixie-operator-charts.storage.googleapis.com
helm install pixie pixie/pixie-operator-chart \
  --set deployKey=YOUR_KEY \
  --set clusterName=production \
  --namespace pl --create-namespace
```

**No code changes needed.** Pixie captures:
- HTTP requests (URL, latency, status)
- MySQL/Postgres queries with timings
- Redis commands
- Kafka producer/consumer events
- gRPC calls
- DNS queries

**Query via PxL (Python-like DSL):**
```python
# script.pxl
import px

# Get HTTP latency by endpoint
df = px.DataFrame('http_events', start_time='-5m')
df = df.groupby(['req_path']).agg(
    avg_latency=('latency', px.mean),
    p95_latency=('latency', px.quantiles, 0.95),
    count=('req_path', px.count),
)
df = df.sort('p95_latency', desc=True)
px.display(df, "Top slow endpoints")
```

**Real-time SQL-like queries:**
```sql
-- See last 1 min of database queries
SELECT
    table_name,
    avg(latency_ms) as avg_lat,
    quantile(latency_ms, 0.99) as p99_lat,
    count(*) as queries
FROM mysql_events
WHERE _start_time > now() - 1m
GROUP BY table_name
ORDER BY p99_lat DESC
LIMIT 10;
```

---

### Q2: Continuous profiling with Pyroscope?

**Answer:** Always-on CPU/memory profiles — no need to enable when issue strikes.

```bash
# Install Pyroscope server (in K8s)
helm repo add grafana https://grafana.github.io/helm-charts
helm install pyroscope grafana/pyroscope -n pyroscope --create-namespace
```

**Option 1: eBPF-based (no code changes)** — install as DaemonSet:
```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: pyroscope-ebpf
spec:
  selector:
    matchLabels: { app: pyroscope-ebpf }
  template:
    metadata:
      labels: { app: pyroscope-ebpf }
    spec:
      hostPID: true
      containers:
      - name: pyroscope-ebpf
        image: grafana/pyroscope-ebpf:latest
        securityContext:
          privileged: true                # required for eBPF
        env:
        - name: PYROSCOPE_SERVER
          value: http://pyroscope:4040
        - name: PYROSCOPE_SPY_NAME
          value: ebpfspy
        volumeMounts:
        - mountPath: /sys/kernel/debug
          name: sys-kernel-debug
      volumes:
      - name: sys-kernel-debug
        hostPath: { path: /sys/kernel/debug }
```

**Option 2: SDK-based** (for richer Python-aware data):
```python
import pyroscope

pyroscope.configure(
    application_name="acme-api",
    server_address="http://pyroscope:4040",
    auth_token="...",
    sample_rate=100,                       # 100 Hz
    detect_subprocesses=True,
    enable_logging=False,
    tags={"env": "production", "region": "ap-south-1"},
)
```

**Flame graphs in Grafana:**
- Spot hot functions in production
- Compare profile A vs B (before/after deploy)
- Find regressions
- See FastAPI route → SQLAlchemy query → kernel sys calls

---

### Q3: bpftrace — ad-hoc kernel tracing?

**Answer:** One-liner shell scripts to trace anything.

```bash
# Install
sudo apt install bpftrace

# Trace slow open() syscalls
sudo bpftrace -e 'tracepoint:syscalls:sys_enter_openat /comm == "python"/ {
    @start[tid] = nsecs;
}
tracepoint:syscalls:sys_exit_openat /@start[tid]/ {
    $dur = (nsecs - @start[tid]) / 1000;
    if ($dur > 1000) {
        printf("Slow open: %s pid=%d %d us\n", comm, pid, $dur);
    }
    delete(@start[tid]);
}'

# Count which files Python processes open
sudo bpftrace -e 'tracepoint:syscalls:sys_enter_openat /comm == "python"/ {
    @opens[str(args->filename)] = count();
}
interval:s:10 { print(@opens); clear(@opens); }'

# Show TCP connections by process
sudo bpftrace -e 'kprobe:tcp_connect {
    printf("%s pid=%d tcp_connect\n", comm, pid);
}'

# Histogram of HTTP response times (via uprobe on a function)
sudo bpftrace -e 'uprobe:/path/to/python:PyObject_Call /comm == "python"/ {
    @latency = hist(retval);
}'
```

**Pre-built scripts in `bcc` package:**
- `tcpconnect` — track all new TCP connections
- `tcptop` — TCP throughput by PID
- `biolatency` — block I/O latency
- `execsnoop` — track process executions
- `opensnoop` — track file opens
- `funccount` — count function calls
- `argdist` — distribution of function arguments
- `profile` — CPU profiler

---

### Q4: Cilium + Hubble for network observability?

**Answer:** L3-L7 network visibility in K8s, no sidecars.

```bash
# Install Cilium
helm repo add cilium https://helm.cilium.io
helm install cilium cilium/cilium --version 1.16 \
  --namespace kube-system \
  --set hubble.relay.enabled=true \
  --set hubble.ui.enabled=true \
  --set hubble.metrics.enabled="{dns,drop,tcp,flow,icmp,http}"

# Install Hubble CLI
HUBBLE_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/hubble/master/stable.txt)
curl -L --remote-name https://github.com/cilium/hubble/releases/download/$HUBBLE_VERSION/hubble-linux-amd64.tar.gz
tar xzvf hubble-linux-amd64.tar.gz
sudo mv hubble /usr/local/bin

# Port-forward to query
cilium hubble port-forward &

# Observe traffic
hubble observe --follow
hubble observe --pod backend-1
hubble observe --to-namespace database
hubble observe --http-status 5+      # errors
hubble observe --protocol tcp --port 5432  # postgres traffic
```

**Network policies enforced at eBPF level:**
```yaml
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: api-policy
spec:
  endpointSelector:
    matchLabels: { app: api }
  ingress:
  - fromEndpoints:
    - matchLabels: { app: frontend }
    toPorts:
    - ports: [{ port: "8000", protocol: TCP }]
      rules:
        http:
        - method: "GET"
          path: "/api/.*"
        - method: "POST"
          path: "/api/orders"

  egress:
  - toEndpoints:
    - matchLabels: { app: postgres }
    toPorts:
    - ports: [{ port: "5432", protocol: TCP }]
```

This denies any HTTP method/path not whitelisted — at kernel level.

---

### Q5: Security observability with Falco?

**Answer:** Detect suspicious syscalls in real-time.

```bash
# Install Falco
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm install falco falcosecurity/falco \
  --namespace falco --create-namespace \
  --set driver.kind=ebpf \
  --set falcosidekick.enabled=true \
  --set falcosidekick.config.slack.webhookurl=YOUR_SLACK_HOOK
```

**Default rules catch:**
- Shell spawned in container
- Sensitive file read (/etc/shadow, /etc/passwd)
- Privilege escalation
- Network tools running unexpectedly
- Kernel module loading
- Mount in container
- Outbound connection to suspicious IP

**Custom rule (Python-specific):**
```yaml
- rule: Python opening reverse shell
  desc: Detect Python opening outbound socket to unusual port
  condition: >
    spawned_process and
    proc.name = "python" and
    fd.type = "ipv4" and
    not fd.sport in (80, 443, 5432, 6379, 9092)
  output: >
    Suspicious Python network connection
    (user=%user.name command=%proc.cmdline connection=%fd.name)
  priority: WARNING
  tags: [network, python, attack]

- rule: Python eval/exec usage
  desc: Detect Python eval/exec — often code injection
  condition: >
    proc.name = "python" and
    evt.type = execve and
    proc.cmdline contains "eval(" or
    proc.cmdline contains "exec("
  output: Possible code injection in Python (cmd=%proc.cmdline)
  priority: CRITICAL
```

---

### Q6: Parca — profiling for cost optimization?

**Answer:** Find which functions are burning CPU → optimize → save money.

```bash
# Install
helm repo add parca https://parca-dev.github.io/helm-charts
helm install parca parca/parca-server

# Install agent
helm install parca-agent parca/parca-agent \
  --set agent.config.streamRemoteStore=true \
  --set agent.config.profilingInterval=10s
```

**Workflow:**
```
1. Parca shows: "function `parse_user()` takes 30% CPU"
2. Look at code: regex compilation in loop
3. Move to module-level → 2% CPU
4. Save: 14% CPU = 1 fewer pod = ₹2000/month
```

**Compare profiles** (before vs after deploy):
```bash
# Query API
curl 'http://parca:7070/api/v1/profiles/diff' \
  -d 'before=2026-05-25T10:00:00Z&after=2026-05-25T14:00:00Z'

# Returns diff flame graph — see what regressed
```

---

### Q7: Tetragon — runtime security with policies?

**Answer:** Define security policies; eBPF enforces at syscall level.

```yaml
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: block-shell-in-prod
spec:
  podSelector:
    matchLabels:
      env: production
  kprobes:
  - call: "fd_install"
    syscall: false
    args:
    - index: 0
      type: int
    - index: 1
      type: "file"
    selectors:
    - matchArgs:
      - index: 1
        operator: "Postfix"
        values:
        - "/bin/sh"
        - "/bin/bash"
      matchActions:
      - action: Sigkill                  # KILL the process
```

**Detects in real-time:**
- Cryptominers (suspicious CPU patterns)
- Container escape attempts
- Privilege escalation
- File integrity violations
- Lateral movement

---

### Q8: Custom eBPF programs in Python via `bcc`?

**Answer:** Write eBPF in C, attach from Python.

```bash
# Install bcc
sudo apt install bpfcc-tools python3-bpfcc

# Custom script: track slow Python HTTP requests
sudo python3 - <<EOF
from bcc import BPF

prog = """
#include <uapi/linux/ptrace.h>

struct request_data_t {
    u64 pid;
    u64 latency_ns;
    char comm[16];
};

BPF_PERF_OUTPUT(events);
BPF_HASH(start_times, u64, u64);

int trace_http_start(struct pt_regs *ctx) {
    u64 pid = bpf_get_current_pid_tgid();
    u64 now = bpf_ktime_get_ns();
    start_times.update(&pid, &now);
    return 0;
}

int trace_http_end(struct pt_regs *ctx) {
    u64 pid = bpf_get_current_pid_tgid();
    u64 *start_ns = start_times.lookup(&pid);
    if (start_ns == NULL) return 0;

    u64 latency = bpf_ktime_get_ns() - *start_ns;
    if (latency > 100000000) {  // > 100ms
        struct request_data_t data = {};
        data.pid = pid;
        data.latency_ns = latency;
        bpf_get_current_comm(&data.comm, sizeof(data.comm));
        events.perf_submit(ctx, &data, sizeof(data));
    }

    start_times.delete(&pid);
    return 0;
}
"""

b = BPF(text=prog)

# Attach to uprobes on Python's interpreter functions
b.attach_uprobe(name="python3", sym="PyEval_EvalCode", fn_name="trace_http_start")

def print_event(cpu, data, size):
    event = b["events"].event(data)
    print(f"PID {event.pid} cmd={event.comm.decode()} latency={event.latency_ns/1e6:.2f}ms")

b["events"].open_perf_buffer(print_event)
while True:
    try:
        b.perf_buffer_poll()
    except KeyboardInterrupt:
        break
EOF
```

---

## eBPF Stack for FastAPI Backends (Recommended 2026)

```
┌────────────────────────────────────────┐
│  Application: FastAPI                   │
└─────────────┬──────────────────────────┘
              │
┌─────────────▼──────────────────────────┐
│  Container (Pod)                        │
└─────────────┬──────────────────────────┘
              │
┌─────────────▼──────────────────────────┐
│  Linux Kernel + eBPF programs           │
│  ┌────────────┬─────────────┬─────────┐ │
│  │  Pixie     │ Pyroscope    │ Cilium  │ │
│  │ (APM)      │ (profile)    │ (net)   │ │
│  ├────────────┼─────────────┼─────────┤ │
│  │  Falco     │ Tetragon     │ Hubble  │ │
│  │ (security) │ (policy)     │ (flow)  │ │
│  └────────────┴─────────────┴─────────┘ │
└─────────────┬──────────────────────────┘
              │
┌─────────────▼──────────────────────────┐
│  Grafana / Loki / Prometheus            │
│  (unified observability dashboard)      │
└────────────────────────────────────────┘
```

---

## When to Use What

| Need | Pick |
|---|---|
| HTTP/DB tracing without code changes | **Pixie** |
| Continuous CPU profiling | **Pyroscope** or **Parca** |
| K8s networking observability | **Cilium + Hubble** |
| Real-time security detection | **Falco** or **Tetragon** |
| Ad-hoc kernel investigation | **bpftrace** |
| Custom tracing logic | **bcc + Python** |
| Service mesh (eBPF-based) | **Cilium Service Mesh** |
| Want one product for everything | **Cilium + Pixie** (both CNCF) |

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| Requires kernel ≥ 5.4 (some features 6.x) | Verify kernel version |
| Requires privileged or `CAP_BPF` | Configure pod security policies |
| eBPF program load failure on cluster upgrade | Pin agent versions |
| Pixie data retention is short | Forward to long-term storage |
| Pyroscope storage grows fast | Set retention policy |
| Cilium replaces kube-proxy (intentional) | Plan migration carefully |
| `bpftrace` scripts only on hosts (not in pods) | Use DaemonSet pattern |
| Performance overhead under-estimated | Benchmark for your workload |
| Falco rule explosion | Tune to your environment |
| eBPF maps memory leak | Monitor `bpftool map show` |

---

## Cost of Observability

| Approach | Cost (50 services, 100 nodes) |
|---|---|
| Datadog APM (full) | $40K/month |
| OpenTelemetry + Tempo + Grafana | $8K/month |
| **Pixie + Pyroscope + Hubble (self-hosted)** | **$3K/month (infra only)** |

**Why eBPF stack is cheaper:**
- No per-request data → no per-event pricing
- Sampling at kernel level → less data shipped
- Open source → no license fees

---

## Senior-level Checklist

- [ ] Kernel ≥ 5.10 confirmed on all nodes
- [ ] Pixie installed for auto APM (HTTP, DB, Redis)
- [ ] Pyroscope/Parca for continuous profiling
- [ ] Cilium + Hubble for K8s networking
- [ ] Falco/Tetragon for runtime security
- [ ] All observability data flows to Grafana
- [ ] Long-term storage configured (Loki/Tempo/Mimir)
- [ ] Alerts on Falco critical events
- [ ] Network policies enforced via Cilium
- [ ] Quarterly review of profiling hot spots
- [ ] On-call has bpftrace cheat sheet
- [ ] Pixie scripts saved per service
- [ ] Cost vs traditional APM tracked

---

## Related Docs
- `05_prometheus_grafana.md` — metrics foundation
- `06_kubernetes_helm.md` — K8s deployment
- `08_elk_loki_logging.md` — log aggregation
- `14_chaos_engineering.md` — combine with chaos for full picture
- `16_sre_practices_sli_slo.md` — SLO monitoring
- `01_Year3-4_Mid/03_Security/16_sast_dast_supply_chain.md` — security pipeline

## External References
- Pixie: https://docs.px.dev
- Pyroscope: https://grafana.com/docs/pyroscope
- Cilium: https://docs.cilium.io
- Falco: https://falco.org/docs
- bpftrace: https://github.com/iovisor/bpftrace
- Brendan Gregg's eBPF book: https://www.brendangregg.com/bpf-performance-tools-book.html
