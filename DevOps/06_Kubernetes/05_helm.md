# Helm — The Kubernetes Package Manager
**DevOps Track · Phase 6: Kubernetes**

## Quick Concepts

- **Helm** = package manager for Kubernetes — templates + manages the lifecycle of a set of manifests as one unit
- **Chart** = a Helm package — a directory of templates + metadata + default config
- **Release** = one deployed instance of a chart, given a name, tracked by Helm in the cluster
- **Chart.yaml** = chart metadata (name, version, dependencies)
- **values.yaml** = default configuration values, overridable per install
- **templates/** = Go-template YAML files rendered using values at install/upgrade time
- **Repository** = a hosted collection of charts (`bitnami`, `ingress-nginx`, your own private repo)
- **Helmfile** = a separate tool for declaratively managing MULTIPLE Helm releases (and their values) as one config

---

## Why This Matters

```
Raw kubectl manifests don't parameterize well — deploying the "same"
app to dev/staging/prod means either maintaining near-duplicate YAML
files per environment, or hand-editing values before every apply.
Helm solves this with templating + a single values file per
environment, and it turns "apply 12 YAML files in the right order"
into "helm install" / "helm upgrade" / "helm rollback" as atomic,
versioned operations with history.

It's also the standard way to consume third-party infrastructure —
almost every popular K8s tool (ingress-nginx, cert-manager, Prometheus
stack, Redis, Postgres operators) ships an official Helm chart instead
of raw manifests.
```

---

## Chart Structure

```
mychart/
├── Chart.yaml              # chart metadata
├── values.yaml              # default configuration values
├── values.schema.json        # (optional) JSON schema to validate values
├── charts/                   # (optional) bundled sub-chart dependencies
├── templates/
│   ├── deployment.yaml        # Go-template YAML, rendered using values
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── _helpers.tpl           # reusable named template snippets
│   └── NOTES.txt              # printed to the user after install/upgrade
├── .helmignore                # files excluded when packaging the chart
└── README.md
```

### Chart.yaml

```yaml
apiVersion: v2
name: mychart
description: A Helm chart for the api service
type: application
version: 0.1.0          # CHART version — bump on any template/values change
appVersion: "1.4.2"      # APP version — the image tag / app release this packages
dependencies:
  - name: postgresql
    version: "13.2.0"
    repository: "https://charts.bitnami.com/bitnami"
    condition: postgresql.enabled
```

`version` vs `appVersion` — a common confusion point: `version` tracks the chart's own template/schema changes (bump when you edit `templates/`); `appVersion` tracks which version of the actual application the chart currently points to (bump when you release a new app image), independently of chart template changes.

### values.yaml

```yaml
replicaCount: 3

image:
  repository: myrepo/api
  tag: "1.4.2"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80
  targetPort: 8000

resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"

ingress:
  enabled: true
  host: app.example.com

postgresql:
  enabled: true
  auth:
    database: mydb
```

### templates/deployment.yaml — Using Values

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-api
  labels:
    app: {{ .Release.Name }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}
    spec:
      containers:
        - name: api
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - containerPort: {{ .Values.service.targetPort }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
```

```yaml
# templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}-api
spec:
  type: {{ .Values.service.type }}
  selector:
    app: {{ .Release.Name }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
```

```yaml
# templates/ingress.yaml — conditional rendering
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ .Release.Name }}-ingress
spec:
  rules:
    - host: {{ .Values.ingress.host }}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {{ .Release.Name }}-api
                port:
                  number: {{ .Values.service.port }}
{{- end }}
```

Built-in template objects available everywhere: `.Release.Name`, `.Release.Namespace`, `.Chart.Name`, `.Chart.Version`, `.Values.*` (your values.yaml, deep-mergeable with `--set`/`-f` overrides), `.Files.*` (read extra files bundled in the chart).

---

## Install / Upgrade / Rollback Workflow

```bash
# Add a repository (for third-party charts)
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Search
helm search repo postgresql

# Install — renders templates + values, applies to the cluster, tracks as a "release"
helm install myapp ./mychart --namespace production --create-namespace

# Install with overrides
helm install myapp ./mychart \
  --set image.tag=1.5.0 \
  --set replicaCount=5 \
  -f values-production.yaml

# Preview rendered manifests WITHOUT installing (critical for review/CI)
helm template myapp ./mychart -f values-production.yaml
helm install myapp ./mychart --dry-run --debug

# Upgrade — new values/chart version, tracked as a new revision
helm upgrade myapp ./mychart --set image.tag=1.6.0

# Upgrade or install in one command (idempotent — common in CI/CD)
helm upgrade --install myapp ./mychart -f values-production.yaml

# List releases + history
helm list --namespace production
helm history myapp

# Rollback to a previous revision
helm rollback myapp 2          # revision number from `helm history`

# Uninstall
helm uninstall myapp
```

```
Every helm install/upgrade creates a new REVISION.
helm keeps the rendered manifest + values for each revision (as a
Secret in the release's namespace by default) — that history is
exactly what `helm rollback` reverts to. This is the core advantage
over raw `kubectl apply`: atomic, versioned, one-command rollback.
```

### Minimal Real Chart — End to End

```bash
helm create mychart          # scaffolds the standard structure shown above
```

```yaml
# values-staging.yaml
replicaCount: 1
image:
  tag: "1.4.2-rc1"
ingress:
  host: staging.app.example.com
```

```yaml
# values-production.yaml
replicaCount: 5
image:
  tag: "1.4.2"
ingress:
  host: app.example.com
resources:
  requests:
    cpu: "250m"
    memory: "256Mi"
```

```bash
helm upgrade --install myapp-staging ./mychart -n staging -f values-staging.yaml
helm upgrade --install myapp-prod ./mychart -n production -f values-production.yaml
# same chart, two isolated releases, different config per environment
```

---

## Helmfile — Managing Multiple Releases Declaratively

Helm itself manages one chart per `install`/`upgrade` invocation. **Helmfile** is a separate, widely-used tool that declares a whole set of releases (your app chart + ingress-nginx + cert-manager + a Redis chart, etc.) in one file, applied together.

```yaml
# helmfile.yaml
repositories:
  - name: bitnami
    url: https://charts.bitnami.com/bitnami

releases:
  - name: myapp
    namespace: production
    chart: ./mychart
    values:
      - values-production.yaml

  - name: redis
    namespace: production
    chart: bitnami/redis
    version: "18.1.5"
    values:
      - redis-values.yaml

  - name: ingress-nginx
    namespace: ingress
    chart: ingress-nginx/ingress-nginx
```

```bash
helmfile sync      # install/upgrade everything declared, in dependency order
helmfile diff       # show what WOULD change, without applying
helmfile destroy    # tear down everything
```

**When to reach for it:** once you're managing more than a handful of Helm releases together (an app + its infra dependencies) and want one command / one file as the source of truth, instead of a shell script chaining several `helm upgrade --install` calls.

### Senior Tip

```
helm template + `kubectl apply --dry-run=server -f -` (or a policy
tool like kubeconform/OPA) in CI, BEFORE `helm upgrade`, catches
templating mistakes and invalid manifests without ever touching the
live cluster. Never let `helm upgrade` be the first time rendered
output is actually validated.

Pin chart versions explicitly (`helm install myapp bitnami/postgresql
--version 13.2.0`) — an un-pinned third-party chart can introduce
breaking changes on a routine `helm repo update` + reinstall.
```

---

## Interview Angle

**Q: What's the difference between `chart version` and `appVersion` in Chart.yaml?**
`version` is the chart's own semantic version — bump it whenever you change templates, values schema, or chart structure. `appVersion` records which version of the underlying application the chart currently deploys (often mirroring the Docker image tag) — it can change independently, e.g., bumping the app's image tag without touching any template logic.

**Q: How do you safely preview what a Helm upgrade will actually change before running it?**
`helm diff upgrade` (via the `helm-diff` plugin) against the live release, or at minimum `helm template` to render manifests locally and diff/review them, and `helm upgrade --dry-run --debug` to validate against the API server without persisting changes. Never treat `helm upgrade` itself as the first validation step in a production pipeline.

**Q: Why would a team adopt Helmfile on top of Helm rather than just scripting multiple `helm upgrade` calls?**
Helmfile gives one declarative file as the source of truth for an entire set of releases (app + dependencies), with ordered apply, environment-specific value layering, and a `diff` command showing planned changes across ALL releases at once — a shell script chaining `helm upgrade` calls has none of that built in and tends to accumulate ad hoc logic over time.

**Q: When would you reach for Kustomize instead of Helm?**
Kustomize patches plain YAML per environment (base + overlays) with no templating language, no values.yaml, no packaging step — it's built into `kubectl` itself (`kubectl apply -k`). Reach for it when you want per-environment config diffs without learning Go-template syntax, or when consuming third-party manifests you don't want to fork into a Helm chart. Reach for Helm when you need packaging/versioning/rollback as a unit, dependency management (sub-charts), or you're consuming an ecosystem tool that already ships as a Helm chart. Many real GitOps setups use both — Helm to render vendor charts, Kustomize to patch the output per environment. Full worked example (`kustomization.yaml`, base/overlays structure) is in the GitOps file linked below.

---

## Related

- [`Backend_Developer/01_Year3-4_Mid/04_DevOps/13_gitops_argocd_flux.md`](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/13_gitops_argocd_flux.md) — Kustomize overlays worked example, plus how ArgoCD/Flux deploy Helm charts and Kustomize output as part of a GitOps pipeline
- [`../10_CICD/`](../10_CICD/) — where `helm upgrade`/`helmfile sync` gets invoked from a pipeline
- [`../21_Projects/README.md`](../21_Projects/README.md) — project 8 wraps the app in a Helm chart
