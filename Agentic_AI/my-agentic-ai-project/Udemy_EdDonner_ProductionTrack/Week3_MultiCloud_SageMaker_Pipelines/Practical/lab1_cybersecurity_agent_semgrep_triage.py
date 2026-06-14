"""
LAB 1 — Cybersecurity AI agent (Semgrep + LLM triage)
=====================================================================================
Title: Ek "Security Researcher" agent banao jo source code ko STATICALLY scan karke
       vulnerabilities dhoondhe (Semgrep = SAST tool), aur phir HAR finding ko ek LLM
       se EXPLAIN + TRIAGE karwaaye (risk kya hai, fix kya hai, kitna urgent hai).
       Yahi Ed ka "MCP-tool pattern" hai: ek SCAN tool findings nikaalta hai, wo
       findings LLM ko feed hote hain — bilkul jaise agent ke paas `semgrep_scan`
       tool hota hai aur LLM uske output par reason karta hai.

KYA SEEKHENGE (what concepts):
- SECURITY AGENT = SCAN TOOL + LLM REASONING. Ek security agent sirf LLM nahi hota.
  Asli kaam ek DETERMINISTIC tool (Semgrep) karta hai (code ko run kiye bina pattern
  match), aur LLM us output ko INSAANI bhaasha me samjhaata + prioritize karta hai.
  Yeh "tool deta hai facts, LLM deta hai judgement" division hi production-grade hai —
  LLM akela vulnerabilities hallucinate kar sakta hai, tool deterministic ground-truth
  deta hai. (L65: agent = Semgrep MCP server + GPT-4.1 mini reasoning.)
- STATIC ANALYSIS (SAST) — code ko CHALAYE BINA source par pattern match. eval/exec,
  hardcoded secrets, subprocess shell=True, pickle.loads, weak md5, SQL string-concat —
  ye classic "code smells that are security bugs". (L65/L66: Semgrep ne airline.py me
  SQL injection + eval arbitrary-code-exec CVSS 9.8 pakda.)
- MCP-TOOL PATTERN — `scan_code()` exactly woh shape hai jo ek MCP server `semgrep_scan`
  tool expose karta: input = code/path, output = structured list of findings. Niche hum
  dikhaayenge ki yeh function ek MCP tool ki tarah register hota (signature + JSON shape).
  (L65: static tool filter se agent ko sirf `semgrep_scan` milta hai = least privilege.)
- LAZY semgrep + GRACEFUL DEGRADE — is env me na `semgrep` binary hai, na pip module,
  na koi API key. To `scan_code()` pehle LAZILY `semgrep --json` try karta hai; missing
  ho to ek built-in REGEX/AST mini-scanner par gir jaata hai (NA crash, NA network, NA
  hang). Aur LLM triage: GROQ_API_KEY na ho to live call SKIP karke ek TEMPLATED
  explanation deta hai — phir bhi findings + triage dikhte hain, exit 0.
- SEVERITY TRIAGE — har finding ko CVSS-style severity (critical/high/medium/low) milta
  hai; agent inhe sort karke "pehle kya fix karo" batata hai (L65: SecurityReport ka
  severity + cvss_score field).

KAISE CHALANA (how to run) — CWD = repo root:
    # Default: self-demo. Ek INTENTIONALLY-vulnerable code string ko scan + triage karta
    # hai, findings + LLM explanation print karta hai. No semgrep / no key bhi => EXIT 0.
    uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab1_cybersecurity_agent_semgrep_triage.py

    # Sirf scan dekhna ho (LLM triage skip):
    uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab1_cybersecurity_agent_semgrep_triage.py --scan-only

    # Apni file scan karni ho:
    uv run .../lab1_cybersecurity_agent_semgrep_triage.py --file path/to/your_code.py

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 3 · Day 1.
  L64 = Multi-Cloud + Cybersecurity Agent intro. Day 1-2 project = "Cyber Security
        Analyst": ek code file leke vulnerabilities check karta hai (Next.js + FastAPI +
        OpenAI Agents SDK + MCP), Docker-packaged, Terraform-deployed (ACA + Cloud Run).
  L65 = AI Security Agents with MCP + Semgrep. Semgrep = free SAST tool (SQL injection,
        hardcoded secrets, unsafe eval pakadta hai). Agent = "Security Researcher" +
        Semgrep MCP server (static tool filter => sirf `semgrep_scan` tool) + structured
        output `SecurityReport` (executive_summary + issues[title/desc/code_fix/cvss/sev]).
  L66 = Containerizing the agent. airline.py scan => SQL injection + eval CVSS 9.8/10
        (critical) + Gradio DoS. MCP server ek SEPARATE PROCESS spawn karta hai, isliye
        serverless mushkil aur CONTAINER (box-within-a-box) ideal hai.
  NOTE: Ed ne lecture me OpenAI Agents SDK + real Semgrep MCP server (paid OpenAI key +
  Semgrep App Token) use kiya. Is offline lab me wahi SHAPE hai par DEPS ke bina chalti
  hai: real `semgrep --json` LAZY try, warna built-in regex/AST mini-scanner; LLM triage
  groq (free) se, key na ho to templated. Concept identical, cost $0, zero crash.

COST: Is lab ko LOCALLY chalana = $0. semgrep na ho to mini-scanner (offline, free);
  GROQ_API_KEY na ho to LLM triage SKIP karke templated explanation — phir bhi findings
  + triage dikhte hain, EXIT 0, zero crash, zero download.
  REAL deploy (Ed ka runbook): Semgrep API free-tier (App Token); OpenAI GPT-4.1 mini
  triage chand cents/scan; agent ek Docker container me ACA (Azure) ya Cloud Run (GCP)
  par — CaaS chhota per-request bill (idle par ~$0), Ed ka pura course estimate ~$5-$10.
"""

import ast
import json
import os
import re
import shutil
import subprocess
import sys

from dotenv import load_dotenv
from openai import OpenAI

# .env load. override=True => .env value shell ki purani value ko jeet jaaye
# (Ed Donner ki convention). GROQ_API_KEY / SEMGREP_APP_TOKEN dono yahin se uthte.
load_dotenv(override=True)


# ===========================================================================
# get_client — LLM triage ke liye. EXACT helper (placeholder fix ke saath).
# ===========================================================================
# Groq/Gemini OpenAI-compatible hain — sirf base_url alag. Isliye wahi ek `openai`
# library teeno providers ko call kar leti hai. Yeh helper triage_finding() ke andar
# use hota hai. Default groq => FREE.
def get_client(provider: str = "groq"):
    """(client, model). Default groq => free. NOTE `or "placeholder"`: OpenAI() None key par
    CONSTRUCTION time hi crash karta hai, isliye placeholder."""
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY") or "placeholder"), "llama-3.3-70b-versatile"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY") or "placeholder"), "gemini-2.5-flash"
    raise ValueError(f"Unknown provider: {provider}")


# ===========================================================================
# INTENTIONALLY-VULNERABLE sample — yahi hum scan karenge (Ed ke airline.py jaisa).
# ===========================================================================
# Ye code JAAN-BOOJH KE buggy hai (teaching ke liye). Isme woh saare classic
# vulnerabilities hain jo SAST tools (Semgrep) flag karte hain. Pause karke khud
# dhoondho — yahi L65 ka "self test" tha (airline.py me SQL injection + eval).
VULNERABLE_SAMPLE = r'''
import hashlib
import os
import pickle
import sqlite3
import subprocess

# Hardcoded secret — kabhi source me API key/password mat rakho (git history me forever).
API_KEY = "sk-live-1234567890abcdefABCDEFghijklmnop"
DB_PASSWORD = "SuperSecret123!"

def get_user(city):
    conn = sqlite3.connect("app.db")
    cur = conn.cursor()
    # SQL injection — user input ko SQL string me SEEDHE concat kiya (L66 ka classic).
    # city = "London'; DROP TABLE users;--" => havoc.
    cur.execute("SELECT * FROM users WHERE city = '" + city + "'")
    return cur.fetchall()

def run_math(expr):
    # Arbitrary code execution — eval() user expression ko Python code ki tarah chalata
    # hai. L66 me yahi CVSS 9.8/10 (critical) nikla tha.
    return eval(expr)

def run_cmd(user_input):
    # Command injection — shell=True + user input => attacker `; rm -rf /` daal sakta hai.
    subprocess.call("ls " + user_input, shell=True)

def load_blob(data):
    # Insecure deserialization — pickle.loads() attacker-controlled bytes par RCE de sakta.
    return pickle.loads(data)

def make_token(password):
    # Weak hash — MD5 cryptographically broken; passwords ke liye bcrypt/argon2 use karo.
    return hashlib.md5(password.encode()).hexdigest()
'''


# ===========================================================================
# SCAN TOOL #1 — REAL semgrep (LAZY). Yahi woh `semgrep_scan` tool hai jo MCP
# server expose karta (L65). Available ho to PRIMARY, warna mini-scanner fallback.
# ===========================================================================
# DESIGN: semgrep binary ko LAZILY (call ke time) dhoondhte hain, module top par NAHI.
# Kyun? Is env me semgrep install hi nahi — top-level import/call poori file crash kar
# deta. shutil.which() se binary check karte hain; mila to `semgrep --json` subprocess
# chalakar uska JSON parse karte hain; nahi mila to False return => mini-scanner chalega.
def _try_semgrep(path: str):
    """REAL semgrep ko LAZILY try karo. Return: findings-list (success) ya None (unavailable).
    NA network (semgrep --config se rules registry se aate, isliye hum --config=auto NAHI
    dete; agar binary ho to bhi offline registry-less run safe rahe). NA hang (timeout)."""
    binary = shutil.which("semgrep")
    if not binary:
        # Saaf Hinglish note: kya missing, kya hoga. Yahi graceful-degrade ka dil hai.
        print("[INFO] semgrep binary not found -> built-in mini-scanner fallback "
              "(offline, free). Real deploy me Semgrep MCP tool yahan aata (L65).")
        return None
    try:
        # `semgrep --json` => machine-readable findings. --error=false taaki non-zero exit
        # par bhi JSON mile. timeout => kabhi hang na ho. Note: bina --config ke semgrep
        # kuch nahi scan karega; real setup me `--config p/python` ya MCP rules deta hai.
        proc = subprocess.run(
            [binary, "scan", "--json", "--quiet", "--config", "p/python", path],
            capture_output=True, text=True, timeout=90,
        )
        data = json.loads(proc.stdout or "{}")
        findings = []
        for r in data.get("results", []):
            extra = r.get("extra", {})
            findings.append({
                "rule": r.get("check_id", "semgrep.rule"),
                "severity": _map_semgrep_severity(extra.get("severity", "WARNING")),
                "line": r.get("start", {}).get("line", 0),
                "snippet": (extra.get("lines", "") or "").strip()[:120],
                "source": "semgrep",
            })
        print(f"[INFO] semgrep ran -> {len(findings)} finding(s) (REAL SAST tool).")
        return findings
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        # semgrep mila par chal nahi paaya (config/network/parse) => mini-scanner par girna.
        print(f"[INFO] semgrep run failed ({type(e).__name__}) -> mini-scanner fallback.")
        return None


def _map_semgrep_severity(sev: str) -> str:
    """Semgrep ERROR/WARNING/INFO ko humare critical/high/medium/low me normalize karo."""
    return {"ERROR": "high", "WARNING": "medium", "INFO": "low"}.get(sev.upper(), "medium")


# ===========================================================================
# SCAN TOOL #2 — built-in REGEX/AST mini-scanner (OFFLINE FALLBACK).
# ===========================================================================
# Jab semgrep available nahi, yeh chalta hai. Do techniques:
#   1) REGEX rules — text patterns (hardcoded secrets, md5, SQL concat). Fast, simple.
#   2) AST walk — `eval`/`exec` calls aur subprocess(shell=True) jaise structural patterns
#      ko regex se zyada reliably pakadta hai (kyunki AST asli function-call samajhta hai,
#      sirf text nahi). Yahi SAST ka asli flavour — code ko CHALAYE BINA structure dekhna.
# Output shape semgrep jaisa hi: {rule, severity, line, snippet, source}.

# --- Regex rules: (rule_id, severity, compiled_pattern, human_msg) ----------
# Har rule ek classic SAST finding hai. WHY severity: hardcoded secret = high (leak =
# instant compromise), md5 = medium (weak par direct RCE nahi), SQL concat = high.
_REGEX_RULES = [
    ("hardcoded-secret-assignment", "high",
     re.compile(r'(?i)(api[_-]?key|secret|password|passwd|token)\s*=\s*["\'][^"\']{6,}["\']'),
     "Hardcoded secret/credential in source"),
    ("hardcoded-aws-key", "critical",
     re.compile(r'AKIA[0-9A-Z]{16}'),
     "Hardcoded AWS access key id"),
    ("weak-hash-md5", "medium",
     re.compile(r'hashlib\.md5\s*\('),
     "Weak hash (MD5) — broken for security use"),
    ("weak-hash-sha1", "medium",
     re.compile(r'hashlib\.sha1\s*\('),
     "Weak hash (SHA1) — deprecated for security use"),
    ("sql-string-concat", "high",
     re.compile(r'(?i)(execute|executemany)\s*\(\s*["\'].*(SELECT|INSERT|UPDATE|DELETE).*["\']\s*[+%]'),
     "SQL built by string concat/format — injection risk"),
    ("sql-fstring", "high",
     re.compile(r'(?i)(execute|executemany)\s*\(\s*f["\']'),
     "SQL built via f-string — injection risk"),
]


def _scan_regex(code: str):
    """Line-by-line regex scan. Findings list (semgrep-shape) return karta hai."""
    findings = []
    for lineno, line in enumerate(code.splitlines(), start=1):
        for rule_id, sev, pat, msg in _REGEX_RULES:
            if pat.search(line):
                findings.append({
                    "rule": rule_id,
                    "severity": sev,
                    "line": lineno,
                    "snippet": line.strip()[:120],
                    "source": "mini-scanner:regex",
                    "_msg": msg,
                })
    return findings


# --- AST rules: function-call patterns jo regex se reliably nahi milte ------
# eval/exec/compile = arbitrary code exec (critical). subprocess(...shell=True) =
# command injection (high). pickle.loads/load = insecure deserialization (high).
# AST walk har Call node ko inspect karta hai — text nahi, asli call structure.
_AST_DANGEROUS_CALLS = {
    "eval":   ("dangerous-eval", "critical", "eval() — arbitrary code execution"),
    "exec":   ("dangerous-exec", "critical", "exec() — arbitrary code execution"),
    "compile": ("dangerous-compile", "high", "compile() of dynamic source — code exec risk"),
}


def _call_name(node: ast.Call) -> str:
    """Call node se function ka 'dotted name' nikaalo: eval -> 'eval',
    pickle.loads -> 'pickle.loads', subprocess.call -> 'subprocess.call'."""
    f = node.func
    parts = []
    while isinstance(f, ast.Attribute):     # foo.bar.baz => baz, bar, foo (reverse)
        parts.append(f.attr)
        f = f.value
    if isinstance(f, ast.Name):
        parts.append(f.id)
    return ".".join(reversed(parts))        # foo.bar.baz


def _scan_ast(code: str):
    """AST walk se structural vulnerabilities. Agar code parse na ho (syntax error),
    gracefully [] return karo — scanner kabhi crash na kare (real files dirty hote hain)."""
    findings = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        print(f"[INFO] AST parse skip (syntax error line {e.lineno}) -> sirf regex rules.")
        return findings

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        base = name.split(".")[-1]          # eval / loads / call
        full = name                          # pickle.loads / subprocess.call

        # 1) eval/exec/compile — bare builtin name match
        if name in _AST_DANGEROUS_CALLS:
            rule_id, sev, msg = _AST_DANGEROUS_CALLS[name]
            findings.append(_ast_finding(rule_id, sev, node, msg, code))

        # 2) pickle.loads / pickle.load — insecure deserialization
        elif full in ("pickle.loads", "pickle.load", "cPickle.loads", "cPickle.load"):
            findings.append(_ast_finding(
                "insecure-deserialization", "high", node,
                "pickle load of untrusted data — remote code execution risk", code))

        # 3) subprocess(...shell=True) ya os.system — command injection
        elif full in ("subprocess.call", "subprocess.run", "subprocess.Popen",
                      "subprocess.check_call", "subprocess.check_output"):
            # shell=True keyword arg dhoondho — yahi command-injection ka trigger.
            shell_true = any(
                kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                for kw in node.keywords
            )
            if shell_true:
                findings.append(_ast_finding(
                    "subprocess-shell-true", "high", node,
                    "subprocess with shell=True — command injection risk", code))
        elif full == "os.system":
            findings.append(_ast_finding(
                "os-system", "high", node,
                "os.system() with dynamic input — command injection risk", code))
        # base 'unused' suppress karne ke liye reference (lint-friendly).
        _ = base
    return findings


def _ast_finding(rule_id, sev, node, msg, code):
    """AST node se ek semgrep-shape finding banao (line number + snippet ke saath)."""
    line = getattr(node, "lineno", 0)
    lines = code.splitlines()
    snippet = lines[line - 1].strip()[:120] if 0 < line <= len(lines) else ""
    return {
        "rule": rule_id,
        "severity": sev,
        "line": line,
        "snippet": snippet,
        "source": "mini-scanner:ast",
        "_msg": msg,
    }


# ===========================================================================
# scan_code — PUBLIC SCAN TOOL. Yahi woh function hai jo MCP server `semgrep_scan`
# tool ban'ta hai (L65). Input = path ya raw text; output = findings list.
# ===========================================================================
# CONTRACT (MCP tool shape):
#   input  : path_or_text (str) — agar file path hai aur exist karta hai to file padho,
#            warna usse hi raw code text maano (flexible — UI se text aata, CLI se path).
#   output : list[{rule, severity, line, snippet, source}]  (severity-sorted)
# FLOW: pehle REAL semgrep LAZY try; available => uske findings. Warna built-in
# regex+AST mini-scanner. DONO hi code ko RUN nahi karte (static analysis = safe).
def scan_code(path_or_text: str):
    """Scan source for vulnerabilities. MCP-tool-shaped: ek string in, findings list out.
    semgrep available => real SAST; warna offline mini-scanner. Kabhi crash/hang/download nahi."""
    # --- path ya raw text? ek choti heuristic: chhota single-line jo file exist karta ho
    #     => file path; warna raw code text. (UI se aksar text aata, CLI se path.)
    code = path_or_text
    src_label = "<inline-text>"
    if "\n" not in path_or_text and len(path_or_text) < 400 and os.path.isfile(path_or_text):
        with open(path_or_text, "r", encoding="utf-8", errors="replace") as fh:
            code = fh.read()
        src_label = path_or_text

    print(f"[scan_code] scanning {src_label} ({len(code)} chars)...")

    # --- 1) REAL semgrep LAZY (sirf tab jab path hai; semgrep file path leta hai) ----
    # Inline text ko temp file ki zaroorat hoti; simplicity ke liye semgrep ko sirf real
    # file path par try karte hain. Inline text => seedha mini-scanner (jo string leta hai).
    if src_label != "<inline-text>":
        sg = _try_semgrep(src_label)
        if sg is not None:
            return _sort_by_severity(sg)

    # --- 2) Built-in mini-scanner (offline fallback) — regex + AST union ----------
    findings = _scan_regex(code) + _scan_ast(code)
    return _sort_by_severity(findings)


# Severity ko numeric rank do taaki critical pehle aaye (triage ordering, L65).
_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _sort_by_severity(findings):
    """Findings ko severity (critical->low) phir line number se sort karo."""
    return sorted(findings, key=lambda f: (_SEV_RANK.get(f["severity"], 9), f["line"]))


# ===========================================================================
# LLM TRIAGE STEP — har finding ko EXPLAIN + FIX + urgency. (L65 SecurityReport)
# ===========================================================================
# Yahi "agent ka dimaag" hai: scan tool ne FACTS diye, LLM ab JUDGEMENT deta hai —
# risk plain bhaasha me, ek concrete code_fix, aur "abhi fix karo ya baad me". Yeh
# OpenAI Agents SDK ke `output_type=SecurityReport` ka offline equivalent hai.
#
# GRACEFUL: GROQ_API_KEY na ho to LIVE call SKIP karke ek TEMPLATED explanation deta
# hai (rule->advice map se). Shape same, cost $0, exit 0. Key set ho to real groq.

# Rule-id -> (why_risky, how_to_fix) — templated knowledge base (no-LLM fallback).
_TRIAGE_TEMPLATES = {
    "hardcoded-secret-assignment": (
        "Secret source code me hai — git history me forever leak, repo access = key access.",
        "Secret ko env var / secrets manager (AWS Secrets Manager, Azure Key Vault) se load karo; key rotate karo."),
    "hardcoded-aws-key": (
        "AWS access key id source me — agar push hua to attacker poora AWS account use kar sakta hai.",
        "Key ko TURANT deactivate+rotate karo (IAM); env/secret store use karo; git history se purge karo."),
    "weak-hash-md5": (
        "MD5 cryptographically broken hai — collisions easy, password hashing ke liye useless.",
        "Passwords ke liye bcrypt/scrypt/argon2 use karo; integrity ke liye SHA-256+."),
    "weak-hash-sha1": (
        "SHA1 deprecated — collision attacks practical hain.",
        "SHA-256+ ya purpose-built password hash (argon2/bcrypt) par switch karo."),
    "sql-string-concat": (
        "SQL string concat se injection — user input query structure todh sakta hai (DROP TABLE etc.).",
        "Parameterized queries / placeholders use karo: cursor.execute(sql, (param,))."),
    "sql-fstring": (
        "f-string se bani SQL = injection — user input directly query me embed.",
        "Parameterized queries use karo; kabhi user input ko SQL text me mat embed karo."),
    "dangerous-eval": (
        "eval() user input ko Python code ki tarah chalata hai = arbitrary code execution (CVSS ~9.8).",
        "eval hatao; numeric ke liye ast.literal_eval ya explicit parser; whitelist allowed ops."),
    "dangerous-exec": (
        "exec() arbitrary code chalata hai = full RCE.",
        "exec ki zaroorat hi nahi honi chahiye; refactor karke explicit logic likho."),
    "dangerous-compile": (
        "Dynamic source compile karna eval/exec jaisa hi risk.",
        "Dynamic code-gen avoid karo; static logic use karo."),
    "insecure-deserialization": (
        "pickle untrusted bytes par arbitrary code chala sakta hai = RCE.",
        "pickle untrusted data par mat use karo; JSON ya signed/verified format use karo."),
    "subprocess-shell-true": (
        "shell=True + dynamic input = command injection (`; rm -rf /` inject ho sakta).",
        "shell=False rakho aur args ko LIST me pass karo: subprocess.run([\"ls\", arg])."),
    "os-system": (
        "os.system dynamic input ke saath = command injection.",
        "subprocess.run([...], shell=False) use karo; user input ko shell me mat daalo."),
}


def _templated_triage(finding):
    """Bina LLM ke ek explanation — rule->advice map se. (no-key fallback)."""
    why, fix = _TRIAGE_TEMPLATES.get(
        finding["rule"],
        ("Potential security issue flagged by static analysis.",
         "Manually review karo aur secure pattern apply karo."))
    return {"explanation": why, "fix": fix, "urgency": finding["severity"], "by": "template"}


def triage_finding(finding, provider: str = "groq"):
    """Ek finding ko LLM se explain+fix+urgency. Key na ho to templated fallback.
    Return: {explanation, fix, urgency, by}. NEVER crash (network error => template)."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        # Graceful skip — live call mat karo (cost $0), templated explanation do.
        return _templated_triage(finding)

    client, model = get_client(provider)
    # SECURITY-RESEARCHER prompt (L65 ke agent instructions ka core). LLM ko JSON do.
    prompt = (
        "You are a senior application security engineer triaging a static-analysis finding. "
        "Reply ONLY with compact JSON: {\"explanation\": str, \"fix\": str, \"urgency\": "
        "\"critical|high|medium|low\"}.\n\n"
        f"Rule: {finding['rule']}\n"
        f"Reported severity: {finding['severity']}\n"
        f"Line {finding['line']}: {finding['snippet']}\n"
        f"Detector: {finding['source']}"
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0,                  # security advice deterministic chahiye
        )
        text = resp.choices[0].message.content.strip()
        # JSON parse defensively — LLM kabhi ```json fence laga deta hai.
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        data = json.loads(text)
        return {
            "explanation": data.get("explanation", "").strip(),
            "fix": data.get("fix", "").strip(),
            "urgency": data.get("urgency", finding["severity"]).strip(),
            "by": f"llm:{provider}",
        }
    except Exception as e:
        # Network/parse/auth fail => templated fallback (degrade, crash nahi).
        print(f"[INFO] LLM triage fail ({type(e).__name__}) -> templated fallback.")
        return _templated_triage(finding)


# ===========================================================================
# run_security_analyst — AGENT ka top-level orchestration (L65 ka SecurityReport).
# ===========================================================================
# scan_code() (tool) => findings, phir har finding par triage_finding() (LLM) => ek
# poora SecurityReport-shape dict. Yahi woh function hai jise FastAPI route call karta
# (L65) aur jo container me deploy hota (L66).
def run_security_analyst(path_or_text: str, provider: str = "groq", do_triage: bool = True):
    """SCAN + TRIAGE pipeline. Return ek SecurityReport-shape dict:
    {executive_summary, scanner, issues:[{rule,severity,line,snippet,explanation,fix,urgency}]}."""
    findings = scan_code(path_or_text)

    issues = []
    for f in findings:
        item = {k: f[k] for k in ("rule", "severity", "line", "snippet", "source")}
        if do_triage:
            t = triage_finding(f, provider)
            item.update(explanation=t["explanation"], fix=t["fix"],
                        urgency=t["urgency"], triaged_by=t["by"])
        issues.append(item)

    # Executive summary (L65 SecurityReport.executive_summary) — counts by severity.
    counts = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    scanner = findings[0]["source"].split(":")[0] if findings else "none"
    summary = (f"Scanned source: {len(findings)} issue(s) found "
               f"({', '.join(f'{v} {k}' for k, v in sorted(counts.items(), key=lambda x: _SEV_RANK.get(x[0], 9))) or 'none'}). "
               f"Detector={scanner}.")
    return {"executive_summary": summary, "scanner": scanner, "issues": issues}


# ===========================================================================
# MCP-TOOL SHAPE explainer — `scan_code` ek MCP server tool kaise banta (L65).
# ===========================================================================
def _print_mcp_shape():
    """Dikhao ki yeh `scan_code()` exactly ek MCP `semgrep_scan` tool hai — sirf print."""
    print("=" * 72)
    print("MCP-TOOL PATTERN — scan_code() = ek `semgrep_scan` MCP tool (L65)")
    print("=" * 72)
    print("Real OpenAI Agents SDK setup (L65 me Ed ne yeh use kiya):")
    print("  semgrep_server = MCPServerStdio(")
    print("      params={'command': 'semgrep', 'env': {'SEMGREP_APP_TOKEN': ...}},")
    print("      client_session_timeout_seconds=120,")
    print("      tool_filter=create_static_tool_filter(allowed_tool_names=['semgrep_scan']))")
    print("  agent = Agent(name='Security Researcher', model='gpt-4.1-mini',")
    print("                mcp_servers=[semgrep_server], output_type=SecurityReport)")
    print()
    print("Is lab ka equivalent (offline, dep-free):")
    print("  TOOL  : scan_code(path_or_text) -> [{rule, severity, line, snippet, source}]")
    print("  REASON: triage_finding(finding) -> {explanation, fix, urgency}  (LLM/template)")
    print("  REPORT: run_security_analyst() -> {executive_summary, issues:[...]}")
    print()
    print(">> Insight (L65): static tool filter => agent ko sirf SCAN tool milta = least")
    print("   privilege. Aur MCP server ek SEPARATE PROCESS spawn karta => serverless")
    print("   mushkil, CONTAINER (box-within-a-box) ideal => ACA/Cloud Run (L66).")
    print()


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args) yahan aata hai. No semgrep / no key => exit 0.
# ===========================================================================
def _print_report(report):
    """SecurityReport-shape dict ko padhne-layak format me print karo (L65 jaisa)."""
    print("=" * 72)
    print("SECURITY REPORT")
    print("=" * 72)
    print("EXECUTIVE SUMMARY:")
    print("  " + report["executive_summary"])
    print()
    if not report["issues"]:
        print("  (no issues found)")
        return
    for i, issue in enumerate(report["issues"], start=1):
        print(f"[{i}] {issue['severity'].upper():8s} {issue['rule']}  (line {issue['line']})")
        print(f"     detector : {issue['source']}")
        print(f"     code     : {issue['snippet']}")
        if "explanation" in issue:
            print(f"     risk     : {issue['explanation']}")
            print(f"     fix      : {issue['fix']}")
            print(f"     urgency  : {issue['urgency']}   (triaged by {issue['triaged_by']})")
        print()


def run_self_demo(scan_only: bool = False, file_path: str | None = None):
    """INTENTIONALLY-vulnerable sample ko scan + triage karke report print karo, phir
    exit 0 (chahe semgrep/key ho ya na ho)."""
    print("\n" + "#" * 72)
    print("#  LAB 1 SELF-DEMO — Cybersecurity AI agent (Semgrep + LLM triage)")
    print("#  (no semgrep / no key bhi OK — offline mini-scanner + templated triage)")
    print("#" * 72 + "\n")

    # --- 1) MCP-tool shape (teaching) --------------------------------------
    _print_mcp_shape()

    # --- 2) Konsa input scan kar rahe ---------------------------------------
    if file_path:
        target = file_path
        print(f"[target] file = {file_path}\n")
    else:
        target = VULNERABLE_SAMPLE
        print("[target] baked-in INTENTIONALLY-vulnerable sample (Ed ke airline.py jaisa)\n")

    # --- 3) Triage on/off + key status --------------------------------------
    has_key = bool(os.getenv("GROQ_API_KEY"))
    do_triage = not scan_only
    print("=" * 72)
    print("CONFIG")
    print("=" * 72)
    print(f"GROQ_API_KEY set?     = {has_key}")
    print(f"LLM triage            = {'ON' if do_triage else 'OFF (--scan-only)'}")
    if do_triage and not has_key:
        print("note                  = key nahi => triage TEMPLATED hoga (live call SKIP, "
              "cost $0). Key set karo to real groq explanation aayega.")
    print()

    # --- 4) SCAN + TRIAGE pipeline ------------------------------------------
    report = run_security_analyst(target, provider="groq", do_triage=do_triage)
    print()
    _print_report(report)

    # --- 5) Wrap-up ----------------------------------------------------------
    print("#" * 72)
    print("#  LAB 1 complete. scan_code() = deterministic SAST tool (semgrep ya offline);")
    print("#  triage_finding() = LLM judgement layer; saath me ek MCP `semgrep_scan` tool")
    print("#  + Security Researcher agent ka shape. Container me ye ACA/Cloud Run par jaata.")
    print("#" * 72 + "\n")
    raise SystemExit(0)


# ===========================================================================
# MAIN — default self-demo; --scan-only => triage skip; --file PATH => apni file.
# ===========================================================================
if __name__ == "__main__":
    args = sys.argv[1:]
    scan_only = "--scan-only" in args
    file_path = None
    if "--file" in args:
        idx = args.index("--file")
        if idx + 1 < len(args):
            file_path = args[idx + 1]
    run_self_demo(scan_only=scan_only, file_path=file_path)
