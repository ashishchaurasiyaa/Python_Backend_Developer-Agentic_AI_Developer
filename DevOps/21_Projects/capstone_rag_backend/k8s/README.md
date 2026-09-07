# RAG Backend — Kubernetes Manifests (Project 5)

Deploys the app built in [`../terraform/`](../terraform/) (Project 4) and
containerized in [`Backend_Developer/.../08_FastAPI_OpenAI_RAG_Backend_starter/Dockerfile`](../../../../Backend_Developer/03_Interview_AnyYear/03_Projects/08_FastAPI_OpenAI_RAG_Backend_starter/Dockerfile) (Project 1).

## Status — honest, not aspirational

These manifests are **written and internally consistent**, not yet **applied to a
live cluster**. Applying needs one of:
- A local cluster (`minikube start` or `kind create cluster`) — free, no AWS needed, the README's own recommended starting point
- A real EKS cluster (via Terraform's EKS module, extending `../terraform/modules/networking`) — costs money, needs an AWS account

Neither was available in the environment these were written in (no `kubectl`,
no local cluster running). **Before treating Project 5 as done**, actually run:

```bash
minikube start
kubectl create configmap rag-backend-config --from-env-file=<(kubectl kustomize .)   # or: kubectl apply -f configmap.yaml
cp secret.example.yaml secret.yaml   # fill in real values first, never commit secret.yaml
kubectl apply -f secret.yaml -f configmap.yaml -f deployment.yaml -f service.yaml -f hpa.yaml

kubectl get pods -w                              # confirm 3 replicas go Ready
kubectl delete pod <one-of-the-pod-names>         # confirm self-healing — DoD item 1
kubectl set image deployment/rag-backend rag-backend=<new-tag>   # confirm zero-downtime rollout — DoD item 2
```

## Every CHANGE-ME in this folder

| File | What to fill in |
|---|---|
| `deployment.yaml` | Real image reference once Project 2's CI pipeline pushes one |
| `deployment.yaml` | Real `resources.requests/limits` after observing actual usage — DoD explicitly forbids guessing |
| `secret.example.yaml` → `secret.yaml` | Real `DATABASE_URL` (from Terraform's RDS output), `JWT_SECRET`, provider keys |
| `ingress.yaml` | Real domain + your cluster's actual ingress controller annotations |

## What's deliberately NOT here

Postgres is **not** deployed in-cluster — Project 5's own scope note says
stateful workloads in K8s are a deeper topic than this project covers. Use
the RDS instance Project 4's Terraform already provisions; `secret.yaml`
just needs to point at its endpoint.
