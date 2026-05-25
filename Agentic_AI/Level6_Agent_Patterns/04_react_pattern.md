# Level 6 — Doc 4: ReAct Pattern (From Scratch) ⭐

> **Goal:** ReAct (Reasoning + Acting) — agentic AI ka **most important pattern**. No framework. Pure Python. Interview gold.

---

## 1. What is ReAct?

**ReAct = Reasoning + Acting**, by Google Research (2022).

Pattern:
```
Thought: "I need to find weather, so I'll use weather tool"
Action: get_weather("Mumbai")
Observation: {"temp": 32, "condition": "sunny"}
Thought: "I have the info. Now I can answer."
Final Answer: "Mumbai is 32°C and sunny."
```

**Loop:** Thought → Action → Observation → Thought → ... → Final Answer

This is THE pattern behind:
- LangGraph agents
- AutoGPT
- BabyAGI
- Most "agent" frameworks

---

## 2. Why "From Scratch"?

Frameworks (LangChain, LangGraph) abstract this. But:
- **Interview question:** "Implement ReAct from scratch"
- **Production debugging:** Understanding internals saves days
- **Customization:** Frameworks restrict creativity

Building it once → understand all agent frameworks forever.

---

## 3. The Algorithm

```python
def react_agent(question, tools, max_iterations=10):
    prompt = build_initial_prompt(question, tools)
    history = []
    
    for i in range(max_iterations):
        # 1. Ask LLM to think + act
        response = llm.call(prompt + history_to_text(history))
        
        # 2. Parse response
        thought, action, action_input = parse(response)
        
        # 3. If "Final Answer", we're done
        if action == "Final Answer":
            return action_input
        
        # 4. Execute the action (tool call)
        observation = execute_tool(action, action_input)
        
        # 5. Add to history
        history.append({
            "thought": thought,
            "action": action,
            "action_input": action_input,
            "observation": observation
        })
    
    return "Max iterations reached"
```

That's it. ~15 lines of Python.

---

## 4. The ReAct Prompt Template

```
You are an AI agent. Solve the user's question step-by-step.

You have access to these tools:
{tool_descriptions}

Use this EXACT format:
Thought: think about what to do
Action: tool_name
Action Input: {parameters as JSON}
Observation: result will appear here

Repeat Thought/Action/Observation until you have enough info.

When done, respond with:
Thought: I now have the answer
Final Answer: your answer here

Question: {user_question}

{history}

Thought:
```

The model is trained well enough to follow this format from the prompt.

---

## 5. Parsing LLM Output

```python
import re
from typing import Optional

def parse_react_output(text: str) -> dict:
    """Parse Thought/Action/Action Input from LLM output."""
    
    # Final answer check
    final_match = re.search(r"Final Answer:\s*(.*)", text, re.DOTALL)
    if final_match:
        return {
            "type": "final",
            "answer": final_match.group(1).strip()
        }
    
    # Extract Thought
    thought_match = re.search(r"Thought:\s*(.*?)(?=Action:|$)", text, re.DOTALL)
    thought = thought_match.group(1).strip() if thought_match else ""
    
    # Extract Action
    action_match = re.search(r"Action:\s*([^\n]+)", text)
    action = action_match.group(1).strip() if action_match else ""
    
    # Extract Action Input
    input_match = re.search(r"Action Input:\s*(.*?)(?=Observation:|$)", text, re.DOTALL)
    action_input_str = input_match.group(1).strip() if input_match else ""
    
    # Try to parse as JSON
    import json
    try:
        action_input = json.loads(action_input_str)
    except:
        action_input = action_input_str
    
    return {
        "type": "action",
        "thought": thought,
        "action": action,
        "action_input": action_input
    }
```

---

## 6. Complete Working ReAct Agent

```python
import json
import re
from openai import OpenAI

client = OpenAI()


class ReActAgent:
    def __init__(self, tools: dict):
        self.tools = tools  # {name: function}
        self.history = []
        
    def build_prompt(self, question: str) -> str:
        tool_descriptions = "\n".join(
            f"- {name}: {func.__doc__}" for name, func in self.tools.items()
        )
        
        history_text = ""
        for step in self.history:
            history_text += f"\nThought: {step['thought']}\n"
            history_text += f"Action: {step['action']}\n"
            history_text += f"Action Input: {json.dumps(step['action_input'])}\n"
            history_text += f"Observation: {step['observation']}\n"
        
        return f"""You are an AI agent. Solve the user's question step-by-step using tools.

TOOLS AVAILABLE:
{tool_descriptions}

FORMAT:
Thought: think about what to do
Action: tool_name
Action Input: {{"param": "value"}}
Observation: result will appear here

When you have the answer, respond with:
Thought: I now have the answer
Final Answer: your answer

Question: {question}
{history_text}
Thought:"""
    
    def run(self, question: str, max_iterations: int = 8) -> str:
        for iteration in range(max_iterations):
            prompt = self.build_prompt(question)
            
            # Call LLM
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                stop=["Observation:"],  # Stop before generating observation
                temperature=0
            )
            output = response.choices[0].message.content
            
            # Parse
            parsed = parse_react_output(output)
            
            # Final answer?
            if parsed["type"] == "final":
                return parsed["answer"]
            
            # Execute tool
            tool_name = parsed["action"]
            tool_args = parsed["action_input"]
            
            if tool_name not in self.tools:
                observation = f"Error: Unknown tool '{tool_name}'"
            else:
                try:
                    observation = self.tools[tool_name](**tool_args)
                except Exception as e:
                    observation = f"Error: {e}"
            
            # Add to history
            self.history.append({
                "thought": parsed["thought"],
                "action": tool_name,
                "action_input": tool_args,
                "observation": observation
            })
        
        return "Max iterations reached"
```

Use it:
```python
def get_weather(city: str):
    """Get weather for a city."""
    return f"{city}: 28°C, sunny"

def calculator(expression: str):
    """Calculate math."""
    return eval(expression)

agent = ReActAgent({
    "get_weather": get_weather,
    "calculator": calculator
})

result = agent.run("What is the weather in Mumbai and what is 15*8?")
print(result)
```

---

## 7. Tracing the Execution

Let's trace what happens for: "What's weather in Mumbai and what's 15*8?"

```
Iteration 1:
  LLM output:
    Thought: I need to find weather in Mumbai first.
    Action: get_weather
    Action Input: {"city": "Mumbai"}
  
  Execute: get_weather(city="Mumbai")
  Observation: "Mumbai: 28°C, sunny"

Iteration 2:
  LLM sees history, outputs:
    Thought: Now I need to calculate 15*8.
    Action: calculator
    Action Input: {"expression": "15*8"}
  
  Execute: calculator(expression="15*8")
  Observation: 120

Iteration 3:
  LLM sees history, outputs:
    Thought: I have both pieces of info now.
    Final Answer: The weather in Mumbai is 28°C and sunny. 15 * 8 = 120.
  
  Return: "The weather in Mumbai is 28°C and sunny. 15 * 8 = 120."
```

3 iterations. 2 tool calls. Final answer.

---

## 8. ReAct vs Function Calling

We covered function calling in Level 4. So why ReAct?

| Feature | Function Calling | ReAct |
|---|---|---|
| **Format** | Native JSON tool calls | Text-based |
| **Reasoning** | Implicit | Explicit (Thought:) |
| **Debugging** | Harder | Easy (see thoughts) |
| **Model support** | Only newer models | Any text model |
| **Customization** | Limited | Full control |
| **Open source models** | Spotty support | Works everywhere |

**When to use ReAct:**
- Want explicit reasoning visible
- Using open-source models without tool use support
- Want fine control over agent behavior

**When to use Function Calling:**
- Using OpenAI/Claude/etc.
- Want simpler code
- Don't need to see reasoning explicitly

In production, modern systems use **function calling** (cleaner). ReAct is for understanding + custom needs.

---

## 9. Variations

### ReAct + Reflection
Add a reflection step:
```
Thought → Action → Observation → REFLECT (did this work?) → 
  if good: continue
  if bad: try different approach
```

### MRKL (Modular Reasoning, Knowledge, Language)
Similar to ReAct but more structured tool routing.

### Plan-and-Solve (Plan & Execute)
Generate full plan first, then execute (next doc).

---

## 10. Common Pitfalls

### Pitfall 1: LLM Outputs Wrong Format
```
Solution: Use stop sequences (stop=["Observation:"])
          Strict parsing with fallback
          Few-shot examples in prompt
```

### Pitfall 2: Infinite Loops
```
LLM keeps calling same tool with same args.
Solution: 
  - max_iterations limit
  - Detect repeated calls
  - Log warnings
```

### Pitfall 3: Wrong Tool Choice
```
LLM picks wrong tool.
Solution:
  - Better tool descriptions (covered in Level 4 Doc 4)
  - Add anti-cousin clarifications
```

### Pitfall 4: Bad Argument Format
```
Action Input: city is Mumbai
(Not JSON!)
Solution: Lenient parsing, examples in prompt
```

---

## 11. Production-Grade ReAct

```python
class ProductionReActAgent:
    def __init__(self, tools, max_iter=8, timeout=30, budget=0.10):
        self.tools = tools
        self.max_iter = max_iter
        self.timeout = timeout
        self.budget = budget
        
        # Metrics
        self.total_cost = 0
        self.iteration_count = 0
        self.tools_called = []
        
    def run(self, question, on_step=None):
        start_time = time.time()
        history = []
        
        for i in range(self.max_iter):
            # Safety checks
            if time.time() - start_time > self.timeout:
                return self._timeout_response(history)
            if self.total_cost > self.budget:
                return self._budget_response(history)
            
            # LLM call
            response = self._llm_call(question, history)
            self.total_cost += response.cost
            
            # Parse
            parsed = parse_react_output(response.text)
            
            # Stream step to user (optional)
            if on_step:
                on_step(parsed)
            
            # Final answer?
            if parsed["type"] == "final":
                return self._success_response(parsed["answer"], history)
            
            # Detect stuck (same tool + args as before)
            if self._is_stuck(parsed, history):
                return self._stuck_response(history)
            
            # Execute tool
            obs = self._execute_tool_safely(parsed)
            
            history.append({**parsed, "observation": obs})
            self.tools_called.append(parsed["action"])
        
        return self._max_iter_response(history)
    
    def _is_stuck(self, parsed, history):
        if len(history) < 2:
            return False
        last = history[-1]
        return (parsed.get("action") == last.get("action") and 
                parsed.get("action_input") == last.get("action_input"))
```

---

## 12. Interview Questions

1. **Q: Explain ReAct.**
   - Reasoning + Acting. Loop: Thought → Action → Observation → ... → Final Answer

2. **Q: ReAct vs function calling?**
   - ReAct: text-based, explicit reasoning, works on any model. Function calling: native, cleaner, needs modern model.

3. **Q: How to handle infinite loops?**
   - Max iterations, detect repeated calls, log/break.

4. **Q: How to debug a stuck agent?**
   - Print thoughts at each step (ReAct makes this easy)

5. **Q: When NOT to use ReAct?**
   - Single tool call sufficient → just use function calling directly. ReAct overhead pointless.

---

## 13. Exercises

1. **Easy:** Build the basic ReAct agent. Test with 2 tools (weather, calculator).
2. **Medium:** Add streaming — show each thought as it's generated.
3. **Hard:** Add tool description-based routing — auto-detect which tool to use from question.
4. **Pro:** Implement self-critique — after each action, ReAct evaluates if observation was useful.

---

## 14. Key Takeaways

✅ ReAct = Thought → Action → Observation → repeat
✅ ~50 lines of Python, no framework needed
✅ Loop until LLM says "Final Answer"
✅ Use `stop=["Observation:"]` so LLM doesn't hallucinate observations
✅ Parse with regex; be lenient on format
✅ Production: add timeout, budget, stuck detection, logging
✅ ReAct = great for explicit reasoning. Function calling = great for simplicity.

**Next:** [05_plan_and_execute.md](05_plan_and_execute.md) — Plan & Execute pattern
