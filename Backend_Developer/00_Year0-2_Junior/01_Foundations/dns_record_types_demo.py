"""
DNS record types -- verified practical: real A, AAAA, MX, TXT, NS lookups
for a real domain, plus a reverse PTR lookup on the resolved IP.
"""

import subprocess

DOMAIN = "google.com"


def dig_short(record_type, name):
    out = subprocess.run(
        ["dig", "+short", record_type, name], capture_output=True, text=True, timeout=10
    ).stdout.strip()
    return out or "(no answer)"


if __name__ == "__main__":
    for rtype in ["A", "AAAA", "MX", "TXT", "NS"]:
        print(f"=== {rtype} {DOMAIN} ===")
        print(dig_short(rtype, DOMAIN))
        print()

    first_ip = dig_short("A", DOMAIN).splitlines()[0]
    print(f"=== PTR (reverse DNS) for {first_ip} ===")
    ptr = subprocess.run(["dig", "+short", "-x", first_ip], capture_output=True, text=True, timeout=10).stdout.strip()
    print(ptr or "(no PTR record)")
