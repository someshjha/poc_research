#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER_NAME="research"

echo "==> Creating kind cluster '$CLUSTER_NAME' (if it doesn't already exist)"
if ! kind get clusters | grep -qx "$CLUSTER_NAME"; then
  kind create cluster --name "$CLUSTER_NAME" --config "$ROOT_DIR/k8s/kind-config.yaml"
else
  echo "cluster already exists, reusing it"
fi
kubectl config use-context "kind-$CLUSTER_NAME"

echo "==> Installing the ingress-nginx controller"
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
sleep 5  # give the controller pod a moment to be scheduled before waiting on it
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

echo "==> Building service images"
docker build -t research/gateway:local "$ROOT_DIR/services/gateway"
docker build -t research/retrieval:local "$ROOT_DIR/services/retrieval"
docker build -t research/simulation:local "$ROOT_DIR/services/simulation"
docker build -t research/orchestrator:local "$ROOT_DIR/services/orchestrator"
docker build -t research/frontend:local "$ROOT_DIR/frontend"

echo "==> Loading images into the kind cluster"
kind load docker-image research/gateway:local --name "$CLUSTER_NAME"
kind load docker-image research/retrieval:local --name "$CLUSTER_NAME"
kind load docker-image research/simulation:local --name "$CLUSTER_NAME"
kind load docker-image research/orchestrator:local --name "$CLUSTER_NAME"
kind load docker-image research/frontend:local --name "$CLUSTER_NAME"

echo "==> Applying manifests"
kubectl apply -f "$ROOT_DIR/k8s/namespace.yaml"
kubectl apply -f "$ROOT_DIR/k8s/configmap.yaml"

if [ -f "$ROOT_DIR/k8s/secret.yaml" ]; then
  kubectl apply -f "$ROOT_DIR/k8s/secret.yaml"
else
  echo "!! k8s/secret.yaml not found — applying k8s/secret.example.yaml with no keys set."
  echo "   Copy it to k8s/secret.yaml and fill in real provider keys, then re-run:"
  echo "   kubectl apply -f k8s/secret.yaml"
  kubectl apply -f "$ROOT_DIR/k8s/secret.example.yaml"
fi

kubectl apply -f "$ROOT_DIR/k8s/postgres.yaml"
kubectl apply -f "$ROOT_DIR/k8s/gateway.yaml"
kubectl apply -f "$ROOT_DIR/k8s/retrieval.yaml"
kubectl apply -f "$ROOT_DIR/k8s/simulation.yaml"
kubectl apply -f "$ROOT_DIR/k8s/orchestrator.yaml"
kubectl apply -f "$ROOT_DIR/k8s/frontend.yaml"
kubectl apply -f "$ROOT_DIR/k8s/ingress.yaml"

echo "==> Waiting for pods to become ready"
kubectl wait --namespace research --for=condition=ready pod --all --timeout=180s || true

echo
echo "==> Done. Open http://localhost:8081"
echo "    (kind-config.yaml maps the ingress controller's port 80 to host port 8081)"
echo
echo "If OLLAMA_BASE_URL (http://host.docker.internal:11434) isn't reachable from"
echo "pods on your machine, apply k8s/ollama-optional.yaml and point the configmap"
echo "at http://ollama:11434 instead — see the README."
