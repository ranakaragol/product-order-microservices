#!/usr/bin/env bash
# Deploy the whole system to a local kind cluster and smoke test it.
#
#   ./scripts/kind-up.sh          # create cluster (if missing), build, deploy, test
#   ./scripts/kind-up.sh down     # delete the cluster
#
# Works in Git Bash on Windows, Linux, macOS and GitHub Actions.
# Needs: docker (running), kind, kubectl, curl.
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-product-order}"
NAMESPACE="product-order"
TAG="dev"                       # must match images: in k8s/kustomization.yaml
SERVICES="auth_service product_service order_service dispatcher"
LOCAL_PORT="${LOCAL_PORT:-8080}"
MONGO_IMAGE="mongo:7.0"            # must match k8s/mongo.yaml
ROLLOUT_TIMEOUT="300s"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

log() { printf '\n==> %s\n' "$*"; }

# auth_service -> product-order/auth-service
image_name() { echo "product-order/${1//_/-}:${TAG}"; }

if [[ "${1:-}" == "down" ]]; then
  kind delete cluster --name "$CLUSTER_NAME"
  exit 0
fi

# 1. Cluster ---------------------------------------------------------------
CLUSTER_EXISTED=false
if kind get clusters | grep -qx "$CLUSTER_NAME"; then
  log "kind cluster '$CLUSTER_NAME' already exists"
  CLUSTER_EXISTED=true
else
  log "Creating kind cluster '$CLUSTER_NAME'"
  kind create cluster --name "$CLUSTER_NAME" --config kind-config.yaml --wait 120s
fi
kubectl config use-context "kind-${CLUSTER_NAME}" >/dev/null

# 2. Build images (runtime stage of the multi-stage Dockerfiles) -------------
for svc in $SERVICES; do
  log "Building $(image_name "$svc")"
  docker build --target runtime -t "$(image_name "$svc")" "src/$svc"
done

# 3. Load images into the kind node -----------------------------------------
# kind nodes cannot see images in your local Docker, and there is no registry,
# so we copy the images into the node's container runtime.
for svc in $SERVICES; do
  log "Loading $(image_name "$svc") into kind"
  kind load docker-image "$(image_name "$svc")" --name "$CLUSTER_NAME"
done

# Pre-pull MongoDB inside the kind node before deploying. Otherwise the pull
# (~300 MB) happens during the rollout and can hit the rollout timeout.
# ("kind load" is not used for it: on Docker Desktop it fails for multi-platform
# images such as mongo, while our own single-platform images load fine.)
log "Pulling $MONGO_IMAGE inside the kind node"
for node in $(kind get nodes --name "$CLUSTER_NAME"); do
  docker exec "$node" crictl pull "$MONGO_IMAGE"
done

# 4. Apply manifests ---------------------------------------------------------
log "Applying k8s/ with Kustomize"
kubectl apply -k k8s/

# The tag stays "dev" across rebuilds, so on a re-run the Deployment spec does
# not change and Kubernetes would keep the old pods. Restart them so they pick
# up the freshly loaded images.
if [[ "$CLUSTER_EXISTED" == true ]]; then
  kubectl -n "$NAMESPACE" rollout restart deployment
fi

# 5. Wait for rollout --------------------------------------------------------
log "Waiting for rollout"
kubectl -n "$NAMESPACE" rollout status statefulset/mongo --timeout="$ROLLOUT_TIMEOUT"
for d in auth-service product-service order-service dispatcher; do
  kubectl -n "$NAMESPACE" rollout status "deployment/$d" --timeout="$ROLLOUT_TIMEOUT"
done
kubectl -n "$NAMESPACE" get pods -o wide

# 6. Smoke test through the gateway -----------------------------------------
"$ROOT_DIR/scripts/smoke-test.sh"

log "Done. To use the API yourself:"
echo "    kubectl -n $NAMESPACE port-forward svc/dispatcher ${LOCAL_PORT}:8000"
echo "    curl http://localhost:${LOCAL_PORT}/health"
