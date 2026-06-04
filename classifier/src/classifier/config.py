from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLASSIFIER_")

    log_path: str = "/logs/access.log"
    metrics_port: int = 8001
    anomaly_threshold: float = 0.75
    ddos_threshold: int = 20
    ddos_window_sec: int = 60
    auth_threshold: int = 5
    auth_window_sec: int = 60
    recon_paths: str = "/admin,/.env,/config,/wp-login,/.git"
    recon_min_paths: int = 3


settings = Settings()
