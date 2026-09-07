"""
Modern Topics — Doc 3: Local LLM Serving (PRACTICAL)
=======================================================
Topics covered:
  1. Connecting to a local Ollama server via the OpenAI-compatible client
     (auto-detects whether Ollama is actually running — doesn't assume)
  2. A hardware-requirement calculator — given model size, estimate RAM/VRAM
  3. Quantization size math — same model, different precisions
  4. Ollama vs vLLM — when each actually makes sense

Install: pip install openai
Optional: install Ollama (https://ollama.com) and `ollama pull llama3.1:8b`
          to see Section 1 run against a real local model

Run: python 03_local_serving_practical.py
"""

import socket


def ollama_running(host="localhost", port=11434, timeout=1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Connect to Local Ollama (OpenAI-Compatible API)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Local Ollama via the OpenAI-Compatible Client")
print("=" * 70)

HAS_OLLAMA = ollama_running()
print(f"\n  Ollama server on localhost:11434: {'RUNNING' if HAS_OLLAMA else 'not running'}")

if HAS_OLLAMA:
    from openai import OpenAI
    client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    try:
        response = client.chat.completions.create(model="llama3.1:8b", messages=[{"role": "user", "content": "Say hello in 3 words"}])
        print(f"  Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"  Server is up but the call failed (model probably not pulled yet): {e}")
        print("  Fix: ollama pull llama3.1:8b")
else:
    print("  [Not running — install from ollama.com, then `ollama pull llama3.1:8b`]")
    print("  The KEY thing to notice: the client code below is IDENTICAL to a")
    print("  normal OpenAI call — only base_url changes. This is why 'OpenAI-")
    print("  compatible' matters: your app code doesn't need a special local-model")
    print("  code path, just a different client configuration.")
    print("""
    from openai import OpenAI
    client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    response = client.chat.completions.create(
        model="llama3.1:8b",
        messages=[{"role": "user", "content": "Hello!"}]
    )""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Hardware Requirement Calculator
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: How Much RAM/VRAM Does a Model Actually Need?")
print("=" * 70)

BYTES_PER_PARAM = {"fp16": 2, "q8": 1, "q4": 0.5, "q2": 0.25}


def estimate_memory_gb(param_count_billions: float, precision: str = "q4") -> float:
    """Rough rule of thumb: memory ≈ params × bytes-per-param, plus ~20%
    overhead for KV cache/activations at moderate context length."""
    bytes_per_param = BYTES_PER_PARAM[precision]
    base_gb = (param_count_billions * 1e9 * bytes_per_param) / 1e9
    return round(base_gb * 1.2, 1)  # +20% overhead


MODELS = {"Phi-3.5 (3B)": 3, "Llama 3.1 (8B)": 8, "Llama 3.1 (13B-class)": 13, "Llama 3.1 (70B)": 70, "Llama 3.1 (405B)": 405}

print(f"\n  {'Model':25s} {'fp16':>8s} {'q8':>8s} {'q4':>8s} {'q2':>8s}")
for name, params in MODELS.items():
    row = "  ".join(f"{estimate_memory_gb(params, p):>6.1f}GB" for p in ["fp16", "q8", "q4", "q2"])
    print(f"  {name:25s} {row}")

my_ram = 16  # change this to your actual machine's RAM
print(f"\n  On a {my_ram}GB RAM machine, what fits at q4?")
for name, params in MODELS.items():
    fits = estimate_memory_gb(params, "q4") < my_ram
    print(f"    {name:25s}: {'fits' if fits else 'too big'}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Quantization — Same Model, Different Trade-offs
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Quantization Trade-off, Quantified")
print("=" * 70)

QUALITY_LOSS = {"fp16": 0, "q8": 1, "q4": 5, "q2": 15}  # rough % relative quality loss, illustrative

print(f"\n  Llama 3.1 8B across precisions:")
for precision in ["fp16", "q8", "q4", "q2"]:
    mem = estimate_memory_gb(8, precision)
    loss = QUALITY_LOSS[precision]
    print(f"    {precision:5s}: {mem:5.1f}GB, ~{loss}% quality loss (illustrative, not measured)")
print("\n  Ollama defaults to q4 for exactly this reason — the size/quality curve")
print("  is steep between fp16->q8->q4 (small quality cost, big size win) and")
print("  flattens/worsens fast below q4 (q2 loses noticeably more per GB saved).")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Ollama vs vLLM — Decision Function
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Ollama vs vLLM")
print("=" * 70)


def pick_local_serving_tool(concurrent_users: int, is_prototyping: bool, needs_throughput_optimization: bool) -> str:
    if is_prototyping or concurrent_users <= 1:
        return "Ollama — simplest setup, single-user, good enough for local dev/testing"
    if needs_throughput_optimization or concurrent_users > 10:
        return "vLLM — continuous batching + PagedAttention, built for multi-user production throughput"
    return "Either works at this scale — Ollama for simplicity, vLLM if you're already in a production K8s setup"


for case in [(1, True, False), (1, False, False), (50, False, True), (5, False, False)]:
    print(f"\n  concurrent_users={case[0]}, prototyping={case[1]}, needs_throughput={case[2]}")
    print(f"    -> {pick_local_serving_tool(*case)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Change `my_ram` to your actual machine's RAM and re-run Section 2.

MEDIUM:
2. Install Ollama, pull a small model (phi3.5 is fastest), and re-run
   Section 1 for real — compare its latency to an API call to a hosted model.

HARD:
3. estimate_memory_gb() ignores context length's effect on KV cache size.
   Add a context_length parameter and scale the +20% overhead term with it
   — a 128K-context request needs meaningfully more memory than a 4K one.

PRO:
4. If you have vLLM installed: benchmark actual tokens/sec for a small model
   under Ollama vs vLLM with 1, 5, and 20 concurrent requests. Does vLLM's
   throughput advantage actually show up at low concurrency, or only at scale?
""")

if __name__ == "__main__":
    print("\nDone. Next: 04_memory_frameworks_practical.py")
