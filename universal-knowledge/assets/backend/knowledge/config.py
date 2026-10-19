import json
from functools import lru_cache
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'postgresql://knowledge:change-me@localhost:5432/knowledge'
    redis_url: str = 'redis://localhost:6379/0'
    auth_tokens: str = '{}'
    embedding_provider: str = 'hash'
    embedding_model: str = 'sentence-transformers/all-MiniLM-L6-v2'
    embedding_dimensions: int = Field(default=384, ge=32, le=4096)
    openai_api_key: str = ''
    openai_embedding_model: str = 'text-embedding-3-small'
    max_file_bytes: int = Field(default=10_000_000, ge=1024, le=100_000_000)
    max_text_chars: int = Field(default=2_000_000, ge=1000, le=10_000_000)
    chunk_chars: int = Field(default=1600, ge=200, le=8000)
    chunk_overlap: int = Field(default=200, ge=0)
    retention_days: int = Field(default=0, ge=0)
    minimum_evidence: float = Field(default=0.2, ge=0, le=1)
    job_attempts: int = Field(default=3, ge=1, le=10)

    @model_validator(mode='after')
    def validate_settings(self):
        if self.chunk_overlap >= self.chunk_chars:
            raise ValueError('chunk_overlap must be smaller than chunk_chars')
        if self.embedding_provider not in {'hash', 'sentence-transformers', 'openai'}:
            raise ValueError('unknown embedding provider')
        if self.embedding_provider == 'openai' and not self.openai_api_key:
            raise ValueError('OPENAI_API_KEY is required')
        tokens = json.loads(self.auth_tokens)
        if not isinstance(tokens, dict):
            raise ValueError('AUTH_TOKENS must be a JSON object')
        for digest, identity in tokens.items():
            if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('AUTH_TOKENS keys must be SHA256 digests')
            if not isinstance(identity, dict) or any(not isinstance(identity.get(k), str) or not identity[k] or len(identity[k]) > 256 for k in ('tenant', 'subject')):
                raise ValueError('identity needs tenant and subject')
            if not isinstance(identity.get('groups', []), list) or any(not isinstance(g, str) or not g or len(g) > 256 for g in identity.get('groups', [])):
                raise ValueError('groups must be a list')
        return self


@lru_cache
def settings():
    return Settings()
