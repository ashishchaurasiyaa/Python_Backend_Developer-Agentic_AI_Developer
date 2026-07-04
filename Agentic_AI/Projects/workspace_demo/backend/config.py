"""
Configuration — loads settings from the environment (and a local .env file).

Never hardcode secrets here. The API key is read from the environment by the
Anthropic SDK itself (see llm.py); this module only holds non-secret config.
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load variables from a local .env file if present (gitignored — see .gitignore).
load_dotenv()


@dataclass(frozen=True)
class Settings:
    # Default model. Switch via CLAUDE_MODEL env var.
    model: str = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")
    host: str = os.environ.get("HOST", "127.0.0.1")
    port: int = int(os.environ.get("PORT", "8000"))

    @property
    def has_api_key(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))


settings = Settings()
