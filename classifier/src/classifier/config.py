from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLASSIFIER_")

    log_path: str = "/logs/access.log"
    metrics_port: int = 8001
    anomaly_threshold: float = 0.75
    ddos_429_threshold: int = 10
    ddos_request_threshold: int = 45
    ddos_window_sec: int = 60
    auth_threshold: int = 5
    auth_window_sec: int = 60
    recon_min_paths: int = 2


settings = Settings()
