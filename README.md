# OS2 — Kubernetes Stack

Extension of the OS2 final project onto a 3-node k3s cluster. The Docker Compose version (Apache, self-signed TLS, as required by the assignment PDF) is in [`../os2-hw2/`](../os2-hw2/). This repo is the Kubernetes deployment I built on top of that.

Deploy steps and troubleshooting: [`INSTALLATION.md`](INSTALLATION.md).

---

## Overview

The app is a FastAPI shop API (`Qahwa Shop`). External traffic hits `https://operating-systems.com`, goes through nginx-ingress for TLS and routing, and gets distributed across multiple webapp pods. nginx writes JSON access logs; a classifier container in the same pod reads those logs and detects attacks (SQLi, XSS, brute-force, DDoS) using signature rules and online ML (`river` HalfSpaceTrees). Prometheus scrapes metrics from the webapp and classifier; Grafana shows them on an OS2 dashboard.

When load goes up, HPA scales the webapp Deployment from 2 to 6 replicas based on CPU. A Locust Deployment in the cluster runs phased traffic on a loop (shoppers → attackers → DDoS burst) so the classifier and HPA always have something to react to.

---

## How traffic flows

```text
Browser  →  https://operating-systems.com:443
                │
         LoadBalancer (k3s ServiceLB)
                │
         nginx-ingress pod
           ├── nginx       TLS + routing
           └── classifier  tails access.log
                │
         Ingress  →  webapp Service  →  webapp pods (Deployment + HPA)
```

1. Request arrives at any node IP on 443 (ServiceLB forwards to ingress).
2. cert-manager issued the TLS cert; nginx terminates HTTPS.
3. Ingress matches `operating-systems.com` and sends traffic to the webapp Service.
4. kube-proxy picks one of the ready webapp pods.
5. nginx logs the request as JSON; classifier processes the line and updates Prometheus metrics.

---

## Cluster

Three Ubuntu 24.04 ARM64 VMs on `192.168.28.0/24`. I run `kubectl` and `helm` from my Mac; the VMs run the workloads.

| Node | IP | Role |
|------|-----|------|
| VM1 | `192.168.28.131` | k3s server |
| VM2 | `192.168.28.133` | k3s worker |
| VM3 | `192.168.28.134` | k3s worker |

I used k3s because it's full Kubernetes API without the overhead of a full cluster install — fine for 4–6 GB VMs.

---

## Main pieces

- **webapp** — FastAPI, exposes `/api/v1/products`, auth, health, `/metrics`
- **nginx-ingress** — Helm chart, edge proxy + TLS. Replaces running Apache in a pod with `hostPort`
- **Ingress** — YAML rule: `operating-systems.com` → webapp Service
- **cert-manager** — watches the Ingress annotation and creates the TLS secret
- **Deployment + Service + HPA** — webapp runs as a Deployment; Service load-balances; HPA scales on CPU
- **classifier** — sidecar on the ingress controller pod, reads `/var/log/nginx/access.log`
- **kube-prometheus-stack** — Prometheus + Grafana via Helm; ServiceMonitor for webapp, PodMonitor for classifier
- **traffic** — Locust daemon Deployment; 12m scenario, 4m pause, repeats

I moved the classifier from an Apache sidecar to an nginx sidecar when I switched to Ingress. Same image, same JSON log format — only the log path changed.

---

## Classifier

Three layers, same as the assignment spec:

1. **Rules** — pattern matching for SQLi, XSS, recon paths (OWASP CRS-style)
2. **ML** — online anomaly score per request, no pre-trained model file
3. **Windows** — in-memory per-IP counters for DDoS and failed login bursts

Metrics on port 8001, scraped by Prometheus.

---

## Why Ingress instead of Apache here

The assignment stack uses Apache as load balancer + TLS + access logs. That works in Docker Compose. On Kubernetes, pinning Apache to one VM with `hostPort: 443` means a single point of failure and no way to run a second edge replica. Ingress Controller + Service + Deployment is how you'd actually run this in production — the Service discovers backends automatically when HPA adds pods, and the edge is reachable on any node.

---

## Files

```text
webapp/           API
classifier/       log analysis
traffic/          locustfile.py
k8s/apps/         webapp + traffic Deployments, Service, Ingress, HPA
k8s/nginx-ingress/  Helm values (JSON log format + classifier sidecar)
k8s/monitoring/   Prometheus/Grafana values + dashboard
k8s/cert-manager/ ClusterIssuer
INSTALLATION.md   how to deploy
```
