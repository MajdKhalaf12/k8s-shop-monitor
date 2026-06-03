import os
import random

from locust import HttpUser, between, task, constant


BASE = os.environ.get("TARGET_HOST", "https://apache")
VERIFY = os.environ.get("LOCUST_VERIFY_SSL", "false").lower() == "true"


class NormalUser(HttpUser):
    host = BASE
    wait_time = between(1, 3)

    def on_start(self):
        self.client.verify = VERIFY

    @task(5)
    def list_products(self):
        self.client.get("/api/v1/products", name="/products")

    @task(2)
    def get_product(self):
        pid = random.randint(1, 4)
        self.client.get(f"/api/v1/products/{pid}", name="/products/id")

    @task(1)
    def login_ok(self):
        self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "secret123"},
            name="/auth/login",
        )


class AttackUser(HttpUser):
    host = BASE
    wait_time = constant(0.1)

    def on_start(self):
        self.client.verify = VERIFY

    @task
    def brute_login(self):
        self.client.post(
            "/api/v1/auth/login",
            json={"username": "bot", "password": "wrong"},
            name="/auth/bruteforce",
        )

    @task
    def probe_admin(self):
        self.client.get("/api/v1/admin", name="/admin")

    @task
    def sqli_probe(self):
        self.client.get(
            "/api/v1/products?q=1' OR '1'='1",
            name="/sqli",
        )


class FloodUser(HttpUser):
    host = BASE
    wait_time = constant(0)

    def on_start(self):
        self.client.verify = VERIFY

    @task(10)
    def flood_products(self):
        self.client.get("/api/v1/products", name="/flood/products")

    @task(5)
    def flood_login(self):
        self.client.post(
            "/api/v1/auth/login",
            json={"username": "x", "password": "y"},
            name="/flood/login",
        )

    @task(3)
    def flood_admin(self):
        self.client.get("/admin", name="/flood/admin")
