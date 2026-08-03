# Docker Storage, Networking & Registries
**DevOps Track · Phase 5: Docker**

## Quick Concepts

- **Bind mount** = maps an exact host path into the container — host owns the data, host paths hardcoded
- **Volume** = Docker-managed storage, lives under `/var/lib/docker/volumes/`, portable, backup-friendly
- **tmpfs mount** = in-memory only, never touches disk, wiped on container stop
- **Bridge network** = default isolated virtual network per host, container-to-container via NAT
- **Host network** = container shares the host's network namespace directly, no NAT (Linux only)
- **Overlay network** = virtual network spanning MULTIPLE Docker hosts, used by Swarm/multi-host setups
- **Registry** = server storing and serving images (Docker Hub, ECR, GCR, ACR, self-hosted)
- **Tag** = human-readable pointer to a specific image digest (`myapp:1.0`, `myapp:latest`)
- **Digest** = immutable content hash of an image (`sha256:abc123...`) — the real identity of an image

---

## Storage: Bind Mounts vs Volumes

### Bind Mounts

Maps a specific path on the **host** directly into the container. The host filesystem structure is exposed as-is.

```bash
docker run -v /Users/me/project:/app myapp
docker run -v $(pwd):/app myapp                 # common dev shorthand
docker run --mount type=bind,source=/Users/me/project,target=/app myapp   # explicit long form
```

```yaml
# compose
volumes:
  - ./src:/app/src            # relative host path → container path
  - ./config.yml:/app/config.yml:ro   # read-only bind mount
```

**When to use:** local development, where you want live code editing on the host to instantly reflect inside the running container (hot reload). Also useful for injecting a single config file from the host.

**Downsides:** hardcoded/relative host paths break portability across machines and CI runners; permission mismatches between host UID and container UID are a common source of "permission denied" bugs; not manageable via `docker volume` commands.

### Volumes

Docker-managed storage. You never reference a raw host path — Docker owns the location (`/var/lib/docker/volumes/<name>/_data` on Linux).

```bash
docker volume create pgdata
docker run -v pgdata:/var/lib/postgresql/data postgres:16
docker volume ls
docker volume inspect pgdata
docker volume rm pgdata
docker volume prune          # remove all unused volumes
```

**When to use:** any persistent data a container writes and needs to survive container recreation — databases, message queue state, uploaded files. This is the production-correct choice.

**Downsides:** less convenient for live-editing source code from your IDE (data lives inside Docker's managed area, not a path you naturally browse).

### Comparison

| | Bind Mount | Volume | tmpfs |
|---|---|---|---|
| Managed by | You (host path) | Docker | Docker (RAM only) |
| Survives container removal | Yes | Yes | No — gone on stop |
| Portable across hosts | No (path-dependent) | Yes (name-dependent, not path) | N/A |
| Backup tooling | Manual (`tar`, `rsync`) | `docker volume` + drivers, easy | N/A |
| Best for | Local dev hot-reload, injecting a single file | Databases, persistent app data — **production default** | Secrets you never want touching disk, scratch/cache dirs |

```bash
# tmpfs example — in-memory scratch space
docker run --tmpfs /app/cache:rw,size=64m myapp
```

---

## Networking

### Bridge (Default)

Every container gets an interface on a private virtual bridge network (`docker0` by default, or a custom bridge per Compose project). Containers on the same bridge reach each other by IP; on a **user-defined** bridge (not the default one), they also get automatic DNS resolution by container/service name.

```bash
docker network create mynet
docker run --network mynet --name api myapp
docker run --network mynet --name db postgres
# 'api' can resolve and reach 'db' by name — only works on USER-DEFINED bridges,
# NOT on the default 'bridge' network, which requires --link (legacy, avoid)
```

Port publishing (`-p host:container`) is how a bridge-networked container becomes reachable from outside the host — iptables NAT rules forward host traffic into the container's private IP.

```bash
docker run -p 8000:8000 myapp     # host:8000 → container:8000
docker run -p 127.0.0.1:8000:8000 myapp   # bind only to loopback, not all host interfaces
```

### Host

The container shares the host's network namespace entirely — no NAT, no port mapping needed, the container's ports ARE the host's ports directly.

```bash
docker run --network host myapp    # Linux only — no-op on Docker Desktop (Mac/Windows VM boundary)
```

**When to use:** performance-sensitive workloads avoiding NAT overhead, or tools that need to see the host's real network interfaces (some monitoring/network-scanning tools). **Tradeoff:** loses network isolation — the container can bind any host port directly, and port collisions with other host processes become possible.

### Overlay

A **virtual network spanning multiple Docker hosts** — containers on different physical/VM hosts communicate as if on the same LAN, using VXLAN tunneling under the hood.

```bash
docker network create -d overlay --attachable my-overlay-net
```

**Role in Swarm/multi-host setups:** Docker Swarm mode uses overlay networks to let a service's replicas — scheduled across different nodes in the swarm — talk to each other and to other services by name, regardless of which physical host they landed on. Without overlay, cross-host container communication would require manual routing/VPN setup. This is conceptually the same problem Kubernetes solves with its CNI (Container Network Interface) plugins (Calico, Flannel, Cilium) — overlay networking is Docker's native (Swarm-scoped) answer to it.

```
Single host:            Multi-host (Swarm):
┌─────────────┐         ┌──────────┐   ┌──────────┐
│ bridge net   │         │ Node A    │   │ Node B    │
│  api ── db   │         │  api-1    │   │  api-2    │
└─────────────┘         │    ↕       │   │    ↕       │
                          └────┼─────┘   └────┼─────┘
                               └───overlay───┘
                          containers reach each other by
                          service name across BOTH hosts
```

### Network Driver Comparison

| Driver | Scope | Use case |
|---|---|---|
| `bridge` | Single host | Default — most local dev and single-host containers |
| `host` | Single host | Max performance, no isolation, Linux only |
| `overlay` | Multi-host | Swarm services, cross-node container communication |
| `none` | N/A | Full network isolation — no interfaces at all |
| `macvlan` | Single host | Container gets its own MAC/IP on the physical LAN, looks like a real device |

---

## Logging Drivers — Where Container Logs Actually Go

`docker logs` works because of a **logging driver** — a pluggable mechanism deciding where stdout/stderr from the container's PID 1 actually end up. The default is rarely the right choice for production.

```bash
# The default — json-file — writes each log line as a JSON object to a
# file on the HOST, under Docker's own storage area
docker inspect myapp --format '{{.HostConfig.LogConfig.Type}}'   # json-file (default)

# Where the default driver actually writes, on the host:
# /var/lib/docker/containers/<container-id>/<container-id>-json.log
```

```
The default's real problem: json-file has NO rotation by default —
a chatty container can fill the host's disk over weeks/months with
an ever-growing log file nobody's watching, until the host runs out
of disk space entirely (and THAT failure mode looks like a completely
unrelated app outage until someone checks `df -h`).
```

```bash
# Fix rotation on the default driver — cap size and count
docker run --log-driver=json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  myapp
# keeps at most 3 files × 10MB = 30MB per container, oldest rotated out
```

```bash
# Send logs to AWS CloudWatch Logs directly from the Docker daemon —
# no separate log-shipping agent needed inside the container
docker run --log-driver=awslogs \
  --log-opt awslogs-region=ap-south-1 \
  --log-opt awslogs-group=/ecs/myapp \
  --log-opt awslogs-stream=myapp-container \
  myapp

# Send to a Fluentd collector (which then routes to ELK/Loki/wherever —
# see Phase 12) instead of writing local files at all
docker run --log-driver=fluentd \
  --log-opt fluentd-address=localhost:24224 \
  --log-opt tag=myapp.{{.Name}} \
  myapp
```

```
Common logging drivers:
  json-file  → default, local file per container, needs explicit rotation config
  local      → similar to json-file but more efficient on-disk format,
               still local-only — neither solves "logs need to leave this host"
  awslogs    → ships straight to CloudWatch Logs, AWS-native, no extra agent
  gelf       → Graylog Extended Log Format, consumed by Graylog or Logstash
  fluentd    → ships to a Fluentd collector — the Docker-level piece that
               feeds into the ELK/Loki pipelines covered in Phase 12
  none       → disables logging entirely (rare — sometimes used for
               extremely high-throughput containers where even local
               file writes are measurable overhead)
```

```yaml
# Compose — set the driver per-service rather than per docker-run invocation
services:
  api:
    image: myapp:1.0
    logging:
      driver: awslogs
      options:
        awslogs-region: ap-south-1
        awslogs-group: /ecs/myapp
```

**Why this matters day-to-day:** in a multi-host or orchestrated environment (ECS, Kubernetes), a container can be rescheduled to a DIFFERENT host at any time — local-file logging (`json-file`/`local`) means those logs are gone the moment the container moves or the host is replaced, unless something is actively shipping them elsewhere first. Configuring a centralized driver (`awslogs`, `fluentd`, `gelf`) — or, more commonly in Kubernetes, letting a node-level log-collector DaemonSet handle shipping instead of configuring this per-container — is what makes `docker logs`/`kubectl logs` actually reliable after a reschedule rather than a coin flip.

---

## Registry: Docker Hub vs Amazon ECR

| | Docker Hub | Amazon ECR |
|---|---|---|
| Hosting | Docker Inc, public cloud | AWS, per-region, per-account |
| Public images | Huge public catalog (official images: `python`, `postgres`, `nginx`) | Private by default; "ECR Public" exists separately for public sharing |
| Auth | `docker login` with Docker ID | IAM-based, short-lived tokens via AWS CLI |
| Rate limits | Anonymous pulls rate-limited (a common CI failure cause) | No Docker-Hub-style anonymous pull limits; governed by AWS IAM/quota |
| Typical use | Base images (`FROM python:3.12-slim`), open-source projects | Private application images in an AWS-centric pipeline (ECS, EKS, Lambda container images) |
| Pricing | Free public repos; paid for private repos beyond a small free tier | Pay for storage + data transfer, no per-repo listing fee |

### Docker Hub Workflow

```bash
docker login                                    # prompts for Docker ID + password/token
docker tag myapp:1.0 myusername/myapp:1.0
docker push myusername/myapp:1.0
docker pull myusername/myapp:1.0
```

### ECR Workflow

```bash
# 1. Authenticate — get a temporary token via AWS CLI, pipe straight into docker login
aws ecr get-login-password --region ap-south-1 \
  | docker login --username AWS --password-stdin 123456789012.dkr.ecr.ap-south-1.amazonaws.com

# 2. Create the repository (one-time, per image name)
aws ecr create-repository --repository-name myapp --region ap-south-1

# 3. Tag the local image with the full ECR URI
docker tag myapp:1.0 123456789012.dkr.ecr.ap-south-1.amazonaws.com/myapp:1.0

# 4. Push
docker push 123456789012.dkr.ecr.ap-south-1.amazonaws.com/myapp:1.0

# 5. Pull (e.g., from an EC2/ECS/EKS node — needs the same IAM auth step first)
docker pull 123456789012.dkr.ecr.ap-south-1.amazonaws.com/myapp:1.0
```

```
ECR image URI anatomy:
  123456789012.dkr.ecr.ap-south-1.amazonaws.com / myapp : 1.0
  └────────── registry host ──────────────────┘  └repo┘  └tag┘
   accountID   .dkr.ecr. region .amazonaws.com
```

### Senior Tip

```
The ECR auth token from `aws ecr get-login-password` expires after
12 hours. In CI/CD, re-run the login step on every pipeline run —
never bake credentials into a long-lived docker config, and never
commit an ECR password/token to source control.

Tag discipline: never rely on `:latest` in a deploy manifest. Use
immutable tags — a git SHA or semver (myapp:a1b2c3d, myapp:1.4.2) —
so a rollback means "point back at a known digest," not "guess what
:latest pointed to yesterday."
```

---

## Interview Angle

**Q: Your Postgres container's data disappeared after `docker compose down -v` — what happened, and how do you prevent it?**
`-v` removes named volumes along with containers. Named volumes (`postgres_data:/var/lib/postgresql/data`) persist across a plain `down`/`up`, but `-v` explicitly deletes them. Prevention: never use `-v` in scripts touching environments with real data; back up volumes (`docker run --rm -v pgdata:/data -v $(pwd):/backup alpine tar czf /backup/pgdata.tar.gz /data`) before any destructive operation.

**Q: Why does `--network host` do nothing useful on Docker Desktop for Mac?**
Docker Desktop runs containers inside a Linux VM. The "host" whose network namespace you'd be joining is the VM, not macOS itself — so host networking there doesn't expose ports on your actual Mac the way it does on native Linux. This is one of the concrete gaps between Docker Desktop and Docker Engine covered in the basics file.

**Q: Why would you choose ECR over Docker Hub for a production AWS deployment?**
IAM-native auth (no separate registry credentials to rotate/leak), no anonymous-pull rate limiting that can randomly break CI, private-by-default repos, and lower latency pulling into EC2/ECS/EKS within the same AWS region. Docker Hub remains the right place to pull public base images from.

**Q: A host running several long-lived containers suddenly runs out of disk space, seemingly unrelated to anything the containers actually do. What's a common overlooked cause, and how do you prevent it?**
The default `json-file` logging driver has no log rotation configured out of the box — a chatty container can grow its log file unbounded over weeks until the host's disk fills up, and the resulting failure looks like an unrelated app outage until someone checks `df -h`. Prevention: set `--log-opt max-size` and `max-file` (or switch to a centralized driver like `awslogs`/`fluentd` that ships logs off the host entirely, so local disk was never the durable copy to begin with).

---

## Related

- [`../12_Logging/01_elk_loki_fluentd.md`](../12_Logging/01_elk_loki_fluentd.md) — what happens to logs once the `fluentd`/`gelf` driver ships them off the host
- [`../11_Monitoring/01_prometheus_grafana_alertmanager.md`](../11_Monitoring/01_prometheus_grafana_alertmanager.md) — alerting on disk usage before an unrotated log file fills the host
- [`01_docker_basics.md`](01_docker_basics.md) — the cgroup/resource-limit mechanics underlying this file's storage and networking behavior
