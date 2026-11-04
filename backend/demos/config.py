from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DEMOS_", env_file=ROOT / ".env", extra="ignore"
    )

    database_url: str = "postgresql://demos:demos_dev@127.0.0.1:5433/demos"
    identity_database_url: str = "postgresql://demos:demos_dev@127.0.0.1:5433/demos_identity"
    identity_url: str = "http://127.0.0.1:8001"
    session_secret: str = "dev-session-secret"
    assertion_secret: str = "dev-assertion-secret"
    identity_pepper: str = "dev-identity-pepper"
    service_token: str = "dev-service-token"
    review_token: str = "dev-review-token"
    sample_data: bool = True
    dev_identity: bool = False
    # Built, but the Proposed answers keep them out of the first version: Italy and World
    # on the Map, the anonymity switch and petitions. Off unless asked for.
    preview_features: bool = False
    log_dir: str = "logs"
    log_max_bytes: int = 10_000_000
    log_backups: int = 3
    world_model: str = "claude-opus-5-5"
    extract_model: str = "claude-haiku-5-5"
    # On a shared VM identity listens on a unix socket instead of a port.
    identity_socket: str = ""

    # Azure OpenAI wins over Claude when it's set. The fallback is tried only when the main one fails.
    azure_endpoint: str = Field("", validation_alias="AZURE_OPENAI_ENDPOINT")
    azure_api_key: str = Field("", validation_alias="AZURE_OPENAI_API_KEY")
    azure_deployment: str = Field("", validation_alias="AZURE_OPENAI_DEPLOYMENT")
    azure_fallback_endpoint: str = Field("", validation_alias="AZURE_OPENAI_FALLBACK_ENDPOINT")
    azure_fallback_api_key: str = Field("", validation_alias="AZURE_OPENAI_FALLBACK_API_KEY")
    azure_fallback_deployment: str = Field("", validation_alias="AZURE_OPENAI_FALLBACK_DEPLOYMENT")
    ai_timeout: float = Field(20.0, validation_alias="AI_TIMEOUT_SECONDS")

    # Hard caps. When the day's AI is spent the World keeps talking with its plain templates.
    daily_request_cap: int = Field(3000, validation_alias="DAILY_REQUEST_CAP")
    daily_token_budget: int = Field(300_000, validation_alias="DAILY_TOKEN_BUDGET")
    rate_talk_per_ip_per_hour: int = Field(120, validation_alias="RATE_TALK_PER_IP_PER_HOUR")
    rate_signin_per_ip_per_hour: int = Field(10, validation_alias="RATE_SIGNIN_PER_IP_PER_HOUR")


@dataclass(frozen=True)
class Thresholds:
    show_count: int = 10
    show_percent: int = 50
    say_we: int = 30
    use_argument: int = 5
    map_solid: int = 30
    map_link_min: float = 0.12
    map_links_per_topic: int = 2
    new_topic_people: int = 20
    new_topic_days: int = 14
    agreement_overall: float = 0.60
    agreement_group: float = 0.55
    agreement_group_base: int = 50
    agreement_hold_days: int = 14
    agreement_lapse_days: int = 7
    close_margin: float = 0.05
    changed_view_days: int = 7
    send_requests: int = 100
    transcript_days: int = 90


@lru_cache
def settings() -> Settings:
    return Settings()


THRESHOLDS = Thresholds()
