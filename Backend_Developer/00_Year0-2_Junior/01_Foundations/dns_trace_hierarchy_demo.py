"""
DNS hierarchy -- verified practical: dig +trace performs REAL iterative
queries against root -> TLD -> authoritative servers, showing the exact
delegation chain from the notes' Section 1, not a diagram.
"""

import subprocess

DOMAIN = "example.com"

if __name__ == "__main__":
    print(f"=== dig +trace {DOMAIN} (real root -> TLD -> authoritative walk) ===\n")
    out = subprocess.run(
        ["dig", "+trace", "+nodnssec", DOMAIN], capture_output=True, text=True, timeout=30
    ).stdout
    print(out)
