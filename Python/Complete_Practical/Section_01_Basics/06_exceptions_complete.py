"""
╔══════════════════════════════════════════════════════════════╗
║  PYTHON COMPLETE PRACTICAL — Section 01                      ║
║  Topic: Exceptions — Complete Reference                      ║
╚══════════════════════════════════════════════════════════════╝
"""

import logging
import traceback
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 1. EXCEPTION HIERARCHY
# ─────────────────────────────────────────────────────────────
"""
BaseException
├── SystemExit
├── KeyboardInterrupt
├── GeneratorExit
└── Exception
    ├── ArithmeticError
    │   ├── ZeroDivisionError
    │   └── OverflowError
    ├── LookupError
    │   ├── IndexError
    │   └── KeyError
    ├── TypeError
    ├── ValueError
    ├── AttributeError
    ├── NameError
    ├── OSError (IOError, FileNotFoundError, PermissionError...)
    ├── RuntimeError
    │   └── RecursionError
    ├── StopIteration
    └── NotImplementedError
"""

# ─────────────────────────────────────────────────────────────
# 2. TRY/EXCEPT/ELSE/FINALLY
# ─────────────────────────────────────────────────────────────

def divide(a: float, b: float) -> float:
    try:
        result = a / b
    except ZeroDivisionError:
        print("Cannot divide by zero!")
        return 0.0
    except TypeError as e:
        print(f"Invalid types: {e}")
        raise   # re-raise the exception
    else:
        # Runs only if NO exception was raised
        print(f"Result: {result}")
        return result
    finally:
        # ALWAYS runs — cleanup code
        print("Division attempted")

divide(10, 2)   # prints result, then cleanup
divide(10, 0)   # prints error, then cleanup


# ─────────────────────────────────────────────────────────────
# 3. CATCHING MULTIPLE EXCEPTIONS
# ─────────────────────────────────────────────────────────────

def parse_config(data: Any) -> dict:
    try:
        return {"value": int(data["key"])}
    except (KeyError, IndexError):
        # Multiple exceptions in one except block
        print("Key not found")
        return {}
    except (TypeError, ValueError) as e:
        print(f"Type/value error: {e}")
        return {}
    except Exception as e:
        # Catch-all — always put last, be specific above
        print(f"Unexpected error: {type(e).__name__}: {e}")
        raise

# Catching exception and re-raising with context
try:
    result = parse_config(None)
except Exception as original:
    raise RuntimeError("Config parse failed") from original  # chains exceptions


# ─────────────────────────────────────────────────────────────
# 4. CUSTOM EXCEPTIONS — production pattern
# ─────────────────────────────────────────────────────────────

class AppError(Exception):
    """Base exception for all application errors."""
    def __init__(self, message: str, code: str = "APP_ERROR", status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "status_code": self.status_code,
        }

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class ValidationError(AppError):
    """Raised when input validation fails."""
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message, code="VALIDATION_ERROR", status_code=422)
        self.field = field

    def to_dict(self) -> dict:
        d = super().to_dict()
        if self.field:
            d["field"] = self.field
        return d


class NotFoundError(AppError):
    """Raised when a resource is not found."""
    def __init__(self, resource: str, id: Any):
        super().__init__(f"{resource} with id={id!r} not found", "NOT_FOUND", 404)
        self.resource = resource
        self.id = id


class AuthError(AppError):
    """Raised for authentication/authorization failures."""
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, "AUTH_ERROR", 401)


class RateLimitError(AppError):
    """Raised when rate limit is exceeded."""
    def __init__(self, limit: int, window_seconds: int):
        super().__init__(
            f"Rate limit of {limit} requests per {window_seconds}s exceeded",
            "RATE_LIMIT_ERROR",
            429,
        )
        self.limit = limit
        self.window_seconds = window_seconds


# AI-specific exceptions
class LLMError(AppError):
    """Base exception for LLM-related errors."""
    def __init__(self, message: str, model: str, provider: str):
        super().__init__(message, "LLM_ERROR", 503)
        self.model = model
        self.provider = provider


class TokenLimitError(LLMError):
    """Raised when token limit is exceeded."""
    def __init__(self, model: str, requested: int, max_allowed: int):
        super().__init__(
            f"Token limit exceeded: {requested} > {max_allowed}",
            model, "openai"
        )
        self.requested = requested
        self.max_allowed = max_allowed
        self.code = "TOKEN_LIMIT_ERROR"


class ContextWindowError(LLMError):
    """Raised when context window is full."""
    pass


# Demo
try:
    raise ValidationError("Email format is invalid", field="email")
except ValidationError as e:
    print(e.to_dict())

try:
    raise TokenLimitError("gpt-4", requested=9000, max_allowed=8192)
except LLMError as e:
    print(f"LLM Error: {e.message} (model={e.model})")


# ─────────────────────────────────────────────────────────────
# 5. EXCEPTION CHAINING — __cause__ and __context__
# ─────────────────────────────────────────────────────────────

# Implicit chaining (from ... is set automatically)
def read_config(path: str) -> dict:
    try:
        with open(path) as f:
            import json
            return json.load(f)
    except FileNotFoundError as e:
        raise AppError(f"Config file not found: {path}") from e  # explicit chain

# Suppress context (when re-raising different exception)
try:
    int("not_a_number")
except ValueError:
    raise RuntimeError("Conversion failed") from None  # suppress original


# ─────────────────────────────────────────────────────────────
# 6. CONTEXT MANAGERS AND EXCEPTIONS
# ─────────────────────────────────────────────────────────────

import contextlib

# contextlib.suppress — clean exception suppression
with contextlib.suppress(FileNotFoundError):
    import os
    os.remove("/tmp/nonexistent_config.json")

# contextlib.suppress with multiple types
with contextlib.suppress(FileNotFoundError, PermissionError):
    pass


# ─────────────────────────────────────────────────────────────
# 7. PRODUCTION EXCEPTION HANDLER — FastAPI/Backend pattern
# ─────────────────────────────────────────────────────────────

def handle_exception(exc: Exception, context: dict | None = None) -> dict:
    """
    Centralized exception handler.
    Converts exceptions to API response format.
    Logs appropriately by severity.
    """
    context = context or {}

    if isinstance(exc, AppError):
        # Known application error — log as warning
        logger.warning(
            f"App error: {exc.code}",
            extra={"error_code": exc.code, "context": context}
        )
        return exc.to_dict()

    elif isinstance(exc, ValidationError):
        logger.info(f"Validation error: {exc}")
        return exc.to_dict()

    else:
        # Unknown error — log full traceback as error
        logger.error(
            f"Unexpected error: {type(exc).__name__}: {exc}",
            exc_info=True,
            extra={"context": context}
        )
        return {
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "status_code": 500,
        }

# Test
resp = handle_exception(NotFoundError("User", 42))
print(f"Response: {resp}")

resp = handle_exception(ValueError("unexpected problem"))
print(f"Response: {resp}")


# ─────────────────────────────────────────────────────────────
# 8. TRACEBACK — capturing and formatting
# ─────────────────────────────────────────────────────────────

import sys

def get_traceback_string(exc: Exception) -> str:
    """Get formatted traceback as string."""
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

try:
    1 / 0
except Exception as e:
    tb_str = get_traceback_string(e)
    # In production: store in Sentry, log to file, include in error response
    print(f"Traceback:\n{tb_str}")


# ─────────────────────────────────────────────────────────────
# 9. EXCEPTION GROUPS (Python 3.11+)
# ─────────────────────────────────────────────────────────────

# ExceptionGroup — multiple exceptions at once (used with TaskGroup)
# try:
#     async with asyncio.TaskGroup() as tg:
#         tg.create_task(failing_task())
#         tg.create_task(another_failing_task())
# except* ValueError as eg:
#     for exc in eg.exceptions:
#         print(f"ValueError: {exc}")
# except* ConnectionError as eg:
#     for exc in eg.exceptions:
#         print(f"ConnectionError: {exc}")


# ─────────────────────────────────────────────────────────────
# 10. BEST PRACTICES SUMMARY
# ─────────────────────────────────────────────────────────────
"""
DO:
  ✓ Be specific — catch the exact exception type
  ✓ Use custom exceptions with meaningful names and data
  ✓ Add context — raise ... from original_exc
  ✓ Log appropriately — debug/info/warning/error
  ✓ Use finally for cleanup (files, DB connections)
  ✓ Use contextlib.suppress for intentional suppression

DON'T:
  ✗ bare except: — catches EVERYTHING including KeyboardInterrupt
  ✗ except Exception: pass — silently swallows errors
  ✗ except Exception as e: print(e) — not enough context
  ✗ Re-raise with raise e — creates new traceback, use raise
  ✗ Use exceptions for flow control (slow, ugly)
"""

# WORST pattern (bare except):
# try:
#     something()
# except:              # catches KeyboardInterrupt, SystemExit, etc.!
#     pass

# BAD (too broad):
# try:
#     something()
# except Exception:   # catches way too much
#     pass

# GOOD:
# try:
#     result = int(user_input)
# except ValueError:   # exactly what can go wrong
#     result = 0

# INTERVIEW QUESTIONS
"""
Q: What is the difference between raise and raise e?
A: raise — re-raises current exception, preserving original traceback.
   raise e — creates a NEW exception with a new traceback (loses context).
   Always use bare 'raise' to re-raise in except blocks.

Q: When does the 'else' clause in try-except run?
A: The else clause runs only when no exception was raised in the try block.
   Use it for code that should run only on success (not in try to avoid
   masking exceptions).

Q: What does 'raise X from Y' do?
A: Creates explicit exception chaining.
   X.__cause__ = Y and X.__suppress_context__ = True.
   Tells Python: "X was caused by Y".
   'raise X from None' suppresses the original context entirely.

Q: What's the difference between finally and __exit__?
A: finally runs at end of try block, always.
   __exit__ is called by context manager when exiting 'with' block.
   Both guarantee cleanup, but __exit__ can receive exception info.
"""
