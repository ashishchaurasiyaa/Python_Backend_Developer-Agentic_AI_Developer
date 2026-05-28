# Protobuf Advanced — Schema Evolution, oneof, map, Well-Known Types

## Quick Concepts

**WHAT:**
- **Field numbers** = wire format identifier (1-15 = 1 byte tag, 16+ = 2 bytes)
- **Schema evolution** = changes to .proto without breaking existing clients
- **Reserved fields** = prevent reuse of removed field numbers/names
- **oneof** = union type (only one field set at a time)
- **map<K, V>** = key-value pairs (like dict/HashMap)
- **Well-Known Types** = pre-defined messages (Timestamp, Any, Struct, FieldMask)

**WHY advanced protobuf matters:**
- ❌ Wrong field numbering = wire format inefficiency
- ❌ Breaking changes = client crashes in production
- ❌ Not using `oneof` = ambiguous "which field is set"
- ❌ Not using well-known types = reinventing the wheel

**HOW protobuf wire format works:**
```
Field tag (varint) = field_number << 3 | wire_type
wire_type:
  0 = VARINT (int32, int64, bool, enum)
  1 = FIXED64 (double, fixed64)
  2 = LENGTH_DELIMITED (string, bytes, message, packed)
  5 = FIXED32 (float, fixed32)

Field number 1-15  → tag fits in 1 byte
Field number 16+   → tag needs 2 bytes
```

---

## Interview Questions & Answers

### Q1: Field numbering rules + best practices kya hain?

**Answer:**

**WHAT:**
- Field numbers identify fields in wire format
- Range: 1 to 536,870,911 (2^29 - 1)
- Reserved: 19000-19999 (Google internal)

**WHY numbering matters:**

```protobuf
// EFFICIENT — frequently used fields get 1-15
message User {
  int32 id = 1;            // 1 byte tag (best for frequent reads)
  string email = 2;        // 1 byte tag
  string name = 3;         // 1 byte tag
  bool is_active = 4;
  int64 created_at = 5;

  // Less frequent fields — 16+
  string preferences_json = 16;   // 2 byte tag
  bytes profile_picture = 17;     // 2 byte tag
}

// INEFFICIENT — wasted 1-15 range
message User {
  string rarely_used_field = 1;   // 1 byte tag but rare = waste
  int32 id = 100;                 // 2 byte tag for common field = bad
}
```

**HOW — Best practices:**

```protobuf
syntax = "proto3";

message User {
  // ⭐ Rule 1: Fields 1-15 for FREQUENTLY accessed fields
  int32 id = 1;
  string email = 2;
  string name = 3;
  Role role = 4;
  bool is_active = 5;

  // Save 6-15 for future common fields
  reserved 6 to 10;       // ⭐ Rule 2: Reserve gaps for future use

  // ⭐ Rule 3: 16+ for less frequently accessed
  google.protobuf.Timestamp created_at = 16;
  google.protobuf.Timestamp updated_at = 17;
  map<string, string> metadata = 18;
  repeated string tags = 19;

  // ⭐ Rule 4: NEVER reuse removed field numbers
  reserved 50, 51, 52;
  reserved "old_field_name", "deprecated_field";
}
```

**Common pitfalls:**

```protobuf
// ❌ DON'T: Reuse field numbers after deletion
message User_BAD {
  // Original: int32 deprecated_id = 1;
  // Removed and replaced:
  string username = 1;    // ❌ DANGER: existing clients see int32 wire data → crash
}

// ✅ DO: Reserve old numbers
message User_GOOD {
  reserved 1;             // ✅ deprecated_id field number 1 reserved
  string username = 2;    // ✅ New field uses next number
}
```

---

### Q2: Schema evolution — backward + forward compatibility kya hai?

**Answer:**

**WHAT:**
- **Backward compatible** = New schema readable by OLD clients
- **Forward compatible** = Old schema readable by NEW clients

**WHY both needed:**
```
Mixed deployment scenario:
- Service A (v1) and Service B (v2) running simultaneously during rollout
- v1 client must read v2 response → forward compat
- v2 client must read v1 response → backward compat
```

**HOW — Compatibility rules:**

| Change | Backward Compat? | Forward Compat? |
|---|---|---|
| **Add new field** | ✅ (old ignores) | ✅ (new defaults) |
| **Remove field** | ⚠️ (data lost) | ✅ (old defaults) |
| **Rename field (number same)** | ✅ (wire format) | ✅ (wire format) |
| **Change field number** | ❌ BREAKING | ❌ BREAKING |
| **Change field type (compatible)** | ✅ int32→int64 | ✅ |
| **Change field type (incompatible)** | ❌ int32→string | ❌ |
| **Make optional → required** | ❌ (proto2) | ❌ |
| **Remove oneof field** | ⚠️ | ✅ |

**HOW — Safe evolution patterns:**

```protobuf
// ── Version 1 (Original) ──
message User {
  int32 id = 1;
  string name = 2;
  string email = 3;
}

// ── Version 2: ADD field (✅ Safe) ──
message User {
  int32 id = 1;
  string name = 2;
  string email = 3;
  string phone = 4;          // ✅ New field — old clients ignore
}

// ── Version 3: RENAME field (✅ Safe — only the name) ──
message User {
  int32 id = 1;
  string full_name = 2;      // ✅ Renamed from "name" — wire format unchanged
  string email = 3;
  string phone = 4;
}

// ── Version 4: REMOVE field (⚠️ Mostly Safe) ──
message User {
  int32 id = 1;
  string full_name = 2;
  reserved 3;                // ⭐ MUST reserve removed field number
  reserved "email";          // ⭐ AND name
  string phone = 4;
}

// ── Version 5: TYPE CHANGE (Compatible) ──
message User {
  int32 id = 1;              // ⚠️ int32 → int64 is compatible (wire format same for small values)
  string full_name = 2;
  reserved 3;
  string phone = 4;
}

// ── Version 6: TYPE CHANGE (INCOMPATIBLE — DON'T DO) ──
message User {
  string id = 1;             // ❌ int32 → string BREAKING
}
```

**Type change compatibility:**

```
✅ COMPATIBLE TYPE CHANGES:
- int32 → int64 → uint32 → uint64 → bool
- sint32 → sint64
- fixed32 → sfixed32
- fixed64 → sfixed64

❌ INCOMPATIBLE:
- string ↔ bytes (encoding diff)
- numeric ↔ string (wire format diff)
- message type ↔ scalar
```

---

### Q3: oneof type kab use karein? Examples?

**Answer:**

**WHAT:** Only ONE field set at a time (mutually exclusive fields).

**WHY use oneof:**
- ✅ Memory efficient (only one field stored)
- ✅ Clear API contract (XOR semantics)
- ✅ Server knows which field client set

**HOW — Common patterns:**

```protobuf
// Pattern 1: Discriminated union (different request types)
message NotificationRequest {
  string user_id = 1;

  oneof notification {
    EmailNotification email = 2;
    SmsNotification   sms   = 3;
    PushNotification  push  = 4;
  }
}

message EmailNotification {
  string to = 1;
  string subject = 2;
  string body = 3;
}

message SmsNotification {
  string phone_number = 1;
  string text = 2;
}


// Pattern 2: Optional value with absence detection
message SearchFilter {
  oneof query {
    string text_query = 1;
    int32  user_id    = 2;
    bytes  blob_query = 3;
  }
  // If none set → no filter
}


// Pattern 3: Polymorphic results
message OperationResult {
  oneof result {
    User    user_result    = 1;   // Success: returned user
    Error   error_result   = 2;   // Failure: error details
    string  redirect_url   = 3;   // Action required
  }
}
```

**HOW — Server-side oneof handling:**

```python
async def SendNotification(self, request, context):
    # ⭐ Check which oneof field is set
    notification_type = request.WhichOneof("notification")

    if notification_type == "email":
        await send_email(request.email.to, request.email.subject, request.email.body)
    elif notification_type == "sms":
        await send_sms(request.sms.phone_number, request.sms.text)
    elif notification_type == "push":
        await send_push(request.push.device_token, request.push.message)
    else:
        await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "No notification type")

    return Empty()
```

**HOW — Client-side oneof:**

```python
# Set ONE field of oneof
request = NotificationRequest(
    user_id="123",
    email=EmailNotification(
        to="alice@example.com",
        subject="Hello",
        body="Hi Alice"
    )
)
# Setting another field automatically clears previous oneof field
request.sms.CopyFrom(SmsNotification(phone_number="555-1234"))
# Now email is cleared, only sms is set
```

**Gotchas:**

```protobuf
// ❌ DON'T mix repeated and map inside oneof (compiler rejects)
oneof bad {
  repeated string items = 1;     // ❌ Not allowed
  map<string, string> mapping = 2;  // ❌ Not allowed
}

// ✅ DO wrap in a message
message ItemList { repeated string items = 1; }
message Mapping  { map<string, string> entries = 1; }

oneof good {
  ItemList items = 1;
  Mapping  mapping = 2;
}
```

---

### Q4: map<K, V> kab use karein? Limitations?

**Answer:**

**WHAT:** Key-value pairs (like dict in Python).

**WHY use map vs repeated message:**

```protobuf
// Option A: map (cleaner)
message User {
  map<string, string> metadata = 1;
}

// Option B: repeated message (more flexible)
message User {
  repeated KeyValue metadata = 1;
}
message KeyValue {
  string key = 1;
  string value = 2;
  int64 updated_at = 3;   // ✅ Can add more fields
}
```

**HOW — Map syntax + restrictions:**

```protobuf
message Config {
  // ✅ Valid map types
  map<string, string>  string_map = 1;
  map<int32, User>     user_by_id = 2;
  map<int64, bytes>    blob_store = 3;

  // ❌ INVALID — key cannot be float, bytes, or message
  // map<float, string> invalid = 4;
  // map<bytes, string> invalid = 5;
  // map<User, int> invalid = 6;

  // Allowed keys: int32, int64, uint32, uint64, sint32, sint64,
  //              fixed32, fixed64, sfixed32, sfixed64, bool, string
}
```

**HOW — Python usage:**

```python
# Server creates
user = User()
user.metadata["role"] = "admin"
user.metadata["team"] = "platform"

# Or batch assign
user.metadata.update({
    "role": "admin",
    "team": "platform",
    "joined_at": "2024-01-15",
})

# Client reads
for key, value in user.metadata.items():
    print(f"{key} = {value}")

role = user.metadata.get("role", "default")
```

**Wire format note:**
- Map is encoded as `repeated message { key = 1; value = 2 }` internally
- Backward compatible with this representation
- No ordering guarantee

---

### Q5: Well-known types kaun se hain? Kab use karein?

**Answer:**

**WHAT:** Pre-defined protobuf types in `google/protobuf/*.proto` for common use cases.

**WHY use over custom:**
- ✅ Standardized across all protobuf services
- ✅ Better tooling support (JSON conversion, libraries)
- ✅ Less reinvention

**HOW — Most useful well-known types:**

```protobuf
syntax = "proto3";

import "google/protobuf/timestamp.proto";
import "google/protobuf/duration.proto";
import "google/protobuf/empty.proto";
import "google/protobuf/wrappers.proto";
import "google/protobuf/struct.proto";
import "google/protobuf/any.proto";
import "google/protobuf/field_mask.proto";

message Event {
  // ⭐ Timestamp (always UTC, microsecond precision)
  google.protobuf.Timestamp occurred_at = 1;

  // ⭐ Duration (e.g., job runtime)
  google.protobuf.Duration  process_time = 2;
}

// ⭐ Empty — for methods that return nothing
service UserService {
  rpc DeleteUser(GetUserRequest) returns (google.protobuf.Empty);
}

// ⭐ Wrapper types (for nullable primitives in proto3)
// proto3 default values can't distinguish "not set" from "set to default"
// Wrappers solve this
message UpdateUserRequest {
  int32 user_id = 1;
  google.protobuf.StringValue name = 2;       // null vs "" distinguishable
  google.protobuf.Int32Value  age  = 3;       // null vs 0 distinguishable
  google.protobuf.BoolValue   is_active = 4;  // null vs false distinguishable
}

// ⭐ Struct — arbitrary JSON-like data
message Config {
  google.protobuf.Struct settings = 1;   // any nested JSON
}

// ⭐ Any — pack any message type
message AuditLog {
  string action = 1;
  google.protobuf.Any payload = 2;       // can be any message type
}

// ⭐ FieldMask — partial updates (which fields to update)
message UpdateUserRequest {
  User user = 1;
  google.protobuf.FieldMask update_mask = 2;
  // Client sends: update_mask = ["name", "email"]
  // Server updates only those fields
}
```

**HOW — Timestamp usage:**

```python
from google.protobuf.timestamp_pb2 import Timestamp
from datetime import datetime, timezone

# Python → Timestamp
ts = Timestamp()
ts.FromDatetime(datetime.now(timezone.utc))

# Or use seconds + nanos
ts.GetCurrentTime()

# Timestamp → Python
dt = ts.ToDatetime(tzinfo=timezone.utc)

# From ISO string
ts.FromJsonString("2024-01-15T10:30:00Z")

# To ISO string
iso_str = ts.ToJsonString()
```

**HOW — FieldMask usage (partial update):**

```python
async def UpdateUser(self, request, context):
    user = await db.get_user(request.user.id)

    # ⭐ Only update fields specified in FieldMask
    for path in request.update_mask.paths:
        if path == "name":
            user.name = request.user.name
        elif path == "email":
            user.email = request.user.email
        elif path == "role":
            user.role = request.user.role
        # Fields NOT in mask = unchanged

    await db.update_user(user)
    return self._user_to_proto(user)


# Client side
request = UpdateUserRequest(
    user=User(id=1, name="New Name"),
    update_mask=FieldMask(paths=["name"])   # Only update name
)
```

---

### Q6: Reserved fields kyu use karein? Examples?

**Answer:**

**WHAT:** Mark field numbers/names as forbidden to prevent accidental reuse.

**WHY:**
```
Without reserved:
v1:  field "user_id" = 5;
v2:  removes user_id field
v3:  someone adds field "tenant_id" = 5 (different type)
v1 clients still in production → receive v3 response → CRASH
(v1 deserializes tenant_id as user_id with wrong type)
```

**HOW — Reserve numbers AND names:**

```protobuf
message User {
  int32 id = 1;
  string name = 2;

  // Removed fields — reserve to prevent reuse
  reserved 3, 4, 5;                          // Numbers
  reserved 10 to 20;                          // Range
  reserved "old_email", "deprecated_phone";   // Names

  // New fields use unreserved numbers
  string username = 21;
  string email = 22;
}
```

**Compiler enforcement:**

```protobuf
message User {
  reserved 3;

  int32 id = 1;
  string name = 2;
  string email = 3;    // ❌ Compile error: field number 3 reserved
}
```

---

### Q7: enum best practices?

**Answer:**

**WHAT:** Named integer constants.

**WHY rules matter:**
- ✅ First enum value MUST be 0 (proto3 requirement)
- ✅ Reserved values prevent breakage when adding new
- ✅ Use prefixes to avoid name collisions

**HOW — Best practices:**

```protobuf
enum UserRole {
  // ⭐ First value must be 0 (default for unset fields)
  // Use "UNSPECIFIED" prefix convention
  USER_ROLE_UNSPECIFIED = 0;

  // ⭐ Prefix with enum name (avoids collisions across files)
  USER_ROLE_GUEST = 1;
  USER_ROLE_USER = 2;
  USER_ROLE_ADMIN = 3;
  USER_ROLE_SUPER_ADMIN = 4;

  // Reserved for future
  reserved 5 to 10;
  reserved "DEPRECATED_ROLE";
}

// Usage
message User {
  int32 id = 1;
  UserRole role = 2;  // Default: USER_ROLE_UNSPECIFIED
}
```

**Allow alias (multiple names for same value):**

```protobuf
enum Status {
  option allow_alias = true;       // ⭐ Enable aliasing

  STATUS_UNSPECIFIED = 0;
  STATUS_ACTIVE = 1;
  STATUS_RUNNING = 1;              // Alias for ACTIVE
  STATUS_STOPPED = 2;
  STATUS_PAUSED = 2;               // Alias for STOPPED
}
```

**Cross-language gotchas:**

```python
# Python access
user.role = UserRole.USER_ROLE_ADMIN

# Get enum name from int value
role_name = UserRole.Name(user.role)  # → "USER_ROLE_ADMIN"

# Get int from name
role_int = UserRole.Value("USER_ROLE_ADMIN")  # → 3

# Iterate all values
for name, value in UserRole.items():
    print(f"{name} = {value}")
```

---

### Q8: Buf — protobuf ecosystem ka modern tool kya hai?

**Answer:**

**WHAT:** `buf` = modern protobuf toolchain (linting, breaking detection, code gen, schema registry).

**WHY use vs raw protoc:**
- ✅ Cleaner CLI than protoc
- ✅ Built-in linting (catches anti-patterns)
- ✅ Breaking change detection
- ✅ Buf Schema Registry (BSR) — npm for protobuf
- ✅ Plugin system for code generation

**HOW — Setup:**

```bash
# Install
brew install bufbuild/buf/buf

# Initialize project
cd protos/
buf mod init buf.build/myorg/userapi

# Creates buf.yaml:
cat buf.yaml
```

```yaml
# buf.yaml
version: v1
name: buf.build/myorg/userapi
deps:
  - buf.build/googleapis/googleapis
lint:
  use:
    - DEFAULT
  except:
    - ENUM_ZERO_VALUE_SUFFIX
breaking:
  use:
    - FILE
```

**HOW — Common commands:**

```bash
# Lint .proto files (catch anti-patterns)
buf lint
# Catches:
# - Missing UNSPECIFIED enum 0 value
# - Field naming conventions
# - Service naming
# - Package naming

# Check breaking changes vs main
buf breaking --against '.git#branch=main'

# Format files
buf format -w

# Generate code (replaces protoc)
buf generate

# Push to Buf Schema Registry
buf push
```

**HOW — Code generation config:**

```yaml
# buf.gen.yaml
version: v1
plugins:
  - plugin: buf.build/protocolbuffers/python
    out: gen/python
    opt:
      - paths=source_relative

  - plugin: buf.build/grpc/python
    out: gen/python
    opt:
      - paths=source_relative

  - plugin: buf.build/protocolbuffers/go
    out: gen/go
    opt:
      - paths=source_relative
```

```bash
buf generate
# Generates code for Python AND Go from same .proto
```

---

## Schema Design Best Practices

```markdown
### .proto File Organization
- [ ] One service per file (or closely related)
- [ ] package = reverse domain (com.myorg.userservice.v1)
- [ ] Use v1, v2 in package for major versions
- [ ] Import only what you need

### Field Numbers
- [ ] 1-15 for frequently accessed fields
- [ ] Reserve gaps for future growth
- [ ] NEVER reuse removed field numbers
- [ ] Reserve both numbers AND names

### Naming Conventions
- [ ] snake_case for field names (id_user, not idUser)
- [ ] PascalCase for messages/services
- [ ] SCREAMING_SNAKE for enum values
- [ ] Prefix enum values with enum name

### Compatibility
- [ ] Use wrapper types for nullable primitives
- [ ] FieldMask for partial updates
- [ ] Add new fields with new numbers (don't reuse)
- [ ] Run `buf breaking` in CI

### Standards
- [ ] Use well-known types (Timestamp, Duration, Empty)
- [ ] First enum value = UNSPECIFIED = 0
- [ ] Document fields with // comments
- [ ] Group related fields together
```
