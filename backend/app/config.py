from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "second-brain"
    backend_log_level: str = "INFO"
    backend_data_dir: str = "/app/data"

    llm_base_url: str = "http://host.docker.internal:1234/v1"
    llm_api_key: str = "lm-studio"
    llm_chat_model: str = "qwen/qwen3-14b"
    llm_embed_model: str = "text-embedding-nomic-embed-text-v1.5"
    llm_timeout_seconds: int = 60

    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    chroma_collection: str = "brain_notes"

    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "please_change_me"
    neo4j_database: str = "neo4j"

    use_in_memory: bool = False


settings = Settings()
