# OS2 HW2 — Production Kubernetes Stack

Multi-container deployment: FastAPI shop (2+ instances), Apache HTTPS load balancer with `/balancer-manager`, hybrid AI log classifier (OWASP signatures + River online ML + Redis windows), Prometheus/Grafana monitoring.

**Primary runtime:** Kubernetes (`make k8s`)  
**Local dev:** `make dev` (uses `docker-compose.dev.yml`)  
**Spec compose file:** `docker-compose.yml` includes the dev stack.

## Prerequisites

| Tool | macOS | Windows | Linux |
|------|-------|---------|-------|
| Docker Desktop + Kubernetes | [Install](https://www.docker.com/products/docker-desktop/) | Same | Same |
| `kubectl` | `brew install kubernetes-cli` | `winget install Kubernetes.kubectl` or [docs](https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/) | Package manager or [docs](https://kubernetes.io/docs/tasks/tools/) |
| Helm | `brew install helm` | `winget install Helm.Helm` | [Install guide](https://helm.sh/docs/intro/install/) |
| Make | Preinstalled on macOS | Git Bash, WSL, or `choco install make` | `apt install make` / equivalent |

**Windows note:** Run `make` from **Git Bash** or **WSL** (recommended). PowerShell/CMD do not run the Makefile natively unless you install `make`.

Enable **Docker Desktop → Settings → Kubernetes → Enable Kubernetes** before the K8s demo.

## Quick start (local dev)

```bash
make dev      # HTTPS https://localhost, Grafana http://localhost:3000
make flood    # traffic generator (60s)
```

Credentials: Grafana `admin` / `admin`. Login API: `admin` / `secret123`.

## Domain (Kubernetes demo)

Map `operating-systems.com` to localhost so the TLS certificate hostname matches.

### macOS / Linux

Add to **`/etc/hosts`** (admin password once):

```text
127.0.0.1 operating-systems.com www.operating-systems.com
```

Or run:

```bash
./scripts/setup-hosts.sh
```

### Windows

Edit **`C:\Windows\System32\drivers\etc\hosts`** as **Administrator** (Notepad → Run as administrator) and add:

```text
127.0.0.1 operating-systems.com www.operating-systems.com
```

Or run in **PowerShell (Admin)**:

```powershell
.\scripts\setup-hosts.ps1
```

Then open (port **443** — no `:30443` on Docker Desktop):

```text
https://operating-systems.com/api/v1/products
https://operating-systems.com/balancer-manager
```

The Apache Service uses **LoadBalancer**; Docker Desktop forwards **443 → Apache** on localhost on both macOS and Windows.

## Kubernetes (interview demo)

```bash
make k8s
make status
# App: https://operating-systems.com  (after hosts setup above)
# Grafana: kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
make flood-k8s
kubectl scale statefulset webapp -n apps --replicas=4
```

Grafana: http://localhost:3000 (`admin` / `admin`) while port-forward is running.

## Architecture highlights

| Component | Production pattern |
|-----------|-------------------|
| Webapp | StatefulSet + headless Service (stable DNS for Apache BalancerMembers) |
| Apache | Single config file `apache/httpd.conf` → Kustomize ConfigMap (`kustomization.yaml` at repo root) |
| Classifier | Sidecar in Apache pod; OWASP CRS + River HalfSpaceTrees + Redis |
| TLS | cert-manager SelfSigned Certificate → K8s Secret |
| Monitoring | kube-prometheus-stack Helm; ServiceMonitor / PodMonitor / PrometheusRule CRDs |

## AI classifier layers

1. **Signatures** — OWASP CRS-inspired SQLi/XSS/recon (rule-based, no training)
2. **ML** — `river.anomaly.HalfSpaceTrees` online anomaly detection
3. **Stateful** — Redis sorted-set sliding windows (DDoS, auth brute-force)

Metrics: `http://classifier:8001/metrics` (dev) or classifier sidecar in K8s.

## Makefile targets

| Target | Description |
|--------|-------------|
| `make dev` | Build + start docker-compose.dev.yml |
| `make k8s` | Build images, Helm (cert-manager, kube-prometheus-stack), apply manifests |
| `make flood` | Locust traffic (compose) |
| `make flood-k8s` | Locust Job in cluster |
| `make test` | Classifier unit tests |
| `make certs` | Generate self-signed certs for local Apache |
| `make clean` | Tear down compose + Helm releases |

## Report screenshots checklist

- Both webapp instances healthy
- HTTPS via Apache (self-signed)
- `/balancer-manager` member stats
- Grafana: **OS2 Stack Overview** dashboard (workloads, load, resources, security)
- Classifier metrics after `make flood`
- (K8s) `kubectl get pods`, HPA scale demo
