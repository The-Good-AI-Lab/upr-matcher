from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    agent_base_url: str = "https://openrouter.ai/api/v1"
    llm_provider: str = "openrouter"
    model: str = "deepseek/deepseek-v4-flash"
    openrouter_api_key: str | None = None
    embedding_provider: str = "openrouter"
    embedding_model: str = "qwen/qwen3-embedding-8b"
    embedding_batch_size: int = 64
    reranker_provider: str = "openrouter"
    reranker_model: str = "cohere/rerank-4-pro"
    rerank_candidate_limit: int = 30
    rerank_top_n: int = 5
    match_threshold: float = 0.0  # top-k retrieval; 0.6 was bge-era and uncalibrated for qwen (es-en recall@10 0.0 -> 0.64)
    match_workers: int = 1
    store_embeddings: bool = False
    save_text_payloads: bool = False
    db_backend: str = "local"
    database_url: str | None = None
    local_db_path: str | None = None
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8080"])
