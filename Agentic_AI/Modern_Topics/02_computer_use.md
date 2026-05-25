# Modern Topics — Doc 2: Computer Use (Claude Desktop Control)

> **Goal:** Claude can take screenshots, move mouse, type — control your computer like a human. Cutting-edge 2024-26.

---

## 1. What is Computer Use?

Anthropic's API where Claude can:
- Take screenshots (see what's on screen)
- Move mouse, click, double-click
- Type text
- Press keys
- Scroll

It's a **vision-based** agent that interacts with any GUI like a human would.

---

## 2. Use Cases

### Automation
- Fill forms
- Data entry
- Test web apps
- Process documents

### Workflows
- Open app → click button → enter data → submit
- Multi-step tasks across apps

### Accessibility
- Help users with disabilities navigate

### Research
- Browse web on user's behalf
- Compare prices across sites

---

## 3. Basic Setup

```python
from anthropic import Anthropic

client = Anthropic()

response = client.beta.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    tools=[
        {
            "type": "computer_20241022",
            "name": "computer",
            "display_width_px": 1920,
            "display_height_px": 1080,
            "display_number": 1
        },
        {
            "type": "text_editor_20241022",
            "name": "str_replace_editor"
        },
        {
            "type": "bash_20241022",
            "name": "bash"
        }
    ],
    messages=[
        {"role": "user", "content": "Open Calculator and compute 1234 * 567"}
    ],
    betas=["computer-use-2024-10-22"]
)
```

---

## 4. Computer Actions Available

Claude can request:

| Action | Description |
|---|---|
| `screenshot` | Take screenshot of current display |
| `left_click` | Click at (x, y) |
| `right_click` | Right-click at (x, y) |
| `double_click` | Double-click at (x, y) |
| `mouse_move` | Move mouse to (x, y) |
| `type` | Type text |
| `key` | Press key (e.g., "Return", "ctrl+a") |
| `scroll` | Scroll up/down |
| `cursor_position` | Get current cursor location |

---

## 5. The Loop

```python
def computer_use_loop(task):
    messages = [{"role": "user", "content": task}]
    
    while True:
        response = client.beta.messages.create(
            model="claude-3-5-sonnet-20241022",
            tools=COMPUTER_TOOLS,
            messages=messages,
            betas=["computer-use-2024-10-22"]
        )
        
        messages.append({"role": "assistant", "content": response.content})
        
        if response.stop_reason != "tool_use":
            return response.content
        
        # Execute Claude's requested action
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                if block.name == "computer":
                    result = execute_computer_action(block.input)
                elif block.name == "bash":
                    result = execute_bash(block.input)
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result  # Can include images!
                })
        
        messages.append({"role": "user", "content": tool_results})
```

---

## 6. Executing Actions (Sandboxed)

Use Docker/VM for safety:

```python
import pyautogui

def execute_computer_action(action: dict):
    action_type = action.get("action")
    
    if action_type == "screenshot":
        screenshot = pyautogui.screenshot()
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.b64encode(screenshot.tobytes()).decode()
            }
        }
    
    elif action_type == "left_click":
        coords = action["coordinate"]
        pyautogui.click(coords[0], coords[1])
        return "Clicked"
    
    elif action_type == "type":
        text = action["text"]
        pyautogui.write(text, interval=0.05)
        return "Typed"
    
    elif action_type == "key":
        keys = action["text"]
        pyautogui.hotkey(*keys.split("+"))
        return "Pressed"
    
    # etc.
```

**SECURITY:** Run in isolated VM/container. Never on user's actual machine without explicit consent.

---

## 7. Reference Implementation (Anthropic's)

```bash
# Anthropic provides ready-to-use Docker setup
docker run -it \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -v $HOME/.anthropic:/home/computeruse/.anthropic \
  -p 5900:5900 \
  -p 8501:8501 \
  -p 6080:6080 \
  -p 8080:8080 \
  ghcr.io/anthropics/anthropic-quickstarts:computer-use-demo-latest
```

Provides:
- Ubuntu desktop in browser
- Claude controls it
- See screen + chat with Claude

---

## 8. Example Task

```python
task = "Open the Firefox browser, search for 'Anthropic Claude', click first result"

result = computer_use_loop(task)
```

Claude:
1. screenshot() → sees desktop
2. left_click(firefox_icon)
3. screenshot() → sees Firefox open
4. left_click(address_bar)
5. type("Anthropic Claude")
6. key("Return")
7. screenshot() → sees results
8. left_click(first_result)
9. Done!

---

## 9. Limitations

- **Slow** — each action = full LLM round-trip
- **Expensive** — many screenshots = many vision tokens
- **Brittle** — UI changes break workflows
- **Errors** — sometimes misses targets
- **Confused** — modal dialogs, popups can derail it

Use for tasks where:
- Other automation doesn't work
- API/SDK isn't available
- Vision-based reasoning needed

---

## 10. Alternatives

### OpenAI Computer Use (via Operator)
OpenAI's recent product. Similar capability.

### Playwright + LLM
For web automation specifically:
```python
from playwright.sync_api import sync_playwright

# Take screenshot, send to LLM, get next action
```

### AutoGen / browser-use
Open-source frameworks for browser-based agents.

### Selenium / RPA (UiPath)
Traditional approach for predictable workflows.

---

## 11. Security Considerations

🚨 **Critical:**
- Never give Computer Use direct access to user's primary machine
- Run in VM with limited permissions
- Audit every action
- Pause for confirmation on destructive actions
- Be careful with credentials (passwords, banking)

```python
def confirm_action(action):
    if action["type"] in ["delete", "send", "purchase"]:
        if input(f"Confirm action {action}? (y/n): ") != "y":
            return "User declined"
```

---

## 12. Cost

Computer use = many vision API calls.

Per session estimate:
- 50 screenshots × 1000 tokens each = 50K input tokens
- 50 actions × 200 tokens each = 10K output tokens
- Cost: ~$0.30 per session for Sonnet
- 1000 sessions/day = $300/day = $9K/month

Not cheap. Use for high-value tasks.

---

## 13. Key Takeaways

✅ Computer Use = Claude controls computer via vision + actions
✅ Actions: screenshot, click, type, scroll, key press
✅ Loop: screenshot → Claude analyzes → takes action → repeat
✅ **Run in isolated VM/Docker** for safety
✅ Best for: tasks where APIs don't exist, vision-needed workflows
✅ Limitations: slow, brittle, expensive
✅ Alternatives: Playwright, Selenium for predictable tasks

**Next:** [03_local_serving.md](03_local_serving.md) — Run LLMs locally (Ollama, vLLM)
