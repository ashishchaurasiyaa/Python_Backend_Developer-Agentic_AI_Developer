# Design Online Code Editor / Replit / CodeSandbox

---

## 1. Requirements

### Functional
- Browser-based IDE with syntax highlighting, autocomplete.
- File tree per project (create/edit/delete files).
- Run code in sandboxed environment (Python, Node, Go, etc.).
- Real-time collaboration (multiple users edit same file).
- Persistent projects (save state across sessions).
- Public/private projects, sharing.
- Live preview for web projects.
- Package installation (pip, npm).
- Custom domains for deployed apps (premium).

### Non-Functional
- 10M users, 1M MAU.
- 100K concurrent users with running sandboxes.
- Code execution latency < 500ms cold start, < 50ms warm.
- File save latency < 100ms.
- 99.9% availability.

---

## 2. Scale Estimation

| Metric | Number |
|---|---|
| Concurrent sandboxes | 100K |
| RAM per sandbox | 256 MB-1 GB |
| Total sandbox RAM needed | 50-100 TB |
| Active editors (just typing, no run) | 500K |
| Files stored | 50M projects × 30 files × 5 KB | 7.5 TB |
| Sessions/sec | 5K |

---

## 3. High-Level Architecture

```
                ┌──────────────┐
                │ Browser (IDE)│
                └──────┬───────┘
                       │
              ┌────────▼─────────┐
              │  API Gateway      │
              └────────┬─────────┘
                       │
   ┌─────────┬─────────┼─────────┬──────────┬─────────┐
   │         │         │         │          │         │
┌──▼───┐ ┌───▼────┐ ┌──▼──────┐ ┌▼─────────┐ ┌▼──────┐ ┌─▼────┐
│Auth  │ │Project │ │File     │ │Container │ │Collab │ │ LSP   │
│Svc   │ │Svc     │ │Svc      │ │Manager   │ │(CRDT) │ │ Svc   │
└──────┘ └────┬───┘ └────┬────┘ └─────┬────┘ └───┬───┘ └──────┘
              │         │             │          │
       ┌──────▼─────────▼──┐    ┌─────▼──────┐  ┌▼─────┐
       │  Postgres + S3   │    │ Kubernetes │  │ Redis │
       │  (metadata+files)│    │ (sandboxes)│  │(state)│
       └──────────────────┘    └────────────┘  └──────┘
```

---

## 4. Sandbox Execution (Critical)

### Security requirements
- Isolated from host.
- No access to other users' code.
- No internet access (except whitelisted endpoints).
- Resource limits (CPU, RAM, disk, network).
- Time limits.

### Options

| Tech | Isolation | Cold start | Density |
|---|---|---|---|
| Docker container | OK (cgroup, namespace) | 1-2s | 100/node |
| gVisor (Google) | Strong (userspace kernel) | 1-2s | 80/node |
| Firecracker (AWS) | Strong (microVM) | 100-250ms | 50/node |
| WebAssembly | Strongest (sandboxed runtime) | 10-50ms | 1000/node |
| Kata Containers | Strong (lightweight VM) | 1s | 60/node |

**Replit uses Nix + Firecracker microVMs.** CodeSandbox started with containers, moved to browser-based WebContainers (Node in WASM).

### Sandbox lifecycle
```python
class SandboxManager:
    async def get_or_create(self, project_id: str) -> Sandbox:
        # Check if warm pool has a free sandbox
        sandbox = await self.warm_pool.acquire(project_id)
        if not sandbox:
            sandbox = await self.spawn_new(project_id)

        # Mount project files (from S3 or persistent volume)
        await sandbox.mount(project_id)

        # Set resource limits
        await sandbox.set_limits(cpu=0.5, mem_mb=512, time_sec=300)

        return sandbox

    async def shutdown_idle(self):
        for sandbox in self.sandboxes:
            if sandbox.idle_time > 30 * 60:   # 30 min idle
                await sandbox.snapshot()
                await sandbox.stop()
```

### Warm pool
Pre-spawn N sandboxes per language. Cold start hidden.

---

## 5. File System

### Option A: Sync to S3 on save
- Each save → write to S3 + DB metadata update.
- Sandbox mounts via FUSE → S3.
- Pros: cheap, scalable. Cons: latency on every read.

### Option B: Persistent volume per project (Replit's approach)
- EBS volume mounted to sandbox.
- Survives across sessions.
- Snapshot for cold storage.
- Pros: fast IO. Cons: expensive, ops complex.

### Option C: In-memory + periodic snapshot (CodeSandbox v1)
- Files in browser memory + server cache.
- Save to S3 every N seconds.
- Pros: low latency. Cons: data loss on crash.

```sql
CREATE TABLE projects (
    id          UUID PRIMARY KEY,
    owner_id    UUID,
    name        TEXT,
    language    TEXT,
    visibility  TEXT,
    storage_path TEXT,         -- S3 prefix or EBS volume ID
    created_at  TIMESTAMPTZ,
    last_active TIMESTAMPTZ
);

CREATE TABLE project_files (
    project_id  UUID,
    path        TEXT,           -- /src/main.py
    size_bytes  INT,
    checksum    TEXT,
    storage_key TEXT,           -- S3 key
    updated_at  TIMESTAMPTZ,
    PRIMARY KEY (project_id, path)
);
```

---

## 6. Real-Time Collaboration (CRDT)

Multiple users editing same file. Two approaches:

### OT (Operational Transformation) — Google Docs style
- Each edit = operation (insert "x" at pos 5).
- Server transforms ops based on others' concurrent ops.
- Complex, requires server arbitration.

### CRDT (Conflict-free Replicated Data Type) — modern preferred
- Each character has a unique global ID.
- Edits commute — any ordering produces same result.
- Peer-to-peer possible, no central server needed.
- Yjs, Automerge are popular libraries.

```javascript
// Browser
const ydoc = new Y.Doc();
const ytext = ydoc.getText('code');

ytext.observe(event => {
  editor.applyChanges(event.changes);
});

// On user edit
ytext.insert(position, "hello");

// Sync via WebSocket
const provider = new WebsocketProvider("wss://ws.example.com", projectId, ydoc);
```

### Server architecture
- WebSocket service brokers CRDT updates.
- Stateless: each WS server just relays to others in same room.
- Persistence: periodically snapshot CRDT state to S3.
- Awareness: cursors + selections of other users.

```python
class CRDTRoom:
    def __init__(self, room_id):
        self.room_id = room_id
        self.clients: set[WebSocket] = set()

    async def broadcast(self, msg, sender):
        for client in self.clients:
            if client != sender:
                await client.send(msg)

@app.websocket("/ws/collab/{project_id}/{file_path}")
async def collab(ws, project_id, file_path):
    room = get_or_create_room(f"{project_id}:{file_path}")
    room.clients.add(ws)
    try:
        async for msg in ws.iter_bytes():
            await room.broadcast(msg, sender=ws)
    finally:
        room.clients.discard(ws)
```

---

## 7. Language Server Protocol (LSP)

For autocomplete, hover info, go-to-def, linting.

### Architecture
```
Browser (Monaco editor) ──WS──► API Gateway ──► LSP Service
                                                    │
                                                    ▼
                                              Language Server
                                              (pyright, gopls, ...)
                                              (containerized)
```

LSP server per project (or per language workspace), tracking open files.

```python
class LSPSession:
    async def init(self, project_id, language):
        self.container = await spawn_container(f"lsp-{language}")
        await self.container.exec(f"pyright --pythonpath /workspace")
        await self.send_init({"workspaceFolders": ["/workspace"]})

    async def request_completion(self, file, line, char):
        return await self.send_request("textDocument/completion", {
            "textDocument": {"uri": file},
            "position": {"line": line, "character": char}
        })
```

---

## 8. Live Preview (Web Projects)

User types HTML/JS → preview updates live.

### Approach
- Sandbox runs a dev server (e.g., `npm run dev`).
- Dev server exposed via reverse proxy.
- Each project gets subdomain: `proj-abc123.user-projects.com`.
- Reverse proxy maps subdomain → sandbox.

```nginx
# Nginx config
server {
    server_name *.user-projects.com;
    location / {
        proxy_pass http://sandbox-{$subdomain};
    }
}
```

### Hot reload
- File change → save → WebSocket notifies sandbox → dev server (Vite/Webpack) hot-reloads.

---

## 9. Container Orchestration

Kubernetes for sandbox containers.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: sandbox-{project_id}
spec:
  containers:
  - name: runner
    image: replit-runner:python-3.11
    resources:
      limits:
        cpu: 500m
        memory: 512Mi
      requests:
        cpu: 100m
        memory: 128Mi
    volumeMounts:
    - name: project-vol
      mountPath: /workspace
  volumes:
  - name: project-vol
    persistentVolumeClaim:
      claimName: pvc-{project_id}
  securityContext:
    runAsNonRoot: true
    readOnlyRootFilesystem: true
    seccompProfile:
      type: RuntimeDefault
    capabilities:
      drop:
        - ALL
```

### Node packing
- Each k8s node hosts ~50-100 sandboxes.
- Auto-scale: scale-up when pool < 20% free.

### Spot instances
- Use spot for cost savings.
- Pre-empted sandboxes drained gracefully (save state, kick user to wait queue).

---

## 10. Package Management

User runs `pip install requests`.

### Naive: install inside sandbox
- Each `pip install` downloads from PyPI → slow + outbound bandwidth.

### Optimized: cached registry
- Internal PyPI mirror (devpi / pypi-server).
- Sandbox configured: `pip install -i https://internal-mirror`.
- Mirror caches popular packages.

### Pre-installed
- Common packages baked into base image (`numpy`, `pandas`, `requests`).
- Saves cold start time.

---

## 11. Persistence Strategy

### On stop (user closes tab)
- Sandbox marked idle.
- After 30 min idle → snapshot to S3.
- Container destroyed.

### On resume (user opens project again)
- Restore from snapshot → mount EBS → start container.
- Cold start: 3-5s for restore + container boot.

### Snapshotting
Snapshot includes:
- File system state (project + node_modules).
- Process state (optional, complex).
- Open terminal sessions.

CRIU (Checkpoint/Restore in Userspace) for process state.

---

## 12. Sharing & Visibility

### Public projects
- Anyone with URL can view (read-only).
- Optional: "fork" — clone into viewer's account.

### Private
- Only owner.
- Add collaborators by email/username.

### Permissions model
```sql
CREATE TABLE project_collaborators (
    project_id UUID,
    user_id    UUID,
    role       TEXT,    -- 'owner', 'editor', 'viewer'
    invited_at TIMESTAMPTZ,
    PRIMARY KEY (project_id, user_id)
);
```

Check on every request.

---

## 13. Networking & Security

### Outbound traffic
- Default: no internet from sandbox.
- Whitelist: pip/npm registry, common APIs.
- Premium: full internet.

### Inbound traffic (preview)
- Each sandbox gets unique URL.
- Routed via reverse proxy.
- Auth check: is requester project owner or public?

### Resource isolation
- cgroup CPU and memory limits.
- network namespace per sandbox.
- file descriptor limits.

### Abuse detection
- Sandbox running for > 24h continuously → flagged.
- High CPU + outbound → maybe crypto mining → kill.
- Spam DNS lookups → kill.
- ML model on workload patterns.

---

## 14. Long-Running Apps (Always-On)

Premium feature: project keeps running 24/7 even when user offline.

### Implementation
- "Always-on" flag on project.
- Sandbox not torn down on idle.
- Health checks keep it alive.
- Auto-restart on crash.

Cost passed to user.

---

## 15. APIs

```
POST /projects                              # create
GET  /projects/{id}                         # metadata
GET  /projects/{id}/files                    # tree
GET  /projects/{id}/files/{path:path}        # file content
PUT  /projects/{id}/files/{path:path}        # save file
POST /projects/{id}/run    { command }      # exec in sandbox
POST /projects/{id}/install { package }      # install dep
POST /projects/{id}/fork                     # clone
WS   /ws/sandbox/{project_id}                # terminal
WS   /ws/collab/{project_id}/{file_path}     # CRDT sync
WS   /ws/lsp/{project_id}                    # autocomplete
```

---

## 16. Edge Cases

### User opens 100 projects
- Limit: 1 active sandbox per user free tier, 5 for paid.
- Excess: closed/swapped.

### Fork bomb / infinite loop
- CPU limit enforced via cgroup.
- Timeout per execution (5 min for free tier).
- Auto-kill on resource exhaustion.

### Browser tab closed mid-edit
- Last edit may not have been saved.
- CRDT mitigates: changes synced via WS in real-time.
- Auto-save every 5s as backup.

### Mid-edit conflict (offline + reconnect)
- CRDT resolves automatically.
- For non-collaborative: user picks "keep local" or "keep server".

---

## 17. Trade-offs

| Decision | Trade-off |
|---|---|
| Firecracker microVMs | Strong isolation, higher resource per sandbox |
| Persistent volumes | Fast IO, ops complex, expensive |
| CRDT over OT | Decentralized, but new dev complexity |
| K8s for orchestration | Mature, learning curve, overhead |
| Pre-warmed pool | Lower cold start, idle resource cost |

---

## 18. Follow-up Questions

- **"How do you support 100 languages?"** → Base images per language. Polyglot projects detect via project config.
- **"How would you implement git integration?"** → Use isomorphic-git in browser or git CLI in sandbox. Connect to GitHub via OAuth.
- **"What about GPU support?"** → Premium feature, NVIDIA GPUs in dedicated nodes, scheduler routes GPU projects to them.
- **"Real-time collab on whiteboard / drawings?"** → Same CRDT primitives, different data type (geometric shapes).
- **"How to handle a viral project?"** → Replicate the snapshot, route fork requests to read-only replicas. Original owner keeps writable.
- **"Why not just use browser WASM (CodeSandbox v2)?"** → Faster cold start, no server cost for compute, but limited to languages with WASM ports (Node, Python via Pyodide).
