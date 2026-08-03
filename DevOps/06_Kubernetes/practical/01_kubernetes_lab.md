# Kubernetes — Hands-On Lab
**DevOps Track · Phase 6 Practical**

## Prerequisites

You need a real cluster — reading YAML without applying it doesn't build the debugging instinct this phase is about. All options below are free:

- **minikube** (recommended for these labs — closest to a "real" cluster, supports LoadBalancer/Ingress add-ons): `brew install minikube` (macOS) or see minikube.sigs.k8s.io. Start with `minikube start`.
- **kind** (Kubernetes-in-Docker, very fast, good if you already have Docker running): `brew install kind`, then `kind create cluster`.
- **Docker Desktop's built-in Kubernetes** (toggle in settings) — single-node, works fine for Labs 1-3.
- **No local install at all**: [Killercoda's Kubernetes playground](https://killercoda.com/kubernetes) gives you a free, disposable multi-node cluster in the browser — good if you don't want to install anything.
- `kubectl` installed locally (`brew install kubectl`, or it comes bundled with minikube/kind setups). Verify with `kubectl version --client` and `kubectl get nodes`.
- `helm` installed for the optional Helm portion of Lab 3 (`brew install helm`) — not required for Labs 1, 2, 4.

Work in a dedicated namespace so you can nuke it and start clean: `kubectl create namespace k8s-lab && kubectl config set-context --current --namespace=k8s-lab`.

---

## Lab 1: Deployments, Services, and Rolling Updates

**Objective:** Deploy something real, expose it, and prove a zero-downtime rolling update actually behaves the way the lesson describes.

**Task:**
1. Write a Deployment manifest for `nginx:1.25` with 3 replicas, resource requests/limits set, and a label `app: web-lab`.
2. Apply it, confirm 3 Pods come up and are `Running` with `kubectl get pods -l app=web-lab`.
3. Write a `ClusterIP` Service selecting `app: web-lab` on port 80. Confirm it has assigned endpoints matching your 3 Pod IPs (`kubectl get endpoints`).
4. Reach the service from INSIDE the cluster (not your host) — run a throwaway debug pod (`kubectl run tmp-curl --image=curlimages/curl --rm -it -- sh`) and curl the service by its DNS name.
5. Trigger a rolling update: change the image to `nginx:1.27` and apply. While it's rolling, watch `kubectl rollout status deployment/<name>` and `kubectl get pods -w` in a second terminal — confirm you never see fewer than 3 Ready pods at once (matching `maxUnavailable: 0` if you set it).
6. Deliberately roll out a BROKEN image (a typo'd tag that doesn't exist, e.g. `nginx:does-not-exist`), watch it fail to progress, then roll back with `kubectl rollout undo` and confirm the working version returns.

<details>
<summary>Solution / walkthrough</summary>

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-lab
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: web-lab
  template:
    metadata:
      labels:
        app: web-lab
    spec:
      containers:
        - name: nginx
          image: nginx:1.25
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: "50m"
              memory: "64Mi"
            limits:
              cpu: "200m"
              memory: "128Mi"
```

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: web-lab-svc
spec:
  selector:
    app: web-lab
  ports:
    - port: 80
      targetPort: 80
```

```bash
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml

kubectl get pods -l app=web-lab
# 3 pods, STATUS Running

kubectl get endpoints web-lab-svc
# NAME          ENDPOINTS
# web-lab-svc   10.244.0.5:80,10.244.0.6:80,10.244.0.7:80   <- 3, matching pod IPs

# 4. Reach it from inside the cluster
kubectl run tmp-curl --image=curlimages/curl --rm -it --restart=Never -- \
  curl -s http://web-lab-svc.k8s-lab.svc.cluster.local
# <html>...nginx welcome page HTML...</html>
# (short form also works inside the same namespace: curl http://web-lab-svc)

# 5. Rolling update, watch it stay available
kubectl set image deployment/web-lab nginx=nginx:1.27
kubectl rollout status deployment/web-lab
# Waiting for deployment "web-lab" rollout to finish: 1 out of 3 new
# replicas have been updated...
# ...
# deployment "web-lab" successfully rolled out

# in a second terminal during the rollout:
kubectl get pods -l app=web-lab -w
# watch READY counts — with maxUnavailable: 0 you should never see
# fewer than 3 pods in Ready state at any point, only MORE briefly
# (up to 4, from maxSurge: 1) as new ones come up before old ones go down

# 6. Broken rollout + rollback
kubectl set image deployment/web-lab nginx=nginx:does-not-exist
kubectl rollout status deployment/web-lab --timeout=30s
# error: deployment "web-lab" exceeded its progress deadline (or times out)
kubectl get pods -l app=web-lab
# one pod stuck in ImagePullBackOff / ErrImagePull — the OLD pods are
# still running and serving traffic, because Kubernetes never removes
# healthy old replicas until new ones are confirmed Ready

kubectl rollout undo deployment/web-lab
kubectl rollout status deployment/web-lab
# rolls back to nginx:1.27 (the last successful revision), confirms
# successfully rolled out
kubectl rollout history deployment/web-lab
```
</details>

---

## Lab 2: ConfigMaps, Secrets, and a StatefulSet With Real Persistence

**Objective:** Wire config/secrets into a Pod both ways (env vars and mounted files), and prove a StatefulSet's storage really does survive Pod deletion — the property that makes it different from a Deployment.

**Task:**
1. Create a ConfigMap with at least 2 key-value pairs, and a Secret with 1 sensitive value (use `kubectl create secret generic ... --from-literal`, not hand-written base64).
2. Deploy a simple Pod that consumes the ConfigMap as environment variables (`envFrom`) AND the Secret as a mounted volume file (not env var this time — mix both patterns).
3. Exec into the Pod, confirm the ConfigMap values show up via `env`, and confirm the Secret's value is readable as a FILE under the mount path, not as an env var.
4. Decode the Secret from `kubectl get secret ... -o yaml` yourself using `base64 -d`, and in your own words explain to yourself why this proves "Secrets are encoded, not encrypted."
5. Deploy a single-replica StatefulSet with a `volumeClaimTemplates` block (any tiny image + a PVC is enough — you don't need a real database). Write a file into the Pod's mounted volume.
6. Delete the Pod (`kubectl delete pod <statefulset-pod-name>`, NOT the StatefulSet itself) and watch Kubernetes recreate it with the SAME name (`<name>-0`). Confirm the file you wrote is still there — proving the PVC survived and was reattached.
7. Compare: do the same delete-and-recreate test against one of your Lab 1 Deployment's Pods and confirm it gets a NEW random-suffix name each time (no stable identity, by design).

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. ConfigMap + Secret
kubectl create configmap app-config \
  --from-literal=LOG_LEVEL=debug \
  --from-literal=FEATURE_X=enabled

kubectl create secret generic app-secret \
  --from-literal=API_KEY='sk-lab-1234567890'
```

```yaml
# config-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: config-test-pod
spec:
  containers:
    - name: app
      image: busybox
      command: ["sleep", "3600"]
      envFrom:
        - configMapRef:
            name: app-config
      volumeMounts:
        - name: secret-vol
          mountPath: /etc/secrets
          readOnly: true
  volumes:
    - name: secret-vol
      secret:
        secretName: app-secret
```

```bash
kubectl apply -f config-pod.yaml
kubectl wait --for=condition=Ready pod/config-test-pod

# 3. Confirm both delivery mechanisms
kubectl exec config-test-pod -- env | grep -E "LOG_LEVEL|FEATURE_X"
# LOG_LEVEL=debug
# FEATURE_X=enabled

kubectl exec config-test-pod -- cat /etc/secrets/API_KEY
# sk-lab-1234567890
kubectl exec config-test-pod -- env | grep API_KEY
# (nothing — the secret was mounted as a FILE, not injected as an env var,
# exactly as configured)

# 4. Prove base64 != encryption
kubectl get secret app-secret -o jsonpath='{.data.API_KEY}'
# c2stbGFiLTEyMzQ1Njc4OTA=
echo 'c2stbGFiLTEyMzQ1Njc4OTA=' | base64 -d
# sk-lab-1234567890
# — trivially recovered with a single, unauthenticated decode. Anyone
# with `kubectl get secret` RBAC access (or raw etcd access) can do
# this same one-liner — it is NOT encryption, it's encoding, exactly
# as the lesson states.
```

```yaml
# statefulset.yaml
apiVersion: apps/v1
kind: Service
metadata:
  name: lab-headless
spec:
  clusterIP: None
  selector:
    app: lab-sts
  ports:
    - port: 80
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: lab-sts
spec:
  serviceName: lab-headless
  replicas: 1
  selector:
    matchLabels:
      app: lab-sts
  template:
    metadata:
      labels:
        app: lab-sts
    spec:
      containers:
        - name: app
          image: busybox
          command: ["sleep", "3600"]
          volumeMounts:
            - name: data
              mountPath: /data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 1Gi
```

```bash
kubectl apply -f statefulset.yaml
kubectl wait --for=condition=Ready pod/lab-sts-0

kubectl exec lab-sts-0 -- sh -c 'echo "this should survive pod deletion" > /data/proof.txt'
kubectl exec lab-sts-0 -- cat /data/proof.txt

# 6. Delete the POD, not the StatefulSet
kubectl delete pod lab-sts-0
kubectl get pods -w   # watch it come back — SAME name, lab-sts-0
kubectl wait --for=condition=Ready pod/lab-sts-0
kubectl exec lab-sts-0 -- cat /data/proof.txt
# this should survive pod deletion    <- SAME PVC reattached, data intact

# 7. Contrast with the Deployment from Lab 1
kubectl get pods -l app=web-lab
# web-lab-7f9c8d6b5-x2j4k
kubectl delete pod web-lab-7f9c8d6b5-x2j4k   # use an actual pod name from your output
kubectl get pods -l app=web-lab
# web-lab-7f9c8d6b5-q8m2p   <- brand NEW random suffix, no stable
# identity, and (since this Deployment has no PVC at all) nothing to
# reattach even if it wanted to — this is the concrete, hands-on proof
# of the Deployment-vs-StatefulSet identity/storage distinction
```
</details>

---

## Lab 3: Ingress, HPA, and RBAC Least-Privilege

**Objective:** Route traffic by path through an Ingress, autoscale under real synthetic load, and prove RBAC actually restricts what a ServiceAccount can do (not just trust the theory).

> Ingress needs an Ingress Controller installed. minikube: `minikube addons enable ingress`. kind: install `ingress-nginx` via its official manifest. If neither is available, do steps 1-2 conceptually (write the YAML, confirm it validates with `kubectl apply --dry-run=server`) and focus your hands-on time on HPA + RBAC below, which need no controller.

**Task:**
1. Deploy two trivially distinguishable backends (e.g. two `hashicorp/http-echo` or `ealen/echo-server` Pods+Services returning different text) and write an Ingress routing `/a` to one and `/b` to the other.
2. If you have an Ingress Controller: confirm both paths route correctly with `curl`. If not: validate the manifest and read through it to confirm you understand the routing rules.
3. Install the Metrics Server if your cluster doesn't have one already (minikube: `minikube addons enable metrics-server`). Confirm `kubectl top pods` returns real numbers (may take a minute after enabling).
4. Deploy a small CPU-hungry workload (a container running a tight loop, or `busybox` with `while true; do :; done` inside `sh -c`) with `resources.requests.cpu` set low, and an HPA targeting `averageUtilization: 50` on CPU, `minReplicas: 1`, `maxReplicas: 5`.
5. Watch `kubectl get hpa -w` and `kubectl get pods -w` — confirm replicas scale up as CPU utilization exceeds target, then scale back down after load stops (this can take a few minutes — HPA polls periodically and has stabilization windows).
6. RBAC: create a ServiceAccount `lab-reader` with a Role that ONLY allows `get`/`list` on `pods` in your namespace — nothing else. Bind it. Then use `kubectl auth can-i` AS that ServiceAccount to prove it CAN list pods but CANNOT delete pods, CANNOT read secrets, and CANNOT do anything in a different namespace.

<details>
<summary>Solution / walkthrough</summary>

```yaml
# echo-a.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: echo-a
spec:
  replicas: 1
  selector:
    matchLabels: {app: echo-a}
  template:
    metadata:
      labels: {app: echo-a}
    spec:
      containers:
        - name: echo
          image: hashicorp/http-echo
          args: ["-text=response from A"]
          ports: [{containerPort: 5678}]
---
apiVersion: v1
kind: Service
metadata:
  name: echo-a-svc
spec:
  selector: {app: echo-a}
  ports: [{port: 80, targetPort: 5678}]
```

(Duplicate for `echo-b` with `-text="response from B"`.)

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: lab-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - http:
        paths:
          - path: /a
            pathType: Prefix
            backend:
              service: {name: echo-a-svc, port: {number: 80}}
          - path: /b
            pathType: Prefix
            backend:
              service: {name: echo-b-svc, port: {number: 80}}
```

```bash
kubectl apply -f echo-a.yaml -f echo-b.yaml -f ingress.yaml
minikube addons enable ingress    # if using minikube and not already on
kubectl get ingress
INGRESS_IP=$(minikube ip)   # or your controller's external IP
curl http://$INGRESS_IP/a
# response from A
curl http://$INGRESS_IP/b
# response from B

# 3. Metrics server
minikube addons enable metrics-server
sleep 60
kubectl top pods
# NAME       CPU(cores)   MEMORY(bytes)
# echo-a-... 0m           4Mi
```

```yaml
# cpu-hog.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cpu-hog
spec:
  replicas: 1
  selector:
    matchLabels: {app: cpu-hog}
  template:
    metadata:
      labels: {app: cpu-hog}
    spec:
      containers:
        - name: hog
          image: busybox
          command: ["sh", "-c", "while true; do :; done"]
          resources:
            requests:
              cpu: "50m"
            limits:
              cpu: "200m"
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: cpu-hog-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: cpu-hog
  minReplicas: 1
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 50
```

```bash
kubectl apply -f cpu-hog.yaml
kubectl get hpa -w
# NAME          TARGETS    MINPODS   MAXPODS   REPLICAS
# cpu-hog-hpa   210%/50%   1         5         1
# ... a minute or two later ...
# cpu-hog-hpa   180%/50%   1         5         4    <- scaled up
kubectl get pods -l app=cpu-hog
# 4 pods now running, each still individually pinned near its CPU limit

# scale down happens after the load pattern settles + the default
# stabilization window — patience needed here, can take 5+ minutes

# 6. RBAC least-privilege proof
kubectl create serviceaccount lab-reader
```

```yaml
# rbac.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader-only
  namespace: k8s-lab
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: lab-reader-binding
  namespace: k8s-lab
subjects:
  - kind: ServiceAccount
    name: lab-reader
    namespace: k8s-lab
roleRef:
  kind: Role
  name: pod-reader-only
  apiGroup: rbac.authorization.k8s.io
```

```bash
kubectl apply -f rbac.yaml

kubectl auth can-i list pods --as=system:serviceaccount:k8s-lab:lab-reader
# yes

kubectl auth can-i delete pods --as=system:serviceaccount:k8s-lab:lab-reader
# no

kubectl auth can-i get secrets --as=system:serviceaccount:k8s-lab:lab-reader
# no

kubectl auth can-i list pods --as=system:serviceaccount:k8s-lab:lab-reader --namespace=default
# no    <- Role is namespace-scoped, grants NOTHING outside k8s-lab,
# even for the exact same verb/resource it's allowed on in its own namespace

kubectl auth can-i --list --as=system:serviceaccount:k8s-lab:lab-reader
# shows the full, short permission list — exactly get/list on pods, nothing else
```
</details>

---

## Lab 4: Diagnose a Pod Stuck in CrashLoopBackOff (Production-Style Scenario)

**Objective:** This is one of the most common real K8s pages. Reproduce it deliberately with a few different root causes, and practice the full `describe` → `logs` → fix diagnostic loop for each.

**Task:**

Reproduce THREE distinct causes of CrashLoopBackOff, diagnosing each one BEFORE looking at the solution:

1. **Bad command**: deploy a Pod whose container command exits immediately with a non-zero code (e.g. `command: ["sh", "-c", "exit 1"]`). Watch it crash-loop, then diagnose using `kubectl describe pod` (check the Events section and "Last State" reason) and `kubectl logs --previous`.
2. **Missing config dependency**: deploy a Pod that references a ConfigMap key that doesn't exist via `envFrom`/`configMapKeyRef` pointing at a nonexistent ConfigMap name entirely. Diagnose the DIFFERENT failure mode this produces (hint: this one may not even reach Running/CrashLoopBackOff — check `describe` Events for what state it actually gets stuck in instead, and explain why that's a different failure class than #1).
3. **Failing readiness/liveness probe**: deploy a Pod with a `livenessProbe` pointed at a path/port that will never succeed (e.g. an HTTP probe on a port nothing listens on). Watch Kubernetes repeatedly restart it due to failed liveness checks, and diagnose via `kubectl describe pod` Events (look for "Liveness probe failed" and "Killing container" lines) — distinguish this from #1 by explaining WHO killed the container (the app itself exiting, vs kubelet killing it because of a failed probe).
4. For each of the 3 causes, write the one-line fix and re-verify the Pod reaches `Running`/`1/1 Ready`.

<details>
<summary>Solution / walkthrough</summary>

```yaml
# crash1-bad-command.yaml
apiVersion: v1
kind: Pod
metadata:
  name: crash-bad-command
spec:
  containers:
    - name: app
      image: busybox
      command: ["sh", "-c", "echo starting; exit 1"]
```

```bash
kubectl apply -f crash1-bad-command.yaml
kubectl get pods crash-bad-command -w
# STATUS cycles: Running -> Error -> CrashLoopBackOff, RESTARTS climbing

kubectl describe pod crash-bad-command
# Last State:  Terminated
#   Reason:    Error
#   Exit Code: 1
# Events:
#   Back-off restarting failed container

kubectl logs crash-bad-command --previous
# starting
# (the app printed exactly what it did before dying — exit code 1 is
# self-inflicted by the app/command, not caused by Kubernetes)

# FIX: whatever the real command was supposed to be, exit 0. In this
# synthetic case:
kubectl delete pod crash-bad-command
# then fix the command to `["sh", "-c", "echo starting; sleep 3600"]` and reapply
```

```yaml
# crash2-missing-config.yaml
apiVersion: v1
kind: Pod
metadata:
  name: crash-missing-config
spec:
  containers:
    - name: app
      image: busybox
      command: ["sleep", "3600"]
      envFrom:
        - configMapRef:
            name: this-configmap-does-not-exist
```

```bash
kubectl apply -f crash2-missing-config.yaml
kubectl get pods crash-missing-config
# STATUS: CreateContainerConfigError  <- NOT CrashLoopBackOff!

kubectl describe pod crash-missing-config
# Events:
#   Warning  Failed  ... Error: configmap "this-configmap-does-not-exist" not found

# Why this is a DIFFERENT failure class from #1: the container never
# even STARTS here — kubelet can't assemble the container's environment
# at all, so there's no process to crash and no exit code to report.
# CrashLoopBackOff specifically means "the container DID start, then
# died, repeatedly." CreateContainerConfigError means "kubelet couldn't
# even construct the container spec." Different root cause, different
# place to look (no point checking `logs --previous` here — there IS
# no previous run to have logs from).

# FIX: create the missing ConfigMap, or fix the typo'd reference
kubectl create configmap this-configmap-does-not-exist --from-literal=X=1
kubectl delete pod crash-missing-config && kubectl apply -f crash2-missing-config.yaml
kubectl get pods crash-missing-config
# Running   1/1
```

```yaml
# crash3-bad-probe.yaml
apiVersion: v1
kind: Pod
metadata:
  name: crash-bad-probe
spec:
  containers:
    - name: app
      image: busybox
      command: ["sleep", "3600"]
      livenessProbe:
        httpGet:
          path: /healthz
          port: 9999          # nothing listens here — busybox + sleep opens no ports
        initialDelaySeconds: 2
        periodSeconds: 3
        failureThreshold: 2
```

```bash
kubectl apply -f crash3-bad-probe.yaml
kubectl get pods crash-bad-probe -w
# Running -> Running (restarting) -> CrashLoopBackOff, RESTARTS climbing

kubectl describe pod crash-bad-probe
# Events:
#   Warning  Unhealthy  ... Liveness probe failed: Get "http://...:9999/healthz":
#                            dial tcp ...:9999: connect: connection refused
#   Normal   Killing    ... Container app failed liveness probe, will be restarted

# The key diagnostic difference from #1: here the APP never exited on
# its own (sleep 3600 was still fine) — kubelet itself killed the
# container because the liveness probe kept failing. "Killing" events
# authored by kubelet, not an app-level Terminated/Error exit code,
# is the fingerprint of a bad probe config rather than a bad app.

# FIX: point the probe at a port/path that's actually served, or
# remove the probe if the app genuinely has no health endpoint yet
kubectl delete pod crash-bad-probe
# then fix livenessProbe.httpGet.port (or remove the probe entirely for
# this synthetic sleep-only container) and reapply
```

**The three-way diagnostic summary to internalize:**
| Symptom | `describe` shows | Meaning |
|---|---|---|
| `CrashLoopBackOff`, exit code from the app itself | `Last State: Terminated, Reason: Error, Exit Code: N` | The app/command exited on its own — check `logs --previous` for why |
| `CreateContainerConfigError` (never reaches Running) | `Error: configmap/secret "X" not found` | kubelet can't even assemble the container spec — check referenced ConfigMaps/Secrets exist |
| `CrashLoopBackOff`, "Killing" events, no self-exit | `Liveness probe failed` ... `Killing container` | kubelet itself is killing a container that's otherwise fine — check the probe config, not the app |
</details>

---

## Self-Check Checklist

- [ ] Can you write a Deployment + Service manifest pair from memory and explain how the Service finds its Pods (label selector, not name)?
- [ ] Can you explain why a rolling update with `maxUnavailable: 0` never drops below full capacity, and watch it happen live?
- [ ] Can you tell the difference between a ConfigMap and a Secret in terms of REAL protection (not just "one is for sensitive data")?
- [ ] Can you explain, having watched it, why a StatefulSet Pod keeps its data across deletion but a Deployment Pod does not?
- [ ] Can you write a NetworkPolicy or explain why K8s networking is flat-by-default without one?
- [ ] Can you set up an HPA and explain why it silently does nothing if Pods have no `resources.requests` set?
- [ ] Can you write a least-privilege Role + RoleBinding and PROVE its boundaries with `kubectl auth can-i`, rather than just trusting the YAML?
- [ ] Given a Pod stuck somewhere between Pending/CrashLoopBackOff/CreateContainerConfigError, can you tell which of those three states you're looking at and know where to check first?
- [ ] Can you distinguish "the app crashed itself" from "kubelet killed it for a failed probe" just from `kubectl describe pod` Events?
- [ ] Can you explain what Ingress adds over just using several LoadBalancer Services, in terms of both cost and routing capability?
