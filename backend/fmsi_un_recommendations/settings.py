from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    agent_base_url: str = "https://openrouter.ai/api/v1"
    model: str = "meta-llama/llama-3.3-70b-instruct"
    openrouter_api_key: str | None = None
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    match_threshold: float = 0.6
    match_workers: int = 1
    reranker_batch_size: int = 16
    store_embeddings: bool = True
    db_backend: str = "local"
    database_url: str | None = None
    local_db_path: str | None = None
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8080"])
