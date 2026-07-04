---
name: implement-milestone
description: Use this skill when asked to implement a milestone for this project. It guides you through reading the spec, creating the right file, implementing it step by step, and running tests.
---

# Implement a Milestone

## Steps

1. **Read the spec**
   - Open `../03_project3_multiagent_code_review.md` and find the milestone section
   - Read `CLAUDE.md` file map to know which file to create/edit

2. **Create the target file** (if it doesn't exist)
   - Milestone 1 → `app/agent/state.py`
   - Milestone 2 → `app/agent/graph.py`
   - Milestones 3-5 → `app/agent/nodes.py`
   - Milestone 6 → `app/api/webhook.py`
   - Milestone 7 → `app/github_client.py`
   - Milestone 8 → `mcp_server/slack_tool.py`

3. **Implement**
   - Use the commented skeleton in `main.py` as the starting point
   - All models must use Pydantic BaseModel + Instructor for structured output
   - All nodes must be `async def` and return a dict with ReviewState keys
   - Always include cost tracking: `"cost_usd": state.get("cost_usd", 0) + estimated_cost`

4. **Verify**
   ```bash
   python main.py          # smoke test — must not crash
   pytest -x               # run tests if they exist
   ```

5. **Confirm** by telling the user: which milestone, which file, what was implemented, any TODOs left.
