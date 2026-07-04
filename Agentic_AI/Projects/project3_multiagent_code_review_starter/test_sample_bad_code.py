"""
Sample file with intentional bugs — for workspace agent demo.
Security + Performance + Style issues all present.
"""
import os, sys, pickle, hashlib
import requests  # blocking — not httpx

# ❌ SECURITY: hardcoded secret
API_KEY = "sk-ant-api03-DEMO_FAKE_KEY_FOR_TESTING_ONLY"
DB_PASS = "admin123"

# ❌ SECURITY: SQL injection vulnerable
def get_user(conn, username):
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    return conn.execute(query)

# ❌ SECURITY: unsafe deserialization
def load_session(data):
    return pickle.loads(data)

# ❌ PERF: N+1 query — loop mein per-item DB call
def get_all_reviews(conn, pr_ids):
    results = []
    for pr_id in pr_ids:                          # N iterations
        row = conn.execute(                        # N DB calls!
            "SELECT * FROM reviews WHERE pr_id = ?", (pr_id,)
        )
        results.append(row.fetchone())
    return results

# ❌ PERF: sync call inside async function
async def fetch_github_pr(repo, pr_id):
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_id}"
    resp = requests.get(url)                       # BLOCKING — should be httpx
    return resp.json()

# ❌ PERF: repeated computation inside loop
def calculate_scores(issues):
    scores = []
    for issue in issues:
        total = len(issues)                        # recalculated every iteration
        scores.append(issue.severity / total)
    return scores

# ❌ STYLE: no type hints, bad names, mutable default
def process(d, l=[]):                              # mutable default arg
    x = d.get("s")                                # unclear name x, s
    l.append(x)
    return l

# ❌ STYLE: no docstring on public function
def analyze_diff(diff, repo, pr):
    if diff == None:                               # should be `is None`
        return {}
    return {"diff": diff, "repo": repo}
