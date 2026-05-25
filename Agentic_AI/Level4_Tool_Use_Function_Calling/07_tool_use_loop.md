# Level 4 — Doc 7: The Tool Use Loop (Deep)

> **Goal:** Agent loop ki saari intricacies — termination, max iterations, state management, summary buffers.

---

## 1. Anatomy of the Loop

```python
def agent_loop(user_msg, tools, tool_funcs, max_iter=10):
    messages = [{"role": "user", "content": user_msg}]
    
    for i in range(max_iter):
        # Step 1: Call LLM with current state
        response = llm_call(messages, tools)
        
        # Step 2: Decide if done
        if not response.tool_calls:
            return response.content  # Final answer
        
        # Step 3: Execute tools
        results = execute_tools(response.tool_calls, tool_funcs)
        
        # Step 4: Add to history
        messages.append(response.assistant_message)
        messages.extend(results)
        
        # Loop back
    
    return "Max iterations reached"  # Failure mode
```

---

## 2. Termination Conditions

LLM stops calling tools when:
1. **Has final answer** (returns text, no tool_calls)
2. **Confused / stuck** (might infinite-loop)
3. **Max iterations** (your safety limit)

### Detect "stuck" patterns:
```python
def is_stuck(messages, lookback=4):
    """Detect if LLM is repeating tool calls."""
    recent_tool_calls = []
    for msg in messages[-lookback:]:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                key = (tc["function"]["name"], tc["function"]["arguments"])
                recent_tool_calls.append(key)
    
    # If same call repeated, probably stuck
    return len(recent_tool_calls) != len(set(recent_tool_calls))
```

---

## 3. State Management

For long-running agents, you need to manage:

```python
class AgentState:
    def __init__(self):
        self.messages: list = []           # Conversation history
        self.tool_results: dict = {}        # Cache of tool results
        self.context: dict = {}             # Shared state (user_id, session_id)
        self.iteration: int = 0             # Current loop iteration
        self.start_time: float = time.time()
        self.cost: float = 0.0
        self.tools_used: list = []          # For audit log
    
    def add_message(self, msg):
        self.messages.append(msg)
    
    def add_tool_call(self, name, args, result):
        self.tools_used.append({
            "iteration": self.iteration,
            "tool": name,
            "args": args,
            "result_summary": str(result)[:200]
        })
    
    def to_dict(self):
        return {
            "iterations": self.iteration,
            "elapsed_seconds": time.time() - self.start_time,
            "total_cost": self.cost,
            "tools_used": self.tools_used,
            "message_count": len(self.messages)
        }
```

---

## 4. Context Window Management

Long agent runs blow context window. Strategies:

### Strategy 1: Truncate old messages
```python
def truncate_messages(messages, max_tokens=10000):
    """Keep only recent messages within token budget."""
    while count_tokens(messages) > max_tokens and len(messages) > 5:
        # Remove second-oldest (keep system, drop oldest user/assistant pair)
        if messages[1]["role"] != "system":
            messages.pop(0)
        else:
            messages.pop(1)
    return messages
```

### Strategy 2: Summarize older messages
```python
def summarize_history(messages):
    """LLM-summarize old messages."""
    if len(messages) < 10:
        return messages
    
    # Keep system + last 5 messages
    system_msg = messages[0]
    recent = messages[-5:]
    old = messages[1:-5]
    
    summary_text = llm_call(
        f"Summarize this conversation history in 200 words: {old}"
    )
    
    return [
        system_msg,
        {"role": "system", "content": f"Previous conversation summary: {summary_text}"},
        *recent
    ]
```

### Strategy 3: Tool result compression
```python
def compress_tool_results(result):
    """Don't pass huge results back. Summarize."""
    if isinstance(result, dict) and "rows" in result:
        if len(result["rows"]) > 10:
            return {
                "rows_count": len(result["rows"]),
                "sample": result["rows"][:5],
                "note": "Showing 5 of N rows. Use pagination tool for more."
            }
    return result
```

---

## 5. Detecting Final Answer

OpenAI:
```python
if response.choices[0].finish_reason == "stop":  # vs "tool_calls"
    return response.choices[0].message.content
```

Anthropic:
```python
if response.stop_reason == "end_turn":  # vs "tool_use"
    return get_text_from_blocks(response.content)
```

---

## 6. Force LLM to Give Final Answer

If max iterations approaching, force final answer:

```python
def agent_loop(user_msg, tools, tool_funcs, max_iter=10):
    messages = [{"role": "user", "content": user_msg}]
    
    for i in range(max_iter):
        # Last iteration: disable tools
        if i == max_iter - 1:
            response = llm_call(messages, tools=None)  # No tools
            return response.content
        
        response = llm_call(messages, tools)
        
        if not response.tool_calls:
            return response.content
        
        # ... execute tools, add to messages
```

---

## 7. Cost Tracking

```python
class CostTrackingLoop:
    def __init__(self, budget=1.0):
        self.budget = budget
        self.spent = 0.0
    
    def call_llm(self, messages, tools):
        # Estimate cost before call
        estimated_cost = self._estimate(messages, tools)
        if self.spent + estimated_cost > self.budget:
            raise BudgetExceededError(f"Budget {self.budget}, already spent {self.spent}")
        
        response = llm.call(messages, tools)
        actual_cost = self._calculate(response)
        self.spent += actual_cost
        return response
```

---

## 8. Streaming the Loop

For better UX, stream both LLM thoughts and tool results:

```python
async def streaming_agent_loop(user_msg, tools, tool_funcs):
    messages = [{"role": "user", "content": user_msg}]
    
    for i in range(10):
        yield {"event": "iteration_start", "iteration": i}
        
        # Stream LLM response
        async for chunk in llm.stream(messages, tools):
            if chunk.text:
                yield {"event": "text_chunk", "text": chunk.text}
            if chunk.tool_call:
                yield {"event": "tool_call_start", "name": chunk.tool_call.name}
        
        # Execute tools
        for tc in tool_calls:
            yield {"event": "tool_executing", "name": tc.name}
            result = await tool_funcs[tc.name](**tc.args)
            yield {"event": "tool_result", "name": tc.name, "result": result}
        
        # Check if done
        if not tool_calls:
            yield {"event": "agent_complete"}
            break
```

---

## 9. Multi-Agent Loop (Hierarchical)

For complex tasks, agent can spawn sub-agents:

```python
def supervisor_agent(task):
    """Supervisor delegates to specialist agents."""
    plan = llm.plan(task)
    
    results = {}
    for subtask in plan:
        if subtask.type == "research":
            results[subtask.id] = research_agent(subtask)
        elif subtask.type == "code":
            results[subtask.id] = code_agent(subtask)
        elif subtask.type == "review":
            results[subtask.id] = review_agent(subtask, results)
    
    return llm.synthesize(task, plan, results)
```

We'll cover this fully in Level 6 (LangGraph multi-agent).

---

## 10. Production Loop Pattern

```python
def production_agent_loop(
    user_msg: str,
    tools: list,
    tool_funcs: dict,
    max_iter: int = 10,
    timeout_seconds: int = 60,
    budget_dollars: float = 0.50,
    enable_streaming: bool = False
):
    state = AgentState()
    start_time = time.time()
    
    state.add_message({"role": "user", "content": user_msg})
    
    for state.iteration in range(max_iter):
        # Safety checks
        if time.time() - start_time > timeout_seconds:
            return {"status": "timeout", "state": state.to_dict()}
        if state.cost > budget_dollars:
            return {"status": "budget_exceeded", "state": state.to_dict()}
        if is_stuck(state.messages):
            return {"status": "stuck", "state": state.to_dict()}
        
        # Truncate if context too long
        state.messages = truncate_messages(state.messages)
        
        # LLM call
        try:
            response = llm_call_with_cost(state.messages, tools)
            state.cost += response.cost
        except Exception as e:
            return {"status": "llm_error", "error": str(e), "state": state.to_dict()}
        
        # Done?
        if not response.tool_calls:
            return {"status": "success", "answer": response.content, "state": state.to_dict()}
        
        # Execute tools
        results = execute_tools_parallel(response.tool_calls, tool_funcs)
        for tc, result in zip(response.tool_calls, results):
            state.add_tool_call(tc.name, tc.args, result)
        
        # Update messages
        state.add_message(response.assistant_message)
        state.messages.extend(results)
    
    return {"status": "max_iterations", "state": state.to_dict()}
```

---

## 11. Key Takeaways

✅ Loop = LLM call → check tools → execute → repeat
✅ Always set `max_iterations` to prevent infinite loops
✅ Detect "stuck" patterns (repeating same calls)
✅ Manage context window (truncate, summarize, compress)
✅ Track cost + budget enforcement
✅ Stream events for UX
✅ State management — preserve across iterations
✅ Force final answer in last iteration (disable tools)

**Next:** [08_tool_error_handling.md](08_tool_error_handling.md) — Error handling, retries, graceful failures
