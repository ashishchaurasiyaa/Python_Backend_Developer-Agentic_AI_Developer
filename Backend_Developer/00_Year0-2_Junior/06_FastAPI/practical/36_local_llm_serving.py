"""
FastAPI — Local LLM Serving (vLLM, Ollama, llama.cpp, LiteLLM Proxy)

Production patterns for self-hosting open-source language models behind a
FastAPI gateway.  Covers:
  - Ollama: developer-friendly runtime with OpenAI-compatible API
  - vLLM: production-grade inference (PagedAttention, continuous batching)
  - llama.cpp: CPU-first GGUF quantized inference via Python binding
  - LiteLLM proxy: single endpoint routing across multiple backends
  - GPU sizing calculator
  - Prometheus observability (GPU + request metrics)
  - Streaming responses (SSE)
  - Tier-based model routing
  - Production gotchas

Prerequisites (install what you need):
    # pip install fastapi uvicorn openai httpx prometheus-client structlog
    # pip install vllm            # GPU inference server (requires CUDA)
    # pip install llama-cpp-python # llama.cpp Python bindings
    # pip install litellm[proxy]  # multi-backend proxy
    # pip install gputil          # GPU usage monitoring
    # brew install ollama         # macOS — or: curl -fsSL https://ollama.com/install.sh | sh

Quick-start:
    uvicorn 36_local_llm_serving:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import AsyncGenerator, Optional

import httpx
import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

# ==========================================================================
# 1. STRUCTURED LOGGING
# ==========================================================================

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ]
)
log = structlog.get_logger()


# ==========================================================================
# 2. CONFIGURATION — environment-driven, no hardcoded secrets
# ==========================================================================

class Config:
    """Central configuration sourced from environment variables."""

    # Ollama
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_DEFAULT_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    # vLLM
    VLLM_BASE_URL: str = os.getenv("VLLM_BASE_URL", "http://localhost:8000")
    VLLM_DEFAULT_MODEL: str = os.getenv(
        "VLLM_MODEL", "meta-llama/Llama-3.3-70B-Instruct"
    )

    # llama.cpp
    LLAMACPP_MODEL_PATH: str = os.getenv(
        "LLAMACPP_MODEL_PATH", "./qwen2.5-7b-q4_k_m.gguf"
    )

    # LiteLLM proxy
    LITELLM_BASE_URL: str = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
    LITELLM_MASTER_KEY: str = os.getenv("LITELLM_MASTER_KEY", "sk-1234")

    # Generation defaults
    DEFAULT_MAX_TOKENS: int = int(os.getenv("DEFAULT_MAX_TOKENS", "512"))
    DEFAULT_TEMPERATURE: float = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))


cfg = Config()


# ==========================================================================
# 3. PYDANTIC SCHEMAS
# ==========================================================================

class UserTier(str, Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: Optional[str] = None
    max_tokens: int = Field(cfg.DEFAULT_MAX_TOKENS, ge=1, le=8192)
    temperature: float = Field(cfg.DEFAULT_TEMPERATURE, ge=0.0, le=2.0)
    stream: bool = False


class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = Field(256, ge=1, le=4096)
    stop_sequences: list[str] = Field(default_factory=list)


class GPUSizingRequest(BaseModel):
    model_params_billions: float = Field(..., ge=0.1, description="Model size, e.g. 70 for Llama-70B")
    quantization: str = Field("fp16", pattern="^(fp16|int8|int4|fp8)$")
    context_length: int = Field(4096, ge=512, le=131072)
    concurrent_users: int = Field(8, ge=1, le=1024)


@dataclass
class GPUSizingResult:
    model_memory_gb: float
    kv_cache_gb_per_user: float
    total_memory_gb: float
    recommended_gpus: int
    notes: list[str] = field(default_factory=list)


# ==========================================================================
# 4. PROMETHEUS METRICS
# ==========================================================================

# Request-level metrics
llm_requests_total = Counter(
    "local_llm_requests_total",
    "Total LLM requests",
    ["backend", "model", "status"],
)
llm_ttft_seconds = Histogram(
    "local_llm_ttft_seconds",
    "Time to first token (seconds)",
    ["backend", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0),
)
llm_tokens_generated = Counter(
    "local_llm_tokens_generated_total",
    "Total output tokens generated",
    ["backend", "model"],
)
llm_active_requests = Gauge(
    "local_llm_active_requests",
    "Requests currently being processed",
    ["backend"],
)

# GPU-level metrics (populated by gpu_metrics_collector background task)
gpu_memory_used_bytes = Gauge(
    "gpu_memory_used_bytes", "GPU memory used", ["gpu_id"]
)
gpu_utilization_percent = Gauge(
    "gpu_utilization_percent", "GPU compute utilization", ["gpu_id"]
)
gpu_temp_celsius = Gauge(
    "gpu_temp_celsius", "GPU temperature in Celsius", ["gpu_id"]
)


# ==========================================================================
# 5. GPU METRICS BACKGROUND COLLECTOR
# ==========================================================================

async def gpu_metrics_collector(interval_seconds: int = 15) -> None:
    """
    Background task: poll GPUtil every `interval_seconds` and push to
    Prometheus gauges.  Falls back gracefully when GPUtil is not installed
    or no GPU is present (common on CPU-only dev machines).
    """
    try:
        import GPUtil  # pip install gputil
    except ImportError:
        log.warning("gpu_metrics_disabled", reason="GPUtil not installed; skipping GPU metrics")
        return

    log.info("gpu_metrics_collector_started", interval_s=interval_seconds)
    while True:
        try:
            for gpu in GPUtil.getGPUs():
                gpu_memory_used_bytes.labels(gpu_id=gpu.id).set(gpu.memoryUsed * 1_048_576)
                gpu_utilization_percent.labels(gpu_id=gpu.id).set(gpu.load * 100)
                gpu_temp_celsius.labels(gpu_id=gpu.id).set(gpu.temperature)
        except Exception as exc:
            log.error("gpu_metrics_error", error=str(exc))
        await asyncio.sleep(interval_seconds)


# ==========================================================================
# 6. LIFESPAN — startup / shutdown
# ==========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Launch GPU metrics collection as a background task.
    task = asyncio.create_task(gpu_metrics_collector())
    log.info("app_startup", ollama_url=cfg.OLLAMA_BASE_URL, vllm_url=cfg.VLLM_BASE_URL)
    yield
    task.cancel()
    log.info("app_shutdown")


app = FastAPI(
    title="Local LLM Serving Gateway",
    description="FastAPI proxy for vLLM, Ollama, llama.cpp and LiteLLM backends",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount Prometheus /metrics endpoint
metrics_asgi = make_asgi_app()
app.mount("/metrics", metrics_asgi)


# ==========================================================================
# 7. METRICS MIDDLEWARE
# ==========================================================================

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.monotonic()
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
    except Exception:
        status_code = "500"
        raise
    finally:
        duration = time.monotonic() - start
        # Only instrument /chat/* and /generate/* paths to keep cardinality low
        if request.url.path.startswith(("/chat", "/generate")):
            log.info(
                "request_complete",
                method=request.method,
                path=request.url.path,
                status=status_code,
                duration_ms=round(duration * 1000, 1),
            )
    return response


# ==========================================================================
# 8. OLLAMA BACKEND — developer-friendly, OpenAI-compatible
# ==========================================================================
#
# Ollama exposes an OpenAI-compatible REST API at :11434/v1.
# Best for: local development, experimentation, small teams (<10 RPS).
# Start: `ollama serve` then `ollama pull qwen2.5:7b`.

def get_ollama_client() -> "AsyncOpenAI":  # type: ignore[name-defined]
    """
    Return an AsyncOpenAI client pointed at the local Ollama server.
    Ollama accepts any non-empty string as the api_key.
    """
    from openai import AsyncOpenAI  # pip install openai

    return AsyncOpenAI(
        base_url=f"{cfg.OLLAMA_BASE_URL}/v1",
        api_key="ollama",
    )


@app.post("/chat/ollama", summary="Chat via Ollama (dev / local)")
async def chat_via_ollama(req: ChatRequest) -> dict:
    """
    Send a chat request to the local Ollama runtime.

    Ollama must be running (`ollama serve`) and the model must be pulled
    (`ollama pull qwen2.5:7b`).  Returns the assistant reply text.
    """
    model = req.model or cfg.OLLAMA_DEFAULT_MODEL
    client = get_ollama_client()

    llm_active_requests.labels(backend="ollama").inc()
    start = time.monotonic()
    first_token_at: Optional[float] = None

    try:
        if req.stream:
            # Streaming is handled by the /chat/ollama/stream endpoint below.
            raise HTTPException(status_code=400, detail="Use /chat/ollama/stream for streaming.")

        response = await client.chat.completions.create(
            model=model,
            messages=[m.model_dump() for m in req.messages],
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
        first_token_at = time.monotonic() - start
        llm_ttft_seconds.labels(backend="ollama", model=model).observe(first_token_at)

        content = response.choices[0].message.content or ""
        # Rough token count from usage object (Ollama provides this)
        out_tokens = getattr(response.usage, "completion_tokens", 0) or 0
        llm_tokens_generated.labels(backend="ollama", model=model).inc(out_tokens)
        llm_requests_total.labels(backend="ollama", model=model, status="success").inc()

        return {
            "text": content,
            "model": model,
            "backend": "ollama",
            "usage": {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", None),
                "completion_tokens": out_tokens,
            },
        }
    except Exception as exc:
        llm_requests_total.labels(backend="ollama", model=model, status="error").inc()
        log.error("ollama_error", error=str(exc), model=model)
        raise HTTPException(status_code=502, detail=f"Ollama error: {exc}") from exc
    finally:
        llm_active_requests.labels(backend="ollama").dec()


@app.post("/chat/ollama/stream", summary="Streaming chat via Ollama (SSE)")
async def stream_ollama(req: ChatRequest) -> StreamingResponse:
    """
    Server-Sent Events stream from Ollama.
    Each event is a raw text delta; the client accumulates them.
    """
    model = req.model or cfg.OLLAMA_DEFAULT_MODEL
    client = get_ollama_client()

    async def generate() -> AsyncGenerator[str, None]:
        llm_active_requests.labels(backend="ollama").inc()
        start = time.monotonic()
        first_chunk = True
        token_count = 0
        try:
            async with client.chat.completions.stream(
                model=model,
                messages=[m.model_dump() for m in req.messages],
                max_tokens=req.max_tokens,
                temperature=req.temperature,
            ) as stream:
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else ""
                    if delta:
                        if first_chunk:
                            ttft = time.monotonic() - start
                            llm_ttft_seconds.labels(backend="ollama", model=model).observe(ttft)
                            first_chunk = False
                        token_count += 1
                        yield f"data: {delta}\n\n"
            llm_tokens_generated.labels(backend="ollama", model=model).inc(token_count)
            llm_requests_total.labels(backend="ollama", model=model, status="success").inc()
            yield "data: [DONE]\n\n"
        except Exception as exc:
            llm_requests_total.labels(backend="ollama", model=model, status="error").inc()
            log.error("ollama_stream_error", error=str(exc))
            yield f"data: [ERROR] {exc}\n\n"
        finally:
            llm_active_requests.labels(backend="ollama").dec()

    return StreamingResponse(generate(), media_type="text/event-stream")


# ==========================================================================
# 9. VLLM BACKEND — production-grade, highest throughput
# ==========================================================================
#
# vLLM exposes an OpenAI-compatible API at :8000/v1.
# Start: python -m vllm.entrypoints.openai.api_server \
#            --model meta-llama/Llama-3.3-70B-Instruct \
#            --tensor-parallel-size 4 \
#            --quantization awq \
#            --enable-prefix-caching
#
# Key features: PagedAttention, continuous batching, prefix caching.

def get_vllm_client() -> "AsyncOpenAI":  # type: ignore[name-defined]
    """AsyncOpenAI client pointed at the vLLM server."""
    from openai import AsyncOpenAI  # pip install openai

    return AsyncOpenAI(
        base_url=f"{cfg.VLLM_BASE_URL}/v1",
        api_key="EMPTY",  # vLLM does not validate the key by default
    )


@app.post("/chat/vllm", summary="Chat via vLLM (production GPU serving)")
async def chat_via_vllm(req: ChatRequest) -> dict:
    """
    Forward a chat request to a running vLLM server.

    vLLM handles continuous batching automatically — no extra work needed
    from this proxy.  For multi-GPU tensor parallelism, configure vLLM at
    startup with --tensor-parallel-size N.
    """
    model = req.model or cfg.VLLM_DEFAULT_MODEL
    client = get_vllm_client()

    llm_active_requests.labels(backend="vllm").inc()
    start = time.monotonic()

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[m.model_dump() for m in req.messages],
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
        ttft = time.monotonic() - start
        llm_ttft_seconds.labels(backend="vllm", model=model).observe(ttft)

        content = response.choices[0].message.content or ""
        out_tokens = getattr(response.usage, "completion_tokens", 0) or 0
        llm_tokens_generated.labels(backend="vllm", model=model).inc(out_tokens)
        llm_requests_total.labels(backend="vllm", model=model, status="success").inc()

        return {
            "text": content,
            "model": model,
            "backend": "vllm",
            "ttft_seconds": round(ttft, 3),
            "usage": {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", None),
                "completion_tokens": out_tokens,
            },
        }
    except Exception as exc:
        llm_requests_total.labels(backend="vllm", model=model, status="error").inc()
        log.error("vllm_error", error=str(exc), model=model)
        raise HTTPException(status_code=502, detail=f"vLLM error: {exc}") from exc
    finally:
        llm_active_requests.labels(backend="vllm").dec()


# --------------------------------------------------------------------------
# vLLM programmatic Python API (used for batch offline inference, not HTTP)
# --------------------------------------------------------------------------

def vllm_batch_inference_example() -> None:
    """
    Illustrates the vLLM Python API for offline batch generation.
    Requires: pip install vllm  and a CUDA-capable GPU.
    Not invoked at runtime — shown here as a reference pattern.
    """
    from vllm import LLM, SamplingParams  # type: ignore  # pip install vllm

    llm = LLM(
        model="meta-llama/Llama-3.3-70B-Instruct",
        tensor_parallel_size=4,       # split across 4 GPUs
        quantization="awq",           # 4-bit AWQ: best quality/size tradeoff
        gpu_memory_utilization=0.95,  # leave 5% headroom
        enable_prefix_caching=True,   # reuse KV cache for shared system prompts
    )

    sampling = SamplingParams(
        temperature=0.7,
        max_tokens=512,
        top_p=0.95,
    )

    # vLLM batches all prompts automatically for maximum GPU utilisation.
    prompts = [f"Summarise paragraph {i}: ..." for i in range(100)]
    outputs = llm.generate(prompts, sampling)

    for output in outputs:
        print(output.outputs[0].text)


# ==========================================================================
# 10. LLAMA.CPP BACKEND — CPU / low-memory inference (GGUF quantized)
# ==========================================================================
#
# llama.cpp uses quantized GGUF model files that fit in CPU RAM.
# Suitable for: development, edge, and servers without GPUs.
# Download a GGUF model:
#   wget https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/\
#        qwen2.5-7b-instruct-q4_k_m.gguf
# Install binding: pip install llama-cpp-python

_llamacpp_model: Optional[object] = None  # lazy-loaded singleton


def get_llamacpp_model():
    """
    Lazy-load the llama.cpp model the first time it is requested.
    Thread-safe for read-only inference; do NOT reload between requests.
    """
    global _llamacpp_model
    if _llamacpp_model is not None:
        return _llamacpp_model

    try:
        from llama_cpp import Llama  # pip install llama-cpp-python

        _llamacpp_model = Llama(
            model_path=cfg.LLAMACPP_MODEL_PATH,
            n_ctx=4096,        # context window in tokens
            n_threads=8,       # CPU threads (tune to core count)
            n_gpu_layers=32,   # offload 32 layers to GPU; 0 = CPU only
            verbose=False,
        )
        log.info("llamacpp_model_loaded", path=cfg.LLAMACPP_MODEL_PATH)
        return _llamacpp_model
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="llama-cpp-python not installed. Run: pip install llama-cpp-python",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to load llama.cpp model: {exc}",
        ) from exc


@app.post("/generate/llamacpp", summary="Text generation via llama.cpp (CPU / GGUF)")
async def generate_via_llamacpp(req: GenerateRequest) -> dict:
    """
    Run raw text completion via the llama.cpp Python binding.

    The model is loaded once and reused.  Inference runs in a thread pool
    executor to avoid blocking the asyncio event loop during CPU-heavy work.
    """
    llm_active_requests.labels(backend="llamacpp").inc()
    start = time.monotonic()

    try:
        model = get_llamacpp_model()
        loop = asyncio.get_running_loop()

        # Run the synchronous (blocking) call in a thread pool.
        output = await loop.run_in_executor(
            None,
            lambda: model(  # type: ignore[operator]
                req.prompt,
                max_tokens=req.max_tokens,
                stop=req.stop_sequences or ["Q:", "\n\n"],
            ),
        )

        elapsed = time.monotonic() - start
        text = output["choices"][0]["text"]
        out_tokens = output.get("usage", {}).get("completion_tokens", 0)

        llm_ttft_seconds.labels(backend="llamacpp", model="gguf").observe(elapsed)
        llm_tokens_generated.labels(backend="llamacpp", model="gguf").inc(out_tokens)
        llm_requests_total.labels(backend="llamacpp", model="gguf", status="success").inc()

        return {
            "text": text,
            "backend": "llamacpp",
            "model_path": cfg.LLAMACPP_MODEL_PATH,
            "elapsed_seconds": round(elapsed, 3),
        }
    except HTTPException:
        raise
    except Exception as exc:
        llm_requests_total.labels(backend="llamacpp", model="gguf", status="error").inc()
        log.error("llamacpp_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        llm_active_requests.labels(backend="llamacpp").dec()


# ==========================================================================
# 11. LITELLM PROXY — multi-model routing + fallback
# ==========================================================================
#
# LiteLLM proxy aggregates multiple backends under a single OpenAI-compat API.
# Start: litellm --config litellm_config.yaml --port 4000
#
# Example litellm_config.yaml:
#
#   model_list:
#     - model_name: local-qwen-7b
#       litellm_params:
#         model: openai/qwen2.5:7b
#         api_base: http://ollama:11434/v1
#         api_key: EMPTY
#
#     - model_name: local-llama-70b
#       litellm_params:
#         model: openai/meta-llama/Llama-3.3-70B-Instruct
#         api_base: http://vllm-prod:8000/v1
#         api_key: EMPTY
#
#     - model_name: claude-fallback
#       litellm_params:
#         model: anthropic/claude-sonnet-4-6
#         api_key: os.environ/ANTHROPIC_API_KEY
#
#   router_settings:
#     routing_strategy: least-busy
#     fallbacks:
#       - local-llama-70b: ["claude-fallback"]
#
#   general_settings:
#     master_key: sk-1234

def get_litellm_client() -> "AsyncOpenAI":  # type: ignore[name-defined]
    """AsyncOpenAI client pointed at the LiteLLM proxy."""
    from openai import AsyncOpenAI  # pip install openai

    return AsyncOpenAI(
        base_url=f"{cfg.LITELLM_BASE_URL}/v1",
        api_key=cfg.LITELLM_MASTER_KEY,
    )


def _select_model_by_tier(tier: UserTier) -> str:
    """
    Map user tier to a LiteLLM model alias.

    Free users are routed to the lighter local model to protect GPU headroom.
    Pro/enterprise users get the high-quality 70B model.
    """
    return {
        UserTier.free: "local-qwen-7b",
        UserTier.pro: "local-llama-70b",
        UserTier.enterprise: "local-llama-70b",
    }[tier]


@app.post("/chat/proxy", summary="Tier-based chat via LiteLLM proxy")
async def chat_via_litellm_proxy(
    req: ChatRequest,
    user_tier: UserTier = UserTier.free,
) -> dict:
    """
    Route to a backend selected by the caller's user tier.

    - free       → local-qwen-7b (Ollama)
    - pro        → local-llama-70b (vLLM)
    - enterprise → local-llama-70b (vLLM, high priority queue)

    LiteLLM transparently falls back to the cloud model (claude-fallback)
    if the primary local backend returns a 5xx error.
    """
    model = req.model or _select_model_by_tier(user_tier)
    client = get_litellm_client()

    llm_active_requests.labels(backend="litellm").inc()
    start = time.monotonic()

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[m.model_dump() for m in req.messages],
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
        ttft = time.monotonic() - start
        llm_ttft_seconds.labels(backend="litellm", model=model).observe(ttft)

        content = response.choices[0].message.content or ""
        out_tokens = getattr(response.usage, "completion_tokens", 0) or 0
        llm_tokens_generated.labels(backend="litellm", model=model).inc(out_tokens)
        llm_requests_total.labels(backend="litellm", model=model, status="success").inc()

        return {
            "text": content,
            "model": model,
            "backend": "litellm",
            "user_tier": user_tier,
            "ttft_seconds": round(ttft, 3),
        }
    except Exception as exc:
        llm_requests_total.labels(backend="litellm", model=model, status="error").inc()
        log.error("litellm_error", error=str(exc), model=model)
        raise HTTPException(status_code=502, detail=f"LiteLLM proxy error: {exc}") from exc
    finally:
        llm_active_requests.labels(backend="litellm").dec()


# ==========================================================================
# 12. GPU SIZING CALCULATOR
# ==========================================================================
#
# Memory math:
#   Model memory ≈ params × bytes_per_param
#     FP16  → 2 bytes/param  → 70B = 140 GB
#     INT8  → 1 byte/param   → 70B =  70 GB
#     INT4  → 0.5 bytes/param → 70B = 35 GB
#     FP8   → 1 byte/param   → 70B =  70 GB (H100-optimised)
#
#   KV cache per request ≈ 4 GB for 70B model at 8K context (rough estimate)

BYTES_PER_PARAM: dict[str, float] = {
    "fp16": 2.0,
    "int8": 1.0,
    "int4": 0.5,
    "fp8": 1.0,
}

A100_VRAM_GB = 80.0  # A100 80 GB SXM4


def calculate_gpu_sizing(req: GPUSizingRequest) -> GPUSizingResult:
    """
    Estimate minimum GPU memory and number of A100 80GB GPUs needed.

    Formula:
        model_memory = params_B × 1e9 × bytes_per_param / 1e9  (GB)
        kv_per_user  ≈ 0.5 GB per 1K context per 7B params (heuristic)
        total        = model_memory + kv_per_user × concurrent_users
        gpus_needed  = ceil(total × 1.1 / A100_VRAM_GB)  (10% overhead)
    """
    import math

    bytes_per = BYTES_PER_PARAM[req.quantization]
    model_gb = req.model_params_billions * bytes_per  # 1B params × bytes = GB

    # KV cache heuristic: scales with context, model size, and concurrency
    kv_per_user_gb = (req.context_length / 8192) * (req.model_params_billions / 70) * 4.0
    total_kv_gb = kv_per_user_gb * req.concurrent_users

    total_gb = model_gb + total_kv_gb
    gpus_needed = math.ceil(total_gb * 1.1 / A100_VRAM_GB)  # 10% memory headroom

    notes: list[str] = []
    if req.quantization == "fp16" and req.model_params_billions >= 70:
        notes.append("FP16 70B+ models require 2+ A100s; consider AWQ INT4 for single-GPU.")
    if req.quantization == "int4":
        notes.append("AWQ INT4 recommended over GPTQ for best quality/size ratio.")
    if req.concurrent_users > 64:
        notes.append("High concurrency: enable continuous batching (vLLM default).")
    if req.model_params_billions <= 7:
        notes.append("7B models fit on a single T4 16GB (INT4); A100 is overkill.")

    return GPUSizingResult(
        model_memory_gb=round(model_gb, 1),
        kv_cache_gb_per_user=round(kv_per_user_gb, 2),
        total_memory_gb=round(total_gb, 1),
        recommended_gpus=max(1, gpus_needed),
        notes=notes,
    )


@app.post("/tools/gpu-sizing", summary="Estimate GPU count for a model configuration")
async def gpu_sizing_endpoint(req: GPUSizingRequest) -> dict:
    """
    Return an estimate of how many A100 80GB GPUs are required to serve a
    model at the given quantization and concurrency level.
    """
    result = calculate_gpu_sizing(req)
    return {
        "model_params_b": req.model_params_billions,
        "quantization": req.quantization,
        "concurrent_users": req.concurrent_users,
        "context_length": req.context_length,
        "model_memory_gb": result.model_memory_gb,
        "kv_cache_gb_per_user": result.kv_cache_gb_per_user,
        "total_memory_gb": result.total_memory_gb,
        "recommended_a100_80gb_gpus": result.recommended_gpus,
        "notes": result.notes,
    }


# ==========================================================================
# 13. HEALTH CHECK — with backend reachability probes
# ==========================================================================

@app.get("/health", summary="Health check (liveness)")
async def health_check() -> dict:
    """
    Liveness probe.  Returns 200 immediately — used by Kubernetes to detect
    that the container process is alive.  Does NOT check backend availability.
    """
    return {"status": "ok"}


@app.get("/health/ready", summary="Readiness probe (checks backends)")
async def readiness_check() -> dict:
    """
    Readiness probe.  Calls /api/tags on Ollama and /health on vLLM to verify
    that at least one backend is reachable before accepting traffic.
    """
    backends: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=3.0) as client:
        # Ollama health
        try:
            r = await client.get(f"{cfg.OLLAMA_BASE_URL}/api/tags")
            backends["ollama"] = "ok" if r.status_code == 200 else f"http_{r.status_code}"
        except Exception as exc:
            backends["ollama"] = f"unreachable: {exc}"

        # vLLM health
        try:
            r = await client.get(f"{cfg.VLLM_BASE_URL}/health")
            backends["vllm"] = "ok" if r.status_code == 200 else f"http_{r.status_code}"
        except Exception as exc:
            backends["vllm"] = f"unreachable: {exc}"

    all_ok = any(v == "ok" for v in backends.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        content={"status": "ready" if all_ok else "degraded", "backends": backends},
        status_code=status_code,
    )


# ==========================================================================
# 14. QUANTIZATION REFERENCE TABLE ENDPOINT
# ==========================================================================

QUANTIZATION_TABLE = [
    {"format": "FP16",    "size_multiplier": 2.0,  "mmlu_vs_fp16": "baseline", "speed_vs_fp16": "1.0x", "use_case": "Maximum quality, abundant GPU memory"},
    {"format": "FP8",     "size_multiplier": 1.0,  "mmlu_vs_fp16": "-0.2%",    "speed_vs_fp16": "1.5x", "use_case": "H100/H200 hardware-accelerated"},
    {"format": "AWQ INT4","size_multiplier": 0.5,  "mmlu_vs_fp16": "-1.5%",    "speed_vs_fp16": "2.0x", "use_case": "Production recommended (best quality/size)"},
    {"format": "GPTQ INT4","size_multiplier": 0.5, "mmlu_vs_fp16": "-1.8%",    "speed_vs_fp16": "1.9x", "use_case": "Older alternative to AWQ"},
    {"format": "GGUF Q4_K_M","size_multiplier":0.57,"mmlu_vs_fp16": "-1.2%",   "speed_vs_fp16": "varies","use_case": "llama.cpp CPU inference"},
    {"format": "GGUF Q2_K","size_multiplier": 0.36,"mmlu_vs_fp16": "-7%",      "speed_vs_fp16": "2.5x", "use_case": "Embedded only — quality loss significant"},
]


@app.get("/reference/quantization", summary="Quantization format comparison table")
async def quantization_reference() -> dict:
    """Return the quantization comparison table from the theory doc."""
    return {"quantization_formats": QUANTIZATION_TABLE}


# ==========================================================================
# 15. PRODUCTION GOTCHAS REFERENCE ENDPOINT
# ==========================================================================

PRODUCTION_GOTCHAS = [
    {"gotcha": "Model load takes 5+ minutes on pod start",
     "fix": "Set generous readinessProbe initialDelaySeconds (300+) in Kubernetes"},
    {"gotcha": "OOM under burst load",
     "fix": "Set --max-num-seqs conservatively in vLLM; use HPA to scale out"},
    {"gotcha": "KV cache fragmentation",
     "fix": "Use PagedAttention — this is vLLM's default behaviour"},
    {"gotcha": "Long context inputs consume excessive memory",
     "fix": "Cap --max-model-len; chunk long inputs at the application layer"},
    {"gotcha": "Stale model after fine-tuning",
     "fix": "Use versioned model paths and a blue/green deployment strategy"},
    {"gotcha": "Quantization breaks tool/function calling",
     "fix": "Test tool-use benchmarks after every quantization change"},
    {"gotcha": "Cold start latency spikes",
     "fix": "Keep min replicas >= 2; use PVC to cache model weights locally"},
    {"gotcha": "Tokenizer mismatch between local and remote endpoints",
     "fix": "Pin exact tokenizer version; always verify with a known test prompt"},
]


@app.get("/reference/gotchas", summary="Production gotchas and their fixes")
async def production_gotchas() -> dict:
    """Return the production gotchas table from the theory doc."""
    return {"gotchas": PRODUCTION_GOTCHAS}


# ==========================================================================
# 16. DECISION HELPER — which backend should I use?
# ==========================================================================

class InfraScenario(str, Enum):
    dev_experimentation = "dev_experimentation"
    production_scale = "production_scale"
    cpu_only = "cpu_only"
    huggingface_ecosystem = "huggingface_ecosystem"
    apple_silicon = "apple_silicon"
    edge_embedded = "edge_embedded"
    multi_model_serving = "multi_model_serving"


BACKEND_DECISION: dict[InfraScenario, dict] = {
    InfraScenario.dev_experimentation: {
        "backend": "Ollama",
        "reason": "Trivial one-command setup, automatic model management, OpenAI-compatible API.",
    },
    InfraScenario.production_scale: {
        "backend": "vLLM",
        "reason": "PagedAttention + continuous batching = highest open-source throughput.",
    },
    InfraScenario.cpu_only: {
        "backend": "llama.cpp",
        "reason": "C++ CPU-first engine; GGUF quantized models run on commodity hardware.",
    },
    InfraScenario.huggingface_ecosystem: {
        "backend": "TGI (Text Generation Inference)",
        "reason": "Deep Hugging Face integration, safetensors, PEFT adapters.",
    },
    InfraScenario.apple_silicon: {
        "backend": "Ollama (MLX backend)",
        "reason": "Ollama auto-selects MLX on M-series Macs for Metal GPU acceleration.",
    },
    InfraScenario.edge_embedded: {
        "backend": "llama.cpp (GGUF Q4_K_M)",
        "reason": "Smallest footprint; runs on Raspberry Pi 5 or a 16 GB laptop.",
    },
    InfraScenario.multi_model_serving: {
        "backend": "vLLM + LiteLLM proxy",
        "reason": "LiteLLM routes across vLLM / Ollama / cloud APIs with fallback and cost tracking.",
    },
}


@app.get("/reference/backend-decision", summary="Which local LLM backend should I use?")
async def backend_decision(scenario: InfraScenario) -> dict:
    """
    Return the recommended backend for a given infrastructure scenario,
    mirroring the decision matrix in the theory doc.
    """
    rec = BACKEND_DECISION[scenario]
    return {"scenario": scenario, **rec}


# ==========================================================================
# 17. STARTUP SELF-CHECK — warn about missing optional dependencies
# ==========================================================================

@app.on_event("startup")
async def startup_dependency_check() -> None:
    """Emit warnings at startup for commonly missing optional packages."""
    optional_packages = {
        "openai": "OpenAI-compat client (Ollama + vLLM + LiteLLM routes)",
        "llama_cpp": "llama.cpp Python binding (/generate/llamacpp route)",
        "GPUtil": "GPU metrics collector",
        "structlog": "Structured logging",
        "prometheus_client": "Prometheus /metrics endpoint",
    }
    for pkg, purpose in optional_packages.items():
        try:
            __import__(pkg)
        except ImportError:
            logging.warning("OPTIONAL PACKAGE MISSING: %s (%s). pip install %s", pkg, purpose, pkg)


# ==========================================================================
# 18. ILLUSTRATIVE: VLLM PROGRAMMATIC BATCH (OFFLINE) SNIPPET
# ==========================================================================

VLLM_BATCH_SNIPPET = '''
# Run offline batch inference with the vLLM Python API (not via HTTP).
# Requires: pip install vllm   and  a CUDA GPU.
#
#   from vllm import LLM, SamplingParams
#
#   llm = LLM(
#       model="meta-llama/Llama-3.3-70B-Instruct",
#       tensor_parallel_size=4,
#       quantization="awq",
#       gpu_memory_utilization=0.95,
#       enable_prefix_caching=True,   # share KV cache for system prompts
#   )
#   sampling = SamplingParams(temperature=0.7, max_tokens=512, top_p=0.95)
#   outputs  = llm.generate(["Prompt A", "Prompt B", ...], sampling)
#   for o in outputs:
#       print(o.outputs[0].text)
'''


@app.get("/reference/vllm-batch-snippet", summary="vLLM offline batch inference code snippet")
async def vllm_batch_snippet() -> dict:
    """Return the vLLM offline batch inference snippet for developer reference."""
    return {"snippet": VLLM_BATCH_SNIPPET.strip()}


# ==========================================================================
# 19. KUBERNETES YAML REFERENCE SNIPPET
# ==========================================================================

K8S_DEPLOYMENT_NOTES = {
    "image": "vllm/vllm-openai:v0.6.0",
    "key_settings": {
        "tensor-parallel-size": 2,
        "quantization": "awq",
        "max-num-seqs": 128,
        "enable-prefix-caching": True,
    },
    "gpu_resource": "nvidia.com/gpu: 2",
    "readiness_probe": {
        "path": "/health",
        "initialDelaySeconds": 300,   # model load takes 5 minutes
        "periodSeconds": 10,
    },
    "hpa": {
        "metric": "vllm_running_requests",
        "target_average_value": 100,
        "min_replicas": 2,
        "max_replicas": 10,
    },
    "model_cache": "PersistentVolumeClaim mounted at /root/.cache/huggingface",
}


@app.get("/reference/k8s-notes", summary="Key Kubernetes deployment notes for vLLM")
async def k8s_notes() -> dict:
    """Return Kubernetes configuration notes for a vLLM GPU deployment."""
    return K8S_DEPLOYMENT_NOTES


# ==========================================================================
# MAIN — demonstration mode
# ==========================================================================

if __name__ == "__main__":
    import uvicorn  # pip install uvicorn

    print(__doc__)
    print("=" * 70)
    print("Running in demonstration mode — external LLM backends are optional.")
    print("Available routes:")
    print("  POST /chat/ollama          — Ollama (start: ollama serve)")
    print("  POST /chat/ollama/stream   — Streaming SSE via Ollama")
    print("  POST /chat/vllm            — vLLM (start: python -m vllm.entrypoints...)")
    print("  POST /generate/llamacpp    — llama.cpp (GGUF model file required)")
    print("  POST /chat/proxy           — LiteLLM proxy (start: litellm --config ...)")
    print("  POST /tools/gpu-sizing     — GPU count estimator (no external deps)")
    print("  GET  /health               — Liveness probe")
    print("  GET  /health/ready         — Readiness probe (checks backends)")
    print("  GET  /metrics              — Prometheus metrics")
    print("  GET  /reference/quantization")
    print("  GET  /reference/gotchas")
    print("  GET  /reference/backend-decision?scenario=dev_experimentation")
    print("  GET  /docs                 — Swagger UI")
    print("=" * 70)

    uvicorn.run(
        "36_local_llm_serving:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
