# HTTP Clients Complete — requests, httpx, aiohttp

## Quick Concepts

**WHAT:**
- **requests** = Sync HTTP client (most popular)
- **httpx** = Modern sync + async (FastAPI's default)
- **aiohttp** = Async HTTP client + server
- **urllib3** = Low-level (used internally by requests)
- **HTTP/2** = Multiplexing, header compression (httpx supports)
- **Connection pooling** = Reuse TCP connections (faster)

**WHY HTTP clients matter:**
- Every backend talks to other services (REST API, webhooks)
- Wrong client choice = performance issues
- Bad retry/timeout = cascading failures

**HOW comparison:**

```
┌──────────┬─────────┬──────────────┬───────────────┐
│ Library  │ Sync    │ Async        │ HTTP/2        │
├──────────┼─────────┼──────────────┼───────────────┤
│ requests │ ✅      │ ❌           │ ❌            │
│ httpx    │ ✅      │ ✅           │ ✅            │
│ aiohttp  │ ❌      │ ✅           │ Limited       │
│ urllib3  │ ✅      │ ❌ (low-lvl) │ ❌            │
└──────────┴─────────┴──────────────┴───────────────┘
```

---

## Interview Questions & Answers

### Q1: requests vs httpx — kab kya use karein?

**Answer:**

**HOW — Decision matrix:**

| Use case | Best choice | Why |
|---|---|---|
| Sync scripts, simple API calls | `requests` | Battle-tested, huge ecosystem |
| FastAPI app (async) | `httpx` | Async support, HTTP/2 |
| Hybrid app (sync + async) | `httpx` | Same API for both |
| Streaming responses | `httpx` or `aiohttp` | Better stream support |
| Very high RPS async | `aiohttp` | Slightly faster than httpx |
| Need HTTP/2 | `httpx` | Built-in |
| Mock-friendly | `httpx` | `respx` library |

**HOW — requests basic:**

```python
import requests

# GET
response = requests.get("https://api.example.com/users/1")
print(response.status_code)  # 200
print(response.json())  # {"id": 1, "name": "Alice"}

# POST with JSON
response = requests.post(
    "https://api.example.com/users",
    json={"name": "Bob"},
    headers={"Authorization": "Bearer token"},
    timeout=10,  # ⭐ ALWAYS set timeout
)

# Query params
response = requests.get(
    "https://api.example.com/search",
    params={"q": "python", "limit": 10}
)
```

**HOW — httpx (sync — drop-in replacement):**

```python
import httpx

# Same API as requests
response = httpx.get("https://api.example.com/users/1", timeout=10)

# ⭐ But also async!
async def fetch_user():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/users/1")
        return response.json()
```

---

### Q2: Connection pooling — kyu zaruri hai?

**Answer:**

**WHAT:** Reuse TCP connections instead of opening new for each request.

**WHY:**
```
Without pooling:
Each request: DNS lookup + TCP handshake + TLS handshake + request
Average: 200-500ms overhead per request

With pooling:
First request: full handshake (200-500ms)
Subsequent: reuse connection (~5ms)

10x faster for repeated calls to same host!
```

**HOW — requests with Session (pooling):**

```python
import requests

# ❌ BAD: New connection every time
for i in range(100):
    response = requests.get(f"https://api.example.com/items/{i}")
    # Each call: full handshake

# ✅ GOOD: Session reuses connections
session = requests.Session()
for i in range(100):
    response = session.get(f"https://api.example.com/items/{i}")
    # First call: full handshake
    # Rest: reuse TCP connection
```

**HOW — httpx Client (pooling):**

```python
# ❌ BAD: per-request client
for i in range(100):
    with httpx.Client() as client:
        response = client.get(...)

# ✅ GOOD: shared client
client = httpx.Client(
    limits=httpx.Limits(
        max_keepalive_connections=20,
        max_connections=100,
    )
)
try:
    for i in range(100):
        response = client.get(...)
finally:
    client.close()


# ✅ Better: context manager
with httpx.Client(limits=httpx.Limits(max_connections=100)) as client:
    for i in range(100):
        response = client.get(...)


# ✅ Async version
async with httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    timeout=httpx.Timeout(10.0, connect=5.0),
    follow_redirects=True,
) as client:
    response = await client.get("https://api.example.com/users")
```

---

### Q3: Timeouts — production patterns?

**Answer:**

**WHAT:** Limit time spent waiting for response.

**WHY:**
- No timeout = thread hangs forever
- Goroutine/connection leak
- Cascading failures

**HOW — requests timeouts:**

```python
import requests

# ❌ BAD: no timeout (default = no timeout!)
response = requests.get("https://slow-api.example.com")

# ✅ GOOD: single timeout for everything
response = requests.get("https://api.example.com", timeout=10)

# ✅ BETTER: separate connect + read timeouts
response = requests.get(
    "https://api.example.com",
    timeout=(5, 30)  # (connect_timeout, read_timeout)
)
```

**HOW — httpx timeouts (more granular):**

```python
import httpx

# ⭐ Granular control
timeout = httpx.Timeout(
    timeout=10.0,    # Default for all operations
    connect=5.0,     # TCP connection
    read=30.0,       # Read response
    write=5.0,       # Write request body
    pool=5.0,        # Wait for connection from pool
)

response = httpx.get("https://api.example.com", timeout=timeout)


# Per-request override
async with httpx.AsyncClient(timeout=timeout) as client:
    # Quick endpoint
    fast_resp = await client.get("/fast", timeout=2.0)

    # Slow endpoint
    slow_resp = await client.get("/slow", timeout=60.0)
```

**HOW — Async timeout (asyncio):**

```python
import asyncio
import httpx

async def fetch_with_timeout():
    try:
        # ⭐ Python 3.11+
        async with asyncio.timeout(5.0):
            async with httpx.AsyncClient() as client:
                response = await client.get("https://api.example.com")
                return response.json()
    except asyncio.TimeoutError:
        return {"error": "timeout"}
```

---

### Q4: Retries with exponential backoff?

**Answer:**

**WHAT:** Retry failed requests with increasing delay.

**WHY:**
- Transient errors (network blip, 503)
- Without backoff = thundering herd
- With jitter = avoid synchronized retries

**HOW — requests with `tenacity`:**

```python
# pip install tenacity

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)
import requests

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=10),
    retry=retry_if_exception_type((
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    )),
    reraise=True,
)
def fetch_user(user_id):
    response = requests.get(
        f"https://api.example.com/users/{user_id}",
        timeout=10
    )
    response.raise_for_status()
    return response.json()


# Or with httpx async
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=30),
)
async def fetch_user_async(user_id):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/users/{user_id}")
        response.raise_for_status()
        return response.json()
```

**HOW — httpx with built-in transport retries:**

```python
import httpx

# Built-in: retry on connection errors (not application errors)
transport = httpx.AsyncHTTPTransport(retries=3)

async with httpx.AsyncClient(transport=transport) as client:
    response = await client.get("https://api.example.com")
```

**HOW — Custom retry logic:**

```python
import asyncio
import random

async def fetch_with_retry(url, max_attempts=5):
    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            # Retry only on 5xx
            if e.response.status_code < 500:
                raise  # 4xx = client error, don't retry
            if attempt == max_attempts:
                raise

        except (httpx.ConnectError, httpx.TimeoutException):
            if attempt == max_attempts:
                raise

        # ⭐ Exponential backoff with jitter
        backoff = min(2 ** attempt, 30) + random.uniform(0, 1)
        await asyncio.sleep(backoff)
```

---

### Q5: Authentication patterns?

**Answer:**

**HOW — Bearer token:**

```python
import httpx

# Per-request
response = httpx.get(
    "https://api.example.com/protected",
    headers={"Authorization": "Bearer eyJhbGc..."}
)

# All requests in client (preferred)
client = httpx.AsyncClient(
    headers={"Authorization": f"Bearer {token}"},
)
```

**HOW — Basic auth:**

```python
# Tuple
response = httpx.get(
    "https://api.example.com",
    auth=("username", "password")
)

# Or httpx.BasicAuth
auth = httpx.BasicAuth(username="user", password="pass")
response = httpx.get("https://api.example.com", auth=auth)
```

**HOW — OAuth2 with auto refresh:**

```python
import httpx
import time

class OAuth2Auth(httpx.Auth):
    """Custom auth class with token refresh."""
    requires_response_body = True

    def __init__(self, client_id, client_secret, token_url):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.token = None
        self.expires_at = 0

    def auth_flow(self, request):
        # Get/refresh token
        if not self.token or time.time() > self.expires_at - 60:
            response = yield self._build_token_request()
            data = response.json()
            self.token = data["access_token"]
            self.expires_at = time.time() + data["expires_in"]

        # Add to request
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request

    def _build_token_request(self):
        return httpx.Request(
            "POST",
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
        )


# Usage
auth = OAuth2Auth(
    client_id="my-service",
    client_secret="...",
    token_url="https://auth.example.com/oauth/token"
)

async with httpx.AsyncClient(auth=auth) as client:
    response = await client.get("https://api.example.com/data")
    # Auto-refreshes token!
```

**HOW — API key in query:**

```python
# Method 1: params
response = httpx.get(
    "https://api.example.com",
    params={"api_key": "secret"}
)

# Method 2: in URL
url = "https://api.example.com?api_key=secret"

# Method 3: header (better!)
response = httpx.get(
    "https://api.example.com",
    headers={"X-API-Key": "secret"}
)
```

---

### Q6: Streaming large responses?

**Answer:**

**WHAT:** Read response in chunks (don't load entire body to memory).

**WHY:**
- Large files (videos, datasets)
- Server-Sent Events
- LLM token streaming
- CSV/JSON-lines parsing

**HOW — Stream download:**

```python
import httpx

# ❌ BAD: loads entire file in memory
response = httpx.get("https://example.com/huge-file.zip")
with open("file.zip", "wb") as f:
    f.write(response.content)


# ✅ GOOD: stream
with httpx.stream("GET", "https://example.com/huge-file.zip") as response:
    with open("file.zip", "wb") as f:
        for chunk in response.iter_bytes(chunk_size=8192):
            f.write(chunk)


# ⭐ Async streaming
async def download_file():
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", "https://example.com/huge.zip") as response:
            async with aiofiles.open("file.zip", "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    await f.write(chunk)
```

**HOW — Stream JSON lines:**

```python
async def stream_users():
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", "https://api.example.com/users.jsonl") as response:
            async for line in response.aiter_lines():
                user = json.loads(line)
                yield user
```

**HOW — Stream Server-Sent Events:**

```python
async def stream_llm_response(prompt):
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            json={"model": "gpt-4", "messages": [{"role": "user", "content": prompt}], "stream": True},
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=httpx.Timeout(60.0),
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    yield chunk["choices"][0]["delta"].get("content", "")


# Usage
async for token in stream_llm_response("Tell me a joke"):
    print(token, end="", flush=True)
```

---

### Q7: aiohttp vs httpx — production differences?

**Answer:**

**HOW — aiohttp (server + client):**

```python
import aiohttp
import asyncio

async def main():
    async with aiohttp.ClientSession() as session:
        # GET
        async with session.get("https://api.example.com") as response:
            data = await response.json()

        # POST
        async with session.post(
            "https://api.example.com/users",
            json={"name": "Alice"},
            headers={"Authorization": "Bearer token"},
        ) as response:
            result = await response.json()

asyncio.run(main())
```

**Key differences:**

| Feature | httpx | aiohttp |
|---|---|---|
| API | Like requests | Different |
| Sync support | ✅ | ❌ |
| HTTP/2 | ✅ | Limited |
| WebSocket | Limited | ✅ Built-in |
| Server | ❌ Client only | ✅ Has server too |
| Performance | Good | Slightly faster |
| Use case | FastAPI ecosystem | aiohttp server stack |

**HOW — aiohttp WebSocket:**

```python
import aiohttp

async def websocket_client():
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect("wss://echo.example.com") as ws:
            await ws.send_str("Hello!")

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    print(f"Received: {msg.data}")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
```

---

### Q8: Production patterns — connection pool tuning?

**Answer:**

**HOW — httpx production setup:**

```python
import httpx
import asyncio

# Production-ready async client
class HTTPClient:
    """Singleton HTTP client for the app."""
    _client: httpx.AsyncClient = None

    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(
                # Connection limits
                limits=httpx.Limits(
                    max_keepalive_connections=100,  # Keep 100 idle
                    max_connections=200,             # Total max
                    keepalive_expiry=30.0,           # 30s idle keepalive
                ),

                # Timeouts
                timeout=httpx.Timeout(
                    timeout=30.0,
                    connect=10.0,
                    read=30.0,
                ),

                # Auto-retry on transport errors
                transport=httpx.AsyncHTTPTransport(retries=2),

                # HTTP/2
                http2=True,  # ⭐ Multiplexing — single connection multiple requests

                # Follow redirects
                follow_redirects=True,
                max_redirects=5,

                # Verify SSL
                verify=True,

                # Default headers
                headers={
                    "User-Agent": "MyApp/1.0",
                    "Accept-Encoding": "gzip, deflate",
                },
            )
        return cls._client

    @classmethod
    async def close(cls):
        if cls._client:
            await cls._client.aclose()


# FastAPI lifespan
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await HTTPClient.close()

app = FastAPI(lifespan=lifespan)


# Use anywhere
@app.get("/external-call")
async def call_external():
    client = await HTTPClient.get_client()
    response = await client.get("https://api.example.com")
    return response.json()
```

---

### Q9: Mocking HTTP in tests?

**Answer:**

**HOW — responses library (for requests):**

```python
# pip install responses

import responses
import requests

@responses.activate
def test_get_user():
    responses.add(
        responses.GET,
        "https://api.example.com/users/1",
        json={"id": 1, "name": "Alice"},
        status=200,
    )

    response = requests.get("https://api.example.com/users/1")
    assert response.json()["name"] == "Alice"
    assert len(responses.calls) == 1
```

**HOW — respx (for httpx):**

```python
# pip install respx

import respx
import httpx
import pytest

@pytest.mark.asyncio
@respx.mock
async def test_async_call():
    route = respx.get("https://api.example.com/users/1").mock(
        return_value=httpx.Response(200, json={"id": 1, "name": "Alice"})
    )

    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/users/1")

    assert response.json()["name"] == "Alice"
    assert route.called
```

**HOW — VCR (record/replay real responses):**

```python
# pip install vcrpy

import vcr
import requests

# First run: records real response to YAML
# Subsequent runs: replays from cassette
@vcr.use_cassette("cassettes/test_users.yaml")
def test_get_users():
    response = requests.get("https://api.example.com/users")
    assert response.status_code == 200
```

---

### Q10: Debugging HTTP requests?

**Answer:**

**HOW — Enable debug logging:**

```python
import httpx
import logging

# httpx logs
logging.basicConfig(level=logging.DEBUG)
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.DEBUG)


# requests logs
import logging
import http.client as http_client

http_client.HTTPConnection.debuglevel = 1
logging.basicConfig(level=logging.DEBUG)
requests_log = logging.getLogger("urllib3")
requests_log.setLevel(logging.DEBUG)
```

**HOW — httpx event hooks (middleware):**

```python
import httpx
import time

async def log_request(request: httpx.Request):
    print(f"→ {request.method} {request.url}")
    request.extensions["start_time"] = time.time()

async def log_response(response: httpx.Response):
    duration = time.time() - response.request.extensions["start_time"]
    print(f"← {response.status_code} ({duration:.2f}s)")

client = httpx.AsyncClient(
    event_hooks={
        "request": [log_request],
        "response": [log_response],
    }
)
```

**HOW — Proxy through mitmproxy for debugging:**

```bash
# Install + run
brew install mitmproxy
mitmproxy --listen-port 8080
```

```python
# Route requests through proxy
proxies = {"http://": "http://localhost:8080", "https://": "http://localhost:8080"}

# requests
response = requests.get("https://api.example.com", proxies=proxies, verify=False)

# httpx
client = httpx.Client(proxies=proxies, verify=False)
```

---

## HTTP Client Checklist

```markdown
### Configuration
- [ ] Always set timeout (NEVER unbounded)
- [ ] Use Session/Client (not per-request)
- [ ] Configure connection limits
- [ ] Enable HTTP/2 if supported
- [ ] Set proper User-Agent

### Reliability
- [ ] Retry on transient errors (5xx, timeouts)
- [ ] Exponential backoff with jitter
- [ ] NOT retry on 4xx (client errors)
- [ ] Circuit breaker for failing services

### Performance
- [ ] Connection pooling (keepalive)
- [ ] Use async for I/O bound (httpx/aiohttp)
- [ ] Stream large responses
- [ ] Enable gzip compression
- [ ] HTTP/2 for multiple requests

### Security
- [ ] Verify TLS certificates (verify=True)
- [ ] Don't log auth headers
- [ ] Validate redirect URLs
- [ ] Use OAuth2 for tokens (auto refresh)
- [ ] Don't expose internal services

### Testing
- [ ] Mock HTTP in unit tests (respx/responses)
- [ ] VCR for integration tests
- [ ] Test timeout/retry behavior
- [ ] Test auth failure paths
```

---

## Library Decision Matrix

| You need to... | Use |
|---|---|
| Quick script with HTTP | requests |
| Async FastAPI app | httpx |
| WebSocket client | aiohttp or websockets |
| HTTP/2 | httpx |
| Sync + Async same codebase | httpx |
| Production async server | aiohttp or FastAPI |
| Mock in tests | respx (httpx) or responses |
| Record real responses | vcrpy |

---

## Performance Benchmarks (rough numbers)

```
Test: 1000 GET requests to same host

requests (no Session):        ~50 seconds (full handshake each)
requests + Session:           ~10 seconds
httpx (sync) + Client:        ~10 seconds
httpx (async) + AsyncClient:  ~3 seconds
aiohttp:                       ~2.5 seconds
httpx with HTTP/2:             ~1.5 seconds (multiplexing!)
```
