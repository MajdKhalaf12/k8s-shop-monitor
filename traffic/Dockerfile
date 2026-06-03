FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir locust==2.32.4
COPY locustfile.py .
ENV TARGET_HOST=https://apache
ENV LOCUST_VERIFY_SSL=false
CMD ["locust", "-f", "locustfile.py", "--headless", "-u", "30", "-r", "5", "--run-time", "60s", "--host", "https://apache"]
