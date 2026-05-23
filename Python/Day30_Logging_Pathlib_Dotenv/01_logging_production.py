"""
DAY 30 — Production Logging Setup
Architecture Level: Senior Python Backend + Agentic AI

The logging module is not just print() with levels.
Senior developers build structured, configurable, production-grade loggers.
"""

import logging
import logging.handlers
import json
import sys
import traceback
from datetime import datetime
from typing import Any
from pathlib import Path


# ═══════════════════════════════════════════════════════
# PART A: Logging fundamentals
# ═══════════════════════════════════════════════════════

# Levels (low to high): DEBUG < INFO < WARNING < ERROR < CRITICAL
# Logger only emits messages at or above its level

# BAD (module-level basicConfig — never do this in a library):
# logging.basicConfig(level=logging.DEBUG)

# GOOD — always create named loggers
logger = logging.getLogger(__name__)  # "Day30_Logging_Pathlib_Dotenv.01_logging_production"

# Logger hierarchy: "myapp.api.users" → "myapp.api" → "myapp" → root
# Child loggers inherit parent's handlers unless propagate=False


# ═══════════════════════════════════════════════════════
# PART B: Production-grade JSON logger
# ═══════════════════════════════════════════════════════

class JSONFormatter(logging.Formatter):
    """
    Structured JSON logging — required for log aggregation tools:
    ELK Stack, Datadog, CloudWatch, Loki, etc.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include exception info if present
        if record.exc_info:
            log_obj["exception"] = {
                "type": record.exc_info[0].__name__,  # type: ignore
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Include extra fields (passed via extra= kwarg)
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            ):
                if not key.startswith("_"):
                    log_obj[key] = value

        return json.dumps(log_obj)


def setup_logger(
    name: str,
    level: str = "INFO",
    log_file: Path | None = None,
    json_format: bool = True,
) -> logging.Logger:
    """
    Factory function for creating production loggers.
    Call once at application startup.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    logger.propagate = False  # don't bubble to root logger

    if logger.handlers:
        return logger  # already configured (prevents duplicate handlers)

    formatter = JSONFormatter() if json_format else logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with rotation (if path provided)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,              # keep 5 backups
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# ═══════════════════════════════════════════════════════
# PART C: Contextual logging with extra fields
# ═══════════════════════════════════════════════════════

class ContextLogger:
    """
    Wraps a logger to automatically include context fields.
    Pattern used in FastAPI middleware for request tracing.
    """

    def __init__(self, logger: logging.Logger, **context):
        self._logger = logger
        self._context = context

    def _log(self, level: int, message: str, **extra):
        self._logger.log(level, message, extra={**self._context, **extra})

    def info(self, msg: str, **extra):
        self._log(logging.INFO, msg, **extra)

    def error(self, msg: str, **extra):
        self._log(logging.ERROR, msg, **extra)

    def warning(self, msg: str, **extra):
        self._log(logging.WARNING, msg, **extra)

    def with_context(self, **extra) -> "ContextLogger":
        """Create child logger with additional context."""
        return ContextLogger(self._logger, **self._context, **extra)


# ═══════════════════════════════════════════════════════
# PART D: Agent-level logging pattern
# ═══════════════════════════════════════════════════════

class AgentLogger:
    """
    Specialized logger for Agentic AI systems.
    Tracks: agent_id, session_id, tool calls, token usage.
    """

    def __init__(self, agent_id: str, session_id: str):
        self._logger = setup_logger(f"agent.{agent_id}", json_format=False)
        self._agent_id = agent_id
        self._session_id = session_id
        self._step = 0

    def _extra(self, **kwargs) -> dict:
        return {
            "agent_id": self._agent_id,
            "session_id": self._session_id,
            "step": self._step,
            **kwargs,
        }

    def step_start(self, description: str):
        self._step += 1
        self._logger.info(
            f"Step {self._step}: {description}",
            extra=self._extra(),
        )

    def tool_call(self, tool: str, args: dict):
        self._logger.info(
            f"Tool call: {tool}",
            extra=self._extra(tool=tool, args=str(args)),
        )

    def tool_result(self, tool: str, success: bool, tokens: int = 0):
        level = logging.INFO if success else logging.ERROR
        self._logger.log(
            level,
            f"Tool result: {tool} {'OK' if success else 'FAILED'}",
            extra=self._extra(tool=tool, success=success, tokens=tokens),
        )

    def llm_call(self, model: str, input_tokens: int, output_tokens: int):
        self._logger.info(
            f"LLM: {model} ({input_tokens}→{output_tokens} tokens)",
            extra=self._extra(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=round((input_tokens * 0.003 + output_tokens * 0.015) / 1000, 6),
            ),
        )


# Demo
agent_log = AgentLogger("research_agent_01", "sess_abc123")
agent_log.step_start("Search for Python asyncio documentation")
agent_log.tool_call("web_search", {"query": "Python asyncio tutorial"})
agent_log.tool_result("web_search", success=True)
agent_log.llm_call("gpt-4", input_tokens=500, output_tokens=200)


# ═══════════════════════════════════════════════════════
# PART E: logging.config.dictConfig — production setup
# ═══════════════════════════════════════════════════════

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": JSONFormatter},
        "simple": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "/tmp/app.log",
            "maxBytes": 10485760,
            "backupCount": 5,
        },
    },
    "loggers": {
        "app": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "app.agent": {"handlers": ["file"], "level": "DEBUG", "propagate": True},
        "uvicorn": {"handlers": ["console"], "level": "INFO"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
}

# Usage: logging.config.dictConfig(LOGGING_CONFIG)


# ─────────────────────────────────────────────
# INTERVIEW — Key points
# ─────────────────────────────────────────────
# 1. Never use print() in production — use logging
# 2. Never use basicConfig in libraries — only in applications
# 3. Always use __name__ as logger name
# 4. Use JSON formatters for log aggregation tools
# 5. Use RotatingFileHandler or TimedRotatingFileHandler for files
# 6. Use extra={} to add structured context fields
# 7. propagate=False prevents duplicate log entries
