"""
Layer 2 (ARP: IP<->MAC on the LAN) and Layer 3 (TTL-based routing/traceroute)
-- verified practical using real OS tools, no raw sockets needed.
"""

import subprocess


def demo_arp_table():
    print("=== Layer 2: ARP table (IP <-> MAC mapping on the local network) ===")
    out = subprocess.run(["arp", "-an"], capture_output=True, text=True, timeout=10).stdout
    print(out.strip() or "(empty -- no other hosts seen on the LAN recently)")
    print()


def demo_traceroute(host="8.8.8.8", max_hops=8):
    print(f"=== Layer 3: TTL-based hop discovery (traceroute to {host}, max {max_hops} hops) ===")
    try:
        out = subprocess.run(
            ["traceroute", "-m", str(max_hops), host],
            capture_output=True, text=True, timeout=25,
        ).stdout
        print(out.strip())
    except FileNotFoundError:
        print("traceroute not available on this system")
    print()
    print("Each intermediate hop replied because THIS packet's TTL hit 0 there and")
    print("it sent back an ICMP 'TTL exceeded' -- the router-forwarding mechanism")
    print("from Part 2 (Routing) and the TTL field in the IP header.")


if __name__ == "__main__":
    demo_arp_table()
    demo_traceroute()
