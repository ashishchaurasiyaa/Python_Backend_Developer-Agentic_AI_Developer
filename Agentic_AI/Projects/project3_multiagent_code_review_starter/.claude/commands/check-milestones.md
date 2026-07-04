# /check-milestones

Check which milestones are done and which are pending.

## Steps
1. Check which target files exist:
   - `app/agent/state.py` → Milestone 1
   - `app/agent/graph.py` → Milestone 2
   - `app/agent/nodes.py` → Milestones 3-5
   - `app/api/webhook.py` → Milestone 6
   - `app/github_client.py` → Milestone 7
   - `mcp_server/slack_tool.py` → Milestone 8

2. For each existing file: grep for `TODO` to see if it's complete or still a stub.

3. Output a status table:
   ```
   Milestone 1 — state.py        ✅ done / ⏳ in progress / ❌ not started
   Milestone 2 — graph.py        ...
   ...
   ```

4. Suggest the next milestone to work on.
