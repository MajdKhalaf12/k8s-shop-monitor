from __future__ import annotations

import os
import random
import time
from urllib.parse import quote

from locust import HttpUser, LoadTestShape, between, constant, task

VERIFY = os.environ.get("LOCUST_VERIFY_SSL", "false").lower() == "true"
HOST_HEADER = os.environ.get("LOCUST_HOST_HEADER")
RUN_MINUTES = int(os.environ.get("TRAFFIC_RUN_MINUTES", "15"))
MAX_USERS = int(os.environ.get("TRAFFIC_MAX_USERS", "500"))
_BASE_PEAK = 18

PRODUCTS = [1, 2, 3, 4]
VALID_CREDS = {"username": "admin", "password": "secret123"}
SEARCH_TERMS = [
    "espresso",
    "beans",
    "mug",
    "ceramic",
    "pour over",
    "cold brew",
    "bottle",
    "coffee",
    "dark roast",
    "gift",
    "kit",
    "insulated",
]
TYPO_SEARCH = ["expreso", "coffe", "mugg", "por over", "cole brew"]
BAD_CREDS = [
    {"username": "admin", "password": "admin"},
    {"username": "root", "password": "root"},
    {"username": "user", "password": "1234"},
    {"username": "test", "password": "test"},
    {"username": "' OR 1=1--", "password": "x"},
]
SQLI_PAYLOADS = [
    "1' OR '1'='1",
    "1; DROP TABLE products--",
    "' UNION SELECT username,password FROM users--",
]
XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "'\"><img src=x onerror=alert(1)>",
    "javascript:alert(document.cookie)",
]
RECON_PATHS = ["/api/v1/admin", "/admin", "/.env", "/api/v1/users"]
UA_NORMAL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]
UA_BOT = ["sqlmap/1.7", "Nikto/2.1.6", "curl/7.88.1", "python-requests/2.31.0"]
FLOOD_IPS = ["198.51.100.10", "198.51.100.11", "198.51.100.12"]


def _think(min_sec: float, max_sec: float) -> None:
    time.sleep(random.uniform(min_sec, max_sec))


def _shopper_ip() -> str:
    return f"92.{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def _attacker_ip() -> str:
    return f"185.{random.randint(200, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def _init_client(client) -> None:
    client.verify = VERIFY
    client.max_redirects = 0


def _browser_headers(ua: str, client_ip: str) -> dict[str, str]:
    headers = {
        "User-Agent": ua,
        "X-Forwarded-For": client_ip,
        "Accept": "application/json, text/html, application/xhtml+xml, */*;q=0.8",
        "Accept-Language": random.choice(
            ["en-US,en;q=0.9", "en-GB,en;q=0.9", "ar-SY,ar;q=0.9,en;q=0.8"]
        ),
    }
    if HOST_HEADER:
        headers["Host"] = HOST_HEADER
    return headers


class Shopper(HttpUser):
    weight = 10
    wait_time = between(4, 18)

    def on_start(self):
        _init_client(self.client)
        self.token: str | None = None
        self.last_product: int | None = None
        self.client.headers.update(_browser_headers(random.choice(UA_NORMAL), _shopper_ip()))

    @task(7)
    def browse_catalog(self):
        with self.client.get("/api/v1/products", name="/products", catch_response=True) as resp:
            if resp.status_code == 200:
                _think(2.0, 6.0)

    @task(6)
    def search_products(self):
        query = random.choice(SEARCH_TERMS)
        if random.random() < 0.15:
            query = random.choice(TYPO_SEARCH)
        self.client.get(
            f"/api/v1/products/search?q={quote(query)}",
            name="/products/search",
            headers={"Referer": f"{self.host}/api/v1/products"},
        )
        _think(1.5, 5.0)

    @task(5)
    def view_product_from_list(self):
        pid = random.choice(PRODUCTS)
        self.last_product = pid
        self.client.get(
            f"/api/v1/products/{pid}",
            name="/products/:id",
            headers={"Referer": f"{self.host}/api/v1/products"},
        )
        _think(4.0, 12.0)

    @task(3)
    def compare_two_products(self):
        first, second = random.sample(PRODUCTS, 2)
        self.client.get(f"/api/v1/products/{first}", name="/products/:id")
        _think(3.0, 8.0)
        self.client.get(f"/api/v1/products/{second}", name="/products/:id (compare)")
        _think(2.0, 6.0)

    @task(2)
    def preview_search_page(self):
        query = random.choice(SEARCH_TERMS)
        self.client.get(
            f"/api/v1/products/preview?q={quote(query)}",
            name="/products/preview",
        )
        _think(2.0, 5.0)

    @task(2)
    def login_and_add_to_cart(self):
        if not self.token:
            resp = self.client.post(
                "/api/v1/auth/login",
                json=VALID_CREDS,
                name="/auth/login (ok)",
            )
            if resp.status_code != 200:
                return
            self.token = resp.json().get("token")
            _think(1.0, 3.0)

        pid = self.last_product or random.choice(PRODUCTS)
        self.client.post(
            "/api/v1/cart",
            json={"product_id": pid, "quantity": random.randint(1, 2)},
            headers={"Authorization": f"Bearer {self.token}"},
            name="/cart/add",
        )
        _think(2.0, 4.0)

    @task(1)
    def wrong_password_then_leave(self):
        self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": random.choice(["admin", "123456", "password"])},
            name="/auth/login (typo)",
        )
        _think(1.0, 2.0)


class Attacker(HttpUser):
    weight = 2
    wait_time = between(3, 8)

    def on_start(self):
        _init_client(self.client)
        self.client.headers.update(
            {**_browser_headers(random.choice(UA_BOT), _attacker_ip()), "Accept": "*/*"}
        )

    @task(3)
    def brute_force_login(self):
        creds = random.choice(BAD_CREDS)
        self.client.post("/api/v1/auth/login", json=creds, name="/auth/bruteforce")
        _think(1.0, 3.0)

    @task(2)
    def sqli_probe(self):
        payload = random.choice(SQLI_PAYLOADS)
        self.client.get(
            f"/api/v1/products/search?q={quote(payload)}",
            name="/products/search (SQLi)",
        )
        _think(2.0, 5.0)

    @task(2)
    def xss_probe(self):
        payload = random.choice(XSS_PAYLOADS)
        self.client.get(
            f"/api/v1/products/preview?q={quote(payload)}",
            name="/products/preview (XSS)",
        )
        _think(2.0, 5.0)

    @task(2)
    def admin_recon(self):
        path = random.choice(RECON_PATHS)
        self.client.get(path, name="/recon")
        _think(3.0, 7.0)


class DDoSFlooder(HttpUser):
    weight = 2
    wait_time = constant(0.05)

    def on_start(self):
        _init_client(self.client)
        flood_ip = random.choice(FLOOD_IPS)
        headers = {
            "User-Agent": "flood-bot/1.0",
            "Connection": "keep-alive",
            "X-Forwarded-For": flood_ip,
        }
        if HOST_HEADER:
            headers["Host"] = HOST_HEADER
        self.client.headers.update(headers)

    @task(8)
    def flood_catalog(self):
        self.client.get("/api/v1/products", name="/flood/products")

    @task(5)
    def flood_search(self):
        self.client.get("/api/v1/products/search?q=coffee", name="/flood/search")

    @task(3)
    def flood_login(self):
        self.client.post(
            "/api/v1/auth/login",
            json={"username": "flood", "password": "flood"},
            name="/flood/login",
        )


class RealisticTrafficShape(LoadTestShape):
    def _scale_users(self, base: int) -> int:
        return max(1, round(base * MAX_USERS / _BASE_PEAK))

    def _scale_spawn(self, base: float) -> float:
        return max(0.5, round(base * MAX_USERS / _BASE_PEAK, 2))

    def _stages(self):
        total = RUN_MINUTES * 60
        raw = [
            {"until": int(total * 0.20), "users": 5, "spawn_rate": 0.2, "classes": [Shopper]},
            {"until": int(total * 0.50), "users": 14, "spawn_rate": 0.3, "classes": [Shopper, Attacker]},
            {"until": int(total * 0.72), "users": 12, "spawn_rate": 0.25, "classes": [Shopper]},
            {"until": total, "users": _BASE_PEAK, "spawn_rate": 0.5, "classes": [Shopper, DDoSFlooder]},
        ]
        return [
            {
                "until": stage["until"],
                "users": self._scale_users(stage["users"]),
                "spawn_rate": self._scale_spawn(stage["spawn_rate"]),
                "classes": stage["classes"],
            }
            for stage in raw
        ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self._stages():
            if run_time < stage["until"]:
                return (stage["users"], stage["spawn_rate"], stage["classes"])
        return None
