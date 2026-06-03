from prometheus_client import Counter, Gauge, start_http_server

LOG_EVENTS = Counter(
    "log_events_total",
    "Classified log events by category",
    ["category", "severity"],
)

LOGS_PROCESSED = Counter("logs_processed_total", "Total log lines processed")
ML_ANOMALY_SCORE = Gauge("ml_anomaly_score", "Latest ML anomaly score (0-1)")
FLAGGED_IPS = Gauge("flagged_ips_total", "IPs flagged by reason", ["reason"])

SEVERITY = {
    "sqli_attempt": "high",
    "xss_attempt": "high",
    "recon": "medium",
    "ml_anomaly": "high",
    "ddos_suspect": "high",
    "auth_attack": "medium",
    "error_5xx": "low",
    "rate_limited": "medium",
}


def inc_category(category: str) -> None:
    LOG_EVENTS.labels(category=category, severity=SEVERITY.get(category, "low")).inc()


def start_metrics_server(port: int) -> None:
    start_http_server(port)
