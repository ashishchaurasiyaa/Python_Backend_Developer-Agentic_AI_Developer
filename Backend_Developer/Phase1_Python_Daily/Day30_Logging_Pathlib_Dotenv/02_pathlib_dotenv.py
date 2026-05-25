"""
DAY 30 — pathlib + dotenv (environment variables)
Architecture Level: Senior Python Backend + Agentic AI
"""

from pathlib import Path
import os


# ═══════════════════════════════════════════════════════
# PART A: pathlib — modern file path handling
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. Path construction — NEVER use string concatenation
# ─────────────────────────────────────────────

# BAD (old style):
# path = "/Users/dev" + "/project" + "/config.json"

# GOOD (pathlib):
base = Path("/Users/dev")
config_path = base / "project" / "config.json"
print(config_path)            # /Users/dev/project/config.json
print(config_path.name)       # config.json
print(config_path.stem)       # config
print(config_path.suffix)     # .json
print(config_path.parent)     # /Users/dev/project
print(config_path.parts)      # ('/', 'Users', 'dev', 'project', 'config.json')


# ─────────────────────────────────────────────
# 2. Path properties and methods
# ─────────────────────────────────────────────

p = Path(__file__)            # current file path
print(p.resolve())            # absolute path (resolves symlinks)
print(p.is_file())            # True
print(p.is_dir())             # False
print(p.exists())             # True


# ─────────────────────────────────────────────
# 3. File operations
# ─────────────────────────────────────────────

# Create directories
tmp = Path("/tmp/ai_agent_demo")
tmp.mkdir(parents=True, exist_ok=True)  # like mkdir -p

# Write and read text
config_file = tmp / "config.json"
config_file.write_text('{"model": "gpt-4", "temperature": 0.7}')
content = config_file.read_text()
print(f"Read: {content}")

# Write and read bytes
binary_file = tmp / "data.bin"
binary_file.write_bytes(b"\x00\x01\x02\x03")
print(f"Bytes: {binary_file.read_bytes()}")

# Append to file
log_file = tmp / "agent.log"
log_file.touch()                          # create if not exists
with log_file.open("a") as f:
    f.write("Agent started\n")
    f.write("Tool called\n")

print(f"Log lines: {log_file.read_text().splitlines()}")


# ─────────────────────────────────────────────
# 4. Glob and directory traversal
# ─────────────────────────────────────────────

# Find all Python files recursively
project_root = Path(".")
py_files = list(project_root.glob("*.py"))        # current dir only
all_py   = list(project_root.rglob("*.py"))       # recursive
print(f"Python files in dir: {len(py_files)}")

# Find specific patterns
# json_files = list(project_root.rglob("*.json"))
# configs    = list(project_root.glob("config*.yaml"))


# ─────────────────────────────────────────────
# 5. ARCHITECTURE PATTERN — Project path manager
# ─────────────────────────────────────────────

class ProjectPaths:
    """
    Centralized path management for a production project.
    Single source of truth for all paths.
    """
    ROOT: Path = Path(__file__).resolve().parent.parent

    @classmethod
    def src(cls) -> Path:
        return cls.ROOT / "src"

    @classmethod
    def tests(cls) -> Path:
        return cls.ROOT / "tests"

    @classmethod
    def data(cls) -> Path:
        return cls.ROOT / "data"

    @classmethod
    def logs(cls) -> Path:
        path = cls.ROOT / "logs"
        path.mkdir(exist_ok=True)
        return path

    @classmethod
    def prompts(cls) -> Path:
        """Prompt template directory for AI agents."""
        path = cls.ROOT / "prompts"
        path.mkdir(exist_ok=True)
        return path

    @classmethod
    def env_file(cls) -> Path:
        return cls.ROOT / ".env"

    @classmethod
    def get_prompt(cls, name: str) -> str:
        """Load a prompt template by name."""
        prompt_file = cls.prompts() / f"{name}.txt"
        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt template not found: {name}")
        return prompt_file.read_text(encoding="utf-8")


# Usage:
# paths = ProjectPaths()
# log_file = ProjectPaths.logs() / "agent.log"
# prompt   = ProjectPaths.get_prompt("research_agent")


# ═══════════════════════════════════════════════════════
# PART B: Environment variables + python-dotenv
# ═══════════════════════════════════════════════════════

# .env file format:
# OPENAI_API_KEY=sk-xxx
# ANTHROPIC_API_KEY=sk-ant-xxx
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db
# DEBUG=true
# LOG_LEVEL=INFO
# MAX_RETRIES=3


# ─────────────────────────────────────────────
# 1. Basic dotenv usage
# ─────────────────────────────────────────────

# Install: pip install python-dotenv
# from dotenv import load_dotenv
# load_dotenv()  # loads .env file into os.environ

# Then access:
api_key = os.getenv("OPENAI_API_KEY", "default_key")
debug   = os.getenv("DEBUG", "false").lower() == "true"
retries = int(os.getenv("MAX_RETRIES", "3"))


# ─────────────────────────────────────────────
# 2. ARCHITECTURE PATTERN — Settings class (Pydantic v2 style)
# ─────────────────────────────────────────────

# This is the PRODUCTION pattern — used with FastAPI + Pydantic
# from pydantic_settings import BaseSettings, SettingsConfigDict
#
# class Settings(BaseSettings):
#     model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
#
#     # AI Config
#     openai_api_key: str
#     anthropic_api_key: str
#     default_model: str = "gpt-4"
#     max_tokens: int = 2000
#     temperature: float = 0.7
#
#     # Database
#     database_url: str
#     redis_url: str = "redis://localhost:6379"
#
#     # App Config
#     debug: bool = False
#     log_level: str = "INFO"
#     secret_key: str
#     allowed_origins: list[str] = ["http://localhost:3000"]
#
#     @property
#     def is_production(self) -> bool:
#         return not self.debug
#
# # Singleton pattern for settings
# @functools.lru_cache(maxsize=1)
# def get_settings() -> Settings:
#     return Settings()
#
# # FastAPI dependency:
# # def route(settings: Settings = Depends(get_settings)):


# ─────────────────────────────────────────────
# 3. Manual settings without Pydantic (fallback)
# ─────────────────────────────────────────────

class Settings:
    """Pure Python settings class — no dependencies."""

    def __init__(self):
        self.openai_key: str      = self._required("OPENAI_API_KEY")
        self.debug: bool          = self._bool("DEBUG", default=False)
        self.log_level: str       = os.getenv("LOG_LEVEL", "INFO")
        self.max_retries: int     = int(os.getenv("MAX_RETRIES", "3"))
        self.database_url: str    = os.getenv("DATABASE_URL", "sqlite:///./app.db")

    def _required(self, key: str) -> str:
        value = os.getenv(key)
        if value is None:
            raise ValueError(f"Required environment variable not set: {key}")
        return value

    def _bool(self, key: str, default: bool = False) -> bool:
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "on")

    def __repr__(self) -> str:
        return (
            f"Settings(debug={self.debug}, log_level={self.log_level}, "
            f"max_retries={self.max_retries})"
        )


# Clean up temp files
import shutil
shutil.rmtree(tmp, ignore_errors=True)

# ─────────────────────────────────────────────
# INTERVIEW — os.environ vs os.getenv
# ─────────────────────────────────────────────
# os.environ["KEY"]       — raises KeyError if missing
# os.getenv("KEY")        — returns None if missing
# os.getenv("KEY", "def") — returns "def" if missing
# os.environ.get("KEY")   — same as os.getenv
#
# pathlib vs os.path:
# os.path.join(a, b, c)  → Path(a) / b / c
# os.path.exists(p)      → Path(p).exists()
# os.makedirs(p)         → Path(p).mkdir(parents=True)
# open(p, 'r').read()    → Path(p).read_text()
# Always use pathlib in new code.
