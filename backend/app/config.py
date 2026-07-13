from pathlib import Path

from pydantic_settings import BaseSettings
from functools import lru_cache

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # --- LLM Provider Keys ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    groq_api_key: str = ""

    # --- Search Tool Keys ---
    tavily_api_key: str = ""
    # Gemini server-side "Grounding with Google Search" for the researcher's
    # search_google_live tool (precision freshness: exact rounds/valuations/M&A).
    grounded_search: bool = True

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # --- App Settings ---
    max_debate_iterations: int = 3
    log_level: str = "INFO"
    # Pilot auth: "" = disabled (local single-operator, pre-auth behavior);
    # "alice:key1,bob:key2" = required X-API-Key on all /api endpoints + per-owner History.
    api_keys: str = ""
    # Hosted multi-user sign-in (Clerk — Google / email magic-link). "" = disabled
    # (the X-API-Key path above stays in force). When set, /api endpoints require a
    # valid Clerk session token as `Authorization: Bearer <jwt>`; the verified user id
    # becomes the request owner (reuses the existing per-owner isolation). Set both to
    # your Clerk instance's Frontend API / issuer URL; jwks_url defaults to
    # <issuer>/.well-known/jwks.json when left blank.
    clerk_issuer: str = ""
    clerk_jwks_url: str = ""
    # Public-data mode for hosted pilots: uploads carry confidential material to
    # third-party LLM APIs, so gate them OFF where no data-handling agreements exist.
    uploads_enabled: bool = True

    # --- Focal-startup document uploads ---
    uploads_dir: str = "/data/uploads"  # shared volume between backend + worker
    vision_model: str = "gemini-2.5-pro"  # multimodal model for image / image-PDF pages
    max_upload_mb: int = 25

    # --- Analysis history (durable report store) ---
    reports_dir: str = "/data/reports"  # shared volume between backend + worker

    # --- LLM Model IDs (per-role, multi-provider) ---
    researcher_model: str = "gemini-2.5-pro"
    analyst_a_model: str = "gemini-2.5-pro"
    analyst_b_model: str = "claude-sonnet-4-6"
    judge_model: str = "gpt-4.1"
    compiler_model: str = "gemini-2.5-pro"

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
