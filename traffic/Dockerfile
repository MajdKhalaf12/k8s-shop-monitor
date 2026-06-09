FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir locust==2.32.4
COPY locustfile.py daemon.py ./
ENV TARGET_HOST=http://ingress-nginx-controller.ingress-nginx.svc.cluster.local
ENV LOCUST_VERIFY_SSL=false
ENV LOCUST_HOST_HEADER=operating-systems.com
ENV TRAFFIC_RUN_MINUTES=12
ENV TRAFFIC_PAUSE_SEC=240
CMD ["python", "daemon.py"]
