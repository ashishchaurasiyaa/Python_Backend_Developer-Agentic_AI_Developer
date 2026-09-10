# Foundations (Year 0-2 · Zero → Senior)

> **The "assumed but required" layer.** Most curricula skip these because senior devs already know them. Included here for **true zero-to-advanced** coverage.

## What's Inside

| # | Topic | When You Need It |
|---|---|---|
| 1 | [Linux & Bash Essentials](01_linux_bash_essentials.md) | Day 1 of any backend job — SSH, logs, processes, deployment |
| 2 | [OS Concepts](02_os_concepts.md) | Understand GIL, async, OOM, containers, performance |
| 3 | [Networking Fundamentals](03_networking_fundamentals.md) | Debug slow APIs, TLS issues, DNS, CORS, connection limits |
| 4 | [Git Workflows](04_git_workflows.md) | Daily — commit, merge, rebase, conflict resolution, PRs |
| 5 | [First API in Plain English](05_first_api_in_plain_english.md) | Grasp what an API is, how HTTP request/response works, and why contracts matter — before writing a single line |
| 6 | [Environment Setup Complete](06_environment_setup_complete.md) | Stand up a professional Python dev environment — virtual envs, interpreter, editors, and toolchain — from scratch |
| 7 | [SQL Fundamentals Standalone](07_sql_fundamentals_standalone.md) | Understand relational databases, how queries execute, and why every backend role requires basic SQL fluency |
| 8 | [Postman & API Testing](08_postman_api_testing.md) | Test and debug HTTP APIs with Postman/curl before a frontend exists — essential for backend-only development cycles |
| 9 | [Reading a Legacy Codebase](09_reading_legacy_codebase.md) | Navigate and contribute to an existing codebase on day one — reading strategies, entry-point tracing, and safe modification |
| 10 | [Linux & Bash Recap Q&A](10_linux_bash_recap_qa.md) | Interview-style self-test recap of Linux/Bash — signals, redirection order, pipe chains, SSH config |
| 11 | [OS Concepts Recap Q&A](11_os_concepts_recap_qa.md) | Interview-style self-test recap of OS Concepts — GIL, virtual memory/COW, FDs, context switching, I/O models, CFS scheduler (with live-verified demo numbers) |
| 12 | [Networking Core Recap Q&A](12_networking_core_recap_qa.md) | Interview-style self-test recap of Networking basics — encapsulation, private/public IP, ports/sockets, TCP handshake, TCP vs UDP, TIME_WAIT (with live-verified demo numbers) |
| 13 | [Networking HTTP/TLS/DNS Recap Q&A](13_networking_http_tls_dns_recap_qa.md) | Interview-style self-test recap of HTTP anatomy, HTTP/1.1 vs HTTP/2, TLS handshake/certificate chain, DNS resolution (with live-verified demo numbers) |
| 14 | [Networking Advanced Recap Q&A](14_networking_advanced_recap_qa.md) | Interview-style self-test recap of connection refused/timeout, NAT/forward/reverse proxy, load balancing, CORS (real browser proof), connection pool exhaustion |
| 15 | [Git Workflows Core Recap Q&A](15_git_workflows_core_recap_qa.md) | Interview-style self-test recap of Git — 4-state model, rebase vs merge, conflict resolution, stash/cherry-pick, reset vs revert, reflog recovery (all live-verified) |
| 16 | [Git Workflows Advanced Recap Q&A](16_git_workflows_advanced_recap_qa.md) | Interview-style self-test recap of Git — branching strategies, small PRs, bisect, tags, blame, pre-commit secret-blocking hooks (all live-verified) |

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

First API     →  request/response cycle, HTTP methods, status codes,
                 REST contract, JSON payloads, client vs server roles

Env Setup     →  Python interpreter, virtual environments, pip,
                 editors/IDEs, dotfiles, linter/formatter toolchain

SQL           →  relational model, SELECT/INSERT/UPDATE/DELETE,
                 JOINs, indexes, transactions, ORM vs raw SQL trade-offs

API Testing   →  Postman collections, curl, request/response inspection,
                 auth headers, environment variables, Thunder Client

Legacy Code   →  entry-point tracing, dependency mapping, safe edits,
                 reading tests as documentation, incremental onboarding
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
