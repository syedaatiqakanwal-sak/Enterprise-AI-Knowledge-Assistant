"""
Secret abstraction layer (Module 12).

Resolves secrets from (highest priority first):
1. Explicit environment variables
2. Docker / Kubernetes mounted secret files under SECRETS_DIR
3. Settings defaults (never for production secrets)
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.core.config import settings


class SecretProvider:
    """Cloud-agnostic secret reader (env + file mounts)."""

    def __init__(self, secrets_dir: str | None = None) -> None:
        self.secrets_dir = Path(
            secrets_dir
            or os.getenv("SECRETS_DIR", "/run/secrets")
        )

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        env_val = os.getenv(name)
        if env_val is not None and env_val != "":
            return env_val

        # Kubernetes/Docker secret file: /run/secrets/SECRET_KEY or SECRETS_DIR/name
        file_name = name.lower().replace("_", "-")
        candidates = [
            self.secrets_dir / name,
            self.secrets_dir / file_name,
            self.secrets_dir / name.lower(),
        ]
        for path in candidates:
            if path.is_file():
                return path.read_text(encoding="utf-8").strip()

        return default

    def require(self, name: str) -> str:
        value = self.get(name)
        if not value:
            raise RuntimeError(f"Required secret '{name}' is not configured")
        return value

    def secret_key(self) -> str:
        return self.get("SECRET_KEY", settings.SECRET_KEY) or settings.SECRET_KEY

    def database_url(self) -> str:
        return self.get("DATABASE_URL", settings.DATABASE_URL) or ""


@lru_cache
def get_secret_provider() -> SecretProvider:
    return SecretProvider()


secrets = get_secret_provider()
