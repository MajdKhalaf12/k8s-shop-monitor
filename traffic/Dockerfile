FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir locust==2.32.4
COPY locustfile.py daemon.py ./
ENV TARGET_HOST=https://ingress-nginx-controller.ingress-nginx.svc.cluster.local.
ENV LOCUST_VERIFY_SSL=false
ENV LOCUST_HOST_HEADER=operating-systems.com
ENV TRAFFIC_RUN_MINUTES=15
ENV TRAFFIC_MAX_USERS=500
ENV TRAFFIC_PAUSE_SEC=120
CMD ["python", "daemon.py"]
