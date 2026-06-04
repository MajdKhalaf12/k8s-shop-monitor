"""
Realistic traffic simulation for OS2 demo.

Timeline (90s total):
  0–30s   Normal shoppers   → green metrics, load balanced across webapp-0/1
  30–60s  Attacker arrives  → 401/403 spikes, SQLi/XSS patterns hit classifier
  60–90s  DDoS burst        → flagged_ips_total rises, ml_anomaly_score spikes

Run:
  locust -f locustfile.py --headless -u 60 -r 5 --run-time 90s \
         --host https://apache.apps.svc.cluster.local \
         --exit-code-on-error 0
"""

import os
import random
import time

from locust import HttpUser, between, task, constant, events
from locust.runners import MasterRunner, WorkerRunner

VERIFY = os.environ.get("LOCUST_VERIFY_SSL", "false").lower() == "true"

PRODUCTS = [1, 2, 3, 4]
VALID_CREDS = {"username": "admin", "password": "secret123"}
BAD_CREDS = [
    {"username": "admin",  "password": "admin"},
    {"username": "root",   "password": "root"},
    {"username": "user",   "password": "1234"},
    {"username": "test",   "password": "test"},
    {"username": "' OR 1=1--", "password": "x"},
]
SQLI_PAYLOADS = [
    "1' OR '1'='1",
    "1; DROP TABLE products--",
    "' UNION SELECT username,password FROM users--",
    "1' AND SLEEP(5)--",
]
XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "'\"><img src=x onerror=alert(1)>",
    "javascript:alert(document.cookie)",
]
UA_NORMAL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) AppleWebKit/605.1.15",
]
UA_BOT = [
    "sqlmap/1.7",
    "Nikto/2.1.6",
    "curl/7.88.1",
    "python-requests/2.31.0",
    "masscan/1.3",
]


# ─────────────────────────────────────────────
# 1. Normal Shopper  (spawned first, 0-30s)
# ─────────────────────────────────────────────
class Shopper(HttpUser):
    """Realistic human browsing a shop: list → view product → maybe login."""
    weight = 5
    wait_time = between(1, 4)

    def on_start(self):
        self.client.verify = VERIFY
        self.client.headers.update({"User-Agent": random.choice(UA_NORMAL)})
        self.token = None

    @task(6)
    def browse_products(self):
        self.client.get("/api/v1/products", name="/products")

    @task(4)
    def view_product(self):
        pid = random.choice(PRODUCTS)
        self.client.get(f"/api/v1/products/{pid}", name="/products/:id")

    @task(2)
    def health_check(self):
        self.client.get("/health", name="/health")

    @task(1)
    def login_and_browse(self):
        r = self.client.post(
            "/api/v1/auth/login",
            json=VALID_CREDS,
            name="/auth/login (ok)",
        )
        if r.status_code == 200:
            self.token = r.json().get("token")
            # After login, view a product with the token
            pid = random.choice(PRODUCTS)
            self.client.get(
                f"/api/v1/products/{pid}",
                headers={"Authorization": f"Bearer {self.token}"},
                name="/products/:id (auth)",
            )


# ─────────────────────────────────────────────
# 2. Attacker  (credential bruteforce + recon)
# ─────────────────────────────────────────────
class Attacker(HttpUser):
    """Single attacker IP: brute-force login, probe admin, inject payloads."""
    weight = 2
    wait_time = between(0.2, 0.8)

    def on_start(self):
        self.client.verify = VERIFY
        self.client.headers.update({"User-Agent": random.choice(UA_BOT)})

    @task(4)
    def brute_force(self):
        creds = random.choice(BAD_CREDS)
        self.client.post(
            "/api/v1/auth/login",
            json=creds,
            name="/auth/bruteforce",
        )

    @task(3)
    def sqli_probe(self):
        payload = random.choice(SQLI_PAYLOADS)
        self.client.get(
            f"/api/v1/products?q={payload}",
            name="/products (SQLi)",
        )

    @task(2)
    def xss_probe(self):
        payload = random.choice(XSS_PAYLOADS)
        self.client.get(
            f"/api/v1/products?search={payload}",
            name="/products (XSS)",
        )

    @task(2)
    def admin_recon(self):
        for path in ["/api/v1/admin", "/admin", "/.env", "/api/v1/users"]:
            self.client.get(path, name="/recon")

    @task(1)
    def path_traversal(self):
        self.client.get(
            "/api/v1/products?file=../../etc/passwd",
            name="/traversal",
        )


# ─────────────────────────────────────────────
# 3. DDoS Flooder  (high-rate, triggers classifier)
# ─────────────────────────────────────────────
class DDoSFlooder(HttpUser):
    """
    Simulates a botnet: constant 0-delay requests from the same source.
    The classifier's sliding window (>20 req/60s per IP) will flag this
    pod's IP and increment flagged_ips_total{reason="ddos_suspect"}.
    """
    weight = 3
    wait_time = constant(0)

    def on_start(self):
        self.client.verify = VERIFY
        self.client.headers.update({"User-Agent": "flood-bot/1.0"})

    @task(10)
    def flood_products(self):
        self.client.get("/api/v1/products", name="/flood/products")

    @task(6)
    def flood_login(self):
        self.client.post(
            "/api/v1/auth/login",
            json={"username": "flood", "password": "flood"},
            name="/flood/login",
        )

    @task(4)
    def flood_health(self):
        self.client.get("/health", name="/flood/health")
