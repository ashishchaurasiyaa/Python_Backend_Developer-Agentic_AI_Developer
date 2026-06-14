"""
eBPF Observability for Python Backends — Production Patterns
============================================================

Covers the complete eBPF observability stack used at senior backend level:
  - Why eBPF beats traditional SDK-based instrumentation
  - Pixie  : zero-code-change APM for HTTP / DB / Redis tracing
  - Pyroscope : continuous CPU profiling (SDK + eBPF DaemonSet modes)
  - bpftrace  : ad-hoc kernel tracing one-liners and script patterns
  - Cilium + Hubble : L3–L7 Kubernetes network observability
  - Falco     : runtime security threat detection
  - Tetragon  : kernel-enforced security policies
  - bcc       : custom eBPF programs authored in C, attached from Python
  - Production gotchas, cost comparison, and senior-level deployment checklist

Runtime notes
─────────────
Most eBPF tooling requires a Linux kernel ≥ 5.4, root / CAP_BPF privileges, and
kernel headers.  The classes and functions below model production patterns and are
structured as importable reference code.  Where a dependency (bcc, pyroscope,
cilium CLI) is not installed the relevant class is designed to degrade gracefully,
printing a clear install hint rather than crashing the process.

The ``__main__`` block at the bottom runs a fully self-contained demo that
exercises every concept using only the Python standard library, so it compiles and
executes on any platform without external infrastructure.

External dependencies (install only on a Linux host with kernel headers):
  pip install pyroscope-io          # Pyroscope SDK  (optional)
  sudo apt install bpfcc-tools python3-bpfcc  # bcc / BPF (Linux only)
  sudo apt install bpftrace         # bpftrace (Linux only)
"""

# ==========================================================================
# Standard library imports — no external requirements for core module
# ==========================================================================

import dataclasses
import json
import logging
import os
import platform
import re
import subprocess
import textwrap
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ebpf_observability")


# ==========================================================================
# 1. eBPF FUNDAMENTALS — KNOWLEDGE STRUCTURES
# ==========================================================================

@dataclass
class EBPFTool:
    """Descriptor for a single tool in the eBPF observability ecosystem."""

    name: str
    purpose: str
    maturity: str
    requires_code_change: bool
    kernel_min: str
    install_hint: str
    typical_overhead_pct: float  # percentage of CPU, measured at P99 load


# Reference catalogue — drawn directly from the theory doc tool landscape table
EBPF_TOOL_CATALOGUE: List[EBPFTool] = [
    EBPFTool(
        name="Pixie",
        purpose="Auto-instrumented APM (HTTP, DB, Redis, Kafka, gRPC, DNS tracing)",
        maturity="Production",
        requires_code_change=False,
        kernel_min="5.4",
        install_hint=(
            "helm repo add pixie https://pixie-operator-charts.storage.googleapis.com && "
            "helm install pixie pixie/pixie-operator-chart "
            "--set deployKey=YOUR_KEY --set clusterName=production "
            "--namespace pl --create-namespace"
        ),
        typical_overhead_pct=0.5,
    ),
    EBPFTool(
        name="Pyroscope",
        purpose="Continuous CPU / memory profiling with flame graphs",
        maturity="Production",
        requires_code_change=False,  # eBPF mode requires no code change
        kernel_min="5.10",
        install_hint=(
            "helm repo add grafana https://grafana.github.io/helm-charts && "
            "helm install pyroscope grafana/pyroscope -n pyroscope --create-namespace"
        ),
        typical_overhead_pct=0.3,
    ),
    EBPFTool(
        name="Parca",
        purpose="Continuous profiling — alternative to Pyroscope, CNCF sandbox",
        maturity="Production",
        requires_code_change=False,
        kernel_min="5.10",
        install_hint=(
            "helm repo add parca https://parca-dev.github.io/helm-charts && "
            "helm install parca parca/parca-server"
        ),
        typical_overhead_pct=0.3,
    ),
    EBPFTool(
        name="Cilium",
        purpose="K8s networking + service mesh, replaces kube-proxy at eBPF level",
        maturity="Production",
        requires_code_change=False,
        kernel_min="5.4",
        install_hint=(
            "helm repo add cilium https://helm.cilium.io && "
            "helm install cilium cilium/cilium --version 1.16 "
            "--namespace kube-system "
            "--set hubble.relay.enabled=true "
            "--set hubble.ui.enabled=true"
        ),
        typical_overhead_pct=0.1,
    ),
    EBPFTool(
        name="Hubble",
        purpose="Cilium network observability — L3–L7 flow visibility",
        maturity="Production",
        requires_code_change=False,
        kernel_min="5.4",
        install_hint="Bundled with Cilium; enable via --set hubble.relay.enabled=true",
        typical_overhead_pct=0.1,
    ),
    EBPFTool(
        name="Falco",
        purpose="Real-time security threat detection via syscall rules",
        maturity="Production",
        requires_code_change=False,
        kernel_min="5.4",
        install_hint=(
            "helm repo add falcosecurity https://falcosecurity.github.io/charts && "
            "helm install falco falcosecurity/falco "
            "--namespace falco --create-namespace "
            "--set driver.kind=ebpf "
            "--set falcosidekick.enabled=true"
        ),
        typical_overhead_pct=0.8,
    ),
    EBPFTool(
        name="Tetragon",
        purpose="Runtime security with kernel-enforced policies (Cilium-related)",
        maturity="Production",
        requires_code_change=False,
        kernel_min="5.10",
        install_hint=(
            "helm repo add cilium https://helm.cilium.io && "
            "helm install tetragon cilium/tetragon -n kube-system"
        ),
        typical_overhead_pct=0.5,
    ),
    EBPFTool(
        name="bpftrace",
        purpose="Ad-hoc kernel tracing scripts (one-liners to complex probes)",
        maturity="Production",
        requires_code_change=False,
        kernel_min="5.4",
        install_hint="sudo apt install bpftrace",
        typical_overhead_pct=0.2,
    ),
    EBPFTool(
        name="bcc",
        purpose="eBPF tools library — write eBPF in C, attach from Python",
        maturity="Mature",
        requires_code_change=True,  # developer writes the eBPF program
        kernel_min="4.9",
        install_hint="sudo apt install bpfcc-tools python3-bpfcc",
        typical_overhead_pct=0.4,
    ),
]


def select_tool(need: str) -> Optional[EBPFTool]:
    """
    Return the recommended tool for a given observability need.

    Maps high-level intents (as described in the 'When to Use What' table
    from the theory doc) to a concrete ``EBPFTool`` entry.

    Parameters
    ----------
    need:
        One of: 'apm', 'profiling', 'networking', 'security', 'ad-hoc',
        'custom', 'mesh'.

    Returns
    -------
    Optional[EBPFTool]
        The best-fit tool, or ``None`` if the need is unrecognised.
    """
    mapping: Dict[str, str] = {
        "apm": "Pixie",
        "profiling": "Pyroscope",
        "networking": "Cilium",
        "security": "Falco",
        "ad-hoc": "bpftrace",
        "custom": "bcc",
        "mesh": "Cilium",
    }
    tool_name = mapping.get(need.lower())
    if tool_name is None:
        return None
    return next((t for t in EBPF_TOOL_CATALOGUE if t.name == tool_name), None)


# ==========================================================================
# 2. PIXIE — AUTO-INSTRUMENTED APM (PxL QUERY PATTERNS)
# ==========================================================================

class PixiePxLTemplates:
    """
    Ready-to-paste PxL script templates for common Pixie queries.

    PxL is a Python-like DSL that queries Pixie's in-memory tables.  These
    templates are meant to be pasted into the Pixie Live UI or executed via
    the Pixie CLI / API.  They require no application code changes.

    Reference: https://docs.px.dev/reference/pxl
    """

    # ------------------------------------------------------------------
    # Detect the slowest HTTP endpoints in the last 5 minutes
    # ------------------------------------------------------------------
    HTTP_LATENCY_BY_ENDPOINT: str = textwrap.dedent("""\
        import px

        df = px.DataFrame('http_events', start_time='-5m')
        df = df.groupby(['req_path', 'req_method']).agg(
            avg_latency_ms=('latency', px.mean),
            p95_latency_ms=('latency', px.quantiles, 0.95),
            p99_latency_ms=('latency', px.quantiles, 0.99),
            error_rate=('resp_status', px.mean),          # fraction that are 5xx
            request_count=('req_path', px.count),
        )
        df = df.sort('p99_latency_ms', descending=True)
        px.display(df, 'Slowest endpoints — last 5 min')
    """)

    # ------------------------------------------------------------------
    # Identify which DB tables are receiving the heaviest query load
    # ------------------------------------------------------------------
    DB_QUERY_HOTSPOTS: str = textwrap.dedent("""\
        import px

        df = px.DataFrame('mysql_events', start_time='-1m')
        df = df.groupby(['table_name']).agg(
            avg_lat_ms=('latency', px.mean),
            p99_lat_ms=('latency', px.quantiles, 0.99),
            query_count=('table_name', px.count),
        )
        df = df.sort('p99_lat_ms', descending=True)
        px.display(df, 'DB hotspots — last 1 min')
    """)

    # ------------------------------------------------------------------
    # Live Redis command latency breakdown
    # ------------------------------------------------------------------
    REDIS_LATENCY: str = textwrap.dedent("""\
        import px

        df = px.DataFrame('redis_events', start_time='-5m')
        df = df.groupby(['cmd']).agg(
            avg_latency_ms=('latency', px.mean),
            call_count=('cmd', px.count),
        )
        df = df.sort('avg_latency_ms', descending=True)
        px.display(df, 'Redis command latency')
    """)

    # ------------------------------------------------------------------
    # Service-to-service call graph with error rates
    # ------------------------------------------------------------------
    SERVICE_CALL_GRAPH: str = textwrap.dedent("""\
        import px

        df = px.DataFrame('http_events', start_time='-15m')
        df.requestor = df.ctx['pod']
        df = df.groupby(['requestor', 'remote_addr', 'req_path']).agg(
            count=('req_path', px.count),
            errors=('resp_status', px.sum),
        )
        px.display(df, 'Service call graph')
    """)

    @staticmethod
    def list_templates() -> List[str]:
        """Return the names of all available PxL templates."""
        return [
            attr for attr in dir(PixiePxLTemplates)
            if not attr.startswith("_") and attr.isupper()
        ]


# ==========================================================================
# 3. PYROSCOPE — CONTINUOUS PROFILING
# ==========================================================================

class PyroscopeConfig:
    """
    Builder for a Pyroscope SDK configuration block.

    The SDK embeds a sampling profiler (default 100 Hz) inside the process
    and ships stacks to the Pyroscope server over HTTP.  Use this when
    eBPF-based profiling is unavailable (e.g. non-Linux hosts or containers
    without kernel access).

    For production Kubernetes workloads, prefer the eBPF DaemonSet mode
    (see ``PyroscopeDaemonSetManifest``) which requires zero code changes.

    pip install pyroscope-io
    """

    def __init__(
        self,
        app_name: str,
        server_address: str = "http://pyroscope:4040",
        sample_rate: int = 100,
        environment: str = "production",
        region: str = "ap-south-1",
        auth_token: Optional[str] = None,
    ) -> None:
        self.app_name = app_name
        self.server_address = server_address
        self.sample_rate = sample_rate
        self.environment = environment
        self.region = region
        self.auth_token = auth_token

    def start(self) -> bool:
        """
        Attempt to start the Pyroscope profiler.

        Returns True on success, False if ``pyroscope`` is not installed
        (non-fatal — the application continues normally without profiling).
        """
        try:
            import pyroscope  # type: ignore

            kwargs: Dict[str, Any] = dict(
                application_name=self.app_name,
                server_address=self.server_address,
                sample_rate=self.sample_rate,
                detect_subprocesses=True,
                enable_logging=False,
                tags={"env": self.environment, "region": self.region},
            )
            if self.auth_token:
                kwargs["auth_token"] = self.auth_token

            pyroscope.configure(**kwargs)
            log.info(
                "Pyroscope profiler started — server=%s app=%s rate=%dHz",
                self.server_address,
                self.app_name,
                self.sample_rate,
            )
            return True

        except ImportError:
            log.warning(
                "pyroscope-io not installed.  "
                "Run: pip install pyroscope-io  "
                "Or deploy the eBPF DaemonSet for zero-code profiling."
            )
            return False

    def as_dict(self) -> Dict[str, Any]:
        """Return the configuration as a plain dictionary (useful for logging)."""
        return {
            "app_name": self.app_name,
            "server_address": self.server_address,
            "sample_rate": self.sample_rate,
            "environment": self.environment,
            "region": self.region,
            "auth_token": "***" if self.auth_token else None,
        }


class PyroscopeDaemonSetManifest:
    """
    Renders the Kubernetes DaemonSet YAML needed to deploy the Pyroscope
    eBPF agent across all cluster nodes.

    This approach requires zero application code changes.  The DaemonSet
    runs with ``hostPID: true`` and mounts ``/sys/kernel/debug`` so that
    eBPF programs can attach to every process on the host.
    """

    TEMPLATE: str = textwrap.dedent("""\
        apiVersion: apps/v1
        kind: DaemonSet
        metadata:
          name: pyroscope-ebpf
          namespace: {namespace}
        spec:
          selector:
            matchLabels:
              app: pyroscope-ebpf
          template:
            metadata:
              labels:
                app: pyroscope-ebpf
            spec:
              hostPID: true          # required: access all host PIDs
              containers:
              - name: pyroscope-ebpf
                image: grafana/pyroscope-ebpf:latest
                securityContext:
                  privileged: true   # required for eBPF program loading
                env:
                - name: PYROSCOPE_SERVER
                  value: {server_address}
                - name: PYROSCOPE_SPY_NAME
                  value: ebpfspy
                volumeMounts:
                - mountPath: /sys/kernel/debug
                  name: sys-kernel-debug
              volumes:
              - name: sys-kernel-debug
                hostPath:
                  path: /sys/kernel/debug
    """)

    @classmethod
    def render(
        cls,
        server_address: str = "http://pyroscope:4040",
        namespace: str = "pyroscope",
    ) -> str:
        """Return the fully rendered DaemonSet YAML string."""
        return cls.TEMPLATE.format(
            server_address=server_address,
            namespace=namespace,
        )


# ==========================================================================
# 4. bpftrace — AD-HOC KERNEL TRACING SCRIPTS
# ==========================================================================

class BpftraceScripts:
    """
    Curated collection of bpftrace one-liners and multi-probe scripts
    that are immediately useful for debugging Python backend services.

    Execute on the host (not inside a container) with root privileges:
        sudo bpftrace -e '<script>'

    Reference: https://github.com/iovisor/bpftrace
    """

    # ------------------------------------------------------------------
    # Detect slow open() syscalls made by any Python process
    # ------------------------------------------------------------------
    SLOW_OPEN_SYSCALLS: str = textwrap.dedent("""\
        tracepoint:syscalls:sys_enter_openat /comm == "python"/ {
            @start[tid] = nsecs;
        }
        tracepoint:syscalls:sys_exit_openat /@start[tid]/ {
            $dur = (nsecs - @start[tid]) / 1000;
            if ($dur > 1000) {
                printf("Slow open: pid=%d comm=%s duration=%d us\\n",
                       pid, comm, $dur);
            }
            delete(@start[tid]);
        }
    """)

    # ------------------------------------------------------------------
    # Count which files Python processes open (10-second rolling window)
    # ------------------------------------------------------------------
    FILE_OPEN_COUNTS: str = textwrap.dedent("""\
        tracepoint:syscalls:sys_enter_openat /comm == "python"/ {
            @opens[str(args->filename)] = count();
        }
        interval:s:10 {
            print(@opens);
            clear(@opens);
        }
    """)

    # ------------------------------------------------------------------
    # Track all new outbound TCP connections by process name
    # ------------------------------------------------------------------
    TCP_CONNECT_TRACE: str = textwrap.dedent("""\
        kprobe:tcp_connect {
            printf("tcp_connect: comm=%s pid=%d\\n", comm, pid);
        }
    """)

    # ------------------------------------------------------------------
    # Histogram of Python function call latency via uprobe
    # (replace /path/to/python3 with actual binary path)
    # ------------------------------------------------------------------
    PYTHON_FUNC_LATENCY_HIST: str = textwrap.dedent("""\
        uprobe:/usr/bin/python3:PyEval_EvalCode {
            @start[tid] = nsecs;
        }
        uretprobe:/usr/bin/python3:PyEval_EvalCode /@start[tid]/ {
            @latency_us = hist((nsecs - @start[tid]) / 1000);
            delete(@start[tid]);
        }
    """)

    # ------------------------------------------------------------------
    # Detect when Python spawns a child process (possible command injection)
    # ------------------------------------------------------------------
    CHILD_PROCESS_SPAWN: str = textwrap.dedent("""\
        tracepoint:syscalls:sys_enter_execve /comm == "python"/ {
            printf("exec: pid=%d parent=python args=%s\\n",
                   pid, str(args->filename));
        }
    """)

    @classmethod
    def run(cls, script: str, dry_run: bool = True) -> Optional[str]:
        """
        Execute a bpftrace script on the local Linux host.

        Parameters
        ----------
        script:
            The bpftrace script body (not the ``-e`` flag — just the script).
        dry_run:
            When ``True`` (default) only validates that ``bpftrace`` is
            installed and returns the command that *would* be run.
            Set to ``False`` to actually execute (requires root on Linux).

        Returns
        -------
        Optional[str]
            Command stdout on success, or ``None`` if bpftrace is absent.
        """
        if platform.system() != "Linux":
            log.warning(
                "bpftrace is Linux-only.  "
                "Current platform: %s", platform.system()
            )
            return None

        # Confirm binary is present
        result = subprocess.run(
            ["which", "bpftrace"], capture_output=True, text=True
        )
        if result.returncode != 0:
            log.warning(
                "bpftrace not found.  Install with: sudo apt install bpftrace"
            )
            return None

        cmd = ["sudo", "bpftrace", "-e", script]
        if dry_run:
            log.info("DRY-RUN bpftrace command: %s", " ".join(cmd))
            return " ".join(cmd)

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return proc.stdout


# ==========================================================================
# 5. bcc — CUSTOM eBPF PROGRAMS FROM PYTHON
# ==========================================================================

# The C source for the eBPF kernel program.  Kept as a module-level
# constant so it can be referenced and reviewed without importing bcc.
BCC_HTTP_LATENCY_PROG: str = textwrap.dedent("""\
    #include <uapi/linux/ptrace.h>

    struct request_data_t {
        u64 pid;
        u64 latency_ns;
        char comm[16];
    };

    BPF_PERF_OUTPUT(events);
    BPF_HASH(start_times, u64, u64);

    /*
     * trace_http_start — attached as a uprobe to PyEval_EvalCode.
     * Records the kernel timestamp at the moment evaluation begins.
     */
    int trace_http_start(struct pt_regs *ctx) {
        u64 pid = bpf_get_current_pid_tgid();
        u64 now = bpf_ktime_get_ns();
        start_times.update(&pid, &now);
        return 0;
    }

    /*
     * trace_http_end — uretprobe counterpart.
     * Computes elapsed nanoseconds; emits an event only when > 100 ms
     * to avoid flooding user-space with normal-latency calls.
     */
    int trace_http_end(struct pt_regs *ctx) {
        u64 pid = bpf_get_current_pid_tgid();
        u64 *start_ns = start_times.lookup(&pid);
        if (start_ns == NULL) return 0;

        u64 latency = bpf_ktime_get_ns() - *start_ns;
        if (latency > 100000000ULL) {   /* > 100 ms threshold */
            struct request_data_t data = {};
            data.pid = pid;
            data.latency_ns = latency;
            bpf_get_current_comm(&data.comm, sizeof(data.comm));
            events.perf_submit(ctx, &data, sizeof(data));
        }
        start_times.delete(&pid);
        return 0;
    }
""")


class BCCPythonTracer:
    """
    Attaches a custom eBPF program (via bcc) to the running Python
    interpreter to surface requests that exceed a latency threshold.

    Requires:
        sudo apt install bpfcc-tools python3-bpfcc
        Root privileges (or CAP_BPF on kernel ≥ 5.8)
        Linux kernel ≥ 4.9

    Usage::

        tracer = BCCPythonTracer(threshold_ms=100)
        tracer.start()   # blocks; Ctrl-C to stop
    """

    def __init__(
        self,
        threshold_ms: int = 100,
        python_binary: str = "/usr/bin/python3",
    ) -> None:
        self.threshold_ms = threshold_ms
        self.python_binary = python_binary
        self._bpf: Any = None

    def _event_handler(self, cpu: int, data: Any, size: int) -> None:
        """Callback invoked by bcc for each slow-request perf event."""
        event = self._bpf["events"].event(data)  # type: ignore
        latency_ms = event.latency_ns / 1_000_000
        log.warning(
            "Slow Python eval: pid=%d comm=%s latency=%.2f ms",
            event.pid,
            event.comm.decode(errors="replace"),
            latency_ms,
        )

    def start(self) -> None:
        """
        Load the eBPF program and begin polling for slow-request events.

        Blocks until KeyboardInterrupt.  Falls back gracefully if bcc
        is not available on the host.
        """
        try:
            from bcc import BPF  # type: ignore  # Linux-only, requires root
        except ImportError:
            log.error(
                "bcc not available.  "
                "Install with: sudo apt install bpfcc-tools python3-bpfcc  "
                "(Linux only, requires kernel headers)"
            )
            return

        log.info(
            "Loading eBPF program — threshold=%d ms, binary=%s",
            self.threshold_ms,
            self.python_binary,
        )
        self._bpf = BPF(text=BCC_HTTP_LATENCY_PROG)

        # Attach uprobes to CPython's evaluation entry and exit points
        self._bpf.attach_uprobe(
            name=self.python_binary,
            sym="PyEval_EvalCode",
            fn_name="trace_http_start",
        )
        self._bpf.attach_uretprobe(
            name=self.python_binary,
            sym="PyEval_EvalCode",
            fn_name="trace_http_end",
        )

        self._bpf["events"].open_perf_buffer(self._event_handler)
        log.info("eBPF probe active — Ctrl-C to stop")

        while True:
            try:
                self._bpf.perf_buffer_poll()
            except KeyboardInterrupt:
                log.info("eBPF tracer stopped.")
                break


# ==========================================================================
# 6. CILIUM + HUBBLE — NETWORK OBSERVABILITY
# ==========================================================================

class CiliumHubbleCLI:
    """
    Wrapper around the ``hubble`` CLI for programmatic network observation.

    Hubble is the observability component of Cilium.  It provides L3–L7
    flow visibility across all pods without sidecars, by hooking into eBPF
    programs that Cilium loads into the kernel.

    Reference: https://docs.cilium.io/en/stable/gettingstarted/hubble/
    """

    def __init__(self, port: int = 4245) -> None:
        self.port = port

    def _run_hubble(self, args: List[str]) -> Optional[str]:
        """Run a hubble CLI command and return stdout, or None on failure."""
        if platform.system() != "Linux":
            log.warning("Hubble CLI is Kubernetes / Linux only.")
            return None
        result = subprocess.run(
            ["hubble"] + args, capture_output=True, text=True
        )
        if result.returncode != 0:
            log.error("hubble error: %s", result.stderr.strip())
            return None
        return result.stdout

    def observe_pod(self, pod_name: str, follow: bool = False) -> Optional[str]:
        """
        Return recent network flows for a specific pod.

        Parameters
        ----------
        pod_name:
            Kubernetes pod name to filter flows on.
        follow:
            If True, stream flows continuously (blocks until interrupted).
        """
        args = ["observe", "--pod", pod_name]
        if follow:
            args.append("--follow")
        return self._run_hubble(args)

    def observe_namespace(self, namespace: str) -> Optional[str]:
        """Return flows destined for a given Kubernetes namespace."""
        return self._run_hubble(["observe", "--to-namespace", namespace])

    def observe_http_errors(self) -> Optional[str]:
        """Return flows where the HTTP status code is 5xx."""
        return self._run_hubble(["observe", "--http-status", "5+"])

    def observe_postgres_traffic(self, port: int = 5432) -> Optional[str]:
        """Return TCP flows on the Postgres port."""
        return self._run_hubble(
            ["observe", "--protocol", "tcp", "--port", str(port)]
        )


@dataclass
class CiliumNetworkPolicy:
    """
    Structured representation of a CiliumNetworkPolicy that restricts
    an API service to only allow specific HTTP methods and paths.

    Rendered to YAML for ``kubectl apply``.
    """

    policy_name: str
    app_label: str
    allowed_source_label: str
    allowed_port: int
    allowed_http_rules: List[Dict[str, str]]  # [{"method": "GET", "path": "/api/.*"}]
    egress_target_label: str
    egress_port: int

    def to_yaml(self) -> str:
        """Render the policy as a CiliumNetworkPolicy YAML manifest."""
        http_rules = "\n".join(
            f"        - method: \"{rule['method']}\"\n"
            f"          path: \"{rule['path']}\""
            for rule in self.allowed_http_rules
        )
        return textwrap.dedent(f"""\
            apiVersion: cilium.io/v2
            kind: CiliumNetworkPolicy
            metadata:
              name: {self.policy_name}
            spec:
              endpointSelector:
                matchLabels:
                  app: {self.app_label}
              ingress:
              - fromEndpoints:
                - matchLabels:
                    app: {self.allowed_source_label}
                toPorts:
                - ports:
                  - port: "{self.allowed_port}"
                    protocol: TCP
                  rules:
                    http:
            {http_rules}
              egress:
              - toEndpoints:
                - matchLabels:
                    app: {self.egress_target_label}
                toPorts:
                - ports:
                  - port: "{self.egress_port}"
                    protocol: TCP
        """)


# ==========================================================================
# 7. FALCO — RUNTIME SECURITY DETECTION
# ==========================================================================

@dataclass
class FalcoRule:
    """
    Typed representation of a Falco security rule.

    Falco rules are evaluated against every syscall on the host; when the
    ``condition`` matches, Falco emits an alert with the formatted ``output``
    string.  Custom rules extend the default ruleset to cover application-
    specific threats.
    """

    rule: str
    desc: str
    condition: str
    output: str
    priority: str  # DEBUG | INFO | NOTICE | WARNING | ERROR | CRITICAL
    tags: List[str] = field(default_factory=list)

    def to_yaml(self) -> str:
        """Render the rule as YAML suitable for a Falco rules file."""
        tags_yaml = ", ".join(self.tags)
        return textwrap.dedent(f"""\
            - rule: {self.rule}
              desc: {self.desc}
              condition: >
                {self.condition}
              output: >
                {self.output}
              priority: {self.priority}
              tags: [{tags_yaml}]
        """)


# Production rules for Python backend services
PYTHON_FALCO_RULES: List[FalcoRule] = [
    FalcoRule(
        rule="Python opening reverse shell",
        desc="Detect Python opening outbound socket to an unexpected port",
        condition=(
            "spawned_process and proc.name = \"python\" and "
            "fd.type = \"ipv4\" and "
            "not fd.sport in (80, 443, 5432, 6379, 9092)"
        ),
        output=(
            "Suspicious Python network connection "
            "(user=%user.name command=%proc.cmdline connection=%fd.name)"
        ),
        priority="WARNING",
        tags=["network", "python", "attack"],
    ),
    FalcoRule(
        rule="Python eval/exec usage",
        desc="Detect Python eval/exec — common code injection vector",
        condition=(
            "proc.name = \"python\" and evt.type = execve and "
            "(proc.cmdline contains \"eval(\" or proc.cmdline contains \"exec(\")"
        ),
        output="Possible code injection in Python (cmd=%proc.cmdline)",
        priority="CRITICAL",
        tags=["injection", "python", "security"],
    ),
    FalcoRule(
        rule="Sensitive file read inside container",
        desc="Detect any process reading /etc/shadow or /etc/passwd",
        condition=(
            "open_read and container and "
            "(fd.name = \"/etc/shadow\" or fd.name = \"/etc/passwd\")"
        ),
        output=(
            "Sensitive file read in container "
            "(user=%user.name file=%fd.name cmd=%proc.cmdline)"
        ),
        priority="ERROR",
        tags=["file", "container", "credentials"],
    ),
    FalcoRule(
        rule="Shell spawned inside container",
        desc="Detect bash/sh spawned inside a production container",
        condition=(
            "spawned_process and container and "
            "proc.name in (shell_binaries)"
        ),
        output=(
            "Shell spawned in container "
            "(user=%user.name shell=%proc.name parent=%proc.pname "
            "image=%container.image.repository)"
        ),
        priority="WARNING",
        tags=["container", "shell", "lateral_movement"],
    ),
]


# ==========================================================================
# 8. TETRAGON — KERNEL-ENFORCED SECURITY POLICIES
# ==========================================================================

class TetragonPolicyTemplates:
    """
    TracingPolicy YAML templates for Tetragon.

    Unlike Falco (which only alerts), Tetragon can enforce policies by
    sending SIGKILL to offending processes directly from eBPF — before the
    malicious action completes.  This is enforcement, not just detection.

    Reference: https://tetragon.io/docs/
    """

    # Kill any shell process that appears inside a production pod
    BLOCK_SHELL_IN_PROD: str = textwrap.dedent("""\
        apiVersion: cilium.io/v1alpha1
        kind: TracingPolicy
        metadata:
          name: block-shell-in-production
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
                - "/bin/zsh"
              matchActions:
              - action: Sigkill   # terminate the process at kernel level
    """)

    # Prevent any process from loading a kernel module inside a container
    BLOCK_KERNEL_MODULE_LOAD: str = textwrap.dedent("""\
        apiVersion: cilium.io/v1alpha1
        kind: TracingPolicy
        metadata:
          name: block-kernel-module-load
        spec:
          kprobes:
          - call: "security_kernel_module_request"
            syscall: false
            selectors:
            - matchActions:
              - action: Sigkill
    """)

    @classmethod
    def render(cls, template_name: str) -> Optional[str]:
        """
        Return a named TracingPolicy YAML template.

        Parameters
        ----------
        template_name:
            One of 'BLOCK_SHELL_IN_PROD' or 'BLOCK_KERNEL_MODULE_LOAD'.
        """
        return getattr(cls, template_name, None)


# ==========================================================================
# 9. OBSERVABILITY STACK — DEPLOYMENT DECISION HELPER
# ==========================================================================

@dataclass
class ObservabilityDecision:
    """Result returned by ``recommend_stack``."""

    selected_tools: List[EBPFTool]
    rationale: str
    estimated_monthly_cost_usd: float
    kernel_requirement: str
    deployment_notes: str


def recommend_stack(
    needs: List[str],
    node_count: int = 10,
    service_count: int = 5,
) -> ObservabilityDecision:
    """
    Recommend an eBPF observability stack for the given needs.

    Parameters
    ----------
    needs:
        A subset of: 'apm', 'profiling', 'networking', 'security',
        'ad-hoc', 'custom'.
    node_count:
        Number of Kubernetes nodes (affects cost estimate).
    service_count:
        Number of distinct backend services.

    Returns
    -------
    ObservabilityDecision
        Tool selection, rationale, and rough cost estimate.
    """
    selected: List[EBPFTool] = []
    for need in needs:
        tool = select_tool(need)
        if tool and tool not in selected:
            selected.append(tool)

    # Very rough infra cost: $30/node/month for the observability DaemonSets
    estimated_cost = node_count * 30.0

    return ObservabilityDecision(
        selected_tools=selected,
        rationale=(
            f"Selected {len(selected)} tool(s) covering: {', '.join(needs)}.  "
            f"All run as eBPF programs in the kernel — no sidecars, no per-request "
            f"SDK overhead, zero application code changes (except Pyroscope SDK mode)."
        ),
        estimated_monthly_cost_usd=estimated_cost,
        kernel_requirement="Linux ≥ 5.10 recommended for full feature compatibility",
        deployment_notes=(
            f"With {service_count} services and {node_count} nodes, deploy each "
            "selected tool as a DaemonSet.  "
            "Unified dashboards via Grafana + Loki + Prometheus + Tempo."
        ),
    )


# ==========================================================================
# 10. PRODUCTION GOTCHAS REGISTRY
# ==========================================================================

@dataclass
class Gotcha:
    """A known production pitfall and its recommended fix."""

    issue: str
    fix: str
    severity: str  # LOW | MEDIUM | HIGH | CRITICAL


PRODUCTION_GOTCHAS: List[Gotcha] = [
    Gotcha(
        issue="Kernel < 5.4 — many eBPF features absent",
        fix="Run 'uname -r' on each node; upgrade OS if needed (Ubuntu 22.04 ships 5.15)",
        severity="CRITICAL",
    ),
    Gotcha(
        issue="eBPF programs rejected without CAP_BPF or privileged context",
        fix="Grant 'CAP_BPF' to the DaemonSet or use 'securityContext.privileged: true'",
        severity="HIGH",
    ),
    Gotcha(
        issue="Pixie data retention is short (in-memory, 1–2 h by default)",
        fix="Configure Pixie to forward data to a long-term store (e.g. Grafana Tempo)",
        severity="MEDIUM",
    ),
    Gotcha(
        issue="Pyroscope / Parca storage grows unbounded",
        fix="Set a retention policy: grafana/pyroscope retention flag or S3 tiering",
        severity="MEDIUM",
    ),
    Gotcha(
        issue="Cilium replaces kube-proxy — unexpected networking breakage on upgrade",
        fix="Plan the kube-proxy migration window; test in staging with eBPF mode first",
        severity="HIGH",
    ),
    Gotcha(
        issue="bpftrace scripts run only on hosts, not inside pods",
        fix="Deploy bpftrace as a privileged DaemonSet pod, or SSH to the node",
        severity="MEDIUM",
    ),
    Gotcha(
        issue="eBPF map memory leak in long-running programs",
        fix="Monitor with 'bpftool map show'; set map max_entries limits in C source",
        severity="HIGH",
    ),
    Gotcha(
        issue="Falco rule explosion — too many alerts, on-call ignores them",
        fix="Tune rules per environment; suppress known-good processes; use priorities",
        severity="MEDIUM",
    ),
    Gotcha(
        issue="Performance overhead under-estimated for high-throughput services",
        fix="Benchmark each tool under realistic load; budget < 1% CPU as acceptable",
        severity="MEDIUM",
    ),
    Gotcha(
        issue="eBPF agent version pinned to cluster kernel — breaks on kernel upgrade",
        fix="Lock agent image tags; test in canary cluster after every OS upgrade",
        severity="HIGH",
    ),
]


# ==========================================================================
# 11. COST COMPARISON UTILITY
# ==========================================================================

@dataclass
class ObservabilityCostEstimate:
    """Monthly cost comparison for three observability approaches."""

    approach: str
    monthly_cost_usd: float
    notes: str


def compare_observability_costs(
    node_count: int,
    service_count: int,
) -> List[ObservabilityCostEstimate]:
    """
    Generate a rough monthly cost comparison for different observability stacks.

    Based on the cost table in the theory doc (50 services, 100 nodes as baseline).
    Costs are scaled linearly from that baseline.

    Parameters
    ----------
    node_count:
        Actual number of cluster nodes.
    service_count:
        Number of backend services to observe.

    Returns
    -------
    List[ObservabilityCostEstimate]
        Three estimates: Datadog APM, OTel + Tempo + Grafana, and the
        self-hosted eBPF stack (Pixie + Pyroscope + Hubble).
    """
    scale = (node_count / 100.0) * (service_count / 50.0)

    return [
        ObservabilityCostEstimate(
            approach="Datadog APM (full, hosted)",
            monthly_cost_usd=40_000 * scale,
            notes=(
                "Per-request tracing, per-host agents, per-user dashboards. "
                "Expensive but managed and battle-tested."
            ),
        ),
        ObservabilityCostEstimate(
            approach="OpenTelemetry SDK + Grafana Tempo + Prometheus (self-hosted)",
            monthly_cost_usd=8_000 * scale,
            notes=(
                "Requires SDK changes in every service.  "
                "Open source tooling; infra + ops cost."
            ),
        ),
        ObservabilityCostEstimate(
            approach="eBPF stack: Pixie + Pyroscope + Cilium/Hubble (self-hosted)",
            monthly_cost_usd=3_000 * scale,
            notes=(
                "No per-request overhead.  "
                "Zero code changes.  "
                "Open source; kernel-level efficiency reduces data volume."
            ),
        ),
    ]


# ==========================================================================
# 12. SENIOR-LEVEL DEPLOYMENT CHECKLIST
# ==========================================================================

@dataclass
class ChecklistItem:
    """A single deployment readiness check."""

    description: str
    category: str
    done: bool = False

    def mark_done(self) -> "ChecklistItem":
        return dataclasses.replace(self, done=True)


SENIOR_DEPLOYMENT_CHECKLIST: List[ChecklistItem] = [
    ChecklistItem("Kernel ≥ 5.10 confirmed on all cluster nodes", "Prerequisites"),
    ChecklistItem("Pixie installed via Helm for auto APM (HTTP, DB, Redis, gRPC)", "APM"),
    ChecklistItem("Pyroscope or Parca DaemonSet running for continuous profiling", "Profiling"),
    ChecklistItem("Cilium installed as CNI, replacing kube-proxy", "Networking"),
    ChecklistItem("Hubble relay and UI enabled; flow metrics active", "Networking"),
    ChecklistItem("Falco deployed with eBPF driver and Slack webhook via falcosidekick", "Security"),
    ChecklistItem("Tetragon TracingPolicies applied for critical production namespaces", "Security"),
    ChecklistItem("All telemetry flows to Grafana (Loki + Tempo + Mimir)", "Dashboards"),
    ChecklistItem("Long-term storage configured with retention policies", "Storage"),
    ChecklistItem("Alerts defined for CRITICAL Falco events → PagerDuty", "Alerting"),
    ChecklistItem("CiliumNetworkPolicy applied on all production namespaces", "Networking"),
    ChecklistItem("Quarterly profiling review scheduled — hunt for CPU hot spots", "Process"),
    ChecklistItem("bpftrace cheat sheet distributed to on-call engineers", "Process"),
    ChecklistItem("Pixie PxL scripts saved per service in the runbook wiki", "Process"),
    ChecklistItem("Monthly cost vs traditional APM tracked in FinOps dashboard", "Cost"),
]


def run_checklist(items: List[ChecklistItem]) -> Dict[str, List[ChecklistItem]]:
    """
    Group checklist items by category and return as a dictionary.

    Parameters
    ----------
    items:
        Full list of ``ChecklistItem`` instances.

    Returns
    -------
    Dict[str, List[ChecklistItem]]
        Keys are category names; values are the items in that category.
    """
    result: Dict[str, List[ChecklistItem]] = {}
    for item in items:
        result.setdefault(item.category, []).append(item)
    return result


# ==========================================================================
# 13. PURE-PYTHON DEMO — runs without external infrastructure
# ==========================================================================

def _demo_tool_catalogue() -> None:
    """Print a formatted summary of the eBPF tool catalogue."""
    print("\n--- eBPF Tool Catalogue ---")
    for tool in EBPF_TOOL_CATALOGUE:
        code_tag = "code-required" if tool.requires_code_change else "zero-code"
        print(
            f"  [{tool.maturity:10s}] [{code_tag:13s}]  "
            f"kernel≥{tool.kernel_min}  "
            f"overhead~{tool.typical_overhead_pct:.1f}%  "
            f"{tool.name}: {tool.purpose}"
        )


def _demo_stack_recommendation() -> None:
    """Illustrate the stack recommendation helper."""
    print("\n--- Stack Recommendation ---")
    decision = recommend_stack(
        needs=["apm", "profiling", "networking", "security"],
        node_count=20,
        service_count=8,
    )
    print(f"  Tools selected ({len(decision.selected_tools)}):")
    for t in decision.selected_tools:
        print(f"    • {t.name}")
    print(f"  Estimated monthly cost : ${decision.estimated_monthly_cost_usd:,.0f}")
    print(f"  Kernel requirement     : {decision.kernel_requirement}")
    print(f"  Notes: {decision.deployment_notes}")


def _demo_pxl_templates() -> None:
    """Show available PxL query template names."""
    print("\n--- Pixie PxL Templates ---")
    for name in PixiePxLTemplates.list_templates():
        print(f"  • PixiePxLTemplates.{name}")
    print("  (Paste template body into the Pixie Live UI or Pixie API)")


def _demo_falco_rules() -> None:
    """Print one Falco rule as YAML to illustrate the format."""
    print("\n--- Sample Falco Rule (YAML) ---")
    rule = PYTHON_FALCO_RULES[0]
    print(textwrap.indent(rule.to_yaml(), "  "))


def _demo_cost_comparison() -> None:
    """Compare observability costs for a representative cluster."""
    print("\n--- Monthly Cost Comparison (20 nodes, 8 services) ---")
    estimates = compare_observability_costs(node_count=20, service_count=8)
    baseline = estimates[-1].monthly_cost_usd
    for est in estimates:
        multiple = est.monthly_cost_usd / baseline
        print(
            f"  {est.approach:<55s}  "
            f"${est.monthly_cost_usd:>8,.0f}/mo  "
            f"({multiple:.1f}x)"
        )


def _demo_checklist() -> None:
    """Print a grouped senior deployment checklist."""
    print("\n--- Senior Deployment Checklist ---")
    grouped = run_checklist(SENIOR_DEPLOYMENT_CHECKLIST)
    for category, items in grouped.items():
        print(f"  [{category}]")
        for item in items:
            status = "✓" if item.done else "○"
            print(f"    {status} {item.description}")


def _demo_gotchas() -> None:
    """Print production gotchas filtered by HIGH or CRITICAL severity."""
    print("\n--- Production Gotchas (HIGH / CRITICAL) ---")
    severe = [g for g in PRODUCTION_GOTCHAS if g.severity in ("HIGH", "CRITICAL")]
    for gotcha in severe:
        print(f"  [{gotcha.severity}]  {gotcha.issue}")
        print(f"           Fix: {gotcha.fix}\n")


def _demo_bpftrace_dry_run() -> None:
    """Show what a bpftrace command would look like (safe, no root needed)."""
    print("\n--- bpftrace Dry-run Command ---")
    scripts = BpftraceScripts()
    result = scripts.run(BpftraceScripts.SLOW_OPEN_SYSCALLS, dry_run=True)
    if result:
        print(f"  Command: {result}")
    else:
        print("  (bpftrace only runs on Linux — showing script body instead)")
        print(textwrap.indent(BpftraceScripts.SLOW_OPEN_SYSCALLS, "  "))


def _demo_cilium_policy() -> None:
    """Render a CiliumNetworkPolicy YAML snippet."""
    print("\n--- CiliumNetworkPolicy YAML ---")
    policy = CiliumNetworkPolicy(
        policy_name="api-policy",
        app_label="api",
        allowed_source_label="frontend",
        allowed_port=8000,
        allowed_http_rules=[
            {"method": "GET",  "path": "/api/.*"},
            {"method": "POST", "path": "/api/orders"},
        ],
        egress_target_label="postgres",
        egress_port=5432,
    )
    print(textwrap.indent(policy.to_yaml(), "  "))


def _demo_pyroscope_config() -> None:
    """Show a Pyroscope SDK config without actually starting the profiler."""
    print("\n--- Pyroscope SDK Config ---")
    config = PyroscopeConfig(
        app_name="acme-api",
        server_address="http://pyroscope:4040",
        sample_rate=100,
        environment="production",
        region="ap-south-1",
    )
    config_dict = config.as_dict()
    print(f"  Config: {json.dumps(config_dict, indent=4)}")
    print("  (Call config.start() inside a Linux container to activate the profiler)")


# ==========================================================================
# MAIN — self-contained demo, no external infra required
# ==========================================================================

if __name__ == "__main__":
    print("=" * 72)
    print("  eBPF Observability for Python Backends — Demo")
    print("  (runs without external infrastructure)")
    print("=" * 72)

    _demo_tool_catalogue()
    _demo_stack_recommendation()
    _demo_pxl_templates()
    _demo_pyroscope_config()
    _demo_bpftrace_dry_run()
    _demo_cilium_policy()
    _demo_falco_rules()
    _demo_cost_comparison()
    _demo_checklist()
    _demo_gotchas()

    print("\n" + "=" * 72)
    print("  Key takeaways")
    print("  ─────────────")
    print("  • eBPF runs in the kernel — sees every syscall, packet, and function.")
    print("  • Zero code changes for APM (Pixie), profiling (Pyroscope eBPF mode),")
    print("    networking (Cilium/Hubble), and security (Falco / Tetragon).")
    print("  • Self-hosted eBPF stack costs ~7× less than Datadog at scale.")
    print("  • Minimum kernel 5.4 (prefer 5.10+) and CAP_BPF / privileged pods.")
    print("  • Use bcc + Python for custom tracing when standard tools fall short.")
    print("=" * 72)
