# Foundations (Year 0-2 · Zero → Senior)

> **The "assumed but required" layer.** Most curricula skip these because senior devs already know them. Included here for **true zero-to-advanced** coverage.

## What's Inside

| # | Topic | When You Need It |
|---|---|---|
| 1 | [Linux & Bash Essentials](01_linux_bash_essentials.md) | Day 1 of any backend job — SSH, logs, processes, deployment |
| 2 | [OS Concepts](02_os_concepts.md) | Understand GIL, async, OOM, containers, performance |
| 3 | [Networking Fundamentals](03_networking_fundamentals.md) | Debug slow APIs, TLS issues, DNS, CORS, connection limits |
| 4 | [Git Workflows](04_git_workflows.md) | Daily — commit, merge, rebase, conflict resolution, PRs |

## Why This Phase Exists

```
Without foundations:
   ✗ You can use FastAPI without understanding TCP
   ✗ You can use asyncio without understanding epoll
   ✗ You can use git without understanding rebase
   → But you can't DEBUG when things break in production

These docs aren't theory for theory's sake.
They're "things you call OS / shell / network 50x/day."
```

## Coverage Density

```
Linux/Bash    →  filesystem, processes, permissions, scripting,
                 SSH, systemd, daily one-liners

OS Concepts   →  process vs thread, virtual memory, syscalls,
                 file descriptors, scheduling, IPC, containers,
                 OOM, NUMA

Networking    →  OSI model, TCP/UDP, HTTP/1.1/2/3, TLS, DNS,
                 sockets, NAT, proxies, CORS, debugging tools

Git           →  daily commands, branching strategies, rebase vs merge,
                 conflicts, hooks, recovery, GitHub workflows
```

## Senior-Level Coverage Note

For a 5-year experienced senior, these are likely already known from job experience. The docs serve as:

- **Quick refresher** before interviews
- **Reference** during debugging
- **Sanity check** for assumed knowledge gaps
- **Onboarding** material for junior team members

## Related

- After Foundations: jump to [Python Daily](../02_Python_Daily) or [Python Advanced](../../01_Year3-4_Mid/01_Python_Advanced)
- For practical use: [DevOps](../../01_Year3-4_Mid/04_DevOps) builds on Linux/networking
- For deeper theory: [System Design HLD Theory](../../02_Year5+_Senior/01_System_Design/HLD_Theory)
