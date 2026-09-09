"""
Routing table / Longest Prefix Match -- verified practical: parse this
machine's REAL routing table and implement the same (dest AND mask ==
network) + longest-prefix-match algorithm the OS/routers actually use.
"""

import ipaddress
import subprocess


def parse_routing_table():
    out = subprocess.run(["netstat", "-rn", "-f", "inet"], capture_output=True, text=True, timeout=5).stdout
    routes = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        dest, gateway = parts[0], parts[1]

        if dest == "default":
            network, prefix = ipaddress.ip_address("0.0.0.0"), 0
        else:
            dest_ip_part = dest.split("/")[0]
            if "/" in dest:
                prefix = int(dest.split("/")[1])
            else:
                octet_count = len(dest_ip_part.split("."))
                prefix = octet_count * 8
            padded = dest_ip_part.split(".") + ["0"] * (4 - len(dest_ip_part.split(".")))
            try:
                network = ipaddress.ip_address(".".join(padded))
            except ValueError:
                continue

        try:
            net = ipaddress.ip_network(f"{network}/{prefix}", strict=False)
        except ValueError:
            continue
        routes.append((net, gateway))
    return routes


def longest_prefix_match(dest_ip, routes):
    dest = ipaddress.ip_address(dest_ip)
    candidates = [(net, gw) for net, gw in routes if dest in net]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0].prefixlen)


if __name__ == "__main__":
    routes = parse_routing_table()
    print(f"Parsed {len(routes)} routing table entries from this machine.\n")

    print("A few real entries:")
    for net, gw in routes[:6]:
        print(f"  {net}  via {gw}")
    print()

    test_ips = ["192.168.1.54", "8.8.8.8", "127.0.0.1"]
    for ip in test_ips:
        match = longest_prefix_match(ip, routes)
        print(f"=== Destination {ip} ===")
        if match:
            net, gw = match
            all_matches = sorted(
                (n for n, _ in routes if ipaddress.ip_address(ip) in n),
                key=lambda n: n.prefixlen,
            )
            print(f"  All matching entries (by prefix length): {[str(n) for n in all_matches]}")
            print(f"  Longest-prefix match wins: {net} (prefix /{net.prefixlen}) via {gw}")
        else:
            print("  No route found")
        print()
