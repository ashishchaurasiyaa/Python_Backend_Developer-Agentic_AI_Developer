"""
Binary method + AND/OR operation -- verified practical: compute network
address, broadcast address, and same-subnet checks using raw bitwise
operations on 32-bit integers (no ipaddress module).
"""

import struct
import socket


def ip_to_int(ip):
    return struct.unpack("!I", socket.inet_aton(ip))[0]


def int_to_ip(n):
    return socket.inet_ntoa(struct.pack("!I", n))


def to_binary_octets(n):
    ip_str = int_to_ip(n)
    return ".".join(f"{int(o):08b}" for o in ip_str.split("."))


def prefix_to_mask_int(prefix):
    return (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF if prefix else 0


def network_address(ip, prefix):
    ip_int = ip_to_int(ip)
    mask_int = prefix_to_mask_int(prefix)
    return int_to_ip(ip_int & mask_int)


def broadcast_address(ip, prefix):
    ip_int = ip_to_int(ip)
    mask_int = prefix_to_mask_int(prefix)
    wildcard = (~mask_int) & 0xFFFFFFFF
    network_int = ip_int & mask_int
    return int_to_ip(network_int | wildcard)


def same_subnet(ip1, ip2, prefix):
    mask_int = prefix_to_mask_int(prefix)
    return (ip_to_int(ip1) & mask_int) == (ip_to_int(ip2) & mask_int)


def show_and_or(ip, prefix):
    ip_int = ip_to_int(ip)
    mask_int = prefix_to_mask_int(prefix)
    net_int = ip_int & mask_int
    wildcard = (~mask_int) & 0xFFFFFFFF
    bcast_int = net_int | wildcard

    print(f"=== {ip}/{prefix} ===")
    print(f"  IP       binary: {to_binary_octets(ip_int)}")
    print(f"  Mask     binary: {to_binary_octets(mask_int)}")
    print(f"  IP AND Mask    : {to_binary_octets(net_int)}  -> Network = {int_to_ip(net_int)}")
    print(f"  Wildcard (~mask): {to_binary_octets(wildcard)}")
    print(f"  Network OR Wildcard: {to_binary_octets(bcast_int)}  -> Broadcast = {int_to_ip(bcast_int)}")
    print()


if __name__ == "__main__":
    show_and_or("192.168.1.77", 26)
    show_and_or("10.0.37.5", 20)

    print("=== Same-subnet check via (IP1 AND mask) == (IP2 AND mask) ===")
    pairs = [
        ("192.168.1.10", "192.168.1.70", 26),
        ("192.168.1.10", "192.168.1.50", 26),
        ("192.168.1.10", "192.168.2.50", 24),
    ]
    for a, b, prefix in pairs:
        result = same_subnet(a, b, prefix)
        print(f"  {a}/{prefix} vs {b}/{prefix} -> {'SAME' if result else 'DIFFERENT'} subnet")
