# Kubernetes Storage, ConfigMaps & Secrets
**DevOps Track · Phase 6: Kubernetes**

## Quick Concepts

- **PersistentVolume (PV)** = a cluster-level piece of actual storage (disk, NFS share, cloud volume) provisioned and ready to use
- **PersistentVolumeClaim (PVC)** = a Pod's REQUEST for storage — "I need 10Gi, ReadWriteOnce" — gets matched/bound to a PV
- **StorageClass** = a template describing HOW to dynamically provision a PV on demand (which backend, which disk type)
- **Dynamic provisioning** = PVC triggers automatic PV creation via a StorageClass, instead of an admin pre-creating PVs by hand
- **ConfigMap** = non-sensitive key-value configuration, injectable as env vars or mounted files
- **Secret** = same shape as ConfigMap, meant for sensitive data — base64-ENCODED, NOT encrypted, by default
- **AccessMode** = how many nodes/Pods can mount a volume simultaneously (RWO, ROX, RWX)

---

## Why This Matters

```
Pods are ephemeral and their local filesystem dies with them. Any
data that must survive a Pod restart (databases, uploaded files,
generated reports) needs a layer of abstraction between "what a Pod
asks for" and "what physical storage actually backs it" — that's the
PV/PVC/StorageClass chain.

ConfigMap vs Secret is a common interview trap: Secrets are base64
ENCODED, not encrypted. Anyone with `kubectl get secret -o yaml`
access (or etcd access, if etcd isn't encrypted at rest) can trivially
decode them. Real secret protection needs RBAC + etcd encryption at
rest, or an external secrets manager.
```

---

## Storage: PV, PVC, StorageClass

### The Relationship

```
   StorageClass                PersistentVolumeClaim         PersistentVolume
   "HOW to provision"    ◄───   "I need 10Gi RWO"      ───►  "here is 10Gi, actually
   (which backend/disk         (Pod-facing request,           backed by an AWS EBS /
    type to use)                 namespaced)                  GCE PD / NFS share)
        │                              │                              │
        │  triggers dynamic            │  bound to                    │  consumed by
        │  provisioning of ─────────►  │  ◄─────────────────────────  │
        ▼                              ▼                              ▼
                                    Pod's volumeMounts reference the PVC by name
```

- A **PV** is cluster-scoped — it exists independently of any namespace, admin-managed (or dynamically created).
- A **PVC** is namespace-scoped — it's what a Pod's spec actually references.
- A **StorageClass** is what makes PVs appear automatically instead of an admin pre-creating them.

### StorageClass (Dynamic Provisioning)

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: ebs.csi.aws.com          # cloud-specific CSI driver
parameters:
  type: gp3
  iops: "3000"
reclaimPolicy: Retain                  # what happens to the PV when PVC is deleted
volumeBindingMode: WaitForFirstConsumer  # delay binding until a Pod actually needs it
                                          # (lets the scheduler pick a zone-appropriate PV)
```

### PersistentVolumeClaim

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
spec:
  storageClassName: fast-ssd
  accessModes:
    - ReadWriteOnce         # RWO: one node can mount read-write
  resources:
    requests:
      storage: 20Gi
```

```
AccessModes:
  ReadWriteOnce (RWO)  — one node, read-write (typical for block storage: EBS, GCE PD)
  ReadOnlyMany  (ROX)  — many nodes, read-only
  ReadWriteMany (RWX)  — many nodes, read-write (needs NFS, EFS, CephFS — not plain block storage)
```

### Consuming the PVC in a Pod

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  serviceName: postgres-headless
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: postgres-pvc
```

For StatefulSets with multiple replicas, `volumeClaimTemplates` (see the architecture/objects file) generates one PVC per Pod ordinal automatically — you rarely hand-write per-replica PVCs.

### Static Provisioning (Manually Pre-Created PV — Less Common Today)

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-manual-nfs
spec:
  capacity:
    storage: 50Gi
  accessModes:
    - ReadWriteMany
  nfs:
    server: nfs.internal.example.com
    path: /exports/shared-data
  persistentVolumeReclaimPolicy: Retain
```

```bash
kubectl get pv
kubectl get pvc
kubectl get storageclass
kubectl describe pvc postgres-pvc     # shows Bound/Pending status and events
```

---

## ConfigMap

Non-sensitive configuration, decoupled from the container image so the same image can run in dev/staging/prod with different config.

### Create via kubectl

```bash
kubectl create configmap app-config \
  --from-literal=LOG_LEVEL=info \
  --from-literal=FEATURE_X_ENABLED=true

kubectl create configmap app-config-file --from-file=app.properties
```

### Create via YAML

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  LOG_LEVEL: "info"
  FEATURE_X_ENABLED: "true"
  app.properties: |
    max_connections=100
    timeout=30
```

---

## Secret

Same shape as ConfigMap, meant for sensitive values — but **base64 is encoding, not encryption**. Anyone who can read the Secret object (via RBAC, or via raw etcd access if etcd isn't encrypted at rest) can trivially decode it with `base64 -d`.

### Create via kubectl (Recommended — Avoids Manual base64)

```bash
kubectl create secret generic db-credentials \
  --from-literal=DB_USER=app \
  --from-literal=DB_PASSWORD='S3cur3P@ss'

kubectl create secret generic tls-cert \
  --from-file=tls.crt=./cert.pem \
  --from-file=tls.key=./key.pem

kubectl create secret docker-registry ecr-pull-secret \
  --docker-server=123456789012.dkr.ecr.ap-south-1.amazonaws.com \
  --docker-username=AWS \
  --docker-password="$(aws ecr get-login-password)"
```

### Create via YAML (You Base64-Encode Manually — Error-Prone)

```bash
echo -n 'app' | base64        # YXBw
echo -n 'S3cur3P@ss' | base64 # UzNjdXIzUEBzcw==
```

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
data:
  DB_USER: YXBw
  DB_PASSWORD: UzNjdXIzUEBzcw==
```

```yaml
# stringData — plaintext in the manifest, Kubernetes base64-encodes it for you
# on creation (convenient, but the plaintext still ends up in git if you commit
# this file — same caveat as any secret checked into version control)
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
stringData:
  DB_USER: app
  DB_PASSWORD: S3cur3P@ss
```

### The Base64 Caveat — Explicitly

```
Secret.data values are base64-ENCODED, not encrypted.

  kubectl get secret db-credentials -o jsonpath='{.data.DB_PASSWORD}' | base64 -d
  → S3cur3P@ss   (trivially recovered by anyone with 'get secrets' RBAC)

Real protection requires layering on top of Secrets, not relying on
base64 itself:
  - RBAC restricting WHO can `get`/`list` Secret objects
  - etcd encryption at rest (EncryptionConfiguration) — otherwise
    Secrets sit as near-plaintext in etcd's data files
  - External secret managers (AWS Secrets Manager, HashiCorp Vault,
    External Secrets Operator) syncing INTO K8s Secrets, keeping the
    real source of truth outside the cluster
  - Sealed Secrets / SOPS for safely committing encrypted secrets to git
```

---

## Mounting: Environment Variables vs Volumes

### As Environment Variables

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: api-pod
spec:
  containers:
    - name: api
      image: myrepo/api:1.4.2
      envFrom:
        - configMapRef:
            name: app-config          # every key becomes an env var
        - secretRef:
            name: db-credentials
      env:
        - name: SPECIFIC_KEY          # or reference just one key
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: LOG_LEVEL
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: DB_PASSWORD
```

### As Mounted Volumes (Files)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: api-pod
spec:
  containers:
    - name: api
      image: myrepo/api:1.4.2
      volumeMounts:
        - name: config-vol
          mountPath: /etc/config       # each key becomes a FILE in this dir
          readOnly: true
        - name: secret-vol
          mountPath: /etc/secrets
          readOnly: true
  volumes:
    - name: config-vol
      configMap:
        name: app-config
    - name: secret-vol
      secret:
        secretName: db-credentials
```

### Env Vars vs Volume Mounts — When to Use Which

| | Env Vars | Volume Mount |
|---|---|---|
| Update propagation | Requires Pod restart to pick up changes | File content updates live (kubelet syncs periodically) without a restart — app must re-read the file though |
| Visibility | Shows in `kubectl describe pod`, process environment (readable by anything in the container, and via `/proc/<pid>/environ`) | Only readable by something that opens the file path |
| Best for | Simple flags, small values (LOG_LEVEL, feature toggles) | Larger config blobs, TLS certs/keys, anything you want live-reloadable |
| Secret-specific risk | Env vars are more likely to leak into crash dumps, logs, `kubectl exec env` | Slightly better hygiene, but still plaintext-on-disk inside the container's filesystem view |

### Senior Tip

```
Prefer mounting Secrets as volumes over env vars where the app
supports reading from a file — it reduces accidental leakage through
crash reporters/logging libraries that dump the process environment,
and it allows rotation without a Pod restart if the app watches the
file for changes (many secret-rotation sidecars rely on exactly this).
```

---

## Interview Angle

**Q: A Secret is "encrypted," right?**
No — by default a Kubernetes Secret is base64-ENCODED, which is trivially reversible, not encrypted. Real protection comes from RBAC on who can read Secret objects, enabling etcd encryption at rest, and/or using an external secrets manager that syncs values in rather than storing the real secret natively in the cluster.

**Q: Why does a StatefulSet use `volumeClaimTemplates` instead of a single shared PVC?**
Each StatefulSet replica needs its OWN distinct, stable storage — `db-0` and `db-1` must never share the same disk. `volumeClaimTemplates` generates one PVC per Pod ordinal automatically, so each replica gets bound to its own PV and keeps that same PV across reschedules.

**Q: What does `volumeBindingMode: WaitForFirstConsumer` on a StorageClass actually solve?**
Without it, a PVC can get dynamically bound to a PV in the wrong availability zone before the scheduler has decided which node/zone the Pod will actually run in — causing a Pod stuck Pending because it can't be scheduled where its volume lives. `WaitForFirstConsumer` delays PV provisioning until a Pod referencing the PVC is actually being scheduled, so the volume is created in a zone the scheduler can reach.
