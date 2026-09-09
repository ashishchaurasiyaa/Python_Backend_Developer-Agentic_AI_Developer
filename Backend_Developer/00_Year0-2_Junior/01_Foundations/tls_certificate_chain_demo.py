"""
TLS certificate chain -- verified practical: real Root -> Intermediate ->
Leaf chain of trust, extracted from a live HTTPS connection.
"""

import subprocess

HOST = "example.com"

if __name__ == "__main__":
    result = subprocess.run(
        ["openssl", "s_client", "-connect", f"{HOST}:443", "-servername", HOST, "-showcerts"],
        input="", capture_output=True, text=True, timeout=10,
    )
    lines = result.stdout.splitlines()

    print(f"=== Certificate chain returned live by {HOST}:443 ===\n")
    in_chain = False
    for line in lines:
        if line.strip() == "Certificate chain":
            in_chain = True
            continue
        if in_chain:
            if line.strip() == "---":
                break
            print(line)

    print("\nDepth 0 = leaf/server certificate (this domain's own cert)")
    print("Depth 1+ = intermediate CA(s) -- the root CA is usually NOT sent by the")
    print("server, since it's already in your OS/browser trust store.")
