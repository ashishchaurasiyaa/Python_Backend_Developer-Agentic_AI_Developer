# Advanced LLM Tool Use / Function Calling
## Python Backend Developer + Agentic AI Interview Prep — 40 LPA Series
### File 02 — Tool Use Advanced Theory

---

## 1. Tool Use / Function Calling Kya Hai?

### Concept Samajhte Hain

Jab tum ek normal LLM se baat karte ho, uske paas sirf **language understanding** aur **knowledge** hai jo training data mein tha. Lekin real-world applications mein tume chahiye:

- Current weather data (LLM ke paas nahi hai)
- Database se live data
- Calculations (LLM mein arithmetic unreliable hoti hai)
- External APIs call karna
- Files read/write karna

**Tool Use** (OpenAI mein "Function Calling") ek mechanism hai jisse tum LLM ko tools dete ho, aur LLM decide karta hai **kab** aur **kaise** unhe use karna hai.

```
Simple Analogy:
LLM = Ek bahut padha-likha employee
Tools = Employee ke paas available resources/systems

Jaise ek employee decide karta hai:
"Yeh calculation ke liye calculator use karunga"
"Yeh data ke liye database check karunga"
"Is user ko email bhejna padega"

LLM bhi exactly yahi decide karta hai — autonomously.
```

### Key Points

1. **LLM khud tools execute nahi karta** — woh sirf batata hai "yeh tool call karo, yeh arguments ke saath"
2. **Tumhara code actual execution karta hai** — tool ki actual logic tumhare server pe run hoti hai
3. **LLM ko tool results milte hain** — phir woh final response generate karta hai
4. **Multi-step possible hai** — LLM multiple tools chain kar sakta hai

### Historical Context

- **June 2023**: OpenAI ne "Function Calling" introduce kiya GPT-3.5/GPT-4 mein
- **Nov 2023**: Anthropic ne "Tool Use" introduce kiya Claude mein
- **2024**: Standardization ki taraf move — same concept, slightly different API formats
- **MCP (Model Context Protocol)**: 2024 mein Anthropic ka tool standardization protocol

---

## 2. Tool Definition Schemas

### 2.1 OpenAI Format

OpenAI mein tools ek `tools` array mein pass karte ho:

```python
tools = [
    {
        "type": "function",           # Always "function" for now
        "function": {
            "name": "get_weather",    # Tool ka naam (snake_case prefer)
            "description": """Get current weather for a specific city.
                Use this when user asks about weather, temperature,
                or climate conditions in any location.""",
            "parameters": {
                "type": "object",     # Root is always object
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city name, e.g. 'Mumbai', 'New Delhi'"
                    },
                    "units": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature units",
                        "default": "celsius"
                    }
                },
                "required": ["city"]  # city mandatory hai, units optional
            }
        }
    }
]

# API call
response = openai_client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Mumbai mein aaj weather kaisa hai?"}],
    tools=tools,
    tool_choice="auto"  # auto | none | required | specific tool
)
```

### 2.2 Anthropic Format

Anthropic ka format slightly different hai — `input_schema` use karta hai:

```python
tools = [
    {
        "name": "get_weather",        # No nested "function" key
        "description": """Get current weather for a specific city.
            Use this when user asks about weather, temperature,
            or climate conditions in any location.""",
        "input_schema": {             # "input_schema" not "parameters"
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city name, e.g. 'Mumbai', 'New Delhi'"
                },
                "units": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature units"
                }
            },
            "required": ["city"]
        }
    }
]

# API call
response = anthropic_client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "Mumbai mein aaj weather kaisa hai?"}]
)
```

### 2.3 Format Comparison Table

```
Feature              | OpenAI                    | Anthropic
---------------------|---------------------------|---------------------------
Tool wrapper         | {"type":"function",       | Direct object
                     |  "function": {...}}        |
Schema key           | "parameters"              | "input_schema"
Tool choice          | tool_choice param         | tool_choice param
Response type        | tool_calls array          | content blocks (tool_use)
Tool result role     | "tool"                    | "user" (with tool_result)
Multiple calls       | Multiple tool_calls       | Multiple tool_use blocks
Stop reason          | "tool_calls"              | "tool_use"
```

### 2.4 JSON Schema Types — Complete Guide

```python
# ---- STRING ----
{
    "type": "string",
    "description": "User ka naam",
    "minLength": 1,          # Minimum length
    "maxLength": 100,        # Maximum length
    "pattern": "^[A-Za-z ]+$"  # Regex pattern
}

# ---- NUMBER (float) ----
{
    "type": "number",
    "description": "Product price",
    "minimum": 0.0,
    "maximum": 999999.99,
    "exclusiveMinimum": 0    # 0 se strictly greater
}

# ---- INTEGER ----
{
    "type": "integer",
    "description": "Page number",
    "minimum": 1,
    "maximum": 1000,
    "default": 1
}

# ---- BOOLEAN ----
{
    "type": "boolean",
    "description": "Include deleted records?"
}

# ---- ENUM (fixed choices) ----
{
    "type": "string",
    "enum": ["pending", "active", "completed", "cancelled"],
    "description": "Order status filter"
}

# ---- ARRAY ----
{
    "type": "array",
    "items": {
        "type": "string"     # Array ke andar kya hoga
    },
    "description": "List of user IDs",
    "minItems": 1,
    "maxItems": 50,
    "uniqueItems": true      # Duplicates nahi
}

# ---- ARRAY OF OBJECTS ----
{
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "quantity": {"type": "integer", "minimum": 1}
        },
        "required": ["id", "quantity"]
    }
}

# ---- NESTED OBJECT ----
{
    "type": "object",
    "properties": {
        "address": {
            "type": "object",
            "properties": {
                "street": {"type": "string"},
                "city": {"type": "string"},
                "pincode": {"type": "string", "pattern": "^[0-9]{6}$"}
            },
            "required": ["city"]
        },
        "contact": {
            "type": "object",
            "properties": {
                "phone": {"type": "string"},
                "email": {"type": "string", "format": "email"}
            }
        }
    }
}

# ---- OPTIONAL FIELD (null allowed) ----
{
    "type": ["string", "null"],   # null bhi accept karo
    "description": "Optional notes"
}
```

### 2.5 Good vs Bad Tool Descriptions

**BAD Description:**
```python
{
    "name": "db",
    "description": "Database",  # Too vague! LLM ko pata nahi kab use karna
    "parameters": {...}
}
```

**GOOD Description:**
```python
{
    "name": "search_products",
    "description": """Search products in the catalog by name, category, or price range.
    
    Use this tool when:
    - User asks to find/search for products
    - User wants to know what products are available
    - User filters by category (electronics, clothing, etc.)
    - User searches within a price range
    
    Do NOT use for:
    - Checking order status (use get_order_status instead)
    - Getting product details by ID (use get_product_by_id instead)
    
    Returns: List of matching products with name, price, stock, category.
    Example: search_products(query="laptop", category="electronics", max_price=50000)
    """,
    "parameters": {...}
}
```

**Lesson**: Description quality directly impacts LLM's tool selection accuracy. Jitna clear, utna better.

---

## 3. Tool Call Flow — Step by Step

### 3.1 Basic Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    TOOL USE FLOW                                 │
│                                                                  │
│  [1] USER MESSAGE                                                │
│      "Mumbai ka weather batao celsius mein"                      │
│              │                                                   │
│              ▼                                                   │
│  [2] SEND TO LLM (messages + tools)                              │
│      POST /chat/completions                                      │
│      { messages: [...], tools: [get_weather, ...] }              │
│              │                                                   │
│              ▼                                                   │
│  [3] LLM RESPONSE: tool_use                                      │
│      stop_reason: "tool_use"                                     │
│      content: [{                                                 │
│        type: "tool_use",                                         │
│        id: "call_abc123",                                        │
│        name: "get_weather",                                      │
│        input: {"city": "Mumbai", "units": "celsius"}             │
│      }]                                                          │
│              │                                                   │
│              ▼                                                   │
│  [4] YOUR CODE EXECUTES TOOL                                     │
│      result = get_weather(city="Mumbai", units="celsius")        │
│      → {"temp": 32, "humidity": 85, "condition": "Humid"}        │
│              │                                                   │
│              ▼                                                   │
│  [5] ADD TOOL RESULT TO MESSAGES                                 │
│      messages.append({                                           │
│        role: "tool" (OpenAI) / "user" (Anthropic),              │
│        tool_call_id: "call_abc123",                              │
│        content: '{"temp": 32, "humidity": 85}'                   │
│      })                                                          │
│              │                                                   │
│              ▼                                                   │
│  [6] SEND BACK TO LLM                                            │
│      LLM ab tool result dekh ke response banata hai              │
│              │                                                   │
│              ▼                                                   │
│  [7] FINAL RESPONSE                                              │
│      stop_reason: "end_turn"                                     │
│      "Mumbai mein aaj 32°C hai, humidity 85% hai..."             │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 OpenAI Code — Complete Flow

```python
import openai
import json

client = openai.OpenAI()

def run_tool_use_loop(user_message: str, tools: list, tool_executor: dict):
    """
    Complete tool use loop — handles multiple tool calls automatically.
    tool_executor: {"tool_name": callable_function}
    """
    messages = [{"role": "user", "content": user_message}]
    
    while True:
        # Step 2: LLM ko bhejo
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        choice = response.choices[0]
        
        # Step 3: Check karo LLM ne tool use kiya ya nahi
        if choice.finish_reason == "stop":
            # No more tools needed — final answer ready
            return choice.message.content
        
        elif choice.finish_reason == "tool_calls":
            # LLM wants to call tools
            assistant_message = choice.message
            messages.append(assistant_message)  # Assistant message add karo
            
            # Step 4 + 5: Har tool call execute karo
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                print(f"  🔧 Calling: {tool_name}({tool_args})")
                
                try:
                    fn = tool_executor[tool_name]
                    result = fn(**tool_args)
                    result_str = json.dumps(result)
                except Exception as e:
                    result_str = json.dumps({"error": str(e)})
                
                # Tool result messages mein add karo
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_str
                })
            
            # Loop continues — LLM ko dobara bhejo with tool results
        else:
            break
    
    return "Could not complete the request."
```

### 3.3 Anthropic Code — Complete Flow

```python
import anthropic
import json

client = anthropic.Anthropic()

def run_anthropic_tool_loop(user_message: str, tools: list, tool_executor: dict):
    messages = [{"role": "user", "content": user_message}]
    
    while True:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            tools=tools,
            messages=messages
        )
        
        # Check stop reason
        if response.stop_reason == "end_turn":
            # Final text response nikalo
            for block in response.content:
                if block.type == "text":
                    return block.text
            return ""
        
        elif response.stop_reason == "tool_use":
            # Assistant message add karo (content blocks ke saath)
            messages.append({
                "role": "assistant",
                "content": response.content  # list of content blocks
            })
            
            # Tool results collect karo
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  🔧 Calling: {block.name}({block.input})")
                    
                    try:
                        fn = tool_executor[block.name]
                        result = fn(**block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result)
                        })
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "is_error": True,
                            "content": str(e)
                        })
            
            # Tool results "user" role mein add karo (Anthropic ka pattern)
            messages.append({
                "role": "user",
                "content": tool_results
            })
```

### 3.4 Message Conversation Structure

```python
# Complete conversation timeline
conversation = [
    # Turn 1: User
    {"role": "user", "content": "Delhi aur Mumbai ka weather compare karo"},
    
    # Turn 2: Assistant (LLM — parallel tool calls)
    {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "id": "call_1", "name": "get_weather",
             "input": {"city": "Delhi"}},
            {"type": "tool_use", "id": "call_2", "name": "get_weather",
             "input": {"city": "Mumbai"}}
        ]
    },
    
    # Turn 3: Tool results (user role in Anthropic)
    {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "call_1",
             "content": '{"temp": 38, "humidity": 40}'},
            {"type": "tool_result", "tool_use_id": "call_2",
             "content": '{"temp": 32, "humidity": 85}'}
        ]
    },
    
    # Turn 4: Final assistant response
    {"role": "assistant", "content": "Delhi mein 38°C aur Mumbai mein 32°C hai..."}
]
```

---

## 4. Parallel Tool Calls

### 4.1 Concept

Jab LLM ko multiple independent tools call karne hote hain, woh **ek hi response mein** multiple calls de sakta hai. Tumhara code inhe **parallel** execute kare taaki time bachao.

```
SEQUENTIAL (Slow):
User Request
    → Call Tool A (wait 500ms)
    → Call Tool B (wait 500ms)  
    → Call Tool C (wait 500ms)
Total: ~1500ms

PARALLEL (Fast):
User Request
    → Call Tool A ─┐
    → Call Tool B ─┼─ All start simultaneously
    → Call Tool C ─┘
Total: ~500ms (as fast as slowest)
```

### 4.2 OpenAI Parallel Tool Calls

```python
# OpenAI automatically sends multiple tool_calls when appropriate
response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools
)

# Response mein multiple tool_calls ho sakte hain
tool_calls = response.choices[0].message.tool_calls
# [ToolCall(id="call_1", function=...),
#  ToolCall(id="call_2", function=...)]

# Parallel execution with asyncio.gather
async def execute_all_tools(tool_calls):
    async def execute_single(tc):
        fn = tool_executor[tc.function.name]
        args = json.loads(tc.function.arguments)
        # Agar sync function hai, thread pool mein run karo
        result = await asyncio.to_thread(fn, **args)
        return tc.id, result
    
    results = await asyncio.gather(*[execute_single(tc) for tc in tool_calls])
    return {call_id: result for call_id, result in results}
```

### 4.3 Anthropic Parallel Tool Calls

```python
# Anthropic response mein multiple tool_use blocks ho sakte hain
for block in response.content:
    if block.type == "tool_use":
        tool_calls.append(block)

# asyncio.gather se parallel execute karo
import asyncio

async def process_tool_calls_parallel(tool_use_blocks, tool_executor):
    async def execute_one(block):
        try:
            fn = tool_executor[block.name]
            result = await asyncio.to_thread(fn, **block.input)
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result)
            }
        except Exception as e:
            return {
                "type": "tool_result", 
                "tool_use_id": block.id,
                "is_error": True,
                "content": f"Error: {str(e)}"
            }
    
    # Sab tools simultaneously execute karo
    results = await asyncio.gather(*[execute_one(b) for b in tool_use_blocks])
    return list(results)
```

### 4.4 When Does LLM Use Parallel vs Sequential?

```
PARALLEL (LLM chooses):
- Independent queries: "Delhi aur Mumbai ka weather"
- Multiple data fetches: "user 1, user 2, user 3 ki info do"
- Batch operations: "5 products ka price check karo"

SEQUENTIAL (LLM chooses):  
- Dependent chain: "Search product → get its details → calculate price with discount"
- Order matters: "Create order → then send confirmation email"
- Conditional: "Check stock, agar available ho toh book karo"
```

---

## 5. Tool Chaining

### 5.1 Concept

Tool chaining mein ek tool ka output dusre tool ka input ban jaata hai. LLM **dynamically** decide karta hai chain.

```
Example: "Find cheapest laptop under 50000 and book it for user ID 123"

Chain:
1. search_products(query="laptop", max_price=50000)
   → Returns: [{id: 42, name: "HP Laptop", price: 45000}]

2. check_stock(product_id=42)
   → Returns: {available: true, stock: 5}

3. create_order(user_id=123, product_id=42, quantity=1)
   → Returns: {order_id: "ORD-789", total: 45000}

4. send_confirmation_email(user_id=123, order_id="ORD-789")
   → Returns: {sent: true}

LLM automatically chains these — tumhe sirf tools define karne hain!
```

### 5.2 ReAct Pattern

ReAct = **Re**asoning + **Act**ing

```
Reason: "User laptop dhundh raha hai. Pehle search karna padega."
Act:    search_products(query="laptop")
Observe: [{"id": 42, "name": "HP Laptop", "price": 45000, "stock": 3}]

Reason: "HP Laptop available hai aur budget mein hai. Stock check karna chahiye."
Act:    check_availability(product_id=42)
Observe: {"available": true, "delivery_days": 2}

Reason: "Product available hai. Order create karo."
Act:    create_order(user_id=123, product_id=42)
Observe: {"order_id": "ORD-789", "status": "confirmed"}

Reason: "Order create ho gaya. User ko email bhejo."
Act:    send_email(user_id=123, order_id="ORD-789")
Observe: {"sent": true}

Reason: "Sab complete ho gaya. Final response do."
Response: "Aapka HP Laptop order ho gaya! Order ID: ORD-789"
```

### 5.3 Max Iterations — Infinite Loop Prevention

```python
MAX_TOOL_ITERATIONS = 10

async def agent_loop(user_message: str, tools: list):
    messages = [{"role": "user", "content": user_message}]
    iteration = 0
    
    while iteration < MAX_TOOL_ITERATIONS:
        iteration += 1
        print(f"  Iteration {iteration}/{MAX_TOOL_ITERATIONS}")
        
        response = await call_llm(messages, tools)
        
        if response.stop_reason == "end_turn":
            return response.final_text
        
        if response.stop_reason == "tool_use":
            results = await execute_tools(response.tool_calls)
            messages.extend(results)
        
    # Max iterations hit
    return "Error: Task too complex, exceeded maximum iterations. Please simplify your request."
```

**Why max iterations?**
- LLM kabhi kabhi circular reasoning mein phase ja sakta hai
- Network errors se infinite retries ho sakte hain
- Cost control — har LLM call expensive hai
- User experience — response time reasonable rakhna

---

## 6. Error Handling in Tools

### 6.1 Error Types aur Handling Strategy

```
Error Type              | Strategy
------------------------|------------------------------------------
Tool not found          | Return error, tell LLM
Validation error        | Return error with details, LLM can retry
Network timeout         | Retry 3 times, then return error
Rate limit              | Wait + retry with exponential backoff
Authorization error     | Return auth error, don't retry
Business logic error    | Return structured error, LLM can adapt
Unexpected exception    | Catch all, log, return generic error
```

### 6.2 Structured Error Response

```python
from typing import TypedDict

class ToolError(TypedDict):
    error: str           # Error type
    message: str         # Human-readable message
    retry: bool          # Kya LLM retry kar sakta hai?
    suggestion: str      # LLM ke liye suggestion

def safe_tool_wrapper(tool_fn, tool_name: str, args: dict) -> str:
    """Universal tool wrapper with error handling"""
    try:
        result = tool_fn(**args)
        return json.dumps(result)
    
    except ValidationError as e:
        error = ToolError(
            error="validation_error",
            message=f"Invalid arguments: {e}",
            retry=True,
            suggestion="Please check argument types and required fields"
        )
        return json.dumps(error)
    
    except TimeoutError:
        error = ToolError(
            error="timeout",
            message=f"Tool {tool_name} timed out after 30s",
            retry=True,
            suggestion="Try with simpler/smaller request"
        )
        return json.dumps(error)
    
    except RateLimitError:
        error = ToolError(
            error="rate_limit",
            message="External API rate limit exceeded",
            retry=False,  # Retry se kuch nahi hoga abhi
            suggestion="Wait a few minutes before trying again"
        )
        return json.dumps(error)
    
    except PermissionError:
        error = ToolError(
            error="permission_denied",
            message="Insufficient permissions for this operation",
            retry=False,
            suggestion="User needs elevated permissions"
        )
        return json.dumps(error)
    
    except Exception as e:
        # Unexpected error — log karo lekin user ko generic message do
        logger.exception(f"Unexpected error in tool {tool_name}: {e}")
        error = ToolError(
            error="internal_error",
            message="An unexpected error occurred",
            retry=False,
            suggestion="Contact support if issue persists"
        )
        return json.dumps(error)
```

### 6.3 LLM Error Recovery Example

```python
# LLM can intelligently recover from tool errors

# Round 1: LLM tries with wrong argument
tool_call_1 = {
    "name": "get_user",
    "args": {"user_id": "abc"}  # String instead of int!
}
result_1 = '{"error": "validation_error", "message": "user_id must be integer"}'

# Round 2: LLM learns from error, retries with correct type
tool_call_2 = {
    "name": "get_user",
    "args": {"user_id": 123}   # Correct!
}
result_2 = '{"id": 123, "name": "Rahul", "email": "rahul@example.com"}'

# LLM sees error → understands → corrects → succeeds
```

### 6.4 Retry with Exponential Backoff

```python
import asyncio
import random

async def execute_with_retry(tool_fn, args: dict, max_retries: int = 3):
    """Exponential backoff retry for transient failures"""
    last_error = None
    
    for attempt in range(max_retries):
        try:
            result = await asyncio.to_thread(tool_fn, **args)
            return result
        
        except (TimeoutError, ConnectionError) as e:
            last_error = e
            if attempt < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s + random jitter
                wait_time = (2 ** attempt) + random.uniform(0, 0.5)
                print(f"  Attempt {attempt+1} failed, retrying in {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
        
        except ValueError as e:
            # Validation error — retry se kuch nahi hoga
            raise e
    
    raise RuntimeError(f"Tool failed after {max_retries} attempts: {last_error}")
```

---

## 7. Tool Result Types

### 7.1 String Results (Most Common)

```python
def get_status(order_id: str) -> str:
    return f"Order {order_id} is currently in 'shipped' status"
# LLM ko simple string milta hai
```

### 7.2 Structured JSON Results (Recommended)

```python
def get_order_details(order_id: str) -> dict:
    return {
        "order_id": order_id,
        "status": "shipped",
        "items": [{"product": "Laptop", "qty": 1, "price": 45000}],
        "tracking": "TRK123456",
        "estimated_delivery": "2024-01-25"
    }
# LLM ko rich data milta hai, better response generate kar sakta hai
```

### 7.3 Image Results (Vision Models)

```python
def get_screenshot(url: str) -> dict:
    """Returns image as base64 for vision models"""
    import base64
    import requests
    
    # Screenshot lo (mock)
    image_bytes = take_screenshot(url)
    image_base64 = base64.b64encode(image_bytes).decode()
    
    return {
        "type": "image",
        "data": image_base64,
        "media_type": "image/png"
    }

# Anthropic tool result mein image dena
{
    "type": "tool_result",
    "tool_use_id": "call_xyz",
    "content": [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": "<base64_string>"
            }
        }
    ]
}
```

### 7.4 Error Results

```python
# Error ko structured format mein return karo
def risky_tool(param: str) -> dict:
    try:
        result = do_something(param)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Ya LLM ke liye is_error flag use karo (Anthropic)
{
    "type": "tool_result",
    "tool_use_id": "call_xyz",
    "is_error": True,  # LLM ko clearly pata chalega
    "content": "Database connection failed: timeout after 30s"
}
```

---

## 8. Building Good Tools

### 8.1 Single Responsibility Principle

```python
# BAD: God tool — does too much
def manage_user(action: str, user_id: int, name: str = None, email: str = None):
    if action == "get": ...
    elif action == "create": ...
    elif action == "update": ...
    elif action == "delete": ...

# GOOD: Separate tools
def get_user(user_id: int) -> dict: ...
def create_user(name: str, email: str) -> dict: ...
def update_user(user_id: int, name: str = None, email: str = None) -> dict: ...
def delete_user(user_id: int) -> dict: ...

# Fayda: LLM clearly samajhta hai kab kya use karna hai
```

### 8.2 Idempotency

```python
# Idempotent = Same result if called multiple times with same args
# Important for retry safety

# NOT idempotent (BAD for retries):
def send_payment(amount: float, account: str) -> dict:
    # Har call pe new transaction
    transaction_id = create_transaction(amount, account)
    return {"transaction_id": transaction_id}

# Idempotent (GOOD):
def send_payment(amount: float, account: str, idempotency_key: str) -> dict:
    # Same key = same result, no duplicate charge
    existing = db.get_by_idempotency_key(idempotency_key)
    if existing:
        return existing
    
    transaction_id = create_transaction(amount, account)
    db.save(idempotency_key, {"transaction_id": transaction_id})
    return {"transaction_id": transaction_id}
```

### 8.3 Return Structured Data

```python
# BAD: Raw text
def get_product_info(product_id: int) -> str:
    return f"Product: Laptop, Price: 45000, Stock: 3 units available"

# GOOD: Structured JSON
def get_product_info(product_id: int) -> dict:
    return {
        "id": product_id,
        "name": "HP Laptop 15",
        "price": 45000,
        "currency": "INR",
        "stock": 3,
        "available": True,
        "category": "electronics"
    }
# LLM structured data se much better reasoning karta hai
```

---

## 9. Tool Security

### 9.1 Input Validation — SQL Injection Prevention

```python
# VULNERABLE:
def get_user_by_name(name: str) -> list:
    query = f"SELECT * FROM users WHERE name = '{name}'"  # INJECTION!
    return db.execute(query)
# Attack: name = "'; DROP TABLE users; --"

# SECURE: Parameterized queries
def get_user_by_name(name: str) -> list:
    query = "SELECT * FROM users WHERE name = %s"
    return db.execute(query, (name,))  # Always parameterized!
```

### 9.2 Path Traversal Prevention

```python
import os
from pathlib import Path

ALLOWED_BASE_DIR = "/var/app/user_files"

# VULNERABLE:
def read_file(filename: str) -> str:
    return open(filename).read()
# Attack: filename = "../../etc/passwd"

# SECURE:
def read_file(filename: str) -> str:
    # Resolve to absolute path
    safe_path = Path(ALLOWED_BASE_DIR) / filename
    
    # Check no traversal happened
    try:
        safe_path = safe_path.resolve()
        base = Path(ALLOWED_BASE_DIR).resolve()
        safe_path.relative_to(base)  # Raises ValueError if outside
    except ValueError:
        raise PermissionError(f"Access denied: path outside allowed directory")
    
    return safe_path.read_text()
```

### 9.3 Rate Limiting Per User

```python
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls = defaultdict(list)
    
    def check(self, user_id: str, tool_name: str) -> bool:
        key = f"{user_id}:{tool_name}"
        now = time.time()
        window_start = now - self.window
        
        # Old calls clean karo
        self._calls[key] = [t for t in self._calls[key] if t > window_start]
        
        if len(self._calls[key]) >= self.max_calls:
            return False  # Rate limit exceeded
        
        self._calls[key].append(now)
        return True

rate_limiter = RateLimiter(max_calls=10, window_seconds=60)

def execute_tool(user_id: str, tool_name: str, args: dict):
    if not rate_limiter.check(user_id, tool_name):
        return {"error": "rate_limit", "message": "Too many requests, please wait"}
    
    return tool_registry[tool_name](**args)
```

### 9.4 Confirmation Pattern for Destructive Actions

```python
class PendingConfirmations:
    """Track operations waiting for user confirmation"""
    def __init__(self):
        self._pending = {}
    
    def request_confirmation(self, operation_id: str, details: dict) -> dict:
        self._pending[operation_id] = details
        return {
            "status": "confirmation_required",
            "operation_id": operation_id,
            "message": f"Are you sure you want to delete {details['count']} records?",
            "operation": details
        }
    
    def confirm(self, operation_id: str) -> dict:
        if operation_id not in self._pending:
            return {"error": "No pending operation found"}
        
        details = self._pending.pop(operation_id)
        return execute_destructive_operation(details)

confirmations = PendingConfirmations()

def delete_records(table: str, filter_condition: str, confirmed_id: str = None) -> dict:
    """Delete records — requires confirmation first"""
    
    if not confirmed_id:
        # Pehle count karo
        count = db.count(table, filter_condition)
        op_id = f"del_{table}_{int(time.time())}"
        return confirmations.request_confirmation(op_id, {
            "type": "delete",
            "table": table,
            "filter": filter_condition,
            "count": count
        })
    
    # Confirmation ke saath execute karo
    return confirmations.confirm(confirmed_id)
```

### 9.5 Audit Logging

```python
import logging
from datetime import datetime

audit_logger = logging.getLogger("tool_audit")

class AuditedToolExecutor:
    def execute(self, user_id: str, tool_name: str, args: dict) -> dict:
        # Log EVERY tool call
        audit_logger.info({
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "tool": tool_name,
            "args": self._sanitize_args(args),  # Remove sensitive data
            "ip": self._get_user_ip(user_id)
        })
        
        result = tool_registry[tool_name](**args)
        
        audit_logger.info({
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "tool": tool_name,
            "success": True,
            "result_size": len(str(result))
        })
        
        return result
    
    def _sanitize_args(self, args: dict) -> dict:
        """Passwords/tokens log mat karo"""
        sensitive_keys = {"password", "token", "api_key", "secret", "credit_card"}
        return {k: "***REDACTED***" if k in sensitive_keys else v 
                for k, v in args.items()}
```

---

## 10. Pydantic Tool Validation

### 10.1 Why Pydantic for Tools?

```
Benefits:
1. Automatic type coercion — "123" → 123 (string to int)
2. Rich validation — regex, ranges, custom validators
3. Clear error messages — LLM ko pata chalega kya galat hai
4. Auto JSON Schema generation — tool definition automatic banta hai
5. Documentation as code — description field se docs ready
```

### 10.2 Complete Pydantic Tool Schema

```python
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Literal, List
import re

class SearchProductInput(BaseModel):
    """Search for products in catalog"""
    
    query: str = Field(
        description="Search query, e.g. 'laptop under 50000', 'red shoes size 42'",
        min_length=1,
        max_length=200
    )
    category: Optional[Literal["electronics", "clothing", "books", "home", "food"]] = Field(
        default=None,
        description="Product category filter"
    )
    min_price: Optional[float] = Field(
        default=None,
        ge=0,
        description="Minimum price in INR"
    )
    max_price: Optional[float] = Field(
        default=None,
        ge=0,
        description="Maximum price in INR"
    )
    sort_by: Literal["price_asc", "price_desc", "rating", "newest"] = Field(
        default="rating",
        description="Sort order for results"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of results to return"
    )
    
    @model_validator(mode='after')
    def validate_price_range(self) -> 'SearchProductInput':
        if self.min_price and self.max_price:
            if self.min_price > self.max_price:
                raise ValueError(f"min_price ({self.min_price}) cannot exceed max_price ({self.max_price})")
        return self

# Auto-generate tool schema
def get_openai_tool_from_pydantic(name: str, model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    description = model.__doc__ or ""
    
    # Pydantic schema mein $defs clean karo
    schema.pop("$defs", None)
    schema.pop("title", None)
    
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": schema
        }
    }

# Usage
tool_def = get_openai_tool_from_pydantic("search_products", SearchProductInput)

# Validate incoming tool args
def execute_search(raw_args: dict) -> dict:
    try:
        validated = SearchProductInput.model_validate(raw_args)
        return search_products_impl(
            query=validated.query,
            category=validated.category,
            min_price=validated.min_price,
            max_price=validated.max_price,
            sort_by=validated.sort_by,
            limit=validated.limit
        )
    except ValidationError as e:
        return {"error": "validation_error", "details": e.errors()}
```

---

## 11. LangChain Tool Patterns

### 11.1 @tool Decorator

```python
from langchain_core.tools import tool
from typing import Optional

# Simplest way — just add @tool decorator
@tool
def get_weather(city: str, units: str = "celsius") -> dict:
    """Get current weather for a city.
    
    Args:
        city: City name, e.g. 'Mumbai', 'Delhi'
        units: Temperature units - 'celsius' or 'fahrenheit'
    
    Returns:
        Weather data including temperature, humidity, conditions
    """
    return {"city": city, "temp": 32, "units": units}

# Tool properties
print(get_weather.name)          # "get_weather"
print(get_weather.description)   # From docstring
print(get_weather.args_schema)   # Auto-generated Pydantic schema
```

### 11.2 StructuredTool with Explicit Schema

```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

class WeatherInput(BaseModel):
    city: str = Field(description="City name")
    units: str = Field(default="celsius", description="celsius or fahrenheit")

def weather_fn(city: str, units: str = "celsius") -> dict:
    return {"city": city, "temp": 32, "units": units}

# Explicit schema
weather_tool = StructuredTool.from_function(
    func=weather_fn,
    name="get_weather",
    description="Get current weather for a city",
    args_schema=WeatherInput,
    return_direct=False  # LLM response mein include karo
)
```

### 11.3 BaseTool — Full Control

```python
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

class DatabaseQueryInput(BaseModel):
    table: str
    filter_by: Optional[str] = None
    limit: int = 10

class DatabaseQueryTool(BaseTool):
    name: str = "query_database"
    description: str = "Query database tables"
    args_schema: type[BaseModel] = DatabaseQueryInput
    
    # Custom attributes
    connection_string: str = "sqlite:///app.db"
    
    def _run(self, table: str, filter_by: str = None, limit: int = 10) -> dict:
        """Sync implementation"""
        # Your actual DB query logic
        return {"table": table, "rows": [], "count": 0}
    
    async def _arun(self, table: str, filter_by: str = None, limit: int = 10) -> dict:
        """Async implementation"""
        # Async DB query
        return await async_db_query(table, filter_by, limit)

db_tool = DatabaseQueryTool(connection_string="postgresql://...")
```

### 11.4 ToolException

```python
from langchain_core.tools import tool, ToolException

@tool
def delete_record(record_id: int, table: str) -> dict:
    """Delete a record from database. Use only when explicitly confirmed by user."""
    
    if table not in ALLOWED_TABLES:
        raise ToolException(f"Table '{table}' is not allowed for deletion")
    
    if not record_exists(table, record_id):
        raise ToolException(f"Record {record_id} not found in {table}")
    
    delete_from_db(table, record_id)
    return {"deleted": True, "id": record_id, "table": table}

# ToolException — LLM ko graceful error message milta hai
# Regular Exception — agent crash kar sakta hai
```

### 11.5 return_direct

```python
@tool(return_direct=True)  # Skip LLM, directly return to user
def get_help_text() -> str:
    """Get help documentation"""
    return """
    Available commands:
    - 'show orders': View your recent orders  
    - 'track order <id>': Track specific order
    - 'contact support': Connect with support team
    """
# return_direct=True mein LLM tool result ko process nahi karta
# Direct user ko mila jaata hai — useful for formatted outputs
```

---

## 12. Computer Use (Anthropic)

### 12.1 Concept

```
Computer Use = LLM can control a computer like a human!

Available Tools:
1. computer  → Screenshot, click, type, scroll, key press
2. bash      → Execute shell commands
3. text_editor → View/create/edit files

Use Case Example:
User: "Go to flipkart.com and search for laptops under 50000"

Agent Loop:
1. screenshot() → See current screen
2. click(x=500, y=300) → Click browser address bar  
3. type("flipkart.com") → Type URL
4. key("Return") → Press Enter
5. screenshot() → See Flipkart
6. type("laptop") → Search box mein type karo
7. click(search_button_x, search_button_y) → Search
8. screenshot() → See results
9. Analyze results and respond to user
```

### 12.2 Computer Use Code (Beta)

```python
import anthropic

client = anthropic.Anthropic()

tools = [
    {
        "type": "computer_20241022",
        "name": "computer",
        "display_width_px": 1024,
        "display_height_px": 768,
        "display_number": 1
    },
    {
        "type": "bash_20241022",
        "name": "bash"
    },
    {
        "type": "text_editor_20241022",
        "name": "str_replace_editor"
    }
]

response = client.beta.messages.create(
    model="claude-opus-4-5",
    max_tokens=4096,
    tools=tools,
    messages=[{
        "role": "user",
        "content": "Check current directory and list Python files"
    }],
    betas=["computer-use-2024-10-22"]
)
```

### 12.3 Safety Considerations

```
RISKS:
- Agent delete important files kar sakta hai
- Unintended form submissions
- Sensitive data exposure (screenshots mein passwords)
- Infinite loops

MITIGATIONS:
- Sandbox environment use karo (VM/Docker)
- Read-only mode option
- Human-in-the-loop for destructive actions  
- Screenshot redaction for sensitive info
- Timeout limits
- Action logging
```

---

## 13. MCP (Model Context Protocol) Tools

### 13.1 What is MCP?

```
MCP = Anthropic ka open standard for tool integration

Problem it solves:
- Har application ko apne tools hardcode karne padte the
- Integration work repeat hota tha
- Tools reusable nahi the

MCP Solution:
- Tools ek standardized "server" expose karta hai
- Claude (ya koi bhi MCP client) dynamically discover karta hai
- Once write, use everywhere

Architecture:
┌──────────────────┐     MCP Protocol      ┌─────────────────┐
│   Claude/LLM     │◄──────────────────────►│   MCP Server    │
│   (MCP Client)   │   JSON-RPC over stdio  │   (Your Tools)  │
└──────────────────┘                        └─────────────────┘
```

### 13.2 MCP Server Example

```python
# server.py — MCP server that exposes tools
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server("my-tools-server")

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Ye tools Claude ko dikhate hain"""
    return [
        types.Tool(
            name="get_weather",
            description="Get weather for a city",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            }
        ),
        types.Tool(
            name="search_database",
            description="Search company database",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "table": {"type": "string"}
                },
                "required": ["query"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Tool execution handler"""
    
    if name == "get_weather":
        city = arguments["city"]
        # Actual weather API call
        weather = fetch_weather(city)
        return [types.TextContent(
            type="text",
            text=f"Weather in {city}: {weather['temp']}°C, {weather['condition']}"
        )]
    
    elif name == "search_database":
        results = db_search(arguments["query"], arguments.get("table"))
        return [types.TextContent(
            type="text",
            text=str(results)
        )]
    
    raise ValueError(f"Unknown tool: {name}")

# Run server
async def main():
    async with stdio_server() as streams:
        await server.run(
            streams[0], streams[1],
            server.create_initialization_options()
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### 13.3 MCP vs Hardcoded Tools

```
Feature          | Hardcoded Tools        | MCP Tools
-----------------|------------------------|------------------------
Reusability      | Per-app               | Universal standard
Discovery        | Manual definition     | Dynamic (list_tools)
Installation     | Code change needed    | Config change only
Maintenance      | In app codebase       | Separate server
Sharing          | Cannot share easily   | Anyone can use your MCP
Claude Desktop   | Not directly usable   | Direct integration
Security         | App handles           | Server handles
```

### 13.4 Claude Desktop Integration

```json
// ~/.config/claude/claude_desktop_config.json
{
  "mcpServers": {
    "my-weather": {
      "command": "python",
      "args": ["/path/to/weather_mcp_server.py"]
    },
    "my-database": {
      "command": "node",
      "args": ["/path/to/db_mcp_server.js"],
      "env": {
        "DB_URL": "postgresql://localhost/mydb"
      }
    }
  }
}
```

---

## 14. Interview Questions & Answers

### Q1: Tool call flow ke exact steps kya hain?

**Answer:**
```
1. User message + tool definitions LLM ko bhejte hain
2. LLM "tool_use"/"tool_calls" response deta hai (tool name + arguments)
3. Humara code tool execute karta hai (actual function call)
4. Tool result messages mein add karte hain (role: "tool" in OpenAI)
5. Updated messages dobara LLM ko bhejte hain
6. LLM final text response deta hai (stop_reason: "end_turn"/"stop")

Key point: LLM khud execute nahi karta — sirf instructions deta hai.
```

### Q2: Parallel tool calls ka benefit kya hai?

**Answer:**
```
Agar 3 independent API calls hain (weather for 3 cities):
- Sequential: 3 × 500ms = 1500ms total
- Parallel (asyncio.gather): max(500ms, 500ms, 500ms) = 500ms total

3x faster user experience.

asyncio.gather() se sab simultaneously execute hote hain.
LLM automatically parallel calls deta hai jab requests independent hote hain.
```

### Q3: Tool errors ko kaise handle karte hain?

**Answer:**
```
1. Tool mein try-except lagao
2. Error ko structured JSON return karo:
   {"error": "timeout", "message": "...", "retry": true}
3. LLM error dekh ke decide karta hai — retry, alternative use, ya user ko batao
4. is_error: true flag use karo (Anthropic) for clear error signaling
5. Critical errors ke liye: don't expose internal details to LLM
6. Always audit log karo tool failures
```

### Q4: Pydantic ko tool validation ke liye kyun use karte hain?

**Answer:**
```
1. Type coercion: LLM kabhi kabhi "123" (string) bhejta hai instead of 123 (int)
   Pydantic automatically convert karta hai
2. Validation: min/max/pattern/enum — invalid data filter hota hai
3. Clear errors: LLM ko exactly pata chalta hai kya galat hai → retry possible
4. Schema generation: model.model_json_schema() → OpenAI/Anthropic format ready
5. Documentation: Field(description=...) → tool description mein directly use

vs manual validation: boilerplate, error-prone, no auto-schema
```

### Q5: ReAct vs plain tool use — kya difference hai?

**Answer:**
```
Plain Tool Use:
- LLM tools call karta hai
- No explicit reasoning step
- Good for simple tasks

ReAct (Reasoning + Acting):
- Explicit Thought → Action → Observation cycle
- LLM "sochta" hai before har action
- Better for complex multi-step tasks
- More transparent reasoning
- More tokens but better accuracy

Example ReAct:
Thought: "User laptop dhundh raha hai. Search karna hoga."
Action: search_products(query="laptop")
Observation: [{"id": 42, "name": "HP", "price": 45000}]
Thought: "HP laptop budget mein hai. Availability check karo."
Action: check_stock(product_id=42)
...
```

### Q6: Max iterations kyun lagaate hain agent loop mein?

**Answer:**
```
Problems without max iterations:
1. Circular reasoning: LLM same tools repeatedly call karta rahe
2. Tool errors: Tool fail ho, LLM retry karta rahe indefinitely
3. Cost: Har LLM call charges hote hain ($$$)
4. Latency: User infinite wait kare
5. Resources: Server memory/CPU exhaust ho

Solution: MAX_ITERATIONS = 10-20

When hit: Return graceful error:
"Task too complex. Please break it into smaller steps."
```

### Q7: Tool security ke major risks kya hain?

**Answer:**
```
1. Prompt Injection: User tool arguments mein malicious instructions inject kare
   Mitigation: Input validation, never execute tool args as code

2. SQL Injection: DB tool mein unsanitized query
   Mitigation: Parameterized queries always

3. Path Traversal: File tool mein ../../etc/passwd type paths
   Mitigation: Path.resolve() + relative_to() check

4. Resource Exhaustion: Unlimited DB queries, large file reads
   Mitigation: Rate limiting, max limit params

5. Privilege Escalation: Tool unauthorized operations perform kare
   Mitigation: Allowlist, RBAC, principle of least privilege

6. Data Exfiltration: Tool sensitive data return kare
   Mitigation: Output filtering, field-level permissions
```

### Q8: LangChain @tool vs BaseTool — kab kya use karo?

**Answer:**
```
@tool decorator:
- Simple functions ke liye
- Quick prototyping
- Pydantic schema auto-generate
- Less boilerplate

BaseTool class:
- Complex tools with state/config
- Custom attributes (DB connections, API clients)
- Override _run and _arun separately  
- More control over behavior
- Dependency injection

StructuredTool.from_function():
- Existing function ko tool banana hai
- Explicit Pydantic schema chahiye
- Between @tool and BaseTool complexity
```

### Q9: return_direct=True kab use karte hain?

**Answer:**
```
return_direct=True: Tool output directly user ko milta hai, LLM process nahi karta

Use cases:
1. Pre-formatted HTML/markdown output — LLM reformat na kare
2. Large datasets — LLM ko process cost nahi
3. Exact output required — LLM paraphrase na kare
4. Help text, documentation — already human-readable

Default (return_direct=False):
Tool output LLM ko milta hai, woh synthesize karke final response deta hai
Better when: Multiple tools combine karne hain, natural language response chahiye
```

### Q10: MCP vs hardcoded tools — production mein kya prefer karein?

**Answer:**
```
Hardcoded Tools (prefer when):
- Simple, app-specific tools
- Full control needed
- No sharing required
- Small team, single application

MCP (prefer when):
- Same tools multiple applications mein use karni hain
- Team has separate tool developers
- Claude Desktop integration chahiye
- Enterprise: centralized tool governance
- Tool marketplace banana hai

Production recommendation:
- Internal tools: Hardcoded (simpler)
- Shared/reusable tools: MCP server
- Customer-facing: MCP with proper auth
```

---

## Summary

Tool Use mastery ke liye ye key concepts yaad rakhein:

1. **Flow**: messages → LLM → tool_use → execute → result → LLM → final response
2. **Parallel**: asyncio.gather() for independent tool calls (3x+ speedup)
3. **Error handling**: Structured errors, retry logic, graceful recovery
4. **Pydantic**: Validation + auto schema generation = best practice
5. **Security**: Input validation, SQL injection, path traversal, rate limiting
6. **LangChain**: @tool quick, BaseTool full control
7. **MCP**: Standardized tool server = reusable, shareable tools
8. **Max iterations**: Always set to prevent infinite loops + cost control

---

*Interview tip: Tool use questions mein always security aur error handling mention karo — ye senior developer ki soch dikhata hai.*
