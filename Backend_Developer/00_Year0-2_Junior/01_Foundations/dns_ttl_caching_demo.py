"""
TTL / DNS caching -- verified practical: query the same record twice with a
real delay between and show the TTL counting DOWN -- proof the resolver
served a cached answer instead of re-querying authoritative DNS.
"""

import re
import subprocess
import time

DOMAIN = "example.com"


def query_ttl(domain):
    out = subprocess.run(
        ["dig", "+noall", "+answer", "A", domain], capture_output=True, text=True, timeout=10
    ).stdout.strip()
    match = re.search(rf"{re.escape(domain)}\.\s+(\d+)\s+IN\s+A", out)
    return int(match.group(1)) if match else None, out


if __name__ == "__main__":
    ttl1, line1 = query_ttl(DOMAIN)
    print(f"Query 1: TTL = {ttl1}")
    print(f"  {line1}\n")

    wait_seconds = 5
    print(f"Waiting {wait_seconds} real seconds...\n")
    time.sleep(wait_seconds)

    ttl2, line2 = query_ttl(DOMAIN)
    print(f"Query 2: TTL = {ttl2}")
    print(f"  {line2}\n")

    if ttl1 is not None and ttl2 is not None:
        dropped = ttl1 - ttl2
        print(f"TTL dropped by {dropped} seconds (we waited {wait_seconds}s)")
        if 0 <= dropped <= wait_seconds + 2:
            print("This proves the resolver served a CACHED answer and is counting the")
            print("TTL down locally -- it did NOT re-query authoritative DNS on query 2.")
        else:
            print("TTL didn't drop as expected (record may have refreshed, or resolver's")
            print("own cache already expired/reset) -- still real data, just a different case.")
