FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app/src
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY tests ./tests
COPY pytest.ini .
EXPOSE 8001
CMD ["python", "-m", "classifier.watcher"]
