import os
import subprocess
import time

HOST = os.environ.get(
    "TARGET_HOST", "http://ingress-nginx-controller.ingress-nginx.svc.cluster.local"
)
MINUTES = os.environ.get("TRAFFIC_RUN_MINUTES", "12")
PAUSE_SEC = int(os.environ.get("TRAFFIC_PAUSE_SEC", "240"))

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
