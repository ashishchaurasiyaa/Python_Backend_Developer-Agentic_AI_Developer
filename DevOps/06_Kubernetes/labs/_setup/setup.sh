#!/usr/bin/env bash
# Bootstraps a local kind cluster for the Kubernetes labs, WITH Calico as the
# CNI instead of kind's default kindnet. This matters for Lab 4: kindnet does
# NOT enforce NetworkPolicy at all (it silently accepts the object and does
# nothing) — Calico does. Everything else in these labs works on either CNI.
set -euo pipefail
cd "$(dirname "$0")"

CLUSTER=k8s-labs

if kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  echo "cluster '$CLUSTER' already exists — skipping create. Run teardown.sh first for a clean slate."
else
  echo "==> creating kind cluster '$CLUSTER' (no default CNI)"
  kind create cluster --name "$CLUSTER" --config kind-config.yaml --wait 90s || true

  echo "==> installing Calico (tigera operator)"
  kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.29.1/manifests/tigera-operator.yaml
  kubectl create -f calico-custom-resources.yaml

  echo "==> waiting for the node to become Ready (needs Calico's CNI plugin installed first)"
  kubectl wait --for=condition=Ready node/${CLUSTER}-control-plane --timeout=180s

  echo "==> waiting for Calico pods to be Ready"
  kubectl wait --for=condition=Ready pods --all -n calico-system --timeout=180s
fi

kubectl create namespace k8s-labs --dry-run=client -o yaml | kubectl apply -f -
kubectl config set-context --current --namespace=k8s-labs

echo
echo "==> cluster ready. context: kind-${CLUSTER}, namespace: k8s-labs"
kubectl get nodes
