import os
import subprocess
import time

HOST = os.environ.get(
    "TARGET_HOST",
    "https://ingress-nginx-controller.ingress-nginx.svc.cluster.local.",
)
MINUTES = os.environ.get("TRAFFIC_RUN_MINUTES", "15")
PAUSE_SEC = int(os.environ.get("TRAFFIC_PAUSE_SEC", "120"))

while True:
    subprocess.run(
        [
            "locust",
            "-f",
            "locustfile.py",
            "--headless",
            "--exit-code-on-error",
            "0",
            "--host",
            HOST,
            "--run-time",
            f"{MINUTES}m",
        ],
        check=False,
    )
    time.sleep(PAUSE_SEC)
