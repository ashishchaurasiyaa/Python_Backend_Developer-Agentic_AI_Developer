# gRPC-Web — Browser Clients, Envoy Proxy, Connect-RPC

## Quick Concepts

**WHAT:**
- **gRPC-Web** = gRPC for browsers (subset, needs proxy)
- **Envoy** = L7 proxy that translates gRPC-Web ↔ gRPC
- **Connect-RPC** = Buf's modern alternative (native browser support)
- **protoc-gen-grpc-web** = TypeScript code generator
- **CORS** = required for browser-to-server (often misconfigured)

**WHY gRPC doesn't work in browsers natively:**
- Browser fetch API doesn't expose HTTP/2 trailers (gRPC requires)
- Cannot manipulate raw HTTP/2 frames from JavaScript
- No support for client/bidirectional streaming
- → Need workaround: gRPC-Web protocol over HTTP/1.1 or HTTP/2

**HOW gRPC-Web works:**
```
Browser ───gRPC-Web───→ Envoy ───gRPC───→ Backend Service
       (over HTTP/1.1)        (over HTTP/2)

Translation:
- Browser sends: POST /UserService/GetUser (base64 body)
- Envoy translates: gRPC over HTTP/2 to backend
- Backend responds: HTTP/2 with trailers
- Envoy translates: trailers as base64 in body for browser
```

---

## Interview Questions & Answers

### Q1: gRPC-Web kya hai? gRPC se kaise different hai?

**Answer:**

**WHAT:** Protocol to call gRPC services from browsers.

**WHY needed:**
- Browsers can't make raw HTTP/2 gRPC calls
- gRPC-Web = gRPC subset that works in browsers

**HOW comparison:**

| Feature | gRPC (native) | gRPC-Web |
|---|---|---|
| **Transport** | HTTP/2 | HTTP/1.1 or HTTP/2 |
| **Unary RPC** | ✅ | ✅ |
| **Server streaming** | ✅ | ✅ |
| **Client streaming** | ✅ | ❌ NOT supported |
| **Bidirectional** | ✅ | ❌ NOT supported |
| **Trailers** | ✅ | Encoded in body |
| **Proxy required** | ❌ | ✅ Envoy/grpcwebproxy |
| **Use case** | Server-to-server | Browser-to-server |

**HOW — Architecture:**

```
┌─────────────────┐
│   Browser       │
│  (TypeScript)   │
└────────┬────────┘
         │ gRPC-Web (HTTP/1.1, base64 body)
         ↓
┌─────────────────┐
│   Envoy Proxy   │  ← Translates protocols
│  :8080          │
└────────┬────────┘
         │ gRPC (HTTP/2, binary)
         ↓
┌─────────────────┐
│  gRPC Backend   │
│  :50051         │
└─────────────────┘
```

---

### Q2: Envoy proxy gRPC-Web ke liye setup kaise karein?

**Answer:**

**WHAT:** Envoy translates gRPC-Web (browser) ↔ gRPC (backend).

**HOW — Envoy config:**

```yaml
# envoy.yaml
static_resources:
  listeners:
    - name: listener_0
      address:
        socket_address: { address: 0.0.0.0, port_value: 8080 }
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                codec_type: AUTO
                stat_prefix: ingress_http
                route_config:
                  name: local_route
                  virtual_hosts:
                    - name: backend
                      domains: ["*"]
                      # ⭐ CORS for browser
                      cors:
                        allow_origin_string_match:
                          - prefix: "*"
                        allow_methods: "GET, PUT, DELETE, POST, OPTIONS"
                        allow_headers: "keep-alive,user-agent,cache-control,content-type,content-transfer-encoding,custom-header-1,x-accept-content-transfer-encoding,x-accept-response-streaming,x-user-agent,x-grpc-web,grpc-timeout"
                        max_age: "1728000"
                        expose_headers: "custom-header-1,grpc-status,grpc-message"
                      routes:
                        - match: { prefix: "/" }
                          route:
                            cluster: backend_service
                            max_stream_duration:
                              grpc_timeout_header_max: 0s
                http_filters:
                  # ⭐ gRPC-Web filter (translates protocol)
                  - name: envoy.filters.http.grpc_web
                  - name: envoy.filters.http.cors
                  - name: envoy.filters.http.router

  clusters:
    - name: backend_service
      connect_timeout: 5s
      type: LOGICAL_DNS
      lb_policy: ROUND_ROBIN
      http2_protocol_options: {}      # ⭐ HTTP/2 to backend
      load_assignment:
        cluster_name: backend_service
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address: { address: user-service, port_value: 50051 }
```

**HOW — Docker Compose setup:**

```yaml
# docker-compose.yml
services:
  backend:
    build: ./backend
    ports:
      - "50051:50051"

  envoy:
    image: envoyproxy/envoy:v1.28-latest
    ports:
      - "8080:8080"
    volumes:
      - ./envoy.yaml:/etc/envoy/envoy.yaml:ro
    depends_on:
      - backend
```

---

### Q3: TypeScript client kaise generate karte ho .proto se?

**Answer:**

**WHAT:** Generate strongly-typed TS client from .proto.

**HOW — Setup protoc + plugins:**

```bash
# Install plugins
npm install --save-dev grpc-web protoc-gen-grpc-web

# Or use buf (recommended)
brew install bufbuild/buf/buf
```

**HOW — Buf config for TypeScript:**

```yaml
# buf.gen.yaml
version: v1
plugins:
  # JavaScript message types
  - plugin: buf.build/protocolbuffers/js
    out: gen
    opt:
      - import_style=commonjs,binary

  # gRPC-Web service stubs
  - plugin: buf.build/grpc/web
    out: gen
    opt:
      - import_style=typescript
      - mode=grpcwebtext           # Text encoding (vs grpcweb binary)
```

```bash
buf generate
# Generates: gen/user_service_pb.ts (messages)
#            gen/user_service_grpc_web_pb.ts (client)
```

**HOW — Use in React:**

```typescript
// user.service.ts
import { UserServiceClient } from './gen/user_service_grpc_web_pb';
import { GetUserRequest, CreateUserRequest } from './gen/user_service_pb';

const client = new UserServiceClient(
  process.env.REACT_APP_API_URL || 'http://localhost:8080',
  null,  // credentials
  null   // options
);

export async function getUser(userId: number) {
  return new Promise((resolve, reject) => {
    const request = new GetUserRequest();
    request.setUserId(userId);

    client.getUser(request, {
      'authorization': `Bearer ${getToken()}`
    }, (err, response) => {
      if (err) reject(err);
      else resolve(response.toObject());
    });
  });
}

// With async/await wrapper
export function asPromise<T>(call: (cb: any) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    call((err: any, response: T) => {
      if (err) reject(err);
      else resolve(response);
    });
  });
}

// Server streaming
export function streamUsers(filter: string) {
  const request = new ListUsersRequest();
  request.setRoleFilter(filter);

  const stream = client.listUsers(request, {});

  stream.on('data', (user) => {
    console.log('Received:', user.toObject());
  });

  stream.on('status', (status) => {
    console.log('Status:', status);
  });

  stream.on('end', () => {
    console.log('Stream ended');
  });

  return stream;  // Caller can cancel via stream.cancel()
}
```

**HOW — React component:**

```tsx
// UserList.tsx
import { useEffect, useState } from 'react';
import { streamUsers } from './user.service';

export function UserList() {
  const [users, setUsers] = useState([]);

  useEffect(() => {
    const stream = streamUsers('admin');

    stream.on('data', (user) => {
      setUsers(prev => [...prev, user.toObject()]);
    });

    return () => {
      stream.cancel();  // ⭐ Cancel on unmount
    };
  }, []);

  return <ul>{users.map(u => <li key={u.id}>{u.name}</li>)}</ul>;
}
```

---

### Q4: gRPC-Web ki limitations kya hain? Workarounds?

**Answer:**

**LIMITATIONS:**

| Feature | Status | Workaround |
|---|---|---|
| **Client streaming** | ❌ | Convert to multiple unary calls |
| **Bidirectional streaming** | ❌ | Use WebSocket + custom protocol |
| **Native HTTP/2 in browsers** | ❌ | Use Connect-RPC (newer) |
| **Header trailers** | ⚠️ | Encoded in body (works transparently) |
| **CORS** | ⚠️ | Configure Envoy proper origins |

**WORKAROUND 1: Client streaming → batch unary:**

```typescript
// Instead of streaming uploads, batch in chunks
async function uploadFileChunked(file: File) {
  const CHUNK_SIZE = 64 * 1024;
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

  for (let i = 0; i < totalChunks; i++) {
    const chunk = file.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE);
    const buf = await chunk.arrayBuffer();

    const request = new UploadChunkRequest();
    request.setSessionId(sessionId);
    request.setChunkIndex(i);
    request.setData(new Uint8Array(buf));

    await asPromise(cb => client.uploadChunk(request, cb));
  }

  // Finalize
  const finalRequest = new FinalizeUploadRequest();
  finalRequest.setSessionId(sessionId);
  return await asPromise(cb => client.finalizeUpload(finalRequest, cb));
}
```

**WORKAROUND 2: Bidirectional → WebSocket bridge:**

```typescript
// Use Socket.IO or native WebSocket for true bidirectional
// gRPC for unary calls
const ws = new WebSocket('wss://api.example.com/chat');
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  // handle incoming
};
ws.send(JSON.stringify({ text: 'hello' }));
```

---

### Q5: Connect-RPC kya hai? gRPC-Web se kaise better hai?

**Answer:**

**WHAT:** Connect-RPC = Buf's modern protocol — supports gRPC + HTTP/JSON + gRPC-Web in one server.

**WHY use over gRPC-Web:**
- ✅ Native browser support (no proxy needed)
- ✅ Three protocols in one (gRPC, gRPC-Web, HTTP/JSON)
- ✅ Better error handling
- ✅ Easier debugging (curl-able)
- ✅ Schema-first (same .proto)
- ❌ Newer (less mature ecosystem)

**HOW — Backend setup (Python):**

```bash
pip install connectrpc-python
```

```python
# server.py
from connectrpc import server as connect_server
from your_proto import UserServiceImpl

# Same servicer code as gRPC
class UserServiceImpl:
    async def GetUser(self, request, ctx):
        user = await db.get_user(request.user_id)
        return UserResponse(user=user)

# Connect supports 3 protocols simultaneously
app = connect_server.create_app([
    UserServiceImpl.as_handler(),
])

# Run with uvicorn
# uvicorn server:app --port 8080
```

**HOW — TypeScript client:**

```bash
npm install @connectrpc/connect @connectrpc/connect-web
```

```typescript
// client.ts
import { createPromiseClient } from "@connectrpc/connect";
import { createConnectTransport } from "@connectrpc/connect-web";
import { UserService } from "./gen/user_service_connect";

const transport = createConnectTransport({
  baseUrl: "https://api.example.com",
  // ⭐ Use HTTP/1.1 + JSON (works in all browsers)
  useBinaryFormat: false,
});

const client = createPromiseClient(UserService, transport);

// Promise-based API (no callbacks!)
const response = await client.getUser({ userId: 123 });
console.log(response.name);

// Server streaming
for await (const user of client.listUsers({ filter: "admin" })) {
  console.log(user.name);
}
```

**Comparison:**

| Aspect | gRPC-Web | Connect-RPC |
|---|---|---|
| **Proxy required** | Envoy needed | ❌ No proxy |
| **Client API style** | Callbacks | Promises/async-await |
| **Debug via curl** | ❌ Hard | ✅ Easy (HTTP/JSON) |
| **TypeScript types** | Manual | Auto-generated |
| **Browser support** | All | All |
| **Maturity** | High | Newer |

---

### Q6: Authentication browser → gRPC-Web service mein kaise karein?

**Answer:**

**HOW — JWT in Authorization header:**

```typescript
// auth-interceptor.ts
import { Metadata } from 'grpc-web';

export function authInterceptor() {
  return (req: any, invoker: any) => {
    const metadata: Metadata = req.getMetadata() || {};
    const token = localStorage.getItem('access_token');
    if (token) {
      metadata['authorization'] = `Bearer ${token}`;
    }
    return invoker(req);
  };
}

// Apply to client
const client = new UserServiceClient(API_URL, null, {
  unaryInterceptors: [authInterceptor()],
  streamInterceptors: [authInterceptor()],
});
```

**HOW — Token refresh interceptor:**

```typescript
// refresh-interceptor.ts
export class RefreshInterceptor {
  async intercept(request: any, invoker: any) {
    try {
      return await invoker(request);
    } catch (err: any) {
      if (err.code === StatusCode.UNAUTHENTICATED) {
        // ⭐ Try to refresh token
        const newToken = await refreshToken();
        if (newToken) {
          request.getMetadata()['authorization'] = `Bearer ${newToken}`;
          return await invoker(request);  // Retry
        }
        // Redirect to login
        window.location.href = '/login';
      }
      throw err;
    }
  }
}
```

---

### Q7: Production deployment of gRPC-Web?

**Answer:**

**WHAT:** Deploy gRPC backend + Envoy + frontend SPA.

**HOW — Kubernetes deployment:**

```yaml
# 1. Backend gRPC service
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-grpc
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: backend
          image: myorg/user-service:1.2.0
          ports:
            - containerPort: 50051

---
# 2. Envoy proxy
apiVersion: apps/v1
kind: Deployment
metadata:
  name: envoy
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: envoy
          image: envoyproxy/envoy:v1.28-latest
          ports:
            - containerPort: 8080
          volumeMounts:
            - name: config
              mountPath: /etc/envoy
      volumes:
        - name: config
          configMap:
            name: envoy-config

---
# 3. Envoy service (exposed to internet via ALB)
apiVersion: v1
kind: Service
metadata:
  name: envoy
spec:
  type: LoadBalancer
  ports:
    - port: 80
      targetPort: 8080
  selector:
    app: envoy
```

**HOW — AWS ALB ingress for Envoy:**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: envoy-ingress
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:..
spec:
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: envoy
                port: { number: 80 }
```

---

## Summary Table

| Approach | Browser Setup | Proxy | Best For |
|---|---|---|---|
| **gRPC-Web + Envoy** | grpc-web npm | Envoy required | Existing gRPC backend |
| **Connect-RPC** | @connectrpc/connect | ❌ None | New projects |
| **REST Gateway** | fetch/axios | grpc-gateway | Polyglot teams |
| **GraphQL Wrapper** | Apollo | GraphQL server | Complex queries |
