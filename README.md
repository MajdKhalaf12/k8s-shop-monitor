# OS2 HW2 — Production Kubernetes Stack

Multi-container deployment: FastAPI shop (2+ instances), Apache HTTPS load balancer with `/balancer-manager`, hybrid AI log classifier (OWASP signatures + River online ML + in-memory sliding windows), Prometheus/Grafana monitoring.


| Runtime                             | Use case                                                                              |
| ----------------------------------- | ------------------------------------------------------------------------------------- |
| **3-node k3s cluster (Ubuntu VMs)** | Primary production demo — multi-node scheduling, HPA, real cluster (documented below) |
| **Docker Desktop Kubernetes**       | Single-node laptop demo — `make k8s` with local kubeconfig                            |
| **Docker Compose**                  | Local dev — `make dev` (`docker-compose.dev.yml`)                                     |


The assignment PDF requires Compose + Apache + monitoring; this repo extends that stack onto Kubernetes while keeping Apache as the HTTPS edge (not Ingress).

---

## Cluster layout (3-node k3s)

Three Ubuntu 24.04 VMs on a private LAN (`192.168.28.0/24`), **4 GB RAM each**, **ARM64** (Apple Silicon UTM/VMware or ARM cloud). The Mac is only an **operator**: SSH, `docker build`, `kubectl` / `helm` — no cluster workloads required on the Mac.


| Node    | IP               | Role                   | k3s install  |
| ------- | ---------------- | ---------------------- | ------------ |
| **VM1** | `192.168.28.131` | control plane (server) | `k3s server` |
| **VM2** | `192.168.28.133` | worker (agent)         | `k3s agent`  |
| **VM3** | `192.168.28.134` | worker (agent)         | `k3s agent`  |


After join, node names may appear as `ubuntu` (server) and `vm2-<id>`, `vm3-<id>` (workers) if you used `--with-node-id` (recommended when every VM shares the default hostname `ubuntu`).

```text
Mac (kubectl, helm, docker build)
  │
  │  KUBECONFIG → https://192.168.28.131:6443
  ▼
VM1 192.168.28.131  ── k3s server / API
  ├── VM2 192.168.28.133  ── k3s agent
  └── VM3 192.168.28.134  ── k3s agent

Traffic: `https://192.168.28.131:30443` (Apache NodePort on any node) → webapp-0 / webapp-1
```

**Why k3s?** [k3s](https://k3s.io/) is a certified, lightweight Kubernetes distribution (same API as “full” Kubernetes). Manifests live under `k8s/`; `kubectl` and `helm` work the same way.

**Why Apache stays?** The course spec requires Apache for TLS termination, load balancing, access logs, rate limiting (429), and `/balancer-manager`. A Kubernetes Ingress could replace the edge for routing, but would not satisfy those requirements without re-architecting the classifier and demos.

### VM sizing (RAM / disk)

**4 GB RAM per VM is tight** for k3s + Apache + webapps + Prometheus/Grafana. You hit **disk pressure** (~10 GB root disk fills with pulled images) and **evictions** before pure RAM limits.


| Upgrade                                    | Helps most           | Why                                                                      |
| ------------------------------------------ | -------------------- | ------------------------------------------------------------------------ |
| **RAM → 6–8 GB on VM2** (`192.168.28.133`) | **First choice**     | Most app pods land here (Apache, webapps).                               |
| **RAM → 6 GB on VM1**                      | Second               | Control plane + `kube-system` + scheduling headroom.                     |
| **Disk → 20+ GB** on **all three**         | Strongly recommended | Fixes `disk-pressure` taints and `ImagePullBackOff` more than RAM alone. |
| **RAM on all three to 6 GB**               | Best if easy         | Balanced workers; avoids everything piling onto one node.                |


Increasing RAM is **easy in UTM/VMware** (shutdown VM → memory slider → boot). Expanding the virtual disk is a bit more work but worth it for this stack.

**Redis was removed** from the stack to save ~128 MiB and a failing dependency; the classifier keeps DDoS/auth windows **in memory** inside the sidecar (fine for one Apache pod).

---

## Prerequisites

### On the Mac

```bash
brew install kubernetes-cli helm
# Docker Desktop or Colima — for building images only
```

### On each Ubuntu VM

- SSH access (`ubuntu@<IP>`)
- VMs can **ping** each other on `192.168.28.x`
- **Swap disabled** (kubelet expects memory limits to be meaningful)
- **Unique node identity** for workers (see troubleshooting below)

---

## Step-by-step: install k3s and deploy OS2

Run commands yourself in order; there are no install scripts in this repo by design.

### Phase 0 — All three VMs

```bash
sudo swapoff -a
# optional, keep swap off after reboot:
# sudo sed -i '/ swap / s/^/#/' /etc/fstab

sudo apt update
sudo apt install -y curl open-iscsi
```

Verify LAN connectivity from each VM:

```bash
ping -c 2 192.168.28.131
ping -c 2 192.168.28.133
ping -c 2 192.168.28.134
```

If **ufw** is enabled, allow cluster traffic or disable for the lab:

```bash
sudo ufw allow 6443/tcp
sudo ufw allow 10250/tcp
sudo ufw allow 8472/udp
# or: sudo ufw disable
```

---

### Phase 1 — VM1 only (`192.168.28.131`): k3s server

```bash
curl -sfL https://get.k3s.io | sudo sh -s - server \
  --tls-san=192.168.28.131 \
  --node-ip=192.168.28.131 \
  --advertise-address=192.168.28.131 \
  --write-kubeconfig-mode=644
```

Wait for system pods:

```bash
sudo kubectl get nodes
sudo kubectl get pods -A
```

Save the join token (needed for workers):

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

---

### Phase 2 — VM2 and VM3: join as agents

**Do not** run the agent install on VM1 (it is already the server).

Optional but recommended — unique hostnames before join:

```bash
# VM1: sudo hostnamectl set-hostname vm1
# VM2: sudo hostnamectl set-hostname vm2
# VM3: sudo hostnamectl set-hostname vm3
```

On **VM2** and **VM3** (same token, replace `<TOKEN>`):

```bash
curl -sfL https://get.k3s.io | sudo K3S_URL=https://192.168.28.131:6443 K3S_TOKEN=<TOKEN> sh -s - agent --with-node-id
```

If a previous join failed, uninstall first:

```bash
sudo /usr/local/bin/k3s-agent-uninstall.sh
```

On **VM1**, confirm three nodes Ready:

```bash
sudo kubectl get nodes -o wide
```

---

### Phase 3 — Mac: kubeconfig

```bash
mkdir -p ~/.kube
scp ubuntu@192.168.28.131:/etc/rancher/k3s/k3s.yaml ~/.kube/config-os2
```

Edit `~/.kube/config-os2` and change:

```yaml
server: https://127.0.0.1:6443
```

to:

```yaml
server: https://192.168.28.131:6443
```

Use the cluster:

```bash
export KUBECONFIG=~/.kube/config-os2
kubectl get nodes -o wide
kubectl get pods -A
```

Add to `~/.zshrc` if you want this permanent:

```bash
export KUBECONFIG=~/.kube/config-os2
```

---

### Phase 4 — Build images on Mac, import on every node

VMs are **arm64**; build for that platform:

```bash
cd /path/to/os2-project
export KUBECONFIG=~/.kube/config-os2

docker build --platform linux/arm64 -t os2-webapp:latest ./webapp
docker build --platform linux/arm64 -t os2-apache:latest ./apache
docker build --platform linux/arm64 -t os2-classifier:latest ./classifier
docker build --platform linux/arm64 -t os2-traffic:latest ./traffic

docker save -o os2-images.tar \
  os2-webapp:latest os2-apache:latest os2-classifier:latest os2-traffic:latest

scp os2-images.tar ubuntu@192.168.28.131:~/
scp os2-images.tar ubuntu@192.168.28.133:~/
scp os2-images.tar ubuntu@192.168.28.134:~/
```

On **each** VM (manual):

```bash
sudo k3s ctr images import ~/os2-images.tar
sudo k3s ctr images ls | grep os2
```

---

### Phase 5 — Deploy from the Mac

Either run the full Makefile target (with `KUBECONFIG` set):

```bash
make k8s
```

Or apply manually (same steps as `make k8s`):

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add jetstack https://charts.jetstack.io
helm repo update

kubectl apply -f k8s/namespaces.yaml

helm upgrade --install cert-manager jetstack/cert-manager \
  -n cert-manager --create-namespace --set crds.enabled=true --wait

kubectl apply -f k8s/cert-manager/clusterissuer.yaml
kubectl apply -f k8s/cert-manager/certificate.yaml
kubectl wait --for=condition=Ready certificate/apache-tls -n apps --timeout=180s

kubectl apply -k .
kubectl rollout status deployment/apache -n apps --timeout=300s
kubectl rollout status statefulset/webapp -n apps --timeout=300s

helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace -f k8s/monitoring/values-prom-stack.yaml

kubectl apply -k k8s/monitoring/

kubectl create configmap grafana-dashboard-os2 \
  --from-file=os2-overview.json=monitoring/grafana/dashboards/os2-overview.json \
  -n monitoring --dry-run=client -o yaml | kubectl apply -f -

kubectl label configmap grafana-dashboard-os2 -n monitoring \
  grafana_dashboard=1 release=kube-prometheus-stack --overwrite
```

Check workloads:

```bash
kubectl get pods -n apps -o wide
kubectl get pods -A
kubectl get svc -n apps
```

**Note:** k3s installs Traefik by default in `kube-system`; this project uses **Apache** as the HTTPS edge. Traefik can be ignored.

**RAM:** Prometheus + Grafana + cert-manager + apps on 3×4 GB is tight. If pods stay `Pending` or OOM, reduce Helm chart resources or run monitoring only on the control-plane node temporarily.

---

### Phase 6 — Access HTTPS and Grafana

```bash
kubectl get svc -n apps apache
```

Apache uses **NodePort** `30443` (HTTPS) on **any** node IP — avoids `svclb-`* pods that exhaust RAM on 4 GB VMs.

On the **Mac**, add to `/etc/hosts`:

```text
192.168.28.131  operating-systems.com www.operating-systems.com
```

Browser (accept self-signed certificate warning). Include the port:

```text
https://operating-systems.com:30443/api/v1/products
https://operating-systems.com:30443/balancer-manager
```

Grafana (from Mac):

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
```

Open [http://localhost:3000](http://localhost:3000) — login `admin` / `admin`.

Traffic / scale demos:

```bash
make flood-k8s
kubectl scale statefulset webapp -n apps --replicas=4
kubectl get pods -n apps -o wide
kubectl get hpa -n apps
```

**Scaling caveat:** HPA can scale the StatefulSet beyond two replicas; Apache is configured with **two** `BalancerMember` backends (`webapp-0`, `webapp-1`) only. Extra pods run in the cluster but are not in the Apache balancer pool unless you change `apache/httpd.conf` / deployment env.

---

## Troubleshooting (multi-node)


| Symptom                                          | Cause                                            | Fix                                                                                                               |
| ------------------------------------------------ | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| Agent stuck: `duplicate hostname`                | All VMs named `ubuntu`                           | `k3s-agent-uninstall.sh`, join with `agent --with-node-id` and/or `hostnamectl set-hostname vm2`                  |
| Agent: `Waiting to retrieve agent configuration` | Firewall, wrong token, or hostname conflict      | Check `ufw`, `nc -zv 192.168.28.131 6443`, fix hostname                                                           |
| `ImagePullBackOff`                               | Image missing on that node                       | `k3s ctr images import` on **every** node                                                                         |
| Pod `exec format error`                          | amd64 image on arm64 VM                          | Rebuild with `--platform linux/arm64`                                                                             |
| Mac `kubectl` cannot connect                     | Wrong server in kubeconfig                       | Use `https://192.168.28.131:6443`                                                                                 |
| Many pods `Pending` / `Completed` / `Error`      | **OOM / eviction** on 4 GB nodes                 | Follow **Recovery (OOM)** below; disable k3s Traefik; `helm upgrade` with `values-prom-stack.yaml`                |
| `svclb-apache` still present                     | Old **LoadBalancer** Service before NodePort fix | `kubectl apply -k .` then `kubectl delete daemonset -n kube-system -l svccontroller.k3s.cattle.io/svcname=apache` |
| Grafana `Failed` / port-forward error            | Grafana pod evicted or not Running               | Fix memory first; port-forward only when `kubectl get pods -n monitoring                                          |
| Traefik + Apache conflict                        | k3s Traefik binds **80/443** on nodes            | Delete Traefik HelmCharts (recovery step 2); use `https://operating-systems.com:30443` (NodePort)                 |


### Recovery (OOM) — run from Mac with `KUBECONFIG` set

**1. See the real reason (pick one Pending pod):**

```bash
kubectl describe node ubuntu | grep -A 6 Conditions
kubectl describe pod -n apps -l app=apache | tail -25
kubectl describe pod -n monitoring prometheus-kube-prometheus-stack-prometheus-0 | tail -25
```

**2. Free RAM — disable k3s Traefik (not used; Apache is the edge):**

```bash
kubectl delete helmchart traefik traefik-crd -n kube-system --ignore-not-found
kubectl delete pod -n kube-system -l app.kubernetes.io/name=traefik --ignore-not-found
```

**3. Remove stale / evicted pods:**

```bash
kubectl delete pods -n apps --field-selector=status.phase=Failed --ignore-not-found
kubectl delete pods -n monitoring --field-selector=status.phase=Failed --ignore-not-found
kubectl get pods -n apps | grep -E 'Completed|Error|Unknown' | awk '{print $1}' | xargs -r kubectl delete pod -n apps --ignore-not-found
```

**4. Re-apply apps (Service is NodePort 30443, not LoadBalancer):**

```bash
kubectl apply -k .
kubectl delete daemonset -n kube-system -l svccontroller.k3s.cattle.io/svcname=apache --ignore-not-found
```

**5. Re-upgrade monitoring with tuned values:**

```bash
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring -f k8s/monitoring/values-prom-stack.yaml
```

**6. Wait and check:**

```bash
kubectl get pods -n apps -w
kubectl get pods -n monitoring -w
```

**7. HTTPS from Mac** — `/etc/hosts` → VM1 IP, then:

```text
https://operating-systems.com:30443/api/v1/products
```

(port **30443** on k3s; not 443 unless you removed Traefik and use a different Service type)

**8. Grafana** (only when pod is Running):

```bash
kubectl get pods -n monitoring -l app.kubernetes.io/name=grafana
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
```

If still failing, deploy **apps only** first (`kubectl apply -k .`), verify Apache/webapp, add monitoring later.

---

Useful commands:

```bash
kubectl describe pod -n apps <name>
kubectl logs -n apps <pod> -c apache
kubectl logs -n apps <pod> -c classifier
kubectl get events -n apps --sort-by='.lastTimestamp'
```

If scheduling is still broken, temporarily run **all app pods on VM3** (most free disk in our lab):

```bash
kubectl patch deployment apache -n apps --type merge -p '{"spec":{"template":{"spec":{"nodeSelector":{"kubernetes.io/hostname":"vm3-e14f45d7"}}}}}'
kubectl patch statefulset webapp -n apps --type merge -p '{"spec":{"template":{"spec":{"nodeSelector":{"kubernetes.io/hostname":"vm3-e14f45d7"}}}}}'
```

Re-import `os2-images.tar` on that node after `k3s crictl rmi --prune`. Expect a **clean** `apps` namespace:

```text
apache-…   2/2  Running   (vm3)
webapp-0   1/1  Running   (vm3)
webapp-1   1/1  Running   (vm3)
```

### Recovery: cluster ran out of memory (apps `Pending`, pods `Completed`)

On the **Mac** with `KUBECONFIG` set:

```bash
# 1) Remove heavy monitoring (reinstall after apps are healthy)
helm uninstall kube-prometheus-stack -n monitoring
kubectl delete namespace monitoring --ignore-not-found --wait

# 2) Delete stuck / evicted workload pods
kubectl delete pod -n apps --all --force --grace-period=0
kubectl delete pod -n kube-system -l app=svclb-apache --force --grace-period=0 2>/dev/null || true

# 3) Re-apply manifests (pull latest repo: slim Helm values + Apache NodePort)
kubectl apply -k .

kubectl rollout status deployment/apache -n apps --timeout=120s
kubectl rollout status deployment/apache -n apps --timeout=180s
kubectl rollout status statefulset/webapp -n apps --timeout=180s

kubectl get pods -n apps -o wide
```

When `apache`, `webapp-0`, `webapp-1` are **Running**, reinstall monitoring:

```bash
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace -f k8s/monitoring/values-prom-stack.yaml
kubectl apply -k k8s/monitoring/
```

Confirm nodes have free memory: `kubectl describe node | grep -A2 "Allocated resources"` and `free -h` on each VM.

---

## Alternative: Docker Desktop (single-node laptop)


| Tool                                | macOS                                                      |
| ----------------------------------- | ---------------------------------------------------------- |
| Docker Desktop + Kubernetes enabled | [Install](https://www.docker.com/products/docker-desktop/) |
| `kubectl`                           | `brew install kubernetes-cli`                              |
| Helm                                | `brew install helm`                                        |
| Make                                | preinstalled                                               |


Enable **Docker Desktop → Settings → Kubernetes → Enable Kubernetes**, then:

```bash
make k8s
make status
```

Map hosts to **localhost**:

```text
127.0.0.1 operating-systems.com www.operating-systems.com
```

Or: `./scripts/setup-hosts.sh`

Docker Desktop forwards **LoadBalancer** port 443 to localhost automatically.

---

## Quick start (local dev — Compose only)

```bash
make dev      # HTTPS https://localhost, Grafana http://localhost:3000
make flood    # traffic generator (60s)
```

Credentials: Grafana `admin` / `admin`. Login API: `admin` / `secret123`.

---

## Architecture highlights


| Component  | Pattern                                                                                  |
| ---------- | ---------------------------------------------------------------------------------------- |
| Webapp     | StatefulSet + headless Service (stable DNS: `webapp-0.webapp.apps.svc.cluster.local`, …) |
| Apache     | Reverse proxy + TLS + `mod_proxy_balancer`; classifier **sidecar** shares log volume     |
| Classifier | OWASP-style signatures + River `HalfSpaceTrees` + in-memory sliding windows (sidecar)    |
| TLS (K8s)  | cert-manager SelfSigned `Certificate` → Secret `apache-tls-secret`                       |
| Monitoring | kube-prometheus-stack Helm; ServiceMonitor / PodMonitor / PrometheusRule                 |
| Scheduling | Multi-node k3s; optional `topologySpreadConstraints` / anti-affinity for spread          |


---

## AI classifier layers

1. **Signatures** — OWASP CRS-inspired SQLi/XSS/recon (rule-based, no training)
2. **ML** — `river.anomaly.HalfSpaceTrees` online anomaly detection
3. **Stateful** — In-process sliding windows per IP (DDoS, auth brute-force)

Metrics: classifier sidecar `:8001/metrics` (scraped in cluster via PodMonitor).

---

## Makefile targets


| Target           | Description                                                                                                     |
| ---------------- | --------------------------------------------------------------------------------------------------------------- |
| `make dev`       | Build + start `docker-compose.dev.yml`                                                                          |
| `make k8s`       | Build images, Helm (cert-manager, kube-prometheus-stack), apply manifests — set `KUBECONFIG` for remote cluster |
| `make k8s-apps`  | Apps only (skip monitoring Helm)                                                                                |
| `make flood`     | Locust traffic (compose)                                                                                        |
| `make flood-k8s` | Locust Job in cluster                                                                                           |
| `make test`      | Classifier unit tests                                                                                           |
| `make certs`     | Self-signed certs for local Compose Apache                                                                      |
| `make status`    | `kubectl get pods -A`                                                                                           |
| `make clean`     | Tear down compose + Helm releases                                                                               |


---

## Report / interview checklist

- Three k3s nodes `Ready` (`kubectl get nodes -o wide`)
- Two webapp pods running (`kubectl get pods -n apps -o wide`)
- HTTPS via Apache (`https://operating-systems.com/...`)
- `/balancer-manager` member stats
- Grafana **OS2 Stack Overview** dashboard
- Classifier metrics after `make flood-k8s`
- `kubectl get hpa -n apps` and optional scale demo
- Screenshots document VM IPs and that the Mac uses `kubectl` against `192.168.28.131:6443`

---

## References

- Assignment: Docker Compose, Apache LB, Prometheus/Grafana, AI log classifier (Damascus University OS2 final project).
- [k3s installation](https://docs.k3s.io/installation/configuration)
- [kubectl install](https://kubernetes.io/docs/tasks/tools/)

