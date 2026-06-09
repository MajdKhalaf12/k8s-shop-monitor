# Installation & Troubleshooting

Step-by-step guide to deploy the OS2 Kubernetes stack on 3 Ubuntu VMs from your Mac.

For project overview and architecture, see [`README.md`](README.md).

`make k8s` is a shortcut that runs Steps 5–9 in one shot — use it only after you understand the manual steps below.

---

## Prerequisites

**Mac:** `kubectl`, `helm`, Docker (for building images only).

```bash
brew install kubernetes-cli helm
```

**Each VM:** SSH access, VMs can ping each other, swap disabled.

---

## Step 1 — Install k3s (one-time)

### 1a. All three VMs — basics

```bash
sudo swapoff -a
sudo apt update && sudo apt install -y curl open-iscsi
ping -c 2 192.168.28.131   # from VM2/VM3
```

If ufw is on: `sudo ufw allow 6443/tcp && sudo ufw allow 8472/udp`

### 1b. VM1 only — k3s server

```bash
curl -sfL https://get.k3s.io | sudo sh -s - server \
  --tls-san=192.168.28.131 \
  --node-ip=192.168.28.131 \
  --advertise-address=192.168.28.131 \
  --write-kubeconfig-mode=644 \
  --disable=traefik

sudo kubectl get nodes
sudo cat /var/lib/rancher/k3s/server/node-token    # save this token
```

### 1c. VM2 and VM3 — join as agents

On **each** worker (replace `<TOKEN>`):

```bash
curl -sfL https://get.k3s.io | sudo K3S_URL=https://192.168.28.131:6443 K3S_TOKEN=<TOKEN> sh -s - agent --with-node-id
```

On VM1, confirm three nodes Ready:

```bash
sudo kubectl get nodes -o wide
```

---

## Step 2 — Mac kubeconfig

If `kubectl` fails with `127.0.0.1:6443 … EOF`, your kubeconfig points at localhost instead of the VM.

```bash
mkdir -p ~/.kube
scp ubuntu@192.168.28.131:/etc/rancher/k3s/k3s.yaml ~/.kube/config-os2
```

Edit `~/.kube/config-os2` — change `server: https://127.0.0.1:6443` to `server: https://192.168.28.131:6443`.

Use it every session (or add to `~/.zshrc`):

```bash
export KUBECONFIG=~/.kube/config-os2
kubectl get nodes -o wide
```

---

## Step 3 — Build images on Mac, import on every node

```bash
cd /path/to/os2-project
export KUBECONFIG=~/.kube/config-os2

docker build --platform linux/arm64 -t os2-webapp:latest ./webapp
docker build --platform linux/arm64 -t os2-classifier:latest ./classifier
docker build --platform linux/arm64 -t os2-traffic:latest ./traffic

docker save -o os2-images.tar \
  os2-webapp:latest os2-classifier:latest os2-traffic:latest

scp os2-images.tar ubuntu@192.168.28.131:~/
scp os2-images.tar ubuntu@192.168.28.133:~/
scp os2-images.tar ubuntu@192.168.28.134:~/
```

On **each VM**:

```bash
sudo k3s ctr images import ~/os2-images.tar
sudo k3s ctr images ls | grep os2
```

---

## Step 4 — Disable k3s Traefik (permanent)

k3s ships Traefik as the default ingress. We use **nginx-ingress** instead. Deleting Traefik pods is not enough — k3s will reinstall Traefik on reconcile or after a VM reboot unless you disable it in the server config.

### 4a. VM1 only — tell k3s never to install Traefik

SSH into **VM1** (`192.168.28.131`):

```bash
sudo mkdir -p /etc/rancher/k3s

# If /etc/rancher/k3s/config.yaml does not exist yet:
sudo tee /etc/rancher/k3s/config.yaml <<'EOF'
disable:
  - traefik
EOF
```

If `config.yaml` already exists with other settings, open it and add the `disable` block — do not overwrite the whole file:

```yaml
disable:
  - traefik
```

Restart k3s on VM1:

```bash
sudo systemctl restart k3s
```

Wait ~30s, then from the Mac:

```bash
export KUBECONFIG=~/.kube/config-os2
kubectl get nodes
```

### 4b. Mac — remove any Traefik leftovers

```bash
kubectl delete helmchart traefik traefik-crd -n kube-system --ignore-not-found
kubectl delete pod -n kube-system -l app.kubernetes.io/name=traefik --ignore-not-found
kubectl delete daemonset -n kube-system -l svccontroller.k3s.cattle.io/svcname=traefik --ignore-not-found
```

### 4c. Verify Traefik stays gone

```bash
kubectl get helmchart -n kube-system          # no traefik / traefik-crd
kubectl get pods -n kube-system | grep traefik  # no output
```

If `traefik` HelmCharts reappear after a reboot, the `disable` block is missing or k3s was not restarted on VM1 — redo 4a.

---

## Step 5 — Helm repos

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

---

## Step 6 — cert-manager

```bash
kubectl apply -f k8s/namespaces.yaml

helm upgrade --install cert-manager jetstack/cert-manager \
  -n cert-manager --create-namespace \
  --set crds.enabled=true --wait

kubectl apply -f k8s/cert-manager/clusterissuer.yaml
kubectl get pods -n cert-manager
```

---

## Step 7 — nginx Ingress + classifier sidecar

```bash
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  -f k8s/nginx-ingress/values.yaml --wait

kubectl get pods -n ingress-nginx -o wide
kubectl get svc -n ingress-nginx
```

Verify classifier sidecar:

```bash
kubectl get pod -n ingress-nginx -l app.kubernetes.io/component=controller \
  -o jsonpath='{.items[0].spec.containers[*].name}'
# expect: controller classifier
```

---

## Step 8 — Deploy the application

```bash
kubectl delete job locust-flood -n apps --ignore-not-found
kubectl apply -k .
```

| Resource | Purpose |
|----------|---------|
| `Deployment/webapp` | FastAPI shop, 2 replicas |
| `Deployment/traffic` | Locust daemon — 12m phased scenario, 4m pause, repeats forever |
| `Service/webapp` | ClusterIP — internal load balancing |
| `Ingress/webapp` | Routes `operating-systems.com` → webapp; TLS via cert-manager |
| `HorizontalPodAutoscaler/webapp` | Auto-scales 2–6 replicas on CPU |

```bash
kubectl rollout status deployment/webapp -n apps
kubectl rollout status deployment/traffic -n apps
kubectl wait --for=condition=Ready certificate/webapp-tls -n apps --timeout=120s
kubectl get ingress -n apps
kubectl get hpa -n apps
```

---

## Step 9 — Monitoring

```bash
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f k8s/monitoring/values-prom-stack.yaml

kubectl apply -k k8s/monitoring/

kubectl create configmap grafana-dashboard-os2 \
  --from-file=os2-overview.json=k8s/monitoring/os2-overview.json \
  -n monitoring --dry-run=client -o yaml | kubectl apply -f -

kubectl label configmap grafana-dashboard-os2 -n monitoring \
  grafana_dashboard=1 release=kube-prometheus-stack --overwrite
```

Grafana:

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
```

Open [http://localhost:3000](http://localhost:3000) — `admin` / `admin` — dashboard **OS2 Stack Overview**.

---

## Step 10 — Access the app

Add to `/etc/hosts` on the Mac:

```text
192.168.28.131  operating-systems.com www.operating-systems.com
```

```bash
curl -k https://operating-systems.com/health
curl -k https://operating-systems.com/api/v1/products
```

---

## Step 11 — Scaling demo

```bash
kubectl scale deployment webapp -n apps --replicas=4
kubectl get pods -n apps -w
kubectl get hpa -n apps -w
```

Traffic runs continuously via `Deployment/traffic`. Watch a cycle:

```bash
kubectl logs -n apps -l app=traffic -f
```

During the DDoS phase (last ~12% of each 12m cycle), HPA should pick up CPU load.

---

## Step 12 — Verify

```bash
kubectl get nodes -o wide
kubectl get pods -A
kubectl get svc -n ingress-nginx
kubectl get ingress -n apps
kubectl get hpa -n apps
kubectl get certificate -n apps
```

Expected:

```text
ingress-nginx   ingress-nginx-controller-…   2/2 Running
apps            webapp-…                     1/1 Running (×2+)
apps            traffic-…                    1/1 Running
monitoring      prometheus-…, grafana-…      Running
cert-manager    cert-manager-…               Running
```

---

## Makefile shortcuts

| Target | What it does |
|--------|--------------|
| `make build` | Build all Docker images |
| `make k8s` | Steps 5–9 in one shot (includes traffic daemon) |
| `make status` | Pods, services, ingress, HPA |
| `make clean` | Uninstall Helm releases and delete namespaces |
| `make test` | Classifier unit tests in Docker |

```bash
export KUBECONFIG=~/.kube/config-os2
make k8s
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `127.0.0.1:6443 … EOF` | kubeconfig points at localhost | Step 2 |
| `ImagePullBackOff` | Image missing on that node | `sudo k3s ctr images import ~/os2-images.tar` on every VM |
| `exec format error` | Wrong CPU arch | Rebuild with `--platform linux/arm64` |
| Port 443 refused | Traefik still bound | Step 4 — permanent disable on VM1 + delete leftovers |
| `traefik` HelmChart came back after reboot | `disable: traefik` not in VM1 config | Step 4a on VM1, restart k3s |
| Ingress has no address | ServiceLB not ready | `kubectl get svc -n ingress-nginx`; wait |
| HPA shows `<unknown>` | metrics-server down | `kubectl get pods -n kube-system -l k8s-app=metrics-server` |
| Classifier panels all **No data** (ML score 0 only) | nginx access log is plain text, not JSON — classifier cannot parse it | **Classifier: no metrics** below |
| Classifier no metrics | Sidecar not running | Check ingress pod is `2/2 Running` |
| Certificate not Ready | cert-manager issue | `kubectl describe certificate webapp-tls -n apps` |
| Agent join stuck | Duplicate hostname `ubuntu` | Uninstall agent, rejoin with `--with-node-id` |
| Grafana graphs show dead webapp pods (`webapp-7d5ff…` + `webapp-8696d7…`) | Prometheus keeps time series for deleted pods; happens on **every** webapp rollout | **Grafana: remove ghost pods** below |

### Grafana: remove ghost webapp pods

**Why it happens every time:** each `kubectl rollout restart deployment/webapp` (or image change) creates new pod names (`webapp-<hash>-abc`). Prometheus still has metrics for the old pods. Graph panels with `sum by (pod)` list every pod that had traffic in your selected time range — not just pods running now.

The **Pod / container status** table is fine (kube-state-metrics = live pods only). The problem is the **HTTP request rate** and **CPU/memory** graphs.

**Do this after every webapp redeploy:**

```bash
export KUBECONFIG=~/.kube/config-os2
make grafana-dashboard
```

Then in Grafana: hard-refresh the dashboard (or close and reopen **OS2 Stack Overview**). The updated queries only plot pods that are **Running** right now.

If ghosts still appear, set the time range to **Last 15 minutes** (top-right in Grafana).

**Only if you want zero history** — wipe Prometheus (removes all metrics, not just webapp):

```bash
helm uninstall kube-prometheus-stack -n monitoring
kubectl delete pvc -n monitoring --all
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace -f k8s/monitoring/values-prom-stack.yaml
kubectl apply -k k8s/monitoring/
make grafana-dashboard
```

**Confirm cluster has no leftover workloads** (not the usual cause, but check once):

```bash
kubectl get pods -n apps
kubectl delete statefulset webapp -n apps --ignore-not-found
kubectl delete deployment apache -n apps --ignore-not-found
```

### Classifier: no metrics in Grafana

The classifier sidecar only understands **JSON** access log lines. If nginx uses the default `upstreaminfo` format, every line is skipped and Grafana shows **No data** for classifier panels (ML score may show `0`).

**1. Check the log format nginx is actually writing:**

```bash
kubectl exec -n ingress-nginx deploy/ingress-nginx-controller -c controller -- tail -1 /var/log/nginx/access.log
```

Good (JSON, one line starting with `{`):

```json
{"time":"2026-06-09T...","ip":"10.42.2.0","method":"GET","uri":"/api/v1/products","status":200,...}
```

Bad (plain text — classifier will not work):

```text
10.42.2.0 - - [09/Jun/2026:19:57:58 +0000] "GET /api/v1/products HTTP/1.1" 200 ...
```

**2. Confirm classifier can see the log file** (sidecar must mount the same `access-logs` volume):

```bash
kubectl exec -n ingress-nginx deploy/ingress-nginx-controller -c classifier -- ls -la /var/log/nginx/access.log
```

If **No such file**, `values.yaml` is missing `volumeMounts` on the classifier `extraContainer` — re-apply Step 7.

**3. Re-apply nginx values** (must use `log-format-upstream` on one line, not `log-format`):

```bash
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx -f k8s/nginx-ingress/values.yaml --wait
kubectl rollout status deployment ingress-nginx-controller -n ingress-nginx
```

**4. Confirm classifier metrics locally:**

```bash
kubectl exec -n ingress-nginx deploy/ingress-nginx-controller -c classifier -- python3 -c "
import urllib.request
print(urllib.request.urlopen('http://127.0.0.1:8001/metrics').read().decode())
" | grep -E 'log_events|logs_processed|flagged'
```

After a minute of traffic you should see non-zero `logs_processed_total` and categories like `auth_attack`, `rate_limited`, `ddos_suspect` during the traffic DDoS phase.

**5. Refresh Grafana** — security panels use `rate(...[1m])`; wait 1–2 minutes after JSON logs are flowing.

Useful debug commands:

```bash
kubectl describe ingress webapp -n apps
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller -c classifier
kubectl logs -n apps -l app=webapp
kubectl get events -n apps --sort-by='.lastTimestamp'
```

---

## After you turn the VMs back on

k3s survives a shutdown — you do **not** reinstall the cluster. Walk through these phases in order.

### What to expect

| What you see | What it means |
|--------------|---------------|
| Pods with age `5d`, `CrashLoopBackOff`, `Error` | Old pod bodies from before shutdown |
| Many `operator-xxx Evicted` lines | **Not extra replicas** — eviction debris from disk/RAM pressure |
| `Pending` everywhere | Often `disk-pressure` taint — nothing can schedule |
| `ImagePullBackOff` | Image missing after `crictl rmi --prune` |
| Mac `kubectl` → `127.0.0.1:6443 EOF` | Wrong kubeconfig — Step 2 |
| Only 3 pods in `kube-system` | Normal — Traefik removed intentionally |

### Phase A — Wake the cluster (each VM)

```bash
# VM1
sudo systemctl status k3s --no-pager
# VM2 / VM3
sudo systemctl status k3s-agent --no-pager
```

If not running:

```bash
sudo systemctl restart k3s          # VM1
sudo systemctl restart k3s-agent    # VM2 / VM3
sudo swapoff -a
```

### Phase B — Mac: reconnect kubectl

```bash
export KUBECONFIG=~/.kube/config-os2
kubectl get nodes -o wide
kubectl get helmchart -n kube-system    # should NOT list traefik if Step 4a was done
```

If `traefik` / `traefik-crd` HelmCharts are back, redo **Step 4a** on VM1 (`disable: traefik` in `/etc/rancher/k3s/config.yaml`, restart k3s), then **Step 4b**.

### Phase C — Disk check

On **each VM**:

```bash
df -h /
```

If above ~85% used:

```bash
sudo k3s crictl rmi --prune
```

If virtual disk was expanded but `df` still shows ~10 GB, grow LVM:

```bash
sudo pvresize /dev/nvme0n1p3
sudo lvextend -l +100%FREE /dev/ubuntu-vg/ubuntu-lv
sudo resize2fs /dev/ubuntu-vg/ubuntu-lv
df -h /
```

### Phase D — Clear taints (Mac)

```bash
kubectl taint nodes --all node.kubernetes.io/disk-pressure:NoSchedule- 2>/dev/null
kubectl taint nodes --all node.kubernetes.io/memory-pressure:NoSchedule- 2>/dev/null
```

### Phase E — Delete junk pods (Mac)

```bash
kubectl delete pods -A --field-selector=status.phase=Failed --grace-period=0
kubectl get pods -A | grep Evicted | awk '{print $2, $1}' | while read pod ns; do
  kubectl delete pod "$pod" -n "$ns" --ignore-not-found
done
kubectl get pods -A | grep -E 'Completed|Error|Unknown' | awk '{print $2, $1}' | while read pod ns; do
  kubectl delete pod "$pod" -n "$ns" --ignore-not-found --force --grace-period=0
done
```

### Phase F — Re-import images

Rebuild on Mac if needed, then `scp` + `sudo k3s ctr images import ~/os2-images.tar` on **each VM** (see Step 3).

### Phase G — Fix pod networking

If probes fail or DNS is broken, restart k3s on all VMs (VM1 first), then:

```bash
kubectl rollout restart deployment ingress-nginx-controller -n ingress-nginx
kubectl rollout restart deployment webapp -n apps
kubectl rollout restart deployment -n cert-manager --all
```

### Phase H — Re-apply manifests

Re-run Steps 4–9 if components are missing or stuck.

### Phase I — Verify

```bash
kubectl get pods -A
curl -k https://operating-systems.com/health
```

### Nuclear option

Stuck `monitoring` namespace:

```bash
kubectl delete namespace monitoring --force --grace-period=0
```

If still Terminating, remove finalizers:

```bash
kubectl get namespace monitoring -o json | python3 -c "
import sys, json
d = json.load(sys.stdin)
d['spec']['finalizers'] = []
print(json.dumps(d))
" | kubectl replace --raw /api/v1/namespaces/monitoring/finalize -f -
```

Full wipe (only after disk is fixed and images imported):

```bash
helm uninstall kube-prometheus-stack -n monitoring 2>/dev/null
helm uninstall ingress-nginx -n ingress-nginx 2>/dev/null
helm uninstall cert-manager -n cert-manager 2>/dev/null
kubectl delete namespace apps monitoring cert-manager ingress-nginx --ignore-not-found
# then run Steps 5–9
```
