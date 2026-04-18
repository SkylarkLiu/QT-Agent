from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseModel):
    name: str = "QT-Agent"
    alias: str = "千通AI助手"
    env: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    allowed_origins: list[str] = Field(default_factory=lambda: ["*"])


class DatabaseConfig(BaseModel):
    host: str = "postgres"
    port: int = 5432
    name: str = "qt_agent"
    user: str = "qt_agent"
    password: str = "qt_agent"
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False

    @property
    def dsn(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisConfig(BaseModel):
    host: str = "redis"
    port: int = 6379
    db: int = 0
    password: str = ""
    ttl_seconds: int = 3600
    window_size: int = 20

    @property
    def url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class MilvusConfig(BaseModel):
    host: str = "milvus"
    port: int = 19530
    user: str = ""
    password: str = ""
    database: str = "default"
    secure: bool = False
    collection: str = "qt_agent_knowledge"
    index_type: str = "AUTOINDEX"
    metric_type: str = "COSINE"

    @property
    def uri(self) -> str:
        scheme = "https" if self.secure else "http"
        return f"{scheme}://{self.host}:{self.port}"


class MinIOConfig(BaseModel):
    endpoint: str = "minio:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    bucket: str = "qt-agent"
    secure: bool = False


class LLMConfig(BaseModel):
    provider: str = "glm"
    model: str = "glm-4-flash"
    base_url: str = ""
    api_key: str = ""
    timeout_seconds: int = 60


class EmbeddingConfig(BaseModel):
    provider: str = "default"
    model: str = "bge-m3"
    base_url: str = ""
    api_key: str = ""
    dimension: int = 1024


class StartupRetryConfig(BaseModel):
    enabled: bool = True
    max_attempts: int = 30
    interval_seconds: int = 2
    timeout_seconds: int = 3


class CacheConfig(BaseModel):
    prefix: str = "qt-agent"
    default_ttl_seconds: int = 300
    enable_local_cache: bool = True


class RAGConfig(BaseModel):
    max_recall_count: int = 2
    relevance_threshold: float = 0.5
    rerank_top_k: int = 3
    query_rewrite_enabled: bool = True
    citation_enabled: bool = True


class IngestionConfig(BaseModel):
    """多模态入库配置。"""

    chunk_size: int = 512
    chunk_overlap: int = 64
    max_file_size_mb: int = 50
    allowed_extensions: list[str] = Field(
        default_factory=lambda: [".txt", ".md", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"]
    )
    embedding_batch_size: int = 32
    ocr_enabled: bool = True
    ocr_lang: str = "chi_sim+eng"
    max_workers: int = 4


class WebSearchConfig(BaseModel):
    """联网搜索配置。"""

    provider: str = "tavily"
    api_key: str = ""
    base_url: str = "https://api.tavily.com"
    max_results: int = 5
    search_depth: str = "basic"  # basic | advanced
    include_answer: bool = True
    timeout_seconds: int = 30


class MemoryConfig(BaseModel):
    """上下文管理与记忆配置。"""

    # 热窗口：Redis 中缓存的最近 N 条消息
    window_size: int = 20
    # 窗口缓存 TTL（秒）
    window_ttl_seconds: int = 3600
    # 摘要触发阈值：历史消息超过此数量时触发摘要压缩
    summary_threshold: int = 50
    # 摘要保留最近 N 条原始消息（不被压缩）
    summary_keep_recent: int = 10
    # 最大摘要 token（粗估字符数）
    summary_max_length: int = 500
    # 缓存相似度阈值：embedding cosine similarity >= 此值视为命中
    cache_similarity_threshold: float = 0.92
    # 缓存候选数量：在 Redis 窗口中最多比对多少条历史 query
    cache_candidate_limit: int = 10


class SSEConfig(BaseModel):
    enabled: bool = True
    ping_interval_seconds: int = 15
    retry_milliseconds: int = 3000


class RuntimeConfig(BaseModel):
    embedding_max_concurrency: int = 2
    embedding_timeout_seconds: int = 60
    object_storage_timeout_seconds: int = 30
    background_task_timeout_seconds: int = 1800
    redis_required_on_startup: bool = False
    minio_required_on_startup: bool = False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app: AppConfig = AppConfig()
    db: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    milvus: MilvusConfig = MilvusConfig()
    minio: MinIOConfig = MinIOConfig()
    llm: LLMConfig = LLMConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    startup_retry: StartupRetryConfig = StartupRetryConfig()
    cache: CacheConfig = CacheConfig()
    rag: RAGConfig = RAGConfig()
    sse: SSEConfig = SSEConfig()
    ingestion: IngestionConfig = IngestionConfig()
    web_search: WebSearchConfig = WebSearchConfig()
    memory: MemoryConfig = MemoryConfig()
    runtime: RuntimeConfig = RuntimeConfig()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
