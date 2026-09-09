"""
Subnet / CIDR -- verified practical using the stdlib ipaddress module.
"""

import ipaddress


def show_network(cidr):
    net = ipaddress.ip_network(cidr, strict=False)
    print(f"{cidr}")
    print(f"  Network address : {net.network_address}")
    print(f"  Broadcast       : {net.broadcast_address}")
    print(f"  Total addresses : {net.num_addresses}")
    print(f"  Usable hosts    : {max(net.num_addresses - 2, 0)}")
    print(f"  Netmask         : {net.netmask}")
    print()


def split_subnet(cidr, new_prefix):
    net = ipaddress.ip_network(cidr, strict=False)
    subnets = list(net.subnets(new_prefix=new_prefix))
    print(f"Splitting {cidr} into /{new_prefix} subnets ({len(subnets)} total):")
    for sn in subnets[:5]:
        print(f"  {sn}")
    if len(subnets) > 5:
        print(f"  ... and {len(subnets) - 5} more")
    print()


def check_membership(cidr, ip):
    net = ipaddress.ip_network(cidr, strict=False)
    addr = ipaddress.ip_address(ip)
    print(f"Is {ip} inside {cidr}? {addr in net}")


if __name__ == "__main__":
    for cidr in ["10.0.0.0/24", "10.0.0.0/16", "10.0.0.0/8", "192.168.1.0/24"]:
        show_network(cidr)

    split_subnet("10.0.0.0/16", 24)

    check_membership("10.0.0.0/24", "10.0.0.50")
    check_membership("10.0.0.0/24", "10.0.1.50")
